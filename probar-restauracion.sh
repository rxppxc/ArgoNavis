#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# ARGO NAVIS (SNM) — Prueba que el último respaldo se puede restaurar (2026-11-22).
#
# Un respaldo que nunca se restauró no es un respaldo. Este guion:
#   1. comprueba que el último respaldo de la base no esté dañado;
#   2. lo carga en una base aparte (argonavis_prueba_restauracion), que borra al terminar;
#   3. comprueba que traiga datos y que cada documento que nombra (y cada autorización
#      emitida) esté, con su tamaño, en la copia de los documentos de esa misma noche.
# No toca la base de verdad ni los documentos. Corre con la prioridad más baja.
#
# Uso: sudo bash probar-restauracion.sh     (la carpeta sale del cron de root, o de DIR_BACKUPS)
# vigilar.py lo corre los lunes y avisa si falla. Termina con 0 si el respaldo sirve.
# ════════════════════════════════════════════════════════════════════════════
set -uo pipefail

if [ -z "${ARGONAVIS_RESPALDO_PRIORIDAD_BAJA:-}" ]; then
  export ARGONAVIS_RESPALDO_PRIORIDAD_BAJA=1
  if command -v ionice >/dev/null 2>&1; then
    exec nice -n 19 ionice -c 3 bash "$0" "$@"
  fi
  exec nice -n 19 bash "$0" "$@"
fi

BASE=argonavis_prueba_restauracion
if [ -z "${DIR_BACKUPS:-}" ]; then
  DIR_BACKUPS=$(crontab -l 2>/dev/null | grep 'backup.sh' | grep -v '^[[:space:]]*#' | grep -o 'DIR_BACKUPS=[^ ]*' | cut -d= -f2)
  DIR_BACKUPS=${DIR_BACKUPS:-/root/backups}
fi

bien()  { echo "  [OK]    $*"; }
falla() { echo "  [FALLA] $*"; echo "Resultado: NO se pudo restaurar el último respaldo."; exit 1; }
en_postgres() { docker exec -i argonavis_postgres sh -c "$1"; }
consulta() { en_postgres "psql -X -U \"\$POSTGRES_USER\" -d $BASE -tA -F '|' -c \"$1\"" < /dev/null; }
limpiar() { en_postgres "dropdb --if-exists --force -U \"\$POSTGRES_USER\" $BASE" < /dev/null >/dev/null 2>&1; }

# ── 1. El respaldo ───────────────────────────────────────────────────────────
ultimo=$(find "$DIR_BACKUPS" -maxdepth 1 -name 'argonavis_bd_*.sql.gz' 2>/dev/null | sort | tail -n 1)
[ -n "$ultimo" ] || falla "No hay respaldos de la base en $DIR_BACKUPS."
echo "Respaldo: $(basename "$ultimo") ($(du -h "$ultimo" | cut -f1))"
gzip -t "$ultimo" 2>/dev/null || falla "El respaldo está dañado: $ultimo"
fecha=$(basename "$ultimo" .sql.gz); fecha=${fecha#argonavis_bd_}
copia="$DIR_BACKUPS/documentos/$fecha"
[ -d "$copia" ] || falla "Falta la copia de los documentos de esa noche ($copia)."
libres=$(df --output=avail -m /var/lib/docker 2>/dev/null | tail -n 1 | tr -d ' ')
if [ -n "$libres" ] && [ "$libres" -lt 1024 ]; then falla "Quedan $libres MB en el disco de Docker: no alcanza para probar."; fi

# ── 2. La base, aparte ───────────────────────────────────────────────────────
[ "$(docker exec argonavis_postgres printenv POSTGRES_DB 2>/dev/null)" != "$BASE" ] || falla "La base de verdad se llama $BASE: no se prueba nada."
trap limpiar EXIT
limpiar
en_postgres "createdb -U \"\$POSTGRES_USER\" $BASE" < /dev/null || falla "No se pudo crear la base de prueba."
inicio=$(date +%s)
if ! gunzip -c "$ultimo" | en_postgres "psql -X -q -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d $BASE" >/dev/null; then
  falla "El respaldo no carga completo (el error está arriba)."
fi
bien "La base carga completa, en $(( $(date +%s) - inicio )) s"

# ── 3. Los datos y los documentos ────────────────────────────────────────────
cuentas=$(consulta "SELECT v.version_num, (SELECT count(*) FROM pg_tables WHERE schemaname = 'public'), (SELECT count(*) FROM solicitudes), (SELECT count(*) FROM users), (SELECT count(*) FROM audit_logs) FROM alembic_version v") \
  || falla "La base restaurada no responde."
IFS='|' read -r version tablas solicitudes usuarios bitacora <<<"$cuentas"
[ "${usuarios:-0}" -gt 0 ] 2>/dev/null || falla "La base restaurada no tiene ningún usuario."
bien "$tablas tablas (esquema $version), $solicitudes solicitudes, $usuarios usuarios y $bitacora líneas de bitácora"

lista=$(consulta "SELECT ruta, tamano FROM solicitud_documentos") || falla "No se pudo leer la lista de documentos."
# Las autorizaciones emitidas (2026-11-22). Un respaldo de antes no tiene esa tabla.
emitidas=$(consulta "SELECT ruta, tamano FROM documentos_emitidos" 2>/dev/null) || emitidas=""
total=0; buenos=0; malos=""
while IFS='|' read -r ruta tamano; do
  [ -n "$ruta" ] || continue
  total=$((total + 1))
  if [ "$(stat -c %s "$copia/$ruta" 2>/dev/null)" = "$tamano" ]; then
    buenos=$((buenos + 1))
  elif [ $((total - buenos)) -le 10 ]; then
    malos="$malos $ruta"
  fi
done <<<"$lista"$'\n'"$emitidas"
if [ "$buenos" -ne "$total" ]; then
  falla "$buenos de $total documentos están bien en la copia. Faltan o no miden lo que deben:$malos"
fi
bien "$buenos de $total documentos, en la copia y con su tamaño"
echo "Resultado: el respaldo se restaura."
