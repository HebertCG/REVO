#!/bin/bash
# ============================================================
# Verificacion de las politicas RLS contra un Postgres real
# ============================================================
# Levanta un Postgres desechable, carga el esquema y las politicas, y ejecuta
# las 16 comprobaciones de aislamiento. No toca la base de datos de
# desarrollo ni la de produccion.
#
# Uso:
#     bash database/pruebas/verificar_rls.sh
#
# Por que existe: una politica RLS mal escrita no da error, simplemente
# devuelve filas de mas. La unica forma de saber que aisla es intentar
# leer los datos de otro alumno y comprobar que no salen.
# ============================================================
set -euo pipefail

CONTENEDOR="revo_rls_verificacion"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

limpiar() {
    docker rm -f "$CONTENEDOR" >/dev/null 2>&1 || true
}
trap limpiar EXIT

echo "==> Levantando Postgres desechable"
limpiar
docker run -d --name "$CONTENEDOR" \
    -e POSTGRES_DB=revo_db \
    -e POSTGRES_USER=revo_user \
    -e POSTGRES_PASSWORD=verificacion_local \
    postgres:16-alpine >/dev/null

for _ in $(seq 1 60); do
    if docker exec "$CONTENEDOR" pg_isready -U revo_user -d revo_db >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "==> Cargando esquema y politicas"
# Solo lo necesario para las politicas: los seeds pesados (04, con 1000 filas
# de entrenamiento) no aportan nada a esta verificacion y la alargan.
for archivo in 01_init 01b_schema_sync 02_seed_specializations 03_seed_questions \
               07_seed_courses 08_seed_jobs 09_psychometric_questions \
               10_rls 12_consentimiento 13_registro 14_cuentas; do
    docker exec -i "$CONTENEDOR" psql -v ON_ERROR_STOP=1 -U revo_user -d revo_db -q \
        < "$RAIZ/database/$archivo.sql" > /dev/null
    echo "    cargado $archivo"
done

echo "==> Ejecutando comprobaciones de aislamiento"
SALIDA=$(docker exec -i "$CONTENEDOR" psql -U revo_user -d revo_db \
    < "$RAIZ/database/pruebas/verificar_rls.sql" 2>&1)

SALIDA_CUENTAS=$(docker exec -i "$CONTENEDOR" psql -U revo_user -d revo_db     < "$RAIZ/database/pruebas/verificar_cuentas.sql" 2>&1)
SALIDA="$SALIDA
$SALIDA_CUENTAS"

echo "$SALIDA" | grep -E "NOTICE|ERROR" | sed 's/^NOTICE:  //'

if echo "$SALIDA" | grep -q "ERROR"; then
    echo ""
    echo "RESULTADO: hay politicas RLS que no aislan como deberian."
    exit 1
fi

echo ""
echo "RESULTADO: todas las comprobaciones de RLS pasaron."
