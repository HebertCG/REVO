#!/bin/bash
# ============================================================
# Verificacion de las fronteras entre servicios
# ============================================================
# Comprueba que cada rol de base de datos alcanza SOLO sus tablas.
#
# Por que hace falta esta prueba: un GRANT de mas no da error, da acceso. La
# unica forma de saber que la frontera existe es intentar cruzarla y
# comprobar que el motor lo rechaza.
#
# Uso:
#     bash database/pruebas/verificar_fronteras.sh                 # base desechable
#     CONTENEDOR=revo_postgres bash database/pruebas/verificar_fronteras.sh
# ============================================================
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESECHABLE="${CONTENEDOR:-}"
PROPIO=0

if [ -z "$DESECHABLE" ]; then
    DESECHABLE="revo_fronteras_test"
    PROPIO=1
fi

limpiar() {
    if [ "$PROPIO" = "1" ]; then
        docker rm -f "$DESECHABLE" >/dev/null 2>&1 || true
    fi
}
trap limpiar EXIT

if [ "$PROPIO" = "1" ]; then
    echo "==> Levantando Postgres desechable"
    limpiar
    docker run -d --name "$DESECHABLE" \
        -e POSTGRES_DB=revo_db -e POSTGRES_USER=revo_user \
        -e POSTGRES_PASSWORD=fronteras_local postgres:16-alpine >/dev/null

    listo=0
    for _ in $(seq 1 60); do
        if docker exec "$DESECHABLE" psql -U revo_user -d revo_db -tAc "SELECT 1" >/dev/null 2>&1; then
            listo=$((listo + 1))
            [ "$listo" -ge 3 ] && break
        fi
        sleep 1
    done

    echo "==> Cargando esquema, politicas y roles"
    for archivo in 01_init 01b_schema_sync 02_seed_specializations 03_seed_questions \
                   07_seed_courses 08_seed_jobs 09_psychometric_questions \
                   10_rls 12_consentimiento 13_registro 14_cuentas \
                   15_roles_por_servicio 17_mover_catalogos \
                   18_compatibilidad_gestionado; do
        docker exec -i "$DESECHABLE" psql -v ON_ERROR_STOP=1 -U revo_user -d revo_db -q \
            < "$RAIZ/database/$archivo.sql" > /dev/null
    done

    docker exec "$DESECHABLE" psql -U revo_user -d revo_db -q -c \
        "ALTER ROLE revo_auth WITH PASSWORD 'x';
         ALTER ROLE revo_survey WITH PASSWORD 'x';
         ALTER ROLE revo_ml WITH PASSWORD 'x';" >/dev/null
fi

pasadas=0
fallidas=0

# comprobar <rol> <tabla> <esperado: abierto|cerrado>
comprobar() {
    local rol="$1" tabla="$2" esperado="$3"
    local salida
    salida=$(docker exec "$DESECHABLE" psql -U "$rol" -d revo_db -tAc \
        "SELECT count(*) FROM $tabla" 2>&1 | head -1)

    # "no permitted to log in" cuenta como cerrado, y es la forma mas fuerte:
    # el rol no solo carece de permisos, es que ni siquiera puede conectarse.
    # Sin este caso, un rol desactivado se clasificaba como "abierto" y la
    # prueba daba un falso positivo.
    local real="abierto"
    case "$salida" in
        *denied*|*"no existe"*|*"does not exist"*) real="cerrado" ;;
        *"not permitted to log in"*|*"no tiene permitido"*)        real="cerrado" ;;
        *"authentication failed"*|*"fallo la autentificacion"*)    real="cerrado" ;;
    esac

    if [ "$real" = "$esperado" ]; then
        pasadas=$((pasadas + 1))
        if [ "$esperado" = "cerrado" ]; then
            printf '  OK    %-12s NO alcanza %s\n' "$rol" "$tabla"
        else
            printf '  OK    %-12s alcanza %s\n' "$rol" "$tabla"
        fi
    else
        fallidas=$((fallidas + 1))
        if [ "$esperado" = "cerrado" ]; then
            printf '  FALLA %-12s ALCANZA %s y no deberia\n' "$rol" "$tabla"
        else
            printf '  FALLA %-12s no alcanza %s y lo necesita\n' "$rol" "$tabla"
        fi
    fi
}

echo ""
echo "== Lo que cada servicio NO debe alcanzar =="
comprobar revo_survey users                  cerrado
comprobar revo_survey user_consents          cerrado
comprobar revo_survey ml_training_data       cerrado
comprobar revo_survey predictions            cerrado
comprobar revo_ml     users                  cerrado
comprobar revo_ml     answers                cerrado
comprobar revo_ml     questionnaire_sessions cerrado
comprobar revo_ml     user_consents          cerrado
comprobar revo_auth   answers                cerrado
comprobar revo_auth   ml_training_data       cerrado
comprobar revo_auth   predictions            cerrado
comprobar revo_auth   questionnaire_sessions cerrado
comprobar revo_survey courses                cerrado
comprobar revo_survey jobs                   cerrado

echo ""
echo "== El rol antiguo compartido quedo cerrado =="
comprobar revo_app users            cerrado
comprobar revo_app answers          cerrado
comprobar revo_app ml_training_data cerrado

echo ""
echo "== Cada servicio si alcanza lo suyo =="
comprobar revo_auth   users                  abierto
comprobar revo_auth   user_consents          abierto
comprobar revo_auth   legal_documents        abierto
comprobar revo_survey questionnaire_sessions abierto
comprobar revo_survey answers                abierto
comprobar revo_survey questions              abierto
comprobar revo_ml     predictions            abierto
comprobar revo_ml     ml_training_data       abierto
comprobar revo_ml     specializations        abierto
comprobar revo_ml     courses                abierto
comprobar revo_ml     jobs                   abierto

echo ""
echo "============================================="
printf '  Pasadas: %d   Fallidas: %d\n' "$pasadas" "$fallidas"
echo "============================================="

[ "$fallidas" -eq 0 ] || exit 1
