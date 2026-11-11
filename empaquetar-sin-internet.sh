#!/usr/bin/env bash
# ARGO NAVIS — paquete para instalar en un servidor SIN salida a internet (2026-11-10).
#
# En un equipo CON internet y Docker, desde la carpeta del proyecto y en el
# commit que se va a instalar:
#   bash empaquetar-sin-internet.sh
# Deja en paquete-sin-internet/:
#   - argonavis-imagenes-<commit>.tar.gz: las imágenes ya construidas (backend,
#     frontend y PostgreSQL), con todas las librerías adentro;
#   - argonavis-codigo-<commit>.tar.gz: el código de ese commit
#     (docker-compose-prod.yml, verificar-despliegue.sh, backup.sh…);
#   - SHA256SUMS: para comprobar en el servidor que llegaron completos.
#
# En el servidor, con Docker ya instalado (sin internet; el .env del servidor no
# va en el paquete: se conserva el que ya está):
#   sha256sum -c SHA256SUMS
#   tar xzf argonavis-codigo-<commit>.tar.gz -C ~/argonavis
#   docker load -i argonavis-imagenes-<commit>.tar.gz
#   cd ~/argonavis && docker compose -f docker-compose-prod.yml up -d --no-build --pull never
#   sudo bash verificar-despliegue.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Hay cambios sin commit: el paquete sale de un commit (haz el commit o guarda los cambios)." >&2
  exit 1
fi
commit=$(git rev-parse --short HEAD)
salida=paquete-sin-internet
postgres=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' docker-compose-prod.yml | head -1)
if [ -z "$postgres" ]; then
  echo "No encontré la imagen de PostgreSQL en docker-compose-prod.yml." >&2
  exit 1
fi
mkdir -p "$salida"

echo "== Construyendo las imágenes del commit $commit =="
# Con docker build y no con compose: compose pide el .env (las contraseñas) aunque solo construya.
docker build -t argonavis-backend:latest backend
docker build -t argonavis-frontend:latest frontend
docker pull "$postgres"

echo "== Guardando =="
imagenes="argonavis-imagenes-$commit.tar.gz"
codigo="argonavis-codigo-$commit.tar.gz"
docker save argonavis-backend:latest argonavis-frontend:latest "$postgres" | gzip > "$salida/$imagenes"
git archive --format=tar.gz -o "$salida/$codigo" HEAD
(cd "$salida" && sha256sum "$imagenes" "$codigo" > SHA256SUMS)

echo "Listo. En $salida/:"
ls -lh "$salida"
