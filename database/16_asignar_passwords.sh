#!/bin/bash
# ============================================================
# REVO DB - Script 16: contrasenas de los roles de servicio
# ============================================================
# Sustituye a 11_asignar_passwords.sh, que solo cubria revo_app y
# revo_service. Desde la migracion 15 cada servicio tiene su propio rol.
#
# Corre dentro del contenedor de Postgres, que es donde estan las variables
# de entorno del compose. Las contrasenas nunca van en un .sql versionado.
# ============================================================
set -euo pipefail

falta() {
    echo "ERROR: falta $1. El servicio correspondiente no podria conectarse." >&2
    exit 1
}

[ -n "${AUTH_DB_PASSWORD:-}" ]    || falta AUTH_DB_PASSWORD
[ -n "${SURVEY_DB_PASSWORD:-}" ]  || falta SURVEY_DB_PASSWORD
[ -n "${ML_DB_PASSWORD:-}" ]      || falta ML_DB_PASSWORD
[ -n "${SERVICE_DB_PASSWORD:-}" ] || falta SERVICE_DB_PASSWORD

# Las contrasenas viajan como variables de psql y se interpolan con :'nombre',
# que las emite como literal correctamente entrecomillado. Concatenarlas a
# mano rompe con cualquier contrasena que lleve una comilla simple, y ese
# fallo se manifiesta en produccion como "no puedo conectarme".
psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -v auth_password="$AUTH_DB_PASSWORD" \
     -v survey_password="$SURVEY_DB_PASSWORD" \
     -v ml_password="$ML_DB_PASSWORD" \
     -v service_password="$SERVICE_DB_PASSWORD" <<'SQL'
ALTER ROLE revo_auth    WITH PASSWORD :'auth_password';
ALTER ROLE revo_survey  WITH PASSWORD :'survey_password';
ALTER ROLE revo_ml      WITH PASSWORD :'ml_password';
ALTER ROLE revo_service WITH PASSWORD :'service_password';

-- revo_app ya no lo usa nadie y la migracion 15 le quito los permisos. Se le
-- retira ademas la capacidad de conectarse: un rol sin uso que aun puede
-- iniciar sesion es una puerta que nadie vigila.
ALTER ROLE revo_app NOLOGIN;
SQL

echo "Contrasenas asignadas: revo_auth, revo_survey, revo_ml, revo_service."
echo "revo_app queda sin permisos y sin poder conectarse."
