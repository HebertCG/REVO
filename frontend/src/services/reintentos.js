/**
 * Reintento de peticiones que fallan por un corte pasajero.
 *
 * QUE SUSTITUYE
 *
 * Este modulo era `arranqueEnFrio.js` y existia por una razon que ya no
 * aplica: el plan gratuito de Render dormia los servicios tras 15 minutos
 * sin trafico y tardaba entre 30 y 60 segundos en levantarlos. Como el
 * proxy de Vercel cortaba a los 30, la unica salida era reintentar, y la
 * pantalla tenia que avisar al alumno de que estaba esperando.
 *
 * Con el despliegue en un VPS los servicios no se duermen. Un 502 ya no
 * significa "espera un minuto": significa que algo pasa. Y mantener la
 * espera larga era peor que quitarla, porque hacia que el alumno aguantara
 * casi treinta segundos antes de ver un error que iba a llegar igual.
 *
 * QUE SE CONSERVA Y POR QUE
 *
 * UN reintento corto. No es herencia del arranque en frio: es que al
 * reiniciar un contenedor o al desplegar una version nueva hay una ventana
 * de uno o dos segundos en la que nginx contesta 502 porque el servicio de
 * detras todavia no acepta conexiones. Fallar ahi le muestra un error a
 * alguien que solo tenia mala suerte de milisegundos.
 *
 * Un intento y 1,2 segundos cubren esa ventana. Si el segundo tambien
 * falla, el problema es real y hay que decirlo ya, no dentro de medio
 * minuto.
 *
 * QUE NO SE REINTENTA
 *
 * Solo los metodos idempotentes. Repetir un POST /auth/register cuando no
 * sabemos si el primero llego a crear la cuenta puede dejar al alumno con
 * un "ese correo ya existe" causado por nosotros mismos.
 */

// Lo que devuelve nginx cuando el servicio de detras no acepta conexiones
// todavia. El 502 es el habitual al reiniciar; el 503 y el 504 aparecen en
// la misma situacion segun donde corte la cadena.
const ESTADOS_PASAJEROS = new Set([502, 503, 504])

// Repetirlos no cambia nada en el servidor, asi que son seguros.
const METODOS_IDEMPOTENTES = new Set(['get', 'head', 'options'])

/** Un solo reintento: cubre un reinicio, no una caida. */
export const MAX_REINTENTOS = 1

/** Suficiente para que un contenedor que acaba de reiniciar acepte la
 *  conexion, y poco para que nadie perciba la espera. */
export const ESPERA_MS = 1200

export const MENSAJE_NO_DISPONIBLE =
  'El servidor no responde ahora mismo. Vuelve a intentarlo en unos segundos.'

/**
 * Distingue un corte pasajero de un fallo del que no se sale reintentando.
 *
 * Un ERR_NETWORK NO cuenta: ese es el usuario sin conexion, y reintentar
 * solo le hace esperar para el mismo resultado.
 */
export function esFalloPasajero(error) {
  const estado = error?.response?.status
  if (estado !== undefined) return ESTADOS_PASAJEROS.has(estado)
  return error?.code === 'ECONNABORTED'
}

/**
 * @param {object} error error de axios
 * @param {number} reintentosHechos cuantas veces se repitio ya esta peticion
 */
export function esReintentable(error, reintentosHechos = 0) {
  if (reintentosHechos >= MAX_REINTENTOS) return false
  if (!esFalloPasajero(error)) return false

  const metodo = (error?.config?.method || 'get').toLowerCase()
  return METODOS_IDEMPOTENTES.has(metodo)
}
