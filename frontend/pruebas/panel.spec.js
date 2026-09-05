import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError, reglaSinRed } from './utiles/apiSimulada.js'
import * as datos from './utiles/datos.js'

/**
 * Panel del alumno.
 *
 * El panel tiene tres estados que se ven distintos y se rompen distinto:
 * cargando, sin ninguna evaluacion, y con historial. Probar solo el tercero
 * deja sin cubrir la primera pantalla que ve una cuenta recien creada.
 */

const abrirPanel = async (page, opciones = {}) => {
  await instalarApiSimulada(page, opciones)
  await iniciarSesion(page)
  await page.goto('/dashboard')
}

test.describe('Estado vacio', () => {
  test('una cuenta sin evaluaciones ve la invitacion a empezar', async ({ page }) => {
    await abrirPanel(page, { historial: [] })

    await expect(page.getByRole('heading', { name: /descubre qué rutas/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /empezar el test/i })).toBeVisible()
    // Sin datos no puede haber metricas: un 0% o un NaN a la vista es peor
    // que no ensenar nada.
    await expect(page.getByText('REVO Score')).toHaveCount(0)
  })

  test('el boton de empezar lleva al cuestionario', async ({ page }) => {
    await abrirPanel(page, { historial: [] })
    await page.getByRole('link', { name: /empezar el test/i }).click()
    await expect(page).toHaveURL(/\/questionnaire$/)
  })
})

test.describe('Con historial', () => {
  test('muestra la ultima especializacion y su confianza', async ({ page }) => {
    await abrirPanel(page)

    await expect(page.getByRole('heading', { name: /lo que más encaja contigo hoy/i })).toBeVisible()
    await expect(page.getByText(datos.HISTORIAL[0].specialization).first()).toBeVisible()
    await expect(page.getByText('87.4', { exact: true })).toBeVisible()
  })

  test('la barra de compatibilidad anuncia su valor a un lector de pantalla', async ({ page }) => {
    await abrirPanel(page)

    const barra = page.getByRole('progressbar', { name: /compatibilidad/i })
    await expect(barra).toHaveAttribute('aria-valuenow', String(datos.HISTORIAL[0].confidence_pct))
    await expect(barra).toHaveAttribute('aria-valuemax', '100')
  })

  test('las metricas cuadran con los datos recibidos', async ({ page }) => {
    await abrirPanel(page)

    // 3 evaluaciones; media de 87.4, 81.2 y 72.9 redondeada = 81.
    await expect(page.locator('.dash-metricas').getByText('3', { exact: true })).toBeVisible()
    await expect(page.locator('.dash-metricas').getByText('81')).toBeVisible()
  })

  test('cada fila reciente enlaza a su propio resultado', async ({ page }) => {
    await abrirPanel(page)

    const filas = page.locator('.dash-lista li a')
    await expect(filas).toHaveCount(datos.HISTORIAL.length)

    await filas.first().click()
    await expect(page).toHaveURL(new RegExp(`/results/${datos.HISTORIAL[0].prediction_id}$`))
  })

  test('con mas de cuatro evaluaciones aparece el enlace al historial completo', async ({ page }) => {
    await abrirPanel(page, { historial: datos.HISTORIAL_LARGO })

    await expect(page.getByRole('link', { name: /ver las 7 evaluaciones/i })).toBeVisible()
    // La lista corta sigue siendo corta: si crece, el panel deja de ser resumen.
    await expect(page.locator('.dash-lista li')).toHaveCount(4)
  })

  test('no se repiten claves de React al pintar la lista', async ({ page, vigilante }) => {
    await abrirPanel(page, { historial: datos.HISTORIAL_LARGO })
    await esperarEstable(page)
    sinErroresDeEjecucion(vigilante)
  })
})

test.describe('Cuando el servicio falla', () => {
  test('si el historial no carga se ensena el estado vacio, no una pantalla rota', async ({ page }) => {
    await abrirPanel(page, {
      reglas: [reglaError(/\/api\/predict\/user\/\d+\/history$/, 'GET', 500, { detail: 'Servicio caido' })],
    })

    await expect(page.getByRole('heading', { name: /descubre qué rutas/i })).toBeVisible()
  })

  test('sin conexion el panel tampoco se queda cargando para siempre', async ({ page }) => {
    await abrirPanel(page, {
      reglas: [reglaSinRed(/\/api\/predict\/user\/\d+\/history$/, 'GET')],
    })

    await expect(page.getByRole('heading', { name: /descubre qué rutas/i })).toBeVisible()
    await expect(page.locator('.dash-esqueleto')).toHaveCount(0)
  })

  test('un historial con campos ausentes no rompe el pintado', async ({ page }) => {
    // Los datos reales llegan de una base que puede tener huecos. Un
    // `specialization` vacio o un `created_at` nulo no puede tumbar la vista.
    await abrirPanel(page, {
      historial: [
        { prediction_id: 1, session_id: 1, specialization: '', icon: '', color: '', confidence_pct: 0, created_at: null },
      ],
    })

    await expect(page.locator('.dash-heroe')).toBeVisible()
  })
})

test.describe('Estado de carga', () => {
  test('mientras llega el historial se ve el esqueleto y no un hueco', async ({ page }) => {
    await instalarApiSimulada(page, { retardoMs: 700 })
    await iniciarSesion(page)
    await page.goto('/dashboard')

    await expect(page.locator('.dash-esqueleto')).toBeVisible()
    await expect(page.locator('.dash-esqueleto')).toBeHidden({ timeout: 10_000 })
  })
})

test.describe('Higiene', () => {
  test('el panel se pinta sin errores de ejecucion', async ({ page, vigilante }) => {
    await abrirPanel(page)
    await esperarEstable(page)
    sinErroresDeEjecucion(vigilante)
  })
})
