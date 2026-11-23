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
# Con --solo-la-pila revisa lo que no depende del servidor (los contenedores, la
# aplicación, la seguridad y la base): es lo que corre la integración continua, que
# no tiene Active Directory, correo ni respaldos. Con --diario, todo menos la prueba del
# freno del login, para no llenar la bitácora: es lo que corre vigilar.py cada mañana.
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

SOLO_LA_PILA=""; DIARIO=""
case "${1:-}" in
  --solo-la-pila) SOLO_LA_PILA=1 ;;
  --diario)       DIARIO=1 ;;
esac

FALLAS=0; AVISOS=0
resultado() {
  echo
  if [ "$FALLAS" -eq 0 ]; then echo "Resultado: todo bien ($AVISOS aviso/s)."; else echo "Resultado: $FALLAS falla/s y $AVISOS aviso/s."; fi
  exit $(( FALLAS > 0 ? 1 : 0 ))
}
bien()    { echo "  [OK]    $*"; }
mal()     { echo "  [FALLA] $*"; FALLAS=$((FALLAS + 1)); }
aviso()   { echo "  [AVISO] $*"; AVISOS=$((AVISOS + 1)); }
info()    { echo "  [INFO]  $*"; }
seccion() { echo; echo "== $* =="; }
env_de()  { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
# -k: con HTTPS se entra por «localhost», que no es el nombre del certificado (se revisa aparte).
# Lo que se busca en una respuesta, se busca después de guardarla: con «curl | grep -q», grep
# corta la tubería al encontrarlo y, con pipefail, curl la da por fallida.
pedir()   { curl -sk --max-time 15 "$@"; }
codigo()  { pedir -o /dev/null -w '%{http_code}' "$@"; }
# Con qué arrancó nginx: aunque no esté en marcha y aunque el .env haya cambiado después.
env_nginx() { docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' argonavis_frontend 2>/dev/null | sed -n "s/^$1=//p" | head -1; }
# Consulta a la base, con las credenciales que ya tiene el contenedor.
psql_bd() { docker exec argonavis_postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tA -F' ' -c \"$1\"" 2>/dev/null; }
# Python dentro del backend (lee el programa de la entrada estándar).
py_backend() { docker exec -i argonavis_backend python -; }

# Con HTTPS (USAR_HTTPS=true en el .env), la aplicación se revisa por el 443.
HTTPS=""; BASE=http://localhost
if env_nginx USAR_HTTPS | grep -qix true; then HTTPS=1; BASE=https://localhost; fi

# ── Contenedores ─────────────────────────────────────────────────────────────
# Recién desplegado, el backend tarda unos segundos en arrancar (aplica las
# migraciones y levanta sus procesos): mientras Docker lo marque «starting», se
# espera, hasta 2 minutos. Sin esto, la revisión justo después del `up -d` daba
# 502 en todo lo que pasa por el backend.
for intento in $(seq 1 24); do
  arrancando=""
  for c in argonavis_postgres argonavis_backend argonavis_frontend; do
    if [ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$c" 2>/dev/null)" = starting ]; then
      arrancando="$arrancando $c"
    fi
  done
  [ -z "$arrancando" ] && break
  [ "$intento" -eq 1 ] && echo "Esperando a que terminen de arrancar:$arrancando…"
  sleep 5
done
seccion "Contenedores"
for c in argonavis_postgres argonavis_backend argonavis_frontend; do
  estado=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}sin chequeo{{end}}|{{.RestartCount}}|{{.HostConfig.RestartPolicy.Name}}' "$c" 2>/dev/null)
  if [ -z "$estado" ]; then mal "$c no existe"; continue; fi
  IFS='|' read -r st salud reinicios politica <<<"$estado"
  if [ "$st" = running ] && [ "$salud" = healthy ]; then bien "$c: en marcha y sano"; else mal "$c: $st, $salud (docker logs $c)"; fi
  if [ "$reinicios" -gt 0 ]; then aviso "$c se reinició solo $reinicios vez/veces (docker logs $c)"; fi
  if [ "$politica" != always ]; then aviso "$c sin «restart: always» ($politica)"; fi
done
# Límites de memoria (2026-11-10): sin ellos, un contenedor desbocado se lleva a los
# demás. Cerca del límite, Docker corta procesos de ese contenedor: hay que subirlo.
suma_mb=0
for c in argonavis_postgres argonavis_backend argonavis_frontend; do
  limite=$(docker inspect -f '{{.HostConfig.Memory}}' "$c" 2>/dev/null) || continue
  if [ "${limite:-0}" -eq 0 ]; then aviso "$c sin límite de memoria (mem_limit en docker-compose-prod.yml)"; continue; fi
  suma_mb=$((suma_mb + limite / 1048576))
  IFS='|' read -r usado porcentaje <<<"$(docker stats --no-stream --format '{{.MemUsage}}|{{.MemPerc}}' "$c" 2>/dev/null)"
  pct=${porcentaje%%.*}; pct=${pct%\%}
  case "$pct" in ''|*[!0-9]*) pct=0 ;; esac
  nano=$(docker inspect -f '{{.HostConfig.NanoCpus}}' "$c" 2>/dev/null)
  cpu=""
  if [ "${nano:-0}" -gt 0 ]; then cpu="; CPU: hasta $(awk -v n="$nano" 'BEGIN { print n / 1e9 }') núcleo(s)"; fi
  if [ "$pct" -lt 80 ]; then
    bien "$c: memoria $usado ($porcentaje de su límite)$cpu"
  else
    aviso "$c usa el $porcentaje de su límite de memoria ($usado): súbelo en el .env (README → Producción → Recursos)$cpu"
  fi
  if [ "$(docker inspect -f '{{.State.OOMKilled}}' "$c" 2>/dev/null)" = true ]; then
    aviso "Docker cortó a $c por falta de memoria: súbele el límite en el .env"
  fi
done
total_mb=$(free -m | awk '/^Mem:/{print $2}')
if [ "$suma_mb" -gt "$total_mb" ]; then
  aviso "Los límites de memoria suman $suma_mb MB y la VM tiene $total_mb MB: bájalos en el .env"
elif [ "$suma_mb" -gt 0 ]; then
  info "Límites de memoria: $suma_mb MB en total; la VM tiene $total_mb MB y $(nproc) núcleo(s)"
fi
murieron=$(docker logs --since 24h argonavis_backend 2>&1 | grep -c 'Child process .* died')
if [ "$murieron" -gt 0 ]; then
  aviso "En 24 h se cayeron $murieron proceso(s) de uvicorn, y uvicorn los levantó (¿límite de memoria?): docker logs --since 24h argonavis_backend 2>&1 | grep -B5 died"
fi
if [ -z "$SOLO_LA_PILA" ]; then
  if [ "$(systemctl is-enabled docker 2>/dev/null)" = enabled ]; then
    bien "Docker arranca solo al encender la máquina"
  else
    mal "Docker no arranca solo al reiniciar la máquina (sudo systemctl enable docker)"
  fi
fi

# ── Aplicación ───────────────────────────────────────────────────────────────
seccion "Aplicación"
salud=$(pedir "$BASE/api/health")
if echo "$salud" | grep -q '"estado":"ok"'; then
  bien "/api/health responde ok (nginx, backend y base de datos)"
else
  mal "/api/health: ${salud:-sin respuesta}"
fi
if grep -q "<title>ARGO NAVIS" <<<"$(pedir "$BASE/")"; then bien "La página de ARGO NAVIS carga"; else mal "La página principal no es la de ARGO NAVIS"; fi
c=$(codigo "$BASE/solicitudes/1")
if [ "$c" = 200 ]; then bien "Recargar una página de la interfaz funciona"; else mal "Recargar una página de la interfaz responde $c"; fi
c=$(codigo "$BASE/api/v1/solicitudes/revision")
case "$c" in 401|403) bien "La API sin sesión no responde nada ($c)";; *) mal "La API sin sesión responde $c (se esperaba 401)";; esac
c=$(codigo "$BASE/api/v1/verificacion/codigo-que-no-existe")
if [ "$c" = 404 ]; then bien "La verificación del QR con un código falso responde 404"; else mal "La verificación del QR con un código falso responde $c"; fi
c=$(codigo "$BASE/api/v1/verificacion/codigo-que-no-existe/autorizacion.pdf")
if [ "$c" = 303 ]; then bien "El PDF por el QR con un código falso lleva a la verificación (303)"; else mal "El PDF por el QR con un código falso responde $c (se esperaba 303)"; fi
info "APP_URL (enlaces de los correos): $(env_de APP_URL)"
if [ -n "$(env_de URL_VERIFICACION_PUBLICA)" ]; then
  info "URL_VERIFICACION_PUBLICA (el QR del PDF): $(env_de URL_VERIFICACION_PUBLICA)"
else
  aviso "Sin URL_VERIFICACION_PUBLICA: el QR del PDF solo se escanea dentro de la red del SNM (README → «Verificación pública del QR»)"
fi
info "PERMITIR_LOGIN_LOCAL (cuentas de las agencias): $(env_de PERMITIR_LOGIN_LOCAL)"
info "CORREO_UCVMM (aviso de cada solicitud nueva): $(env_de CORREO_UCVMM)"

# ── Seguridad ────────────────────────────────────────────────────────────────
seccion "Seguridad"
for ruta in / /api/health; do
  cabeceras=$(pedir -D - -o /dev/null "$BASE$ruta")
  faltan=""
  for h in "content-security-policy" "x-frame-options: DENY" "x-content-type-options: nosniff" "referrer-policy" "x-robots-tag: noindex"; do
    echo "$cabeceras" | grep -qi "^$h" || faltan="$faltan ${h%%:*}"
  done
  if [ -z "$faltan" ]; then bien "Cabeceras de seguridad en $ruta"; else mal "Faltan cabeceras en $ruta:$faltan"; fi
done
if pedir "$BASE/robots.txt" | tr -d '\r' | grep -qx 'Disallow: /'; then
  bien "robots.txt pide que no se indexe nada"
else
  mal "robots.txt no bloquea la indexación"
fi
servidor=$(pedir -D - -o /dev/null "$BASE/" | grep -i '^server:' | tr -d '\r')
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
uid=$(docker exec argonavis_backend id -u 2>/dev/null)
if [ "$uid" = 10001 ]; then bien "El backend corre sin privilegios (uid 10001)"; else mal "El backend corre con uid ${uid:-?} (se esperaba 10001)"; fi
# Contenedores endurecidos (2026-11-22, docker-compose-prod.yml): lo que dice el proceso
# principal de cada uno (usuario, privilegios que puede llegar a tener y si puede ganar más).
for c in argonavis_postgres argonavis_backend argonavis_frontend; do
  read -r u privilegios sin_ganar <<<"$(docker exec "$c" grep -E '^(Uid|CapBnd|NoNewPrivs):' /proc/1/status 2>/dev/null | awk '{print $2}' | paste -sd ' ' -)"
  solo_lectura=$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$c" 2>/dev/null)
  if [ "${u:-0}" != 0 ] && [ "${privilegios:-}" = 0000000000000000 ] && [ "${sin_ganar:-}" = 1 ] && [ "$solo_lectura" = true ]; then
    bien "$c: sin root (uid $u), sin privilegios del sistema y con la imagen de solo lectura"
  else
    mal "$c sin endurecer: uid ${u:-?}, privilegios ${privilegios:-?}, no-new-privileges ${sin_ganar:-?}, solo lectura ${solo_lectura:-?} (docker-compose-prod.yml)"
  fi
done
if ! docker exec argonavis_frontend nc -z -w 3 backend 8000 2>/dev/null; then
  mal "nginx no alcanza al backend"
elif docker exec argonavis_frontend nc -z -w 3 postgres_db 5432 2>/dev/null; then
  mal "nginx alcanza a PostgreSQL: van en redes separadas (docker-compose-prod.yml)"
else
  bien "nginx alcanza al backend y no a PostgreSQL"
fi
# Un envío se guarda mientras llega, en nginx y en el backend (los volúmenes temporales_*):
# 3 MB sin sesión llegan enteros a los dos y se rechazan (401 o 403), sin dejar rastro.
c=$(head -c 3145728 /dev/zero | codigo -F 'solicitud={}' -F 'archivos=@-;filename=prueba.pdf;type=application/pdf' "$BASE/api/v1/solicitudes")
case "$c" in 401|403) bien "Los envíos tienen dónde guardarse mientras llegan (sin sesión: $c)";; *) mal "Un envío de 3 MB sin sesión responde $c (se esperaba 401): ¿puede escribir nginx en /var/cache/nginx y el backend en /tmp?";; esac
if [ "$(docker exec argonavis_backend printenv APP_ENV 2>/dev/null)" = production ]; then bien "APP_ENV=production"; else mal "APP_ENV no es production"; fi
c=$(codigo "$BASE/api/docs")
if [ "$c" = 404 ]; then bien "La documentación de la API está oculta"; else aviso "/api/docs responde $c"; fi
sk=$(env_de SECRET_KEY)
if [ "${#sk}" -ge 32 ]; then bien "SECRET_KEY de ${#sk} caracteres"; else mal "SECRET_KEY corta (${#sk} caracteres)"; fi
# Tope del cuerpo (2026-11-10): nginx corta sin leer lo que pase de 1 MB en la API (y
# de 345 MB al enviar una solicitud). No llega al backend: no deja rastro.
c=$(head -c 2097152 /dev/zero | codigo -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/v1/auth/login")
if [ "$c" = 413 ]; then bien "nginx corta las peticiones de más de 1 MB en la API (413)"; else mal "Un cuerpo de 2 MB en el login respondió $c (se esperaba 413): revisa client_max_body_size en nginx.conf"; fi
if [ -z "$DIARIO" ]; then
  frenado=""
  for i in $(seq 1 25); do
    c=$(codigo -X POST -H 'Content-Type: application/json' \
        -d '{"username":"verificacion.freno","password":"no-es-una-clave"}' "$BASE/api/v1/auth/login")
    if [ "$c" = 429 ]; then frenado=$i; break; fi
  done
  if [ -n "$frenado" ]; then
    bien "El login se frena tras varios intentos (429 al intento $frenado; usuario inexistente, sin tocar el AD)"
  else
    mal "El login no se frenó tras 25 intentos"
  fi
fi
# Los registros (2026-11-22), en volúmenes: la salida de Docker se borra al recrear el
# contenedor. nginx acaba de recibir las peticiones de arriba: su archivo de hoy existe.
if docker exec argonavis_backend sh -c 'f=/app/registros/.verificacion; touch "$f" && rm -f "$f" && ls /app/registros/argonavis-*.log' >/dev/null 2>&1; then
  bien "El backend guarda sus registros ($(docker exec argonavis_backend sh -c 'ls /app/registros | wc -l; du -sh /app/registros | cut -f1' | paste -sd ' ' - | sed 's/ / archivo(s), /'))"
else
  mal "El backend no guarda sus registros en /app/registros (volumen registros)"
fi
if docker exec argonavis_frontend sh -c 'test -s "/var/log/argonavis/acceso-$(date +%F).log"' 2>/dev/null; then
  bien "nginx guarda los accesos de cada día"
else
  mal "nginx no guarda los accesos en /var/log/argonavis (volumen registros_nginx)"
fi

# ── HTTPS (2026-11-22) ───────────────────────────────────────────────────────
seccion "HTTPS"
if [ -z "$HTTPS" ]; then
  aviso "Sin HTTPS: la contraseña de cada login viaja en claro por la red (README → HTTPS)"
else
  publico=$(env_nginx APP_URL); publico=${publico#https://}; publico=${publico%%/*}
  destino=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 15 http://localhost/solicitudes/1)
  if [ "$destino" = "301 https://$publico/solicitudes/1" ]; then bien "El 80 solo lleva a https://$publico"; else mal "El 80 responde «$destino» (se esperaba 301 a https://$publico)"; fi
  if grep -qi '^strict-transport-security: max-age=' <<<"$(pedir -D - -o /dev/null "$BASE/")"; then bien "El navegador no vuelve a probar HTTP (Strict-Transport-Security)"; else mal "Falta Strict-Transport-Security"; fi
  # El certificado que nginx está usando, que puede no ser el de la carpeta si no se recargó.
  saludo=$(openssl s_client -connect localhost:443 -servername "${publico%%:*}" </dev/null 2>/dev/null)
  servido=$(openssl x509 2>/dev/null <<<"$saludo")
  if [ -z "$servido" ]; then
    mal "No se pudo leer el certificado del 443 (openssl s_client -connect localhost:443)"
  else
    vence=$(openssl x509 -noout -enddate <<<"$servido" | cut -d= -f2)
    dias=$(( ( $(date -d "$vence" +%s) - $(date +%s) ) / 86400 ))
    if ! openssl x509 -noout -checkend 0 <<<"$servido" >/dev/null; then
      mal "El certificado venció el $vence: los navegadores no dejan entrar"
    elif [ "$dias" -le 21 ]; then
      aviso "El certificado vence en $dias día(s) ($vence): hay que cambiarlo (README → HTTPS)"
    else
      bien "El certificado vale $dias días más ($vence)"
    fi
    if openssl x509 -noout -checkhost "${publico%%:*}" <<<"$servido" | grep -q 'does match' \
       && openssl x509 -noout -ext subjectAltName <<<"$servido" 2>/dev/null | grep -q 'DNS:'; then
      bien "El certificado es de ${publico%%:*}"
    else
      mal "El certificado no es de ${publico%%:*} (el nombre de APP_URL tiene que estar en su subjectAltName)"
    fi
    if [ "$(openssl x509 -noout -fingerprint -sha256 <<<"$servido")" != "$(openssl x509 -noout -fingerprint -sha256 -in certificados/https/argonavis.crt 2>/dev/null)" ]; then
      aviso "nginx sigue con el certificado anterior: sudo docker exec argonavis_frontend nginx -s reload"
    fi
    cadena=$(sed -n 's/^ *Verify return code: //p' <<<"$saludo" | head -1)
    if [ "$cadena" = "0 (ok)" ]; then
      bien "Lo firma una autoridad que este servidor conoce, con sus intermedios"
    else
      aviso "Este servidor no puede comprobar quién firma el certificado (${cadena:-sin respuesta}): o le falta un intermedio a argonavis.crt, o es de la CA interna y los equipos de las agencias verán una advertencia (README → HTTPS)"
    fi
  fi
  permisos=$(stat -c %a certificados/https/argonavis.key 2>/dev/null)
  if [ -n "$permisos" ] && [ $(( 8#$permisos & 8#077 )) -eq 0 ]; then
    bien "La clave privada solo la lee nginx"
  else
    mal "La clave privada la pueden leer otros (${permisos:-no está}): sudo chmod 400 certificados/https/argonavis.key"
  fi
fi

# ── Base de datos ────────────────────────────────────────────────────────────
seccion "Base de datos"
rev=$(docker exec argonavis_backend alembic current 2>/dev/null | tail -1)
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
cuenta=$(py_backend <<'PY' 2>/dev/null
import asyncio
from sqlalchemy import text
from app.infrastructure.database import motor_bd

async def main():
    async with motor_bd.connect() as c:
        fila = (await c.execute(text(
            "SELECT current_user, rolsuper, has_table_privilege(current_user, 'audit_logs', 'UPDATE'), "
            "has_table_privilege(current_user, 'audit_logs', 'INSERT') FROM pg_roles WHERE rolname = current_user"
        ))).one()
    await motor_bd.dispose()
    print(*fila)

asyncio.run(main())
PY
)
read -r c_nombre c_super c_edita c_agrega <<<"$cuenta"
if [ "${c_super:-}" = False ] && [ "${c_edita:-}" = False ] && [ "${c_agrega:-}" = True ]; then
  bien "La aplicación entra como $c_nombre: sin privilegios de administrador y con la bitácora solo para agregar"
elif [ "${c_super:-}" = True ]; then
  aviso "La aplicación entra como superusuario ($c_nombre): falta POSTGRES_APP_PASSWORD (README → Producción)"
else
  aviso "Cuenta de la aplicación: ${cuenta:-sin respuesta} (se esperaba sin superusuario y la bitácora solo para agregar)"
fi
max=$(psql_bd "show max_connections")
workers=$(docker exec argonavis_backend printenv UVICORN_WORKERS 2>/dev/null); workers=${workers:-1}
bd_pool=$(docker exec argonavis_backend printenv BD_POOL 2>/dev/null)
bd_extra=$(docker exec argonavis_backend printenv BD_POOL_EXTRA 2>/dev/null)
por_proceso=$(( ${bd_pool:-5} + ${bd_extra:-10} ))
necesarias=$(( workers * por_proceso ))
if [ -n "$max" ] && [ "$necesarias" -lt "$max" ]; then
  bien "Conexiones: hasta $necesarias ($workers procesos × $por_proceso) de las $max que admite PostgreSQL"
else
  mal "Se pueden pedir $necesarias conexiones y PostgreSQL admite ${max:-?}"
fi
if [ "$workers" -gt 1 ]; then
  corriendo=$(docker top argonavis_backend 2>/dev/null | grep -c 'spawn_main')
  if [ "$corriendo" -eq "$workers" ]; then bien "$workers procesos del backend en marcha"; else aviso "Se pidieron $workers procesos del backend y hay $corriendo"; fi
fi
# Los datos, en un volumen con nombre (2026-11-22). Si POSTGRES_IMAGEN y POSTGRES_VOLUMEN no
# casan, PostgreSQL los guardaría en uno sin nombre, que se pierde de vista al bajar la pila.
datos=$(psql_bd "show data_directory")
volumen=$(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Destination}} {{.Name}}{{println}}{{end}}{{end}}' argonavis_postgres 2>/dev/null \
  | while read -r destino nombre; do case "$datos/" in "$destino/"*) echo "${#destino} $nombre" ;; esac; done | sort -rn | head -1 | cut -d' ' -f2)
case "$volumen" in
  argonavis_postgres_*) bien "PostgreSQL $(psql_bd "show server_version" | cut -d' ' -f1) guarda los datos en su volumen ($volumen)" ;;
  *) mal "PostgreSQL guarda los datos (${datos:-?}) en «${volumen:-ningún volumen}» y no en el suyo: revisa POSTGRES_IMAGEN y POSTGRES_VOLUMEN (README → PostgreSQL 18)" ;;
esac
if docker exec argonavis_backend sh -c 'f=/app/storage/documentos/.verificacion; touch "$f" && rm -f "$f"' 2>/dev/null; then
  bien "El backend puede escribir en el volumen de documentos"
else
  mal "El backend no puede escribir en /app/storage/documentos (¿volumen creado como root? README → Producción)"
fi
# Cada documento y cada autorización emitida sigue en el disco y mide lo mismo (2026-11-22), y
# los de hoy coinciden con su huella: las solicitudes se consultan años después.
if documentos=$(docker exec argonavis_backend python -m app.infrastructure.revisar_documentos 2>/dev/null); then
  bien "Archivos de las solicitudes: $documentos"
else
  mal "Archivos de las solicitudes: ${documentos:-no se pudieron revisar (docker exec argonavis_backend python -m app.infrastructure.revisar_documentos)}"
fi
info "Tamaño de la base: $(psql_bd "select pg_size_pretty(pg_database_size(current_database()))"); conexiones abiertas: $(psql_bd "select count(*) from pg_stat_activity where datname = current_database()")"

if [ -n "$SOLO_LA_PILA" ]; then resultado; fi

# ── Integraciones ────────────────────────────────────────────────────────────
seccion "Integraciones"
ldap=$(py_backend <<'PY' 2>&1 | tail -1
from app.core.ldap import servicio_ldap
servicio_ldap._cerrar(servicio_ldap._conectar_cuenta_servicio())
print("ok")
PY
)
if [ "$ldap" = ok ]; then bien "Active Directory: la cuenta de servicio entra"; else mal "Active Directory: ${ldap:-sin respuesta}"; fi
if grep -qix true <<<"$(docker exec argonavis_backend printenv LDAP_USAR_SSL LDAP_STARTTLS 2>/dev/null)"; then
  bien "Active Directory: por TLS"
else
  aviso "Active Directory sin TLS: la contraseña de cada login viaja en claro hasta el controlador de dominio (README → HTTPS)"
fi
smtp=$(py_backend <<'PY' 2>&1 | tail -1
import os
import smtplib
import ssl
def si(variable):
    return os.environ.get(variable, "").lower() == "true"
host = os.environ.get("MAIL_HOST", "")
if not host:
    print("sin MAIL_HOST")
else:
    puerto = int(os.environ.get("MAIL_PORT") or 25)
    # Con TLS, el certificado se valida como lo valida la aplicación (MAIL_CA_CERT o las del sistema).
    contexto = ssl.create_default_context(cafile=os.environ.get("MAIL_CA_CERT") or None)
    conexion = smtplib.SMTP_SSL(host, puerto, timeout=10, context=contexto) if si("MAIL_USAR_SSL") else smtplib.SMTP(host, puerto, timeout=10)
    with conexion as s:
        s.ehlo()
        if si("MAIL_STARTTLS"):
            s.starttls(context=contexto)
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

# ── Sectores de UCVMM (2026-11-10) ───────────────────────────────────────────
# Al desplegar, todos los puestos y revisores quedan en el Pacífico (como antes):
# el administrador pasa a Atlántico los suyos. Sin sector, un revisor no ve nada.
seccion "Sectores de UCVMM"
sectores=$(psql_bd "select s.nombre || ': ' || count(p.id) || ' puesto(s)' from sectores s left join puestos_control p on p.sector_id = s.id group by s.id, s.nombre order by s.id" | paste -sd ';' - | sed 's/;/; /g')
info "Puestos por sector: ${sectores:-sin sectores (¿falta la migración?)}"
sin_sector=$(psql_bd "select count(*) from users u join roles r on r.id = u.rol_id where r.nombre in ('UCVMM', 'Supervisor de sector') and u.status::text in ('ACTIVO', 'active') and not exists (select 1 from usuarios_sectores us where us.usuario_id = u.id)")
if [ "${sin_sector:-0}" -gt 0 ]; then
  aviso "$sin_sector usuario(s) de UCVMM o de supervisión de sector sin sector: no ven solicitudes (Catálogos → Sectores)"
else
  bien "Los usuarios de UCVMM y de supervisión de sector tienen su sector"
fi
atlantico=$(psql_bd "select count(p.id) from sectores s left join puestos_control p on p.sector_id = s.id where s.nombre = 'Sector Atlántico'")
if [ "${atlantico:-0}" -eq 0 ]; then
  aviso "El Sector Atlántico no tiene puestos: pasa los suyos en Catálogos → Puestos de control"
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
# Los documentos, en una copia por día que solo agrega lo nuevo (desde el 2026-11-10;
# antes, un .tar.gz con todo cada noche).
copia=$(find "$dir/documentos" -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | tail -n 1)
if [ -n "$copia" ]; then
  horas=$(( ( $(date +%s) - $(stat -c %Y "$copia") ) / 3600 ))
  if [ "$horas" -le 26 ]; then bien "Última copia de los documentos: $(basename "$copia"), hace $horas h"; else aviso "La última copia de los documentos tiene $horas h: ¿corre el cron?"; fi
elif ls "$dir"/argonavis_documentos_*.tar.gz >/dev/null 2>&1; then
  aviso "Los documentos se respaldan todavía con el formato anterior (.tar.gz): el próximo respaldo pasa a la copia diaria"
else
  mal "No hay respaldos de los documentos en $dir/documentos"
fi
if [ -d "$dir" ]; then
  # Puede ser otro disco que el de Docker (en Rocky, /home suele ir aparte de /).
  uso_respaldos=$(df --output=pcent "$dir" | tail -1 | tr -dc '0-9')
  if [ "$uso_respaldos" -ge 85 ]; then aviso "El disco de los respaldos ($dir) está al ${uso_respaldos}%: baja RETENER_DIAS o llévalos a otro servidor"; fi
  info "Los respaldos ocupan $(du -sh "$dir" 2>/dev/null | cut -f1) y quedan en este mismo servidor: cópialos también a otro (rsync -aH)."
fi

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
# De los archivos de hoy y de ayer, que también tienen lo de antes del último despliegue.
desde=$(TZ=EST5 date -d '24 hours ago' '+%F %T')
errores=$(for dia in "$(TZ=EST5 date -d yesterday +%F)" "$(TZ=EST5 date +%F)"; do
  docker exec argonavis_backend cat "/app/registros/argonavis-$dia.log" 2>/dev/null
done | awk -v desde="$desde" '($3 == "ERROR" || $3 == "CRITICAL") && ($1 " " $2) >= desde' | wc -l)
if [ "$errores" -eq 0 ]; then
  bien "Sin errores en el registro del backend (últimas 24 h)"
else
  aviso "$errores error(es) en el registro del backend (últimas 24 h): docker exec argonavis_backend sh -c \"grep -A10 -E ' (ERROR|CRITICAL) ' /app/registros/argonavis-\$(date +%F).log\""
fi

# ── Vigilancia (2026-11-22) ──────────────────────────────────────────────────
seccion "Vigilancia"
if crontab -l 2>/dev/null | grep -v '^[[:space:]]*#' | grep -q 'vigilar.py'; then
  minutos=$(( ( $(date +%s) - $(stat -c %Y /var/lib/argonavis/vigilancia.json 2>/dev/null || echo 0) ) / 60 ))
  if [ "$minutos" -le 15 ]; then bien "La vigilancia corre (hace $minutos min)"; else mal "La vigilancia está en el cron de root pero no corre (tail /var/log/argonavis-vigilancia.log)"; fi
else
  aviso "Sin vigilancia: nadie se entera si el sistema se cae (instrucciones en vigilar.py)"
fi
if [ -n "$(env_de CORREO_ALERTAS)" ]; then
  info "Los avisos llegan a: $(env_de CORREO_ALERTAS)"
else
  aviso "Sin CORREO_ALERTAS en el .env: la vigilancia no le avisa a nadie"
fi

resultado
