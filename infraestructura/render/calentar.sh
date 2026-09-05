#!/usr/bin/env bash
# ============================================================================
#  Despertar los cuatro servicios antes de usarlos
# ============================================================================
#
#      bash infraestructura/render/calentar.sh https://revo-pasarela.onrender.com
#
#  PARA QUE
#      Render duerme los servicios del plan gratuito a los 15 minutos sin
#      trafico y tarda entre 30 y 60 segundos en levantar cada uno. La primera
#      persona que entra se come esa espera, y si es en una sustentacion
#      parece que el sistema esta roto.
#
#      Esto la paga por adelantado: lanzalo diez minutos antes y entra a la
#      sala sabiendo que los cuatro estan en pie.
#
#  COMO SABE QUE ESTAN DESPIERTOS
#      No mira si la respuesta es correcta, solo si HAY respuesta. Un 401 de
#      auth-service significa "estoy vivo y me falta tu credencial", que es
#      justo lo que queremos comprobar. Lo que delata a un servicio dormido es
#      un 502, un 504 o que no conteste.
#
#      /health lo responde la propia pasarela sin consultar a nadie, asi que
#      no sirve para saber si los backends estan levantados. Por eso se toca
#      una ruta de cada uno.
# ============================================================================
set -uo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
    echo "Uso: bash $0 https://revo-pasarela.onrender.com" >&2
    exit 1
fi
URL="${URL%/}"

# Una ruta por servicio. Que pidan sesion da igual: responder ya prueba que
# el servicio esta en pie.
RUTAS=(
    "pasarela|/health"
    "auth|/api/auth/me"
    "survey|/api/questions/"
    "ml|/api/courses/"
)

# Un servicio recien despierto responde en menos de esto. Por encima, sigue
# arrancando o la base de datos esta fria.
UMBRAL_RAPIDO="${UMBRAL_RAPIDO:-3}"
VUELTAS="${VUELTAS:-6}"

echo "Pasarela: $URL"
echo

for ((vuelta = 1; vuelta <= VUELTAS; vuelta++)); do
    echo "── Vuelta $vuelta ────────────────────────────────"
    todos_listos=1

    for entrada in "${RUTAS[@]}"; do
        nombre="${entrada%%|*}"
        ruta="${entrada#*|}"

        # --max-time 120: por encima del arranque en frio mas lento, para no
        # cortar justo cuando el servicio estaba a punto de contestar.
        salida=$(curl -s -o /dev/null -w '%{http_code} %{time_total}' \
                 --max-time 120 "$URL$ruta" 2>/dev/null || echo "000 0")
        codigo="${salida%% *}"
        segundos="${salida##* }"

        if [[ "$codigo" == "000" ]]; then
            printf '  %-9s sin respuesta (%ss)\n' "$nombre" "$segundos"
            todos_listos=0
        elif [[ "$codigo" == "502" || "$codigo" == "503" || "$codigo" == "504" ]]; then
            printf '  %-9s HTTP %s — todavia arrancando (%ss)\n' "$nombre" "$codigo" "$segundos"
            todos_listos=0
        else
            # awk porque bash no compara decimales.
            rapido=$(awk -v s="$segundos" -v u="$UMBRAL_RAPIDO" 'BEGIN{print (s<u)?1:0}')
            if [[ "$rapido" == "1" ]]; then
                printf '  %-9s HTTP %s en %ss — despierto\n' "$nombre" "$codigo" "$segundos"
            else
                printf '  %-9s HTTP %s en %ss — responde, pero lento aun\n' "$nombre" "$codigo" "$segundos"
                todos_listos=0
            fi
        fi
    done

    if [[ "$todos_listos" == "1" ]]; then
        echo
        echo "════════════════════════════════════════════════"
        echo "  Los cuatro responden rapido. Puedes empezar."
        echo
        echo "  Se vuelven a dormir tras 15 minutos sin trafico."
        echo "════════════════════════════════════════════════"
        exit 0
    fi

    echo
done

cat <<FIN
════════════════════════════════════════════════
  Alguno sigue sin responder bien tras $VUELTAS vueltas.

  Si es 'sin respuesta' o 502/504 de forma insistente, no es
  el arranque en frio: mira los logs de ese servicio en Render.
  Lo mas comun es DATABASE_URL mal puesta.

  Si solo es lento, dale otra vuelta:
      bash $0 $URL
════════════════════════════════════════════════
FIN
exit 1
