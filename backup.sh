#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# ARGO NAVIS (SNM) — Respaldo de base de datos + archivos subidos.
#
# Respalda dos cosas (ambas viven en volúmenes Docker y se pierden si muere
# el disco de la VM):
#   1. La base de datos Postgres (pg_dump comprimido).
#   2. Los documentos de los expedientes (volumen documentos).
#
# Instalación en el servidor (una sola vez):
#   chmod +x backup.sh
#   crontab -e   →  agregar esta línea (corre todos los días a las 2 AM):
#   0 2 * * * /home/vperez/argo-navis/backup.sh >> /home/vperez/backups/backup.log 2>&1
#
# IMPORTANTE: esto deja los respaldos en el MISMO servidor. Para protección
# real ante pérdida del disco, copiar periódicamente DIR_BACKUPS a otra
# máquina (scp/rsync a un NAS o servidor de respaldos institucional).
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

DIR_BACKUPS="${DIR_BACKUPS:-$HOME/backups}"
RETENER_DIAS="${RETENER_DIAS:-14}"
FECHA="$(date +%F_%H%M)"

mkdir -p "$DIR_BACKUPS"

# ── 1. Base de datos ─────────────────────────────────────────────────────────
# Usa las credenciales que ya viven dentro del contenedor — no hay que
# escribir contraseñas acá.
archivo_bd="$DIR_BACKUPS/argonavis_bd_${FECHA}.sql.gz"
docker exec snm_postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$archivo_bd"
echo "[$(date '+%F %T')] BD respaldada: $archivo_bd ($(du -h "$archivo_bd" | cut -f1))"

# ── 2. Documentos de los expedientes (volumen) ───────────────────────────────
archivo_storage="$DIR_BACKUPS/argonavis_documentos_${FECHA}.tar.gz"
docker run --rm --volumes-from snm_backend -v "$DIR_BACKUPS":/backup alpine \
  tar czf "/backup/$(basename "$archivo_storage")" -C /app/storage/documentos .
echo "[$(date '+%F %T')] Documentos respaldados: $archivo_storage ($(du -h "$archivo_storage" | cut -f1))"

# ── 3. Retención: borrar respaldos con más de RETENER_DIAS días ──────────────
find "$DIR_BACKUPS" -name "argonavis_*.gz" -mtime +"$RETENER_DIAS" -delete
echo "[$(date '+%F %T')] Retención aplicada (>$RETENER_DIAS días eliminados)."
