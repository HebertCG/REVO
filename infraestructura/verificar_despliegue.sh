#!/bin/bash
# ============================================================
# Verificacion del despliegue completo
# ============================================================
# Comprueba, contra la pila realmente levantada, las propiedades que se
# pidieron para produccion:
#
#   - Ninguna API expuesta: solo la pasarela publica un puerto.
#   - La documentacion de la API no se sirve al exterior.
#   - El consentimiento informado se graba en el alta.
#   - Un alumno no alcanza los datos de otro.
#   - El rate limit corta y devuelve Retry-After.
#   - Las cabeceras de seguridad viajan en todas las respuestas.
#   - Los errores no devuelven trazas.
#
# Uso:
#     PUERTO=8080 bash infraestructura/verificar_despliegue.sh
# ============================================================
set -uo pipefail

PUERTO="${PUERTO:-8080}"
BASE="http://localhost:${PUERTO}"
API="${BASE}/api"

VERDE='\033[0;32m'; ROJO='\033[0;31m'; GRIS='\033[0;90m'; RESET='\033[0m'
PASADAS=0
FALLIDAS=0

ok()    { PASADAS=$((PASADAS+1)); printf "${VERDE}  OK${RESET}  %s\n" "$1"; }
fallo() { FALLIDAS=$((FALLIDAS+1)); printf "${ROJO}FALLO${RESET}  %s\n" "$1"; }
seccion() { printf "\n${GRIS}== %s ==${RESET}\n" "$1"; }

codigo() { curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$@"; }

# ────────────────────────────────────────────────────────────
seccion "Superficie expuesta"

if [ "$(codigo "${BASE}/health")" = "200" ]; then
    ok "la pasarela responde en el puerto ${PUERTO}"
else
    fallo "la pasarela no responde en el puerto ${PUERTO}"
fi

# Los microservicios no deben tener ningun puerto publicado. Si responden
# aqui, es que alguien reanadio un `ports:` al compose.
for puerto in 8001 8002 8003 5432 5434 6379; do
    if curl -s --max-time 2 "http://localhost:${puerto}/" >/dev/null 2>&1; then
        fallo "el puerto ${puerto} esta expuesto y no deberia"
    else
        ok "el puerto ${puerto} no esta expuesto"
    fi
done

seccion "Documentacion de la API"

for ruta in "auth/docs" "sessions/docs" "predict/docs" "auth/openapi.json" "legal/redoc"; do
    if [ "$(codigo "${API}/${ruta}")" = "404" ]; then
        ok "/${ruta} no se sirve al exterior"
    else
        fallo "/${ruta} responde y expone el mapa de la API"
    fi
done

seccion "Cabeceras de seguridad"

CABECERAS=$(curl -s -D- -o /dev/null --max-time 10 "${API}/auth/me")
for cabecera in "x-content-type-options: nosniff" "x-frame-options: DENY" "referrer-policy: no-referrer"; do
    if echo "$CABECERAS" | tr 'A-Z' 'a-z' | grep -qi "${cabecera%%:*}"; then
        ok "viaja ${cabecera%%:*}"
    else
        fallo "falta ${cabecera%%:*}"
    fi
done

if echo "$CABECERAS" | grep -qi "^server:.*nginx/[0-9]"; then
    fallo "la cabecera Server revela la version de nginx"
else
    ok "la cabecera Server no revela version"
fi

seccion "Documentos legales"

LEGAL=$(curl -s --max-time 10 "${API}/legal/documents")
for tipo in terms privacy data_commercial ai_training; do
    if echo "$LEGAL" | grep -q "\"$tipo\""; then
        ok "el documento '${tipo}' esta disponible sin tener cuenta"
    else
        fallo "el documento '${tipo}' no esta disponible"
    fi
done

if curl -s --max-time 10 "${API}/legal/documents/privacy" | grep -q "Ley 29733"; then
    ok "la politica de privacidad trae el texto completo para 'Leer mas'"
else
    fallo "la politica de privacidad no trae el texto completo"
fi

seccion "Registro y consentimiento"

SUFIJO=$(date +%s)$RANDOM
EMAIL_A="verifica.a.${SUFIJO}@uni.pe"
EMAIL_B="verifica.b.${SUFIJO}@uni.pe"
CLAVE="ClaveSegura2026!"

registrar() {
    curl -s --max-time 15 -X POST "${API}/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$1\",\"password\":\"${CLAVE}\",\"full_name\":\"Alumno Verificacion\",\"student_code\":\"$2\",\"semester\":7,\"accept_terms\":true,\"consent_data_commercial\":$3,\"consent_ai_training\":$3}"
}

RESP_A=$(registrar "$EMAIL_A" "V${SUFIJO}A" false)
TOKEN_A=$(echo "$RESP_A" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -n "$TOKEN_A" ]; then
    ok "una cuenta valida se crea y devuelve token"
else
    fallo "no se pudo crear la cuenta: $(echo "$RESP_A" | head -c 200)"
fi

SIN_TERMINOS=$(codigo -X POST "${API}/auth/register" -H "Content-Type: application/json" \
    -d "{\"email\":\"rechaza.${SUFIJO}@uni.pe\",\"password\":\"${CLAVE}\",\"full_name\":\"Sin Terminos\",\"accept_terms\":false}")
if [ "$SIN_TERMINOS" = "422" ]; then
    ok "sin aceptar los terminos no se crea la cuenta"
else
    fallo "se creo una cuenta sin aceptar los terminos (codigo $SIN_TERMINOS)"
fi

DEBIL=$(codigo -X POST "${API}/auth/register" -H "Content-Type: application/json" \
    -d "{\"email\":\"debil.${SUFIJO}@uni.pe\",\"password\":\"12345678\",\"full_name\":\"Clave Debil\",\"accept_terms\":true}")
if [ "$DEBIL" = "422" ]; then
    ok "una contrasena debil se rechaza"
else
    fallo "se acepto una contrasena debil (codigo $DEBIL)"
fi

CONSENTS=$(curl -s --max-time 10 "${API}/auth/me/consents" -H "Authorization: Bearer ${TOKEN_A}")
if [ "$(echo "$CONSENTS" | python -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)" = "4" ]; then
    ok "el alta graba las cuatro decisiones de consentimiento"
else
    fallo "el alta no grabo las cuatro decisiones"
fi

OPCIONAL=$(echo "$CONSENTS" | python -c "
import sys, json
estado = {f['doc_type']: f['granted'] for f in json.load(sys.stdin)}
print('si' if estado.get('ai_training') is False else 'no')" 2>/dev/null)
if [ "$OPCIONAL" = "si" ]; then
    ok "lo opcional queda desmarcado si no se pide"
else
    fallo "lo opcional quedo marcado sin haberlo pedido"
fi

REVOCA=$(codigo -X PUT "${API}/auth/me/consents" -H "Authorization: Bearer ${TOKEN_A}" \
    -H "Content-Type: application/json" -d '{"doc_type":"ai_training","granted":true}')
if [ "$REVOCA" = "200" ]; then
    ok "el consentimiento opcional se puede cambiar despues"
else
    fallo "no se pudo cambiar el consentimiento (codigo $REVOCA)"
fi

seccion "Aislamiento entre alumnos"

RESP_B=$(registrar "$EMAIL_B" "V${SUFIJO}B" false)
TOKEN_B=$(echo "$RESP_B" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

SESION_B=$(curl -s --max-time 10 -X POST "${API}/sessions/" -H "Authorization: Bearer ${TOKEN_B}" \
    | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

if [ -n "$SESION_B" ]; then
    ok "un alumno abre su cuestionario"
else
    fallo "no se pudo abrir el cuestionario"
fi

AJENA=$(codigo "${API}/sessions/${SESION_B}/questions" -H "Authorization: Bearer ${TOKEN_A}")
if [ "$AJENA" = "404" ]; then
    ok "un alumno no alcanza la sesion de otro ni con su id exacto"
else
    fallo "se alcanzo la sesion de otro alumno (codigo $AJENA)"
fi

SIN_TOKEN=$(codigo "${API}/sessions/")
if [ "$SIN_TOKEN" = "401" ]; then
    ok "sin token no se llega a ninguna sesion"
else
    fallo "se llego sin token (codigo $SIN_TOKEN)"
fi

ADMIN=$(codigo "${API}/stats/overview" -H "Authorization: Bearer ${TOKEN_A}")
if [ "$ADMIN" = "403" ]; then
    ok "un alumno no entra al panel de administracion"
else
    fallo "un alumno entro al panel de administracion (codigo $ADMIN)"
fi

DATASET=$(codigo "${API}/stats/export-csv" -H "Authorization: Bearer ${TOKEN_A}")
if [ "$DATASET" = "403" ]; then
    ok "un alumno no descarga el dataset de entrenamiento"
else
    fallo "un alumno pudo tocar el dataset (codigo $DATASET)"
fi

MODELO=$(codigo "${API}/predict/model/importances" -H "Authorization: Bearer ${TOKEN_A}")
if [ "$MODELO" = "403" ]; then
    ok "un alumno no lee los pesos del modelo"
else
    fallo "un alumno leyo los pesos del modelo (codigo $MODELO)"
fi

seccion "Rate limit"

# Se usa una cuenta que no existe: el cupo de login cuenta por credencial,
# asi que esto no gasta el cupo de los alumnos de arriba.
VICTIMA="fuerzabruta.${SUFIJO}@uni.pe"
ULTIMO=""
for _ in $(seq 1 12); do
    ULTIMO=$(codigo -X POST "${API}/auth/login" -H "Content-Type: application/json" \
        -d "{\"email\":\"${VICTIMA}\",\"password\":\"loQueSea1!\"}")
done

if [ "$ULTIMO" = "429" ]; then
    ok "la fuerza bruta contra una cuenta se corta con 429"
else
    fallo "la fuerza bruta no se corto (ultimo codigo $ULTIMO)"
fi

RETRY=$(curl -s -D- -o /dev/null --max-time 10 -X POST "${API}/auth/login" \
    -H "Content-Type: application/json" -d "{\"email\":\"${VICTIMA}\",\"password\":\"x1!\"}" \
    | grep -i "retry-after" | head -1)
if [ -n "$RETRY" ]; then
    ok "el rechazo indica cuanto esperar (${RETRY%%$'\r'*})"
else
    fallo "el rechazo no indica Retry-After"
fi

# El aula: otro alumno con OTRA cuenta debe seguir entrando aunque el
# anterior haya agotado su cupo desde la misma IP.
OTRO=$(codigo -X POST "${API}/auth/login" -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL_A}\",\"password\":\"${CLAVE}\"}")
if [ "$OTRO" = "200" ]; then
    ok "otro alumno de la misma IP sigue entrando (el aula no se cae)"
else
    fallo "el aula se bloqueo por la IP compartida (codigo $OTRO)"
fi

seccion "Errores e inyeccion"

for carga in "' OR '1'='1" "admin@uni.pe'--" "'; DROP TABLE users;--"; do
    RESP=$(curl -s --max-time 10 -X POST "${API}/auth/login" -H "Content-Type: application/json" \
        -d "{\"email\":\"${carga}\",\"password\":\"x\"}")
    if echo "$RESP" | grep -qiE "traceback|psycopg2|sqlalchemy|\.py"; then
        fallo "la carga «${carga}» devolvio detalle interno"
    else
        ok "la carga «${carga}» se trata como texto"
    fi
done

if [ "$(codigo -X POST "${API}/auth/register" -H "Content-Type: application/json" \
        -d "{\"email\":\"tras.inyeccion.${SUFIJO}@uni.pe\",\"password\":\"${CLAVE}\",\"full_name\":\"Sigue Viva\",\"accept_terms\":true}")" = "201" ]; then
    ok "la tabla de usuarios sigue en pie tras los intentos de inyeccion"
else
    fallo "algo se rompio tras los intentos de inyeccion"
fi

# ────────────────────────────────────────────────────────────
printf "\n${GRIS}=============================================${RESET}\n"
printf "  Pasadas: ${VERDE}%s${RESET}   Fallidas: ${ROJO}%s${RESET}\n" "$PASADAS" "$FALLIDAS"
printf "${GRIS}=============================================${RESET}\n"

[ "$FALLIDAS" -eq 0 ]
