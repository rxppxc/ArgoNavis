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
#      Un documento nunca se modifica ni se borra (2026-11-22): si uno falta o cambió en
#      el servidor, es una pérdida, y la copia conserva el original y lo dice aquí.
#   3. Retención, con margen (todavía no se sabe cuántos años se conservan): las últimas
#      RETENER_DIAS noches (14), la primera noche de los últimos RETENER_MESES meses (12)
#      y la primera de los últimos RETENER_ANIOS años (10). La base y la copia de los
#      documentos, de las mismas noches: se restauran juntas.
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
RETENER_MESES="${RETENER_MESES:-12}"
RETENER_ANIOS="${RETENER_ANIOS:-10}"
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
docker exec argonavis_postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$archivo_bd.parcial"
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
# Solo lo que la copia no tiene: lo que ya estaba no se toca, aunque en el servidor falte o
# haya cambiado. Lo de un envío en curso (tmp-*) y lo que se está escribiendo no se copia.
archivos_de() {
  ( cd "$1" && find . -type f ! -path './tmp-*' ! -name '*.parcial' ! -name '.verificacion' -printf "$2" ) | LC_ALL=C sort
}
copiar_lo_nuevo() {
  ( cd "$origen" && LC_ALL=C comm -23 <(archivos_de "$origen" '%p\n') <(archivos_de "$EN_CURSO" '%p\n') |
      xargs -d '\n' -r cp -a --parents -t "$EN_CURSO" -- )
}
# Si justo un archivo se fue (un envío rechazado), se vuelve a mirar una vez.
copiar_lo_nuevo || { sleep 5; copiar_lo_nuevo; }
# La carpeta, con el dueño y los permisos de la de verdad: al restaurar, el volumen queda igual
# (las de adentro ya los traen de «cp -a --parents»).
chown --reference="$origen" "$EN_CURSO"
chmod --reference="$origen" "$EN_CURSO"
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
# Lo que está en la copia y en el servidor ya no es igual (nombre, tamaño o fecha).
perdidos=0; cambiados=0
while IFS=$'\t' read -r ruta _; do
  if [ -e "$origen/$ruta" ]; then cambiados=$((cambiados + 1)); else perdidos=$((perdidos + 1)); fi
done < <(LC_ALL=C comm -13 <(archivos_de "$origen" '%p\t%s\t%T@\n') <(archivos_de "$COPIAS/$FECHA" '%p\t%s\t%T@\n'))
if [ $((perdidos + cambiados)) -gt 0 ]; then
  log "OJO: $perdidos archivo(s) ya no están en el servidor y $cambiados cambiaron. La copia conserva los originales:" \
      "recupéralos de ahí (README → Respaldos)."
fi

# ── 3. Retención ─────────────────────────────────────────────────────────────
# De una lista de fechas, de la más vieja a la más nueva, las que sobran. Por el nombre, no
# por la fecha del archivo.
sobran() {
  awk -v dias="$RETENER_DIAS" -v meses="$RETENER_MESES" -v anios="$RETENER_ANIOS" '
    { fecha[NR] = $0 }
    END {
      for (i = NR; i > 0 && i > NR - dias; i--) queda[i] = 1
      for (i = NR; i > 0; i--) {
        if (meses > 0 && (i == 1 || substr(fecha[i - 1], 1, 7) != substr(fecha[i], 1, 7))) { queda[i] = 1; meses-- }
        if (anios > 0 && (i == 1 || substr(fecha[i - 1], 1, 4) != substr(fecha[i], 1, 4))) { queda[i] = 1; anios-- }
      }
      for (i = 1; i <= NR; i++) if (!(i in queda)) print fecha[i]
    }'
}
find "$COPIAS" -mindepth 1 -maxdepth 1 -type d -name '20*' -printf '%f\n' | sort | sobran |
  while IFS= read -r vieja; do rm -rf -- "${COPIAS:?}/$vieja"; done
find "$DIR_BACKUPS" -maxdepth 1 -type f -name 'argonavis_bd_20*.sql.gz' -printf '%f\n' |
  sed 's/^argonavis_bd_//; s/\.sql\.gz$//' | sort | sobran |
  while IFS= read -r vieja; do rm -f -- "$DIR_BACKUPS/argonavis_bd_$vieja.sql.gz"; done
# Los .tar.gz de los documentos, de antes del 2026-11-10.
find "$DIR_BACKUPS" -maxdepth 1 -name 'argonavis_documentos_*.tar.gz' -mtime +"$RETENER_DIAS" -delete
log "Retención aplicada. Los respaldos ocupan $(du -sh "$DIR_BACKUPS" | cut -f1)" \
    "y quedan $(df -h --output=avail "$DIR_BACKUPS" | tail -n 1 | tr -d ' ') libres en ese disco."
