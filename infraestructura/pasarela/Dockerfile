# Etapa 1: el frontend se compila con Node, pero Node no llega a produccion.
FROM node:24.21.0-alpine3.24 AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/public/ ./public/
COPY frontend/src/ ./src/

RUN npm run build


# Etapa 2: una sola imagen publica sirve React y actua como pasarela de API.
FROM nginx:1.30.4-alpine3.24

ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx

COPY infraestructura/pasarela/nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY --from=frontend /frontend/dist/ /usr/share/nginx/html/

EXPOSE 80
