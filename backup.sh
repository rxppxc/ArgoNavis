#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# ARGO NAVIS (SNM) — Respaldo de la base de datos y de los documentos.
#
# Cada noche (cron de root, abajo):
#   1. La base de datos: pg_dump comprimido (argonavis_bd_FECHA.sql.gz). PostgreSQL
#      lo saca de una foto consistente sin frenar al sistema: se sigue trabajando
#      mientras tanto (solo esperaría a una migración que corriera a esa hora).
#   2. Los documentos de los expedientes: una copia por día (documentos/FECHA/) en la
#      que solo se copian los archivos nuevos. Los que ya estaban en la copia anterior
#      se enlazan (hard link): no se vuelven a copiar ni ocupan espacio otra vez. Cada
#      copia se ve completa y se restaura sola (README → Producción → Restaurar).
#      Sirve porque un documento nunca se modifica: reemplazarlo es guardar otro.
#   3. Retención: las últimas RETENER_DIAS copias de cada uno.
# Corre con la prioridad más baja de CPU y de disco: si alguien trabaja a esa hora
# (los puestos operan de noche), el sistema va primero.
#
# Hasta el 2026-11-10 cada noche empaquetaba TODOS los documentos en un .tar.gz y
# guardaba 14: los respaldos ocupaban 14 veces lo que pesan los documentos, cada
# noche tardaban más y comprimían PDF que ya vienen comprimidos. Esos .tar.gz se
# borran solos al cumplir los 14 días.
#
# Instalación en el servidor (una sola vez):
#   sudo crontab -e   →  agregar esta línea (corre todos los días a las 2 AM):
#   0 2 * * * DIR_BACKUPS=/home/vperez/backups bash /home/vperez/argonavis/backup.sh >> /home/vperez/backups/backup.log 2>&1
# En el crontab de root: docker lo pide, y también leer el volumen. DIR_BACKUPS
# explícito porque el $HOME de root es /root; "bash ..." porque el clon puede no
# traer el permiso de ejecución.
#
# IMPORTANTE: esto deja los respaldos en el MISMO servidor. Para protección real
# ante pérdida del disco, copiar DIR_BACKUPS a otra máquina con «rsync -aH»: la H
# conserva los enlaces (con scp o rsync sin -H, cada copia ocuparía todo).
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

DIR_BACKUPS="${DIR_BACKUPS:-$HOME/backups}"
RETENER_DIAS="${RETENER_DIAS:-14}"
VOLUMEN_DOCUMENTOS="${VOLUMEN_DOCUMENTOS:-argonavis_documentos}"
FECHA="$(date +%F_%H%M%S)"
COPIAS="$DIR_BACKUPS/documentos"
EN_CURSO="$COPIAS/.en-curso"

# Prioridad baja de CPU (nice) y de disco (ionice, si el disco la respeta) para todo
# lo que corre aquí. pg_dump corre dentro del contenedor de PostgreSQL.
if [ -z "${ARGONAVIS_RESPALDO_PRIORIDAD_BAJA:-}" ]; then
  export ARGONAVIS_RESPALDO_PRIORIDAD_BAJA=1
  if command -v ionice >/dev/null 2>&1; then
    exec nice -n 19 ionice -c 3 bash "$0" "$@"
  fi
  exec nice -n 19 bash "$0" "$@"
fi

log() { echo "[$(date '+%F %T')] $*"; }

mkdir -p "$DIR_BACKUPS" "$COPIAS"
# Uno a la vez: si uno se alarga o alguien lo corre a mano a la hora del cron, el
# otro no empieza encima.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$DIR_BACKUPS/.respaldo.lock"
  if ! flock -n 9; then
    log "Ya hay un respaldo en curso: este no corre."
    exit 1
  fi
fi
archivo_bd="$DIR_BACKUPS/argonavis_bd_${FECHA}.sql.gz"
trap 'rm -rf -- "$archivo_bd.parcial" "$EN_CURSO"' EXIT

# ── 1. Base de datos ─────────────────────────────────────────────────────────
# Con las credenciales que ya viven dentro del contenedor: no hay que escribir
# contraseñas aquí. Va a un archivo aparte que se renombra al terminar: uno
# cortado a mitad no queda con el nombre de un respaldo bueno.
docker exec snm_postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$archivo_bd.parcial"
mv "$archivo_bd.parcial" "$archivo_bd"
log "BD respaldada: $archivo_bd ($(du -h "$archivo_bd" | cut -f1))"

# ── 2. Documentos de los expedientes ─────────────────────────────────────────
origen="$(docker volume inspect "$VOLUMEN_DOCUMENTOS" --format '{{ .Mountpoint }}')"
anterior="$(find "$COPIAS" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -n 1)"
rm -rf -- "$EN_CURSO"
mkdir "$EN_CURSO"
if [ -n "$anterior" ]; then
  cp -al "$anterior/." "$EN_CURSO/"                       # la copia anterior, enlazada
fi
# Lo nuevo. -u: solo lo que no está o cambió; --remove-destination: lo que cambió
# reemplaza al enlace, sin escribir sobre el archivo de la copia anterior.
cp -a -u --remove-destination "$origen/." "$EN_CURSO/"
# Lo que ya no está en el volumen (documentos reemplazados) sale también de esta copia.
( cd "$EN_CURSO" && find . -mindepth 1 -depth -print0 ) |
  while IFS= read -r -d '' ruta; do
    if [ ! -e "$origen/$ruta" ] && [ ! -L "$origen/$ruta" ]; then
      rm -rf -- "${EN_CURSO:?}/$ruta"
    fi
  done
mv -T "$EN_CURSO" "$COPIAS/$FECHA"   # -T: si ya existiera, falla en vez de meterla adentro
touch "$COPIAS/$FECHA"   # cp -a le pasa la fecha del volumen: que diga la de la copia
archivos=$(find "$COPIAS/$FECHA" -type f | wc -l)
if [ -n "$anterior" ]; then
  # du cuenta una sola vez cada archivo enlazado: la segunda línea es lo que suma esta copia.
  nuevo=$(du -sh "$anterior" "$COPIAS/$FECHA" | tail -n 1 | cut -f1)
else
  nuevo=$(du -sh "$COPIAS/$FECHA" | cut -f1)
fi
log "Documentos respaldados: $COPIAS/$FECHA ($archivos archivos; esta copia suma $nuevo)"

# ── 3. Retención ─────────────────────────────────────────────────────────────
find "$DIR_BACKUPS" -maxdepth 1 -name "argonavis_*.gz" -mtime +"$RETENER_DIAS" -delete
# Las copias de los documentos, por nombre (la fecha), no por la fecha del archivo.
find "$COPIAS" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | head -n -"$RETENER_DIAS" |
  while IFS= read -r vieja; do rm -rf -- "$vieja"; done
log "Retención aplicada. Los respaldos ocupan $(du -sh "$DIR_BACKUPS" | cut -f1)" \
    "y quedan $(df -h --output=avail "$DIR_BACKUPS" | tail -n 1 | tr -d ' ') libres en ese disco."
