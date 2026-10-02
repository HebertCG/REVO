/**
 * resultadoConfianza.js — Lo que el modelo dice sobre su propia respuesta,
 * listo para pintar.
 *
 * Dos piezas que ml-service ya calculaba y la pantalla nunca mostraba:
 *
 *   aviso de cautela     cuando el perfil del alumno se parece poco a los que
 *                        el sistema conoce. El porcentaje sigue ahi, pero no
 *                        significa lo mismo, y el alumno tiene que saberlo.
 *   ocupaciones afines   ocupaciones reales de O*NET con un perfil de
 *                        intereses (RIASEC) parecido al que el modelo le
 *                        atribuye. Salen de pgvector.
 *
 * Logica pura, sin React: se prueba con `node --test` como historyInsights.
 * Los datos vienen de la API, asi que se validan aqui: con el codigo SOC se
 * construye un enlace, y un enlace no se construye con lo que llegue.
 */

export const MAXIMO_OCUPACIONES = 5

// Formato de O*NET-SOC: 15-1212.00. Solo con esta forma se arma el enlace.
const CODIGO_SOC = /^\d{2}-\d{4}\.\d{2}$/

const ONET_RESUMEN = 'https://www.onetonline.org/link/summary/'

/**
 * Mensaje de cautela, o null si no hace falta.
 *
 * Las predicciones anteriores a la migracion 38 no traen `presentacion` y
 * salen sin aviso: no se inventa una duda que en su momento no se midio.
 *
 * @param {object} data respuesta de GET /predict/{id}
 * @returns {{ mensaje: string, explicacion: string | null } | null}
 */
export function avisoDeCautela(data) {
  const presentacion = data?.presentacion
  if (presentacion?.cautela !== true || typeof presentacion.mensaje !== 'string') {
    return null
  }
  const explicacion = data?.incertidumbre?.explicacion
  return {
    mensaje: presentacion.mensaje,
    explicacion: typeof explicacion === 'string' ? explicacion : null,
  }
}

/**
 * Etiqueta cualitativa del parecido entre dos perfiles.
 *
 * NO se muestra como porcentaje a proposito: una correlacion de 0,98 no es
 * "98 % de coincidencia", y junto al "72 % de compatibilidad" del resultado
 * el alumno leeria las dos cifras como si midieran lo mismo.
 *
 * @param {number} correlacion Pearson entre perfiles RIASEC, -1..1
 * @returns {string | null}
 */
export function etiquetaDeParecido(correlacion) {
  if (!Number.isFinite(correlacion)) return null
  if (correlacion >= 0.9) return 'Muy parecido'
  if (correlacion >= 0.75) return 'Parecido'
  return 'Algo parecido'
}

/**
 * Ocupaciones afines, validadas y recortadas para la pantalla.
 *
 * @param {object} data respuesta de GET /predict/{id}
 * @param {number} [maximo]
 * @returns {{ codigo: string, titulo: string, parecido: string, enlace: string }[]}
 */
export function ocupacionesAfines(data, maximo = MAXIMO_OCUPACIONES) {
  const lista = Array.isArray(data?.ocupaciones_afines) ? data.ocupaciones_afines : []

  return lista
    .filter((o) =>
      typeof o?.codigo_soc === 'string' && CODIGO_SOC.test(o.codigo_soc) &&
      typeof o.titulo === 'string' && o.titulo.trim() !== '' &&
      etiquetaDeParecido(o.correlacion) !== null)
    .slice(0, maximo)
    .map((o) => ({
      codigo: o.codigo_soc,
      titulo: o.titulo.trim(),
      parecido: etiquetaDeParecido(o.correlacion),
      enlace: `${ONET_RESUMEN}${o.codigo_soc}`,
    }))
}
