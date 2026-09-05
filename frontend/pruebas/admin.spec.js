import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError } from './utiles/apiSimulada.js'
import { elementosDesbordados, detallar } from './utiles/inspector.js'
import { graficos } from './utiles/localizadores.js'
import * as datos from './utiles/datos.js'

/**
 * Laboratorio de administracion.
 *
 * Aqui se ensenan los pesos del modelo y se descarga el dataset completo: es
 * la pantalla con mas que perder si el control de acceso falla. Ademas
 * refresca sola cada cinco segundos, asi que un fallo de red no se ve una
 * vez, se ve doce veces por minuto.
 */

const abrirAdmin = async (page, opciones = {}) => {
  await instalarApiSimulada(page, { usuario: datos.ADMIN, ...opciones })
  await iniciarSesion(page)
  await page.goto('/admin')
  await esperarEstable(page)
}

test.describe('Contenido', () => {
  test('muestra las cifras del ultimo entrenamiento', async ({ page }) => {
    await abrirAdmin(page)

    await expect(page.getByRole('heading', { name: /laboratorio científico/i })).toBeVisible()
    // 0.914 se pinta como "91.4%", y las muestras del ultimo entrenamiento
    // tal cual.
    await expect(page.getByText('91.4%').first()).toBeVisible()
    await expect(page.getByText(String(datos.RESUMEN_ADMIN.last_training.samples)).first()).toBeVisible()
    await expect(page.getByText(`${datos.RESUMEN_ADMIN.avg_confidence_pct}%`).first()).toBeVisible()
  })

  test('reparte el dataset entre dato sintetico y dato humano', async ({ page }) => {
    await abrirAdmin(page)

    await expect(page.getByText('Sintético (Base)')).toBeVisible()
    await expect(page.getByText('Humano (Real)')).toBeVisible()
    await expect(page.getByText(String(datos.RESUMEN_ADMIN.data_sources.human)).first()).toBeVisible()
  })

  test('la distribucion por especializacion que se pide llega a la pantalla', async ({ page }) => {
    await abrirAdmin(page)

    // /stats/overview devuelve `specialization_dist` y Admin.jsx lo guarda en
    // una variable que despues no usa: se descarga en cada refresco (cada 5 s)
    // una consulta con GROUP BY sobre predictions que nadie llega a ver.
    for (const spec of datos.RESUMEN_ADMIN.specialization_dist) {
      await expect(
        page.getByText(spec.name).first(),
        `La especializacion "${spec.name}" viene en la respuesta pero no se pinta`,
      ).toBeVisible()
    }
  })

  test('los tres graficos se dibujan con tamano real', async ({ page }) => {
    await abrirAdmin(page)

    // Un ResponsiveContainer que mide 0 no lanza ningun error: simplemente
    // deja el hueco vacio. Se recorren todos los que haya en la pantalla y se
    // exige que cada uno ocupe algo.
    const lienzos = graficos(page)
    const total = await lienzos.count()
    expect(total, 'el laboratorio deberia pintar graficos').toBeGreaterThan(0)

    for (let i = 0; i < total; i++) {
      const caja = await lienzos.nth(i).boundingBox()
      expect(caja.width, `el grafico ${i} se quedo sin ancho`).toBeGreaterThan(100)
      expect(caja.height, `el grafico ${i} se quedo sin alto`).toBeGreaterThan(50)
    }
  })
})

test.describe('Reentrenamiento', () => {
  test('el boton lanza el entrenamiento y muestra el resultado', async ({ page }) => {
    await abrirAdmin(page)

    await page.getByRole('button', { name: /reentrenar/i }).first().click()

    // El aviso de exito compone accuracy, F1 y muestras del entrenamiento nuevo.
    await expect(page.locator('.admin-alert')).toContainText('92.0%', { timeout: 15_000 })
    await expect(page.locator('.admin-alert')).toContainText('5500')
  })

  test('si el entrenamiento falla se explica en pantalla', async ({ page }) => {
    await abrirAdmin(page, {
      reglas: [reglaError(/\/api\/stats\/train$/, 'POST', 500, { detail: 'Faltan muestras humanas' })],
    })

    await page.getByRole('button', { name: /reentrenar/i }).first().click()
    await expect(page.getByText(/faltan muestras humanas/i)).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('Descarga del dataset', () => {
  test('la descarga sale con la cabecera de autorizacion', async ({ page }) => {
    const cabeceras = []
    await instalarApiSimulada(page, {
      usuario: datos.ADMIN,
      reglas: [[
        /\/api\/stats\/export-csv$/, 'GET',
        (route, _m, request) => {
          cabeceras.push(request.headers())
          return route.fulfill({ status: 200, contentType: 'text/csv', body: 'a,b\n1,2\n' })
        },
      ]],
    })
    await iniciarSesion(page)
    await page.goto('/admin')

    await page.getByRole('button', { name: /exportar|dataset|csv/i }).first().click()

    // El fallo historico: la descarga se hacia con un <a href> suelto, que
    // sale del navegador SIN Authorization y siempre respondia 401.
    await expect.poll(() => cabeceras.length, { timeout: 15_000 }).toBeGreaterThan(0)
    expect(cabeceras[0].authorization, 'la descarga tiene que llevar el token').toMatch(/^Bearer /)
  })

  test('un fallo en la descarga se comunica en vez de no hacer nada', async ({ page }) => {
    await abrirAdmin(page, {
      reglas: [reglaError(/\/api\/stats\/export-csv$/, 'GET', 403, { detail: 'Solo administradores' })],
    })

    await page.getByRole('button', { name: /exportar|dataset|csv/i }).first().click()
    await expect(page.getByText(/permiso|administradores|no se pudo/i).first()).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('Refresco automatico', () => {
  test('los datos se vuelven a pedir sin recargar la pagina', async ({ page }) => {
    const registro = (await instalarApiSimulada(page, { usuario: datos.ADMIN })).registro
    await iniciarSesion(page)
    await page.goto('/admin')

    const contar = () => registro.llamadas.filter((l) => l.ruta.endsWith('/stats/overview')).length
    await expect.poll(contar, { timeout: 15_000 }).toBeGreaterThan(1)
  })

  test('el refresco se detiene al salir de la pantalla', async ({ page }) => {
    const registro = (await instalarApiSimulada(page, { usuario: datos.ADMIN })).registro
    await iniciarSesion(page)
    await page.goto('/admin')
    await expect.poll(
      () => registro.llamadas.filter((l) => l.ruta.endsWith('/stats/overview')).length,
      { timeout: 15_000 },
    ).toBeGreaterThan(0)

    await page.goto('/dashboard')
    const alSalir = registro.llamadas.filter((l) => l.ruta.endsWith('/stats/overview')).length
    await page.waitForTimeout(7_000)
    const despues = registro.llamadas.filter((l) => l.ruta.endsWith('/stats/overview')).length

    // Un intervalo que sobrevive al desmontaje sigue pidiendo datos de admin
    // desde cualquier pantalla, y con un token que ya puede no valer.
    expect(despues, 'el intervalo de refresco no se limpio al desmontar').toBe(alSalir)
  })
})

test.describe('Cuando el servicio falla', () => {
  test('un 500 en las estadisticas no deja la pantalla cargando para siempre', async ({ page, vigilante }) => {
    await abrirAdmin(page, {
      reglas: [
        reglaError(/\/api\/stats\/overview$/, 'GET', 500, { detail: 'Caido' }),
        reglaError(/\/api\/stats\/training-history$/, 'GET', 500, { detail: 'Caido' }),
      ],
    })

    await expect(page.getByRole('heading', { name: /laboratorio científico/i })).toBeVisible({ timeout: 15_000 })
    expect(vigilante.excepciones).toEqual([])
  })
})

test.describe('Maquetacion', () => {
  test('el laboratorio cabe en una tableta', async ({ page }) => {
    await instalarApiSimulada(page, { usuario: datos.ADMIN })
    await iniciarSesion(page)
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/admin')
    await esperarEstable(page)

    const desbordes = await elementosDesbordados(page, 2)
    expect(desbordes, detallar('El laboratorio se sale de la ventana a 768px', desbordes)).toEqual([])
  })

  test('el laboratorio se pinta sin errores de ejecucion', async ({ page, vigilante }) => {
    await abrirAdmin(page)
    sinErroresDeEjecucion(vigilante)
  })
})
