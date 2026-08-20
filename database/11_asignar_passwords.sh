#!/bin/bash
# ============================================================
# REVO DB - Script 11: contrasenas de los roles de aplicacion
# ============================================================
# Las contrasenas de revo_app y revo_service NO pueden ir en un .sql
# versionado. Este script corre dentro del contenedor de Postgres, donde si
# tiene acceso a las variables de entorno del compose.
#
# Postgres ejecuta en orden alfabetico todo lo que hay en
# /docker-entrypoint-initdb.d, asi que este 11 va despues del 10 que crea
# los roles.
# ============================================================
set -euo pipefail

if [ -z "${APP_DB_PASSWORD:-}" ]; then
    echo "ERROR: falta APP_DB_PASSWORD. Los servicios no podrian conectarse." >&2
    exit 1
fi

if [ -z "${SERVICE_DB_PASSWORD:-}" ]; then
    echo "ERROR: falta SERVICE_DB_PASSWORD. El reentrenamiento no podria correr." >&2
    exit 1
fi

# Las contrasenas viajan como variables de psql y se interpolan con :'nombre',
# que las emite como literal correctamente entrecomillado. Concatenarlas a
# mano rompe con cualquier contrasena que lleve comilla simple, y ese fallo
# se manifiesta como "no puedo conectarme" en produccion.
#
# Nota operativa: si el servidor corre con log_statement=all, estas dos
# sentencias quedan en el log. Es aceptable en el arranque inicial, pero por
# eso el log del contenedor de base de datos no debe exponerse.
psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -v app_password="$APP_DB_PASSWORD" \
     -v service_password="$SERVICE_DB_PASSWORD" <<'SQL'
ALTER ROLE revo_app     WITH PASSWORD :'app_password';
ALTER ROLE revo_service WITH PASSWORD :'service_password';
SQL

echo "Contrasenas de revo_app y revo_service asignadas."
