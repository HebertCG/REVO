import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError } from './utiles/apiSimulada.js'
import { elementosDesbordados, detallar } from './utiles/inspector.js'
import { graficos } from './utiles/localizadores.js'
import * as datos from './utiles/datos.js'

/**
 * Historial y su grafico.
 *
 * El grafico lo dibuja recharts dentro de un `ResponsiveContainer`, que mide
 * su contenedor despues del primer pintado. Es el sitio clasico donde una
 * altura de 0 deja el grafico invisible sin que nadie lance un error: por eso
 * se comprueban las dimensiones reales del SVG y no solo que exista.
 */

const abrirHistorial = async (page, opciones = {}) => {
  await instalarApiSimulada(page, opciones)
  await iniciarSesion(page)
  await page.goto('/history')
  await esperarEstable(page)
}

test.describe('Contenido', () => {
  test('lista una entrada por evaluacion', async ({ page }) => {
    await abrirHistorial(page)
    await expect(page.locator('.hist-list > li')).toHaveCount(datos.HISTORIAL.length)
  })

  test('lee el patron correcto cuando las dos ultimas coinciden', async ({ page }) => {
    // Las dos primeras del historial base son "Data Science & IA", la tercera no.
    await abrirHistorial(page)
    await expect(page.getByText('Perfil emergente')).toBeVisible()
  })

  test('reconoce un perfil consolidado con tres evaluaciones iguales', async ({ page }) => {
    const consolidado = datos.HISTORIAL.map((h) => ({ ...h, specialization: 'Ciberseguridad' }))
    await abrirHistorial(page, { historial: consolidado })
    await expect(page.getByText('Perfil consolidado')).toBeVisible()
  })

  test('con una sola evaluacion habla de punto de partida', async ({ page }) => {
    await abrirHistorial(page, { historial: [datos.HISTORIAL[0]] })
    await expect(page.getByText('Primera señal registrada')).toBeVisible()
  })
})

test.describe('Grafico de trayectoria', () => {
  test('el grafico se dibuja con tamano real', async ({ page }) => {
    await abrirHistorial(page)

    const svg = graficos(page, '.hist-chart').first()
    await expect(svg).toBeVisible()

    const caja = await svg.boundingBox()
    expect(caja, 'el SVG del grafico deberia existir').not.toBeNull()
    expect(caja.width, 'un ResponsiveContainer con ancho 0 deja el grafico invisible').toBeGreaterThan(100)
    expect(caja.height, 'un ResponsiveContainer con alto 0 deja el grafico invisible').toBeGreaterThan(50)
  })

  test('el grafico dibuja un punto por evaluacion', async ({ page }) => {
    await abrirHistorial(page)
    const area = page.locator('.hist-chart svg path.recharts-area-area')
    await expect(area).toHaveCount(1)
  })

  test('el grafico no se sale del contenedor en movil', async ({ page }) => {
    await instalarApiSimulada(page)
    await iniciarSesion(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/history')
    await esperarEstable(page)

    const desbordes = await elementosDesbordados(page, 2)
    expect(desbordes, detallar('El historial se sale de la ventana en movil', desbordes)).toEqual([])
  })

  test('con una sola evaluacion el grafico no se rompe', async ({ page, vigilante }) => {
    await abrirHistorial(page, { historial: [datos.HISTORIAL[0]] })
    sinErroresDeEjecucion(vigilante)
  })
})

test.describe('Estado vacio y fallos', () => {
  test('sin evaluaciones no se pinta un grafico de la nada', async ({ page, vigilante }) => {
    await abrirHistorial(page, { historial: [] })

    await expect(page.locator('.hist-list > li')).toHaveCount(0)
    sinErroresDeEjecucion(vigilante)
  })

  test('si el servicio falla se cae al estado vacio sin excepciones', async ({ page, vigilante }) => {
    await abrirHistorial(page, {
      reglas: [reglaError(/\/api\/predict\/user\/\d+\/history$/, 'GET', 503, { detail: 'No disponible' })],
    })

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(vigilante.excepciones).toEqual([])
  })

  test('una confianza no numerica no propaga un NaN a la pantalla', async ({ page }) => {
    await abrirHistorial(page, {
      historial: [{ ...datos.HISTORIAL[0], confidence_pct: null }],
    })

    // `buildHistorySummary` convierte a 0 con `Number(...) || 0` justo para
    // esto. Si alguna vez se quita, aparece "NaN%" en la portada del historial.
    await expect(page.getByText('NaN')).toHaveCount(0)
  })
})

test.describe('Higiene', () => {
  test('el historial se pinta sin errores de ejecucion', async ({ page, vigilante }) => {
    await abrirHistorial(page)
    sinErroresDeEjecucion(vigilante)
  })
})
