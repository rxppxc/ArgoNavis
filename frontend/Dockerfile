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
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
