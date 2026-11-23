# Versiones exactas de las imágenes base (2026-11-10): con «node:24-alpine» y
# «nginx:alpine» cada build podía traer otra versión sin que nadie lo decidiera.
# Node 24 (LTS): la misma versión con la que se desarrolla. Node 20 quedó sin soporte en abril de 2026.
FROM node:24.22.2-alpine3.24 AS build
WORKDIR /app
COPY package*.json ./
# npm ci instala exactamente lo del package-lock.json (build reproducible).
RUN npm ci
COPY . .
RUN npm run build

# nginx de la rama principal («mainline», la que recomienda nginx), como era «nginx:alpine».
FROM nginx:1.31.8-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# HTTP o HTTPS, según USAR_HTTPS del .env: lo decide elegir-modo.sh al arrancar.
COPY nginx/*.conf /etc/nginx/argonavis/
COPY nginx/elegir-modo.sh /docker-entrypoint.d/05-elegir-modo.sh
# Sin root (2026-11-22): todo nginx corre con el usuario nginx (101) de la imagen.
#   - Las carpetas donde guarda los envíos mientras llegan y los accesos de cada día son
#     suyas; los volúmenes nuevos que las ocupan copian ese dueño.
#   - Se quita la línea «user», que solo sirve si arranca como root (si no, avisa en cada arranque).
#   - Escucha en el 8080 y, con HTTPS, en el 8443: el 80 y el 443 son solo para root.
#     Docker los publica ahí.
#   - La imagen de nginx solo corre los guiones ejecutables, y ese permiso no viaja en un
#     commit hecho en Windows; sin los CR, por si el clon también es de Windows.
RUN mkdir -p /var/cache/nginx /var/log/argonavis \
    && chown -R nginx:nginx /var/cache/nginx /var/log/argonavis \
    && sed -i '/^user /d' /etc/nginx/nginx.conf \
    && sed -i 's/\r$//' /docker-entrypoint.d/05-elegir-modo.sh \
    && chmod 755 /docker-entrypoint.d/05-elegir-modo.sh
USER nginx
EXPOSE 8080 8443
CMD ["nginx", "-g", "daemon off;"]
