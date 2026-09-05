import { test, expect, RUTAS, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError, reglaSinRed } from './utiles/apiSimulada.js'
import * as datos from './utiles/datos.js'

/**
 * Resistencia a fallos de red.
 *
 * REVO se usa desde los laboratorios de la universidad, con la conexion que
 * hay. Todo lo de aqui va a pasar en produccion: el 429 del limitador, el
 * 500 de un servicio que se reinicia, el token que caduca a mitad del test.
 *
 * Lo que se comprueba en todos los casos es lo mismo: que la pantalla diga
 * algo, y que se pueda seguir. Una pantalla en blanco o un cargador eterno
 * son peores que un error, porque el alumno no sabe si esperar o recargar.
 */

const TODAS_LAS_RUTAS = [...RUTAS.publicas, ...RUTAS.privadas]

/** Ninguna pantalla puede quedarse en blanco pase lo que pase. */
const tieneContenidoVisible = async (page) =>
  page.evaluate(() => (document.body.innerText || '').trim().length > 20)

test.describe('Servicios caidos', () => {
  for (const ruta of RUTAS.privadas) {
    test(`${ruta.nombre} sigue diciendo algo con todo el backend en 500`, async ({ page, vigilante }) => {
      await instalarApiSimulada(page, {
        reglas: [
          // El perfil sigue respondiendo: si no, todo redirige al login y no
          // se llega a probar la pantalla.
          [/\/api\/auth\/me$/, 'GET', (r) => r.fulfill({
            status: 200, contentType: 'application/json', body: JSON.stringify(datos.USUARIO),
          })],
          reglaError(/\/api\//, 'GET', 500, { detail: 'Servicio no disponible' }),
          reglaError(/\/api\//, 'POST', 500, { detail: 'Servicio no disponible' }),
        ],
      })
      await iniciarSesion(page)
      await page.goto(ruta.camino)
      await esperarEstable(page)

      expect(await tieneContenidoVisible(page), `${ruta.nombre} se queda en blanco con el backend caido`).toBe(true)
      expect(vigilante.excepciones, `${ruta.nombre} lanza excepciones con el backend caido`).toEqual([])
    })
  }

  for (const ruta of RUTAS.privadas) {
    test(`${ruta.nombre} sigue diciendo algo sin conexion`, async ({ page, vigilante }) => {
      await instalarApiSimulada(page, {
        reglas: [
          [/\/api\/auth\/me$/, 'GET', (r) => r.fulfill({
            status: 200, contentType: 'application/json', body: JSON.stringify(datos.USUARIO),
          })],
          reglaSinRed(/\/api\//, 'GET'),
          reglaSinRed(/\/api\//, 'POST'),
        ],
      })
      await iniciarSesion(page)
      await page.goto(ruta.camino)
      await esperarEstable(page)

      expect(await tieneContenidoVisible(page), `${ruta.nombre} se queda en blanco sin conexion`).toBe(true)
      expect(vigilante.excepciones).toEqual([])
    })
  }
})

test.describe('Sesion caducada a mitad de uso', () => {
  test('un 401 en cualquier llamada borra el token', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/predict\/user\/\d+\/history$/, 'GET', 401, { detail: 'Token expirado' })],
    })
    await iniciarSesion(page)
    await page.goto('/dashboard')
    await esperarEstable(page)

    const token = await page.evaluate(() => sessionStorage.getItem('revo_token'))
    expect(token, 'un 401 en cualquier ruta tiene que invalidar la sesion local').toBeNull()
  })

  test('tras el 401, la siguiente navegacion pide entrar de nuevo', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/predict\/user\/\d+\/history$/, 'GET', 401, { detail: 'Token expirado' })],
    })
    await iniciarSesion(page)
    await page.goto('/dashboard')
    await esperarEstable(page)

    await page.goto('/history')
    await expect(page).toHaveURL(/\/login$/)
  })
})

test.describe('Limite de peticiones', () => {
  test('el 429 se explica con los segundos que dice el servidor', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(
        /\/api\/auth\/login$/, 'POST', 429,
        { detail: 'Demasiadas peticiones' },
        { 'retry-after': '120' },
      )],
    })
    await page.goto('/login')

    await page.getByRole('textbox', { name: /correo institucional/i }).fill('ana@universidad.edu.pe')
    await page.locator('input[type="password"]').first().fill('contrasena-larga-123')
    await page.locator('form button[type="submit"]').click()

    await expect(page.getByRole('alert')).toContainText('120')
  })

  test('sin cabecera retry-after se usa el valor por defecto y no un NaN', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/auth\/login$/, 'POST', 429, { detail: 'Demasiadas peticiones' })],
    })
    await page.goto('/login')

    await page.getByRole('textbox', { name: /correo institucional/i }).fill('ana@universidad.edu.pe')
    await page.locator('input[type="password"]').first().fill('contrasena-larga-123')
    await page.locator('form button[type="submit"]').click()

    const alerta = page.getByRole('alert')
    await expect(alerta).toContainText('60')
    await expect(alerta).not.toContainText('NaN')
  })
})

test.describe('Respuestas malformadas', () => {
  test('un JSON invalido no tumba la pantalla', async ({ page, vigilante }) => {
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/predict\/user\/\d+\/history$/, 'GET',
        (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{esto no es json' }),
      ]],
    })
    await iniciarSesion(page)
    await page.goto('/dashboard')
    await esperarEstable(page)

    expect(await tieneContenidoVisible(page)).toBe(true)
    expect(vigilante.excepciones).toEqual([])
  })

  test('un array donde se espera un objeto tampoco', async ({ page, vigilante }) => {
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/predict\/\d+$/, 'GET',
        (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
      ]],
    })
    await iniciarSesion(page)
    await page.goto('/results/903')
    await esperarEstable(page)

    expect(await tieneContenidoVisible(page)).toBe(true)
    expect(vigilante.excepciones).toEqual([])
  })

  test('un historial nulo se trata como vacio', async ({ page, vigilante }) => {
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/predict\/user\/\d+\/history$/, 'GET',
        (route) => route.fulfill({ status: 200, contentType: 'application/json', body: 'null' }),
      ]],
    })
    await iniciarSesion(page)
    await page.goto('/dashboard')
    await esperarEstable(page)

    await expect(page.getByRole('heading', { name: /descubre qué rutas/i })).toBeVisible()
    expect(vigilante.excepciones).toEqual([])
  })
})

test.describe('Conexion lenta', () => {
  test('con dos segundos de retardo cada pantalla avisa de que esta cargando', async ({ page }) => {
    await instalarApiSimulada(page, { retardoMs: 2000 })
    await iniciarSesion(page)
    await page.goto('/dashboard')

    // Antes de que llegue nada tiene que haber senal de vida: un hueco mudo
    // hace que el alumno recargue y multiplique la carga del servidor.
    await expect(page.locator('.dash-esqueleto')).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Sin errores de consola en el recorrido feliz', () => {
  test('recorrer todas las pantallas no deja errores en consola', async ({ page, vigilante }) => {
    await instalarApiSimulada(page)
    await iniciarSesion(page)

    for (const ruta of TODAS_LAS_RUTAS) {
      await page.goto(ruta.camino)
      await esperarEstable(page)
    }

    const errores = vigilante.consola.filter((c) => c.tipo === 'error')
    expect(errores, `Errores de consola durante el recorrido:\n${JSON.stringify(errores, null, 2)}`).toEqual([])
    expect(vigilante.excepciones).toEqual([])
  })

  test('ninguna pantalla pide una ruta de API que no existe', async ({ page }) => {
    const { registro } = await instalarApiSimulada(page)
    await iniciarSesion(page)

    for (const ruta of TODAS_LAS_RUTAS) {
      await page.goto(ruta.camino)
      await esperarEstable(page)
    }

    // Una ruta no simulada es o una llamada nueva sin cubrir en la bateria,
    // o una URL que el frontend construye mal.
    expect(
      registro.noReconocidas,
      `Rutas pedidas que no existen en el contrato simulado: ${JSON.stringify(registro.noReconocidas)}`,
    ).toEqual([])
  })
})
