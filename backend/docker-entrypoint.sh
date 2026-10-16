#!/usr/bin/env bash
set -euo pipefail

echo "==> Aplicando migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando uvicorn..."
# --proxy-headers: la IP del cliente sale de X-Forwarded-For (la pone nginx).
# Confiar en cualquier origen ("*") es seguro aquí porque el puerto 8000 no se
# publica: al backend solo llega nginx, y nginx reemplaza esa cabecera con la IP
# real (no la agrega a la que mande el cliente; ver frontend/nginx.conf). Sin
# esto, todos los usuarios tendrían la IP de nginx y compartirían el rate limit
# del login.
exec uvicorn app.main:aplicacion --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips="*" --no-server-header
