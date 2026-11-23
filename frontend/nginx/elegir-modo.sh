#!/bin/sh
# HTTP o HTTPS, según USAR_HTTPS del .env (2026-11-22). Lo corre la imagen de nginx al arrancar
# (/docker-entrypoint.d), antes que nginx. Deja en /run/argonavis dónde escucha y, con HTTPS,
# el servidor del 80 que redirige; nginx.conf los incluye. Si algo falta, nginx no arranca y
# el registro dice qué (docker logs argonavis_frontend): volver solo a HTTP, sin que nadie se
# entere, sería peor.
set -eu
origen=${1:-/etc/nginx/argonavis}
certificados=${2:-/certificados}
destino=${3:-/run/argonavis}

no_arranca() {
  echo "ARGO NAVIS no arranca: $*" >&2
  exit 1
}

mkdir -p "$destino"
rm -f "$destino/escucha.conf" "$destino/redireccion.conf"

case "${USAR_HTTPS:-false}" in
  [Tt][Rr][Uu][Ee]) ;;
  [Ff][Aa][Ll][Ss][Ee])
    : > "$destino/redireccion.conf"
    cp "$origen/http.conf" "$destino/escucha.conf"
    echo "ARGO NAVIS atiende por HTTP (USAR_HTTPS=false)."
    exit 0 ;;
  *) no_arranca "USAR_HTTPS=$USAR_HTTPS no se entiende: en el .env va true o false." ;;
esac

for archivo in argonavis.crt argonavis.key; do
  [ -s "$certificados/$archivo" ] || no_arranca "USAR_HTTPS=true y falta certificados/https/$archivo (README → HTTPS)."
  [ -r "$certificados/$archivo" ] || no_arranca "nginx no puede leer certificados/https/$archivo: sudo chown 101:101 certificados/https/$archivo (README → HTTPS)."
done

case "${APP_URL:-}" in
  https://*) ;;
  *) no_arranca "con USAR_HTTPS=true, APP_URL del .env tiene que empezar con https:// (hoy: ${APP_URL:-vacía})." ;;
esac
nombre=${APP_URL#https://}
nombre=${nombre%%/*}
case "$nombre" in
  '' | *[!A-Za-z0-9.:-]*) no_arranca "APP_URL del .env no lleva el nombre del servidor: $APP_URL" ;;
esac

sed "s/NOMBRE/$nombre/" "$origen/redireccion.conf" > "$destino/redireccion.conf"
cp "$origen/https.conf" "$destino/escucha.conf"
echo "ARGO NAVIS atiende por HTTPS (https://$nombre); el 80 solo redirige."
