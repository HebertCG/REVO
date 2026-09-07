/**
 * Tolerancia al arranque en frio de los servicios.
 *
 * POR QUE EXISTE
 *
 * El plan gratuito de Render duerme un servicio tras 15 minutos sin
 * trafico y tarda entre 30 y 60 segundos en levantarlo. En REVO eso no
 * pasa una vez, sino DOS seguidas: el navegador llama a la pasarela y la
 * pasarela llama al servicio, y despues de un rato quieto las dos estan
 * dormidas. Sumadas pasan del minuto.
 *
 * Nginx ya espera lo suficiente (proxy_read_timeout 90s), pero eso no
 * salva la peticion, porque delante de la pasarela hay un proxy mas: el
 * `rewrite` de Vercel, que corta alrededor de los 30 segundos y devuelve
 * 502. El techo real lo pone el intermediario mas impaciente de toda la
 * cadena, no el que hayamos configurado nosotros.
 *
 * Como ese corte no se puede subir desde aqui, la unica salida es volver
 * a intentarlo: el primer intento no se pierde, despierta al servicio, y
 * para cuando toca el segundo o el tercero ya esta en pie.
 *
 * QUE NO SE REINTENTA
 *
 * Solo los metodos idempotentes. Repetir un POST /auth/register cuando no
 * sabemos si el primero llego a crear la cuenta puede dejar al alumno con
 * un "ese correo ya existe" causado por nosotros mismos. Para esos casos
 * hay un mensaje que explica la espera, no un reintento a ciegas.
 */

// Lo que devuelve un intermediario cuando el servicio de destino todavia
// no esta en pie. El 502 es el de Vercel al agotar su espera; el 503 y el
// 504 los ponen otros escalones de la cadena ante el mismo hecho.
const ESTADOS_DE_ARRANQUE = new Set([502, 503, 504])

// Repetirlos no cambia nada en el servidor, asi que son seguros.
const METODOS_IDEMPOTENTES = new Set(['get', 'head', 'options'])

/** Intentos extra tras el primero. Con la espera de abajo cubre ~2 min. */
export const MAX_REINTENTOS = 3

const ESPERA_BASE_MS = 4000
const ESPERA_MAXIMA_MS = 15000

export const MENSAJE_ARRANQUE =
  'El servidor estaba dormido y esta despertando. Espera unos segundos y vuelve a intentarlo.'

/**
 * Distingue "el servicio esta arrancando" de "el servicio esta roto".
 *
 * El timeout de axios (ECONNABORTED) cuenta como arranque: significa que
 * nadie contesto a tiempo, que es exactamente el sintoma. Un ERR_NETWORK
 * NO cuenta: ese es el alumno sin conexion, y reintentar tres veces solo
 * le hace esperar medio minuto para el mismo resultado.
 */
export function esArranqueEnFrio(error) {
  const estado = error?.response?.status
  if (estado !== undefined) return ESTADOS_DE_ARRANQUE.has(estado)
  return error?.code === 'ECONNABORTED'
}

/**
 * @param {object} error error de axios
 * @param {number} reintentosHechos cuantas veces se repitio ya esta peticion
 */
export function esReintentable(error, reintentosHechos = 0) {
  if (reintentosHechos >= MAX_REINTENTOS) return false
  if (!esArranqueEnFrio(error)) return false

  const metodo = (error?.config?.method || 'get').toLowerCase()
  return METODOS_IDEMPOTENTES.has(metodo)
}

/**
 * Espera creciente antes del siguiente intento: 4s, 8s, 15s.
 *
 * Crece porque cada fallo es una pista de que el arranque va largo, y se
 * detiene en 15s porque por encima de eso el alumno ya penso que la
 * pagina esta rota.
 */
export function esperaAntesDeReintentar(reintentosHechos = 0) {
  const espera = ESPERA_BASE_MS * 2 ** reintentosHechos
  return Math.min(espera, ESPERA_MAXIMA_MS)
}
