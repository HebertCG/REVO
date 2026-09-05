import { test } from '@playwright/test'
import { instalarApiSimulada, iniciarSesion } from './utiles/apiSimulada.js'
import { esperarEstable } from './utiles/fixtures.js'

/**
 * Carga sintetica del frontend.
 *
 * Playwright no sustituye a k6 para medir la capacidad del backend. Esta
 * bateria comprueba que seis clientes, con pantallas distintas, pueden
 * renderizar a la vez las vistas mas pesadas. La API va simulada para aislar
 * el coste y la estabilidad del frontend.
 */

const VISTAS = [
  { width: 320, height: 640, nombre: 'movil minimo' },
  { width: 375, height: 812, nombre: 'movil comun' },
  { width: 768, height: 1024, nombre: 'tableta' },
  { width: 1366, height: 768, nombre: 'portatil' },
  { width: 1440, height: 900, nombre: 'escritorio' },
  { width: 1920, height: 1080, nombre: 'monitor grande' },
]

const RUTAS = [
  { camino: '/dashboard', raiz: '.dash-heroe' },
  { camino: '/history', raiz: '.hist-hero' },
  { camino: '/results/903', raiz: '.result-hero' },
]

test.describe('Carga concurrente', () => {
  test.describe.configure({ mode: 'parallel' })

  for (const vista of VISTAS) {
    test(`un cliente ${vista.nombre} completa las vistas principales`, async ({ page }) => {
      await page.setViewportSize({ width: vista.width, height: vista.height })
      await instalarApiSimulada(page)
      await iniciarSesion(page)

      for (const ruta of RUTAS) {
        await page.goto(ruta.camino, { waitUntil: 'domcontentloaded' })
        await page.locator(ruta.raiz).first().waitFor({ state: 'visible', timeout: 10_000 })
        await esperarEstable(page)
      }
    })
  }
})
