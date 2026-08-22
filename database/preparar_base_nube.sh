#!/bin/bash
# ============================================================
# Preparar una base de datos NUEVA en la nube (Supabase, Neon, RDS)
# ============================================================
# Aplica el esquema completo, los datos iniciales, las politicas RLS y los
# roles de servicio sobre una base vacia, y despues comprueba que quedo bien.
#
# No hace falta tener psql instalado: usa la imagen de Postgres por Docker.
#
# Uso:
#     DATABASE_URL="postgresql://postgres.xxx:CLAVE@host:5432/postgres" \
#         bash database/preparar_base_nube.sh
#
# Es idempotente en lo esencial (las migraciones usan IF NOT EXISTS y
# ON CONFLICT), pero esta pensado para una base recien creada.
# ============================================================
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGEN="postgres:16-alpine"

# Solo para probar contra una base que vive en una red de Docker local.
# Contra Supabase o cualquier host de internet se deja vacio.
RED_DOCKER="${RED_DOCKER:-}"
ARGS_RED=()
[ -n "$RED_DOCKER" ] && ARGS_RED=(--network "$RED_DOCKER")

if [ -z "${DATABASE_URL:-}" ]; then
    cat >&2 <<'AYUDA'
ERROR: falta DATABASE_URL.

En Supabase la encuentras en: Project Settings -> Database -> Connection string
Usa la de "Session pooler" (puerto 5432).

    DATABASE_URL="postgresql://postgres.xxxx:CLAVE@aws-0-REGION.pooler.supabase.com:5432/postgres" \
        bash database/preparar_base_nube.sh
AYUDA
    exit 1
fi

# psql dentro de un contenedor: asi no hace falta instalarlo en la maquina.
psql_nube() {
    docker run --rm -i "${ARGS_RED[@]}" "$IMAGEN" psql "$DATABASE_URL" "$@"
}

psql_archivo() {
    docker run --rm -i "${ARGS_RED[@]}" "$IMAGEN" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q < "$1"
}

echo "==> Comprobando la conexion"
if ! psql_nube -tAc "SELECT 1" >/dev/null 2>&1; then
    echo "ERROR: no se pudo conectar. Revisa DATABASE_URL." >&2
    echo "       Si la contrasena tiene caracteres raros (@ : / ?), hay que" >&2
    echo "       codificarlos en la URL (@ es %40, : es %3A)." >&2
    exit 1
fi

VERSION=$(psql_nube -tAc "SHOW server_version" | tr -d ' ')
echo "    conectado. PostgreSQL $VERSION"

echo "==> Extensiones"
psql_nube -q -c "CREATE EXTENSION IF NOT EXISTS pgcrypto" >/dev/null 2>&1 \
    && echo "    pgcrypto lista" \
    || echo "    aviso: no se pudo crear pgcrypto (puede que ya exista)"
psql_nube -q -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' >/dev/null 2>&1 \
    && echo "    uuid-ossp lista" \
    || echo "    aviso: no se pudo crear uuid-ossp (puede que ya exista)"

# El orden es el mismo que usa Postgres al inicializar por Docker. Cambiarlo
# rompe: 10_rls necesita las tablas, y 12/14 necesitan las funciones de 10.
MIGRACIONES=(
    01_init
    01b_schema_sync
    02_seed_specializations
    03_seed_questions
    04_seed_training_data
    05_seed_users
    06_fix_passwords
    07_seed_courses
    08_seed_jobs
    09_psychometric_questions
    10_rls
    12_consentimiento
    13_registro
    14_cuentas
    15_roles_por_servicio
    17_mover_catalogos
    18_compatibilidad_gestionado
)

echo "==> Aplicando ${#MIGRACIONES[@]} migraciones"
for m in "${MIGRACIONES[@]}"; do
    archivo="$RAIZ/database/${m}.sql"
    if [ ! -f "$archivo" ]; then
        echo "ERROR: no existe $archivo" >&2
        exit 1
    fi

    salida=$(psql_archivo "$archivo" 2>&1)
    if [ $? -eq 0 ]; then
        printf '    OK     %s\n' "$m"
    else
        printf '    FALLA  %s\n' "$m"
        echo "$salida" | grep -E "^ERROR" | head -3 | sed 's/^/           /'
        echo ""
        echo "Se detiene aqui. Corrige el error antes de seguir: las" >&2
        echo "migraciones posteriores dependen de esta." >&2
        exit 1
    fi
done

echo "==> Comprobando el resultado"
fallos=0

comprobar() {
    local descripcion="$1" consulta="$2" esperado="$3"
    local real
    real=$(psql_nube -tAc "$consulta" 2>/dev/null | tr -d ' ')
    if [ "$real" = "$esperado" ]; then
        printf '    OK     %s\n' "$descripcion"
    else
        printf '    FALLA  %s (esperado %s, obtenido %s)\n' "$descripcion" "$esperado" "$real"
        fallos=$((fallos + 1))
    fi
}

comprobar "4 documentos legales vigentes" \
    "SELECT count(*) FROM legal_documents WHERE is_current" "4"

comprobar "los tres roles de servicio existen" \
    "SELECT count(*) FROM pg_roles WHERE rolname IN ('revo_auth','revo_survey','revo_ml')" "3"

comprobar "revo_survey NO alcanza la tabla de usuarios" \
    "SELECT has_table_privilege('revo_survey','users','SELECT')" "f"

comprobar "revo_ml NO alcanza las respuestas del cuestionario" \
    "SELECT has_table_privilege('revo_ml','answers','SELECT')" "f"

comprobar "revo_auth SI alcanza la tabla de usuarios" \
    "SELECT has_table_privilege('revo_auth','users','SELECT')" "t"

# La comprobacion mas importante: si esta falla, nadie podra iniciar sesion.
comprobar "el login puede recuperar credenciales" \
    "SELECT count(*) FROM revo_credenciales_por_email('admin@revo.edu')" "1"

comprobar "RLS activo en las tablas de alumnos" \
    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
       AND c.relname IN ('users','questionnaire_sessions','answers','predictions','user_consents')" "5"

echo ""
if [ "$fallos" -eq 0 ]; then
    cat <<'FIN'
=============================================
  Base de datos lista.
=============================================

Siguiente: dar contrasena a los roles de servicio. Genera cuatro distintas:

    python -c "import secrets; print(secrets.token_urlsafe(36))"

Y ejecutalas en el editor SQL de Supabase:

    ALTER ROLE revo_auth    WITH PASSWORD 'la-primera';
    ALTER ROLE revo_survey  WITH PASSWORD 'la-segunda';
    ALTER ROLE revo_ml      WITH PASSWORD 'la-tercera';
    ALTER ROLE revo_service WITH PASSWORD 'la-cuarta';
    ALTER ROLE revo_app NOLOGIN;
FIN
    exit 0
else
    echo "Quedaron $fallos comprobaciones sin pasar. No sigas hasta resolverlas."
    exit 1
fi
