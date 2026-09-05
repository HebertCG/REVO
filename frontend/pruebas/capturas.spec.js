import { test, expect, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError } from './utiles/apiSimulada.js'
import * as datos from './utiles/datos.js'
import { forzarMinijuego } from './utiles/cuestionario.js'
import { MINI_GAMES } from '../src/pages/questionnaireMiniGames.js'

/**
 * Capturas de revision visual.
 *
 * No afirma nada: sirve para mirar el estado de las pantallas sin levantar
 * los tres microservicios. Se ejecuta a mano con
 * `npx playwright test capturas --project=escritorio`.
 */
const CARPETA = 'pruebas/.capturas'

test.describe('Capturas', () => {
  test('pantallas publicas y privadas', async ({ page }) => {
    test.slow()
    await instalarApiSimulada(page)

    await page.goto('/')
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/01-portada.png`, fullPage: true })

    await page.goto('/login')
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/02-acceso.png` })

    await iniciarSesion(page)

    // `esperarEstable` mira si el DOM deja de crecer, y el hueco de carga de
    // una ruta diferida es estatico: hay que esperar al contenido de verdad.
    await page.goto('/dashboard')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 })
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/03-panel.png`, fullPage: true })

    await page.goto('/history')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 })
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/04-historial.png`, fullPage: true })

    await page.goto('/results/903')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 })
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/05-resultado.png`, fullPage: true })
  })

  test('laboratorio del modelo', async ({ page }) => {
    await instalarApiSimulada(page, { usuario: datos.ADMIN })
    await iniciarSesion(page)
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: /laboratorio científico/i })).toBeVisible({ timeout: 15_000 })
    await esperarEstable(page)
    await page.screenshot({ path: `${CARPETA}/06-laboratorio.png`, fullPage: true })
  })

  test('cuestionario cuando la partida no se puede preparar', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/sessions\/?$/, 'POST', 500, { detail: 'Servicio caido' })],
    })
    await iniciarSesion(page)
    await forzarMinijuego(page, MINI_GAMES.CARDS)
    await page.goto('/questionnaire')

    await expect(page.getByText(/no pudimos repartir las cartas/i)).toBeVisible({ timeout: 20_000 })
    await page.screenshot({ path: `${CARPETA}/07-cuestionario-error.png` })
  })
})
