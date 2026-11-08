#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# ARGO NAVIS (SNM) — Verificación de un despliegue con Docker.
#
# Revisa que todo esté en pie y bien configurado: contenedores, aplicación,
# seguridad, base de datos, Active Directory, correo, respaldos y sistema.
# No cambia nada. Solo deja dos rastros:
#   - la prueba del freno del login hace intentos fallidos con un usuario que
#     no existe (quedan en la bitácora; al AD no se le pregunta nada);
#   - la del volumen de documentos crea y borra un archivo vacío.
# La prueba del Active Directory entra con la cuenta de servicio (solo lee).
#
# Uso, desde la carpeta del repo en el servidor, después de cada despliegue:
#   sudo bash verificar-despliegue.sh
# Termina con 0 si no hay fallas (los avisos no cuentan como falla).
# ════════════════════════════════════════════════════════════════════════════
set -uo pipefail
cd "$(dirname "$0")" || exit 1

if [ "$(id -u)" -ne 0 ]; then
  echo "Córrelo con sudo: sudo bash $0"; exit 1
fi
if [ ! -f .env ] || [ ! -f docker-compose-prod.yml ]; then
  echo "Falta .env o docker-compose-prod.yml en $(pwd)"; exit 1
fi

FALLAS=0; AVISOS=0
bien()    { echo "  [OK]    $*"; }
mal()     { echo "  [FALLA] $*"; FALLAS=$((FALLAS + 1)); }
aviso()   { echo "  [AVISO] $*"; AVISOS=$((AVISOS + 1)); }
info()    { echo "  [INFO]  $*"; }
seccion() { echo; echo "== $* =="; }
env_de()  { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
codigo()  { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
# Consulta a la base, con las credenciales que ya tiene el contenedor.
psql_bd() { docker exec snm_postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tA -F' ' -c \"$1\"" 2>/dev/null; }
# Python dentro del backend (lee el programa de la entrada estándar).
py_backend() { docker exec -i snm_backend python -; }

# ── Contenedores ─────────────────────────────────────────────────────────────
seccion "Contenedores"
for c in snm_postgres snm_backend snm_frontend; do
  estado=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}sin chequeo{{end}}|{{.RestartCount}}|{{.HostConfig.RestartPolicy.Name}}' "$c" 2>/dev/null)
  if [ -z "$estado" ]; then mal "$c no existe"; continue; fi
  IFS='|' read -r st salud reinicios politica <<<"$estado"
  if [ "$st" = running ] && [ "$salud" = healthy ]; then bien "$c: en marcha y sano"; else mal "$c: $st, $salud (docker logs $c)"; fi
  if [ "$reinicios" -gt 0 ]; then aviso "$c se reinició solo $reinicios vez/veces (docker logs $c)"; fi
  if [ "$politica" != always ]; then aviso "$c sin «restart: always» ($politica)"; fi
done
if [ "$(systemctl is-enabled docker 2>/dev/null)" = enabled ]; then
  bien "Docker arranca solo al encender la máquina"
else
  mal "Docker no arranca solo al reiniciar la máquina (sudo systemctl enable docker)"
fi

# ── Aplicación ───────────────────────────────────────────────────────────────
seccion "Aplicación"
salud=$(curl -s --max-time 15 http://localhost/api/health)
if echo "$salud" | grep -q '"estado":"ok"'; then
  bien "/api/health responde ok (nginx, backend y base de datos)"
else
  mal "/api/health: ${salud:-sin respuesta}"
fi
if curl -s --max-time 15 http://localhost/ | grep -q "<title>ARGO NAVIS"; then bien "La página de ARGO NAVIS carga"; else mal "La página principal no es la de ARGO NAVIS"; fi
c=$(codigo http://localhost/solicitudes/1)
if [ "$c" = 200 ]; then bien "Recargar una página de la interfaz funciona"; else mal "Recargar una página de la interfaz responde $c"; fi
c=$(codigo http://localhost/api/v1/solicitudes/revision)
case "$c" in 401|403) bien "La API sin sesión no responde nada ($c)";; *) mal "La API sin sesión responde $c (se esperaba 401)";; esac
c=$(codigo http://localhost/api/v1/verificacion/codigo-que-no-existe)
if [ "$c" = 404 ]; then bien "La verificación del QR con un código falso responde 404"; else mal "La verificación del QR con un código falso responde $c"; fi
info "APP_URL (enlaces de los correos y del QR): $(env_de APP_URL)"
info "PERMITIR_LOGIN_LOCAL (cuentas de las agencias): $(env_de PERMITIR_LOGIN_LOCAL)"
info "CORREO_UCVMM (aviso de cada solicitud nueva): $(env_de CORREO_UCVMM)"

# ── Seguridad ────────────────────────────────────────────────────────────────
seccion "Seguridad"
for ruta in / /api/health; do
  cabeceras=$(curl -s -D - -o /dev/null --max-time 15 "http://localhost$ruta")
  faltan=""
  for h in "content-security-policy" "x-frame-options: DENY" "x-content-type-options: nosniff" "referrer-policy"; do
    echo "$cabeceras" | grep -qi "^$h" || faltan="$faltan ${h%%:*}"
  done
  if [ -z "$faltan" ]; then bien "Cabeceras de seguridad en $ruta"; else mal "Faltan cabeceras en $ruta:$faltan"; fi
done
servidor=$(curl -s -D - -o /dev/null --max-time 15 http://localhost/ | grep -i '^server:' | tr -d '\r')
if echo "$servidor" | grep -q '[0-9]'; then aviso "El servidor muestra su versión ($servidor)"; else bien "nginx no muestra su versión"; fi
ip=$(hostname -I | awk '{print $1}')
if timeout 3 bash -c "</dev/tcp/$ip/8000" 2>/dev/null; then
  mal "El puerto 8000 (backend) está abierto en $ip: solo nginx debe publicarse"
else
  bien "El backend no se publica (puerto 8000 cerrado en $ip)"
fi
if ss -tlnH | awk '{print $4}' | grep -E ':5432$' | grep -vqE '^(127\.0\.0\.1|\[::1\]):'; then
  mal "PostgreSQL escucha fuera de este equipo"
else
  bien "PostgreSQL solo escucha en este equipo (127.0.0.1)"
fi
uid=$(docker exec snm_backend id -u 2>/dev/null)
if [ "$uid" = 10001 ]; then bien "El backend corre sin privilegios (uid 10001)"; else mal "El backend corre con uid ${uid:-?} (se esperaba 10001)"; fi
if [ "$(docker exec snm_backend printenv APP_ENV 2>/dev/null)" = production ]; then bien "APP_ENV=production"; else mal "APP_ENV no es production"; fi
c=$(codigo http://localhost/api/docs)
if [ "$c" = 404 ]; then bien "La documentación de la API está oculta"; else aviso "/api/docs responde $c"; fi
sk=$(env_de SECRET_KEY)
if [ "${#sk}" -ge 32 ]; then bien "SECRET_KEY de ${#sk} caracteres"; else mal "SECRET_KEY corta (${#sk} caracteres)"; fi
frenado=""
for i in $(seq 1 25); do
  c=$(codigo -X POST -H 'Content-Type: application/json' \
      -d '{"username":"verificacion.freno","password":"no-es-una-clave"}' http://localhost/api/v1/auth/login)
  if [ "$c" = 429 ]; then frenado=$i; break; fi
done
if [ -n "$frenado" ]; then
  bien "El login se frena tras varios intentos (429 al intento $frenado; usuario inexistente, sin tocar el AD)"
else
  mal "El login no se frenó tras 25 intentos"
fi

# ── Base de datos ────────────────────────────────────────────────────────────
seccion "Base de datos"
rev=$(docker exec snm_backend alembic current 2>/dev/null | tail -1)
if echo "$rev" | grep -q '(head)'; then bien "Esquema al día: $rev"; else mal "Esquema sin migrar: ${rev:-sin respuesta}"; fi
topes=$(py_backend <<'PY' 2>/dev/null
import asyncio
from sqlalchemy import text
from app.infrastructure.database import motor_bd

async def main():
    async with motor_bd.connect() as c:
        consulta = (await c.execute(text("show statement_timeout"))).scalar()
        inactiva = (await c.execute(text("show idle_in_transaction_session_timeout"))).scalar()
    await motor_bd.dispose()
    print(consulta, inactiva)

asyncio.run(main())
PY
)
read -r t_consulta t_inactiva <<<"$topes"
if [ -n "${t_consulta:-}" ] && [ "$t_consulta" != 0 ] && [ "${t_inactiva:-0}" != 0 ]; then
  bien "Topes por conexión: consulta $t_consulta, transacción inactiva $t_inactiva"
else
  mal "Sin topes por conexión (${topes:-sin respuesta})"
fi
max=$(psql_bd "show max_connections")
workers=$(docker exec snm_backend printenv UVICORN_WORKERS 2>/dev/null); workers=${workers:-1}
bd_pool=$(docker exec snm_backend printenv BD_POOL 2>/dev/null)
bd_extra=$(docker exec snm_backend printenv BD_POOL_EXTRA 2>/dev/null)
por_proceso=$(( ${bd_pool:-5} + ${bd_extra:-10} ))
necesarias=$(( workers * por_proceso ))
if [ -n "$max" ] && [ "$necesarias" -lt "$max" ]; then
  bien "Conexiones: hasta $necesarias ($workers procesos × $por_proceso) de las $max que admite PostgreSQL"
else
  mal "Se pueden pedir $necesarias conexiones y PostgreSQL admite ${max:-?}"
fi
if [ "$workers" -gt 1 ]; then
  corriendo=$(docker top snm_backend 2>/dev/null | grep -c 'spawn_main')
  if [ "$corriendo" -eq "$workers" ]; then bien "$workers procesos del backend en marcha"; else aviso "Se pidieron $workers procesos del backend y hay $corriendo"; fi
fi
if docker exec snm_backend sh -c 'f=/app/storage/documentos/.verificacion; touch "$f" && rm -f "$f"' 2>/dev/null; then
  bien "El backend puede escribir en el volumen de documentos"
else
  mal "El backend no puede escribir en /app/storage/documentos (¿volumen creado como root? README → Producción)"
fi
info "Tamaño de la base: $(psql_bd "select pg_size_pretty(pg_database_size(current_database()))"); conexiones abiertas: $(psql_bd "select count(*) from pg_stat_activity where datname = current_database()")"

# ── Integraciones ────────────────────────────────────────────────────────────
seccion "Integraciones"
ldap=$(py_backend <<'PY' 2>&1 | tail -1
from app.core.ldap import servicio_ldap
servicio_ldap._cerrar(servicio_ldap._conectar_cuenta_servicio())
print("ok")
PY
)
if [ "$ldap" = ok ]; then bien "Active Directory: la cuenta de servicio entra"; else mal "Active Directory: ${ldap:-sin respuesta}"; fi
smtp=$(py_backend <<'PY' 2>&1 | tail -1
import os
import smtplib
host = os.environ.get("MAIL_HOST", "")
if not host:
    print("sin MAIL_HOST")
else:
    puerto = int(os.environ.get("MAIL_PORT") or 25)
    clase = smtplib.SMTP_SSL if os.environ.get("MAIL_USAR_SSL", "").lower() == "true" else smtplib.SMTP
    with clase(host, puerto, timeout=10) as s:
        s.ehlo()
    print("ok")
PY
)
case "$smtp" in
  ok) bien "Correo: el servidor SMTP responde (no se envió nada)";;
  "sin MAIL_HOST") aviso "Correo apagado (MAIL_HOST vacío): no salen avisos";;
  *) mal "Correo: $smtp";;
esac
cola=$(psql_bd "select estado || '=' || count(*) from correos_salida group by estado order by estado" | tr '\n' ' ')
info "Cola de correos: ${cola:-vacía}"
fallidos=$(psql_bd "select count(*) from correos_salida where estado = 'fallido'")
if [ "${fallidos:-0}" -gt 0 ]; then
  aviso "$fallidos correo(s) fallido(s). Para ver el motivo: select numero, asunto, ultimo_error from correos_salida where estado = 'fallido';"
fi

# ── Respaldos ────────────────────────────────────────────────────────────────
seccion "Respaldos"
linea=$(crontab -l 2>/dev/null | grep 'backup.sh' | grep -v '^[[:space:]]*#')
dir=""
if [ -n "$linea" ]; then
  bien "Respaldo programado en el cron de root: $(echo "$linea" | awk '{print $1, $2, $3, $4, $5}')"
  dir=$(echo "$linea" | grep -o 'DIR_BACKUPS=[^ ]*' | cut -d= -f2)
else
  mal "No hay respaldo programado en el cron de root (instrucciones en backup.sh)"
fi
dir=${dir:-/root/backups}
ultimo=$(ls -t "$dir"/argonavis_bd_*.sql.gz 2>/dev/null | head -1)
if [ -z "$ultimo" ]; then
  mal "No hay respaldos de la base en $dir"
elif ! gzip -t "$ultimo" 2>/dev/null; then
  mal "El último respaldo de la base está dañado: $ultimo"
else
  horas=$(( ( $(date +%s) - $(stat -c %Y "$ultimo") ) / 3600 ))
  if [ "$horas" -le 26 ]; then bien "Último respaldo de la base: $(basename "$ultimo"), hace $horas h, íntegro"; else aviso "El último respaldo de la base tiene $horas h: ¿corre el cron?"; fi
fi
info "Los respaldos quedan en este mismo disco: cópialos también a otro servidor."

# ── Sistema ──────────────────────────────────────────────────────────────────
seccion "Sistema"
uso=$(df --output=pcent / | tail -1 | tr -dc '0-9')
if [ "$uso" -lt 85 ]; then bien "Disco: ${uso}% usado"; else aviso "Disco al ${uso}%: borra imágenes viejas (docker image prune) o respaldos"; fi
disponible=$(free -m | awk '/^Mem:/{print $7}')
if [ "$disponible" -gt 300 ]; then bien "Memoria disponible: ${disponible} MB"; else aviso "Poca memoria disponible: ${disponible} MB"; fi
if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = yes ]; then
  bien "Reloj sincronizado (los plazos y el horario laboral dependen de la hora)"
else
  aviso "El reloj no está sincronizado (timedatectl): los plazos y el horario laboral dependen de la hora"
fi
errores=$(docker logs --since 24h snm_backend 2>&1 | grep -cE ' (ERROR|CRITICAL) |Traceback')
if [ "$errores" -eq 0 ]; then
  bien "Sin errores en el log del backend (últimas 24 h)"
else
  aviso "$errores línea(s) de error en el log del backend (últimas 24 h): docker logs --since 24h snm_backend 2>&1 | grep -B2 -A10 -E ' (ERROR|CRITICAL) |Traceback'"
fi

echo
if [ "$FALLAS" -eq 0 ]; then echo "Resultado: todo bien ($AVISOS aviso/s)."; else echo "Resultado: $FALLAS falla/s y $AVISOS aviso/s."; fi
exit $(( FALLAS > 0 ? 1 : 0 ))
