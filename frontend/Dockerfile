# Node 24 (LTS): la misma versión con la que se desarrolla. Node 20 quedó sin soporte en abril de 2026.
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
# npm ci instala exactamente lo del package-lock.json (build reproducible).
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
