#!/bin/bash
# ============================================================
# Aplicar las migraciones nuevas a una base de datos EXISTENTE
# ============================================================
# Por que hace falta este script:
#
# Postgres solo ejecuta lo que hay en /docker-entrypoint-initdb.d cuando el
# directorio de datos esta VACIO. En una base que ya existe (la de desarrollo,
# o produccion tras una actualizacion) los ficheros nuevos se ignoran en
# silencio. El sintoma es confuso: los servicios arrancan y fallan al
# conectarse con 'el rol "revo_app" no existe'.
#
# Este script aplica las migraciones que anaden RLS, roles de aplicacion,
# consentimiento informado y alta de alumnos. Es idempotente: se puede
# ejecutar varias veces.
#
# Uso (contenedor de docker compose):
#     bash database/aplicar_migraciones.sh
#
# Uso (base externa, por ejemplo Render):
#     DATABASE_URL="postgresql://dueno:clave@host/revo_db" \
#     APP_DB_PASSWORD="..." SERVICE_DB_PASSWORD="..." \
#         bash database/aplicar_migraciones.sh
# ============================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRACIONES=(10_rls 12_consentimiento 13_registro)

# ── Contrasenas de los roles de aplicacion ───────────────────
cargar_del_env() {
    local clave="$1"
    [ -f "$RAIZ/.env" ] || return 0
    grep -E "^${clave}=" "$RAIZ/.env" | head -1 | cut -d= -f2- || true
}

APP_DB_PASSWORD="${APP_DB_PASSWORD:-$(cargar_del_env APP_DB_PASSWORD)}"
SERVICE_DB_PASSWORD="${SERVICE_DB_PASSWORD:-$(cargar_del_env SERVICE_DB_PASSWORD)}"

if [ -z "${APP_DB_PASSWORD:-}" ] || [ -z "${SERVICE_DB_PASSWORD:-}" ]; then
    echo "ERROR: faltan APP_DB_PASSWORD y/o SERVICE_DB_PASSWORD." >&2
    echo "Definelas en el entorno o en el .env de la raiz." >&2
    exit 1
fi

# ── Como hablar con la base ──────────────────────────────────
if [ -n "${DATABASE_URL:-}" ]; then
    echo "==> Base externa"
    ejecutar_sql() { psql "$DATABASE_URL" -v ON_ERROR_STOP=1 "$@"; }
else
    CONTENEDOR="${CONTENEDOR_POSTGRES:-revo_postgres}"
    USUARIO="${POSTGRES_USER:-revo_user}"
    BASE="${POSTGRES_DB:-revo_db}"

    if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
        echo "ERROR: el contenedor '$CONTENEDOR' no esta corriendo." >&2
        echo "Levantalo con: docker compose up -d postgres" >&2
        exit 1
    fi

    echo "==> Contenedor $CONTENEDOR (base $BASE, usuario $USUARIO)"
    ejecutar_sql() { docker exec -i "$CONTENEDOR" psql -v ON_ERROR_STOP=1 -U "$USUARIO" -d "$BASE" "$@"; }
fi

# ── Aplicar ──────────────────────────────────────────────────
for migracion in "${MIGRACIONES[@]}"; do
    archivo="$RAIZ/database/${migracion}.sql"
    if [ ! -f "$archivo" ]; then
        echo "ERROR: no existe $archivo" >&2
        exit 1
    fi
    echo "    aplicando ${migracion}"
    ejecutar_sql -q < "$archivo" > /dev/null
done

# ── Contrasenas de los roles ─────────────────────────────────
# Se pasan como variables de psql y se interpolan con :'nombre', que las
# emite como literal correctamente entrecomillado. Concatenarlas a mano
# rompe con cualquier contrasena que lleve una comilla simple.
echo "    asignando contrasenas a revo_app y revo_service"
ejecutar_sql -q \
    -v app_password="$APP_DB_PASSWORD" \
    -v service_password="$SERVICE_DB_PASSWORD" <<'SQL' > /dev/null
ALTER ROLE revo_app     WITH PASSWORD :'app_password';
ALTER ROLE revo_service WITH PASSWORD :'service_password';
SQL

# ── Comprobacion ─────────────────────────────────────────────
echo "==> Comprobando"

SIN_RLS=$(ejecutar_sql -tAc "
    SELECT coalesce(string_agg(c.relname, ', '), '')
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND c.relname IN ('users','questionnaire_sessions','answers','predictions',
                        'prediction_feedbacks','feedback','ml_training_data',
                        'user_consents','legal_documents')
      AND NOT c.relrowsecurity;")

if [ -n "$SIN_RLS" ]; then
    echo "ERROR: estas tablas quedaron sin RLS: $SIN_RLS" >&2
    exit 1
fi

DOCUMENTOS=$(ejecutar_sql -tAc "SELECT count(*) FROM legal_documents WHERE is_current;")
if [ "$DOCUMENTOS" != "4" ]; then
    echo "ERROR: hay $DOCUMENTOS documentos legales vigentes, deberian ser 4" >&2
    exit 1
fi

echo ""
echo "Migraciones aplicadas: RLS activo, 4 documentos legales vigentes,"
echo "roles revo_app y revo_service listos."
