#!/usr/bin/env bash
# ============================================================================
#  ¿Se puede burlar el limite de peticiones con una cabecera?
# ============================================================================
#
#      bash infraestructura/render/verificar_proxies.sh https://revo-pasarela.onrender.com
#
#  QUE COMPRUEBA
#      El servicio decide quien eres contando TRUSTED_PROXY_COUNT saltos desde
#      la derecha de X-Forwarded-For. Si ese numero es mayor que el numero real
#      de proxies, la posicion elegida cae en territorio que escribe el cliente:
#      basta mandar un X-Forwarded-For distinto en cada intento para estrenar
#      cupo, y la defensa del login contra rociado de credenciales desaparece.
#
#      No hay error, no hay log, no hay nada raro en el panel. Por eso se mide.
#
#  COMO
#      Manda peticiones de login con credenciales falsas, cada una con un
#      X-Forwarded-For inventado distinto y un email distinto.
#
#      - Si el sistema IGNORA la cabecera, todas cuentan contra tu IP real y
#        acaba respondiendo 429. Es lo que queremos.
#      - Si la cabecera MANDA, cada peticion estrena cupo y nunca sale 429.
#
#      El email cambia en cada intento a proposito: asi el cupo por credencial
#      (8 intentos por cuenta) no salta antes y enmascara el resultado.
#
#  EFECTO SECUNDARIO — LEELO
#      Si el resultado es el bueno, al terminar habras agotado el cupo de login
#      de TU IP: 400 intentos por hora. No podras iniciar sesion desde esta red
#      hasta que pase la ventana. Ejecutalo despues de desplegar, nunca justo
#      antes de una demostracion.
#
#      No crea cuentas ni modifica datos: son intentos de login fallidos.
# ============================================================================
set -uo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
    echo "Uso: bash $0 https://revo-pasarela.onrender.com" >&2
    exit 1
fi
URL="${URL%/}"

# El cupo por IP del login: 400 en 3600 s (services/auth-service/politicas.py).
# Se manda un poco por encima para cruzar el umbral con margen.
INTENTOS="${INTENTOS:-410}"

# Nginx limita /api/auth/login a 5 r/s. Se va por debajo para que el 429 que
# salga venga del servicio y no de la pasarela: son cosas distintas y aqui
# solo interesa la del servicio.
PAUSA="${PAUSA:-0.25}"

echo "Pasarela : $URL"
echo "Intentos : $INTENTOS"
echo

# ── La pasarela responde ────────────────────────────────────────────────────
codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time 120 "$URL/health" || echo "000")
if [[ "$codigo" != "200" ]]; then
    echo "ERROR: $URL/health devolvio $codigo (se esperaba 200)." >&2
    echo "       Si es 000, la pasarela no responde o tardo mas de 120 s." >&2
    exit 1
fi
echo "✓ La pasarela responde"
echo

# ── La prueba ───────────────────────────────────────────────────────────────
intentar() {
    # $1 X-Forwarded-For inventado   $2 email
    # Imprime "<codigo> <1|0 si trae cabeceras de rate limit del servicio>"
    local cabeceras
    cabeceras=$(curl -s -o /dev/null -D - --max-time 60 \
        -X POST "$URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -H "X-Forwarded-For: $1" \
        -d "{\"email\":\"$2\",\"password\":\"credencial-que-no-existe\"}" 2>/dev/null)

    local cod tiene
    cod=$(printf '%s' "$cabeceras" | head -1 | awk '{print $2}')
    # El 429 del servicio trae X-RateLimit-Limit; el de nginx no. Distinguirlos
    # importa: el de nginx no dice nada sobre TRUSTED_PROXY_COUNT.
    tiene=$(printf '%s' "$cabeceras" | grep -ci '^x-ratelimit-limit' 2>/dev/null || true)
    printf '%s %s' "${cod:-000}" "${tiene:-0}"
}

echo "Mandando $INTENTOS intentos, cada uno con una IP falsa distinta..."
echo "(unos $(( INTENTOS / 4 )) segundos; si sale 429 antes, para ahi)"
echo

corte=0
corte_del_servicio=0
for ((i = 1; i <= INTENTOS; i++)); do
    falsa="198.51.100.$(( i % 254 + 1 ))"          # rango reservado para documentacion
    read -r cod tiene <<<"$(intentar "$falsa" "inexistente-$i@ejemplo.invalid")"

    if [[ "$cod" == "429" ]]; then
        corte=$i
        corte_del_servicio=$tiene
        break
    fi

    if (( i % 50 == 0 )); then
        echo "  $i intentos, ultimo codigo $cod"
    fi
    sleep "$PAUSA"
done

echo
echo "════════════════════════════════════════════════════════════════════"

if (( corte > 0 )) && (( corte_del_servicio > 0 )); then
    cat <<FIN
  CORRECTO

  Cortó en el intento $corte con un 429 del servicio, pese a que cada
  peticion venia con una IP falsa distinta. La cabecera se esta
  ignorando: TRUSTED_PROXY_COUNT vale lo que tiene que valer.

  Tu IP tiene el cupo de login agotado durante la ventana de una hora.
FIN
    exit 0
fi

if (( corte > 0 )); then
    cat <<FIN
  NO CONCLUYENTE

  Cortó en el intento $corte, pero el 429 no traia cabeceras
  X-RateLimit-*, asi que lo puso nginx (5 r/s) y no el servicio. Eso no
  dice nada sobre TRUSTED_PROXY_COUNT.

  Vuelve a lanzarlo mas despacio:
      PAUSA=0.5 bash $0 $URL
FIN
    exit 2
fi

cat <<FIN
  MAL — la proteccion del login no esta funcionando

  $INTENTOS intentos y ningun 429. Cada IP falsa estreno su propio cupo,
  o sea que el servicio esta creyendose la cabecera X-Forwarded-For que
  manda el cliente. Con eso, un atacante prueba contrasenas sin limite:
  cambia la cabecera en cada intento y nunca topa con nada.

  QUE HACER
    1. Baja TRUSTED_PROXY_COUNT en uno. Esta en render.yaml, una vez por
       cada uno de los tres servicios (auth, survey, ml).
    2. Vuelve a desplegar los tres en Render.
    3. Repite esta comprobacion. Si sigue igual, baja otro punto.

  El valor correcto es el numero real de proxies delante del servicio.
  Pasarse hacia arriba abre este agujero; quedarse corto hace que todos
  los alumnos compartan cupo y reciban 429 sin motivo.
FIN
exit 1
