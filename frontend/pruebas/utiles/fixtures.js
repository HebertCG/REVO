import { test as base, expect } from '@playwright/test'
import { instalarApiSimulada, iniciarSesion } from './apiSimulada.js'
import * as datos from './datos.js'

/**
 * Fixtures compartidos.
 *
 * `vigilante` engancha la consola y la red de CADA prueba. No afirma nada por
 * si mismo: es la prueba la que decide si un error de consola invalida el
 * caso. Recolectar siempre y decidir despues evita el patron de tener una
 * unica prueba "sin errores de consola" que se cae por culpa de otra pagina
 * y no dice donde.
 *
 * Se filtran los mensajes de infraestructura de Vite (recarga en caliente) y
 * los avisos de descarga de fuentes: no son fallos de la aplicacion y
 * convierten el vigilante en ruido que se acaba ignorando.
 */

const RUIDO_CONOCIDO = [
  /\[vite\]/i,
  /Download the React DevTools/i,
  /favicon/i,
  /fonts\.(googleapis|gstatic)\.com/i,
]

const esRuido = (texto) => RUIDO_CONOCIDO.some((patron) => patron.test(texto))

export const test = base.extend({
  /**
   * Movimiento reducido en todas las pruebas.
   *
   * La opcion `reducedMotion` del fichero de configuracion no llega a la
   * pagina con esta version de Playwright (se comprobo consultando
   * `matchMedia` desde el navegador: devolvia false). Se emula a mano, que
   * si funciona.
   *
   * Importa mas de lo que parece: el cuestionario tiene temporizadores de
   * 3,2 s que bajan a 350 ms con la preferencia activa. Sin ella una partida
   * completa no cabe en el tiempo limite de una prueba.
   */
  movimientoReducido: [async ({ page }, use) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await use(true)
  }, { auto: true }],

  /** Recolector de errores de consola, excepciones y peticiones fallidas. */
  vigilante: async ({ page }, use) => {
    const registro = { consola: [], excepciones: [], peticionesFallidas: [], respuestasError: [] }

    page.on('console', (msg) => {
      if (msg.type() !== 'error' && msg.type() !== 'warning') return
      const texto = msg.text()
      if (esRuido(texto)) return
      registro.consola.push({ tipo: msg.type(), texto, url: page.url() })
    })

    page.on('pageerror', (err) => {
      registro.excepciones.push({ mensaje: err.message, pila: (err.stack || '').split('\n').slice(0, 4).join('\n') })
    })

    page.on('requestfailed', (req) => {
      const url = req.url()
      if (esRuido(url)) return
      registro.peticionesFallidas.push({ url, error: req.failure()?.errorText })
    })

    page.on('response', (res) => {
      if (res.status() < 400) return
      if (esRuido(res.url())) return
      registro.respuestasError.push({ url: res.url(), estado: res.status() })
    })

    await use(registro)
  },

  /** Pagina con la API simulada instalada y sin sesion iniciada. */
  paginaPublica: async ({ page }, use) => {
    const simulada = await instalarApiSimulada(page)
    await use({ page, ...simulada })
  },

  /** Pagina con sesion de alumno ya iniciada. */
  paginaAlumno: async ({ page }, use) => {
    const simulada = await instalarApiSimulada(page)
    await iniciarSesion(page)
    await use({ page, ...simulada })
  },

  /** Pagina con sesion de administrador. */
  paginaAdmin: async ({ page }, use) => {
    const simulada = await instalarApiSimulada(page, { usuario: datos.ADMIN })
    await iniciarSesion(page)
    await use({ page, ...simulada })
  },
})

export { expect }

/**
 * Afirma que no hubo errores graves de ejecucion.
 *
 * Las excepciones no capturadas y los avisos de React sobre claves o
 * atributos invalidos se tratan igual: los dos indican que el arbol se esta
 * pintando con datos que el codigo no esperaba.
 */
export function sinErroresDeEjecucion(vigilante, { permitir = [] } = {}) {
  const permitido = (texto) => permitir.some((patron) => patron.test(texto))

  const excepciones = vigilante.excepciones.filter((e) => !permitido(e.mensaje))
  const erroresConsola = vigilante.consola.filter((c) => c.tipo === 'error' && !permitido(c.texto))

  expect(excepciones, `Excepciones no capturadas:\n${JSON.stringify(excepciones, null, 2)}`).toEqual([])
  expect(erroresConsola, `Errores de consola:\n${JSON.stringify(erroresConsola, null, 2)}`).toEqual([])
}

/** Rutas publicas y privadas que recorren las baterias transversales. */
export const RUTAS = {
  publicas: [
    { camino: '/', nombre: 'portada' },
    { camino: '/login', nombre: 'inicio de sesion' },
    { camino: '/register', nombre: 'registro' },
  ],
  privadas: [
    { camino: '/dashboard', nombre: 'panel' },
    { camino: '/history', nombre: 'historial' },
    { camino: '/results/903', nombre: 'resultado' },
  ],
}

/** Anchos donde el diseno de REVO cambia de forma. */
export const ANCHOS = [
  { ancho: 320, alto: 640, nombre: 'movil minimo' },
  { ancho: 360, alto: 800, nombre: 'movil compacto' },
  { ancho: 375, alto: 812, nombre: 'movil comun' },
  { ancho: 414, alto: 896, nombre: 'movil grande' },
  { ancho: 768, alto: 1024, nombre: 'tableta vertical' },
  { ancho: 1024, alto: 768, nombre: 'tableta horizontal' },
  { ancho: 1280, alto: 800, nombre: 'portatil' },
  { ancho: 1366, alto: 768, nombre: 'portatil comun' },
  { ancho: 1440, alto: 900, nombre: 'escritorio' },
  { ancho: 1920, alto: 1080, nombre: 'monitor grande' },
]

/**
 * Espera a que la pagina se estabilice.
 *
 * `networkidle` no sirve aqui: la aplicacion tiene animaciones con
 * temporizadores y graficos de recharts que miden el contenedor tras el
 * primer pintado. Se espera a que el DOM deje de crecer.
 *
 * Antes de eso hay que dejar atras el hueco de carga de las rutas
 * diferidas. Ese hueco es un DOM pequeno y COMPLETAMENTE ESTATICO, asi que
 * el criterio de "ha dejado de crecer" se cumple de inmediato y las sondas
 * acababan midiendo el cargador en vez de la pantalla: paginas sin h1, pies
 * sin enlaces y textos recortados que no existian en la vista real.
 */
export async function esperarEstable(page, { intentos = 20, pausaMs = 100 } = {}) {
  await page.waitForFunction(
    () => !document.querySelector('[data-cargando-ruta]'),
    null,
    { timeout: 20_000 },
  ).catch(() => {})

  let previo = -1
  for (let i = 0; i < intentos; i++) {
    const actual = await page.evaluate(() => document.body.innerHTML.length)
    if (actual === previo) return
    previo = actual
    await page.waitForTimeout(pausaMs)
  }
}
