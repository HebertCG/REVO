import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError, reglaSinRed } from './utiles/apiSimulada.js'
import { elementosDesbordados, detallar } from './utiles/inspector.js'
import { graficos } from './utiles/localizadores.js'
import * as datos from './utiles/datos.js'

/**
 * Pantalla de resultado.
 *
 * Es la unica que combina cuatro fuentes: la prediccion del modelo, los
 * cursos del catalogo, los pesos del modelo (solo admin) y una API publica
 * ajena (Remotive). Tres de las cuatro pueden fallar sin que la pantalla
 * pierda su razon de ser, y eso es justo lo que se comprueba aqui: que el
 * resultado se lea aunque lo accesorio no llegue.
 */

const ID = datos.PREDICCION.prediction_id

// El nombre de la especialidad se repite como h1 del heroe y como h3 en el
// top 3, asi que se acota al titular principal.
const titular = (page) => page.locator('h1.result-main-name')

const abrirResultado = async (page, opciones = {}) => {
  await instalarApiSimulada(page, opciones)
  await iniciarSesion(page)
  await page.goto(`/results/${ID}`)
  await esperarEstable(page)
}

test.describe('Contenido principal', () => {
  test('muestra la especializacion recomendada y su porcentaje', async ({ page }) => {
    await abrirResultado(page)

    await expect(titular(page)).toBeVisible()
    await expect(page.getByText('87.4%').first()).toBeVisible()
  })

  test('lista las tres especializaciones mas probables', async ({ page }) => {
    await abrirResultado(page)

    await expect(page.locator('.top3-item')).toHaveCount(3)
    for (const spec of datos.PREDICCION.top3) {
      await expect(page.locator('.top3-item').getByText(spec.name)).toBeVisible()
    }
  })

  test('los dos graficos se dibujan con tamano real', async ({ page }) => {
    await abrirResultado(page)

    const lienzos = graficos(page, '.results-panel')
    await expect(lienzos).toHaveCount(2)

    for (let i = 0; i < 2; i++) {
      const caja = await lienzos.nth(i).boundingBox()
      expect(caja.width, `el grafico ${i} no tiene ancho`).toBeGreaterThan(100)
      expect(caja.height, `el grafico ${i} no tiene alto`).toBeGreaterThan(50)
    }
  })

  test('los cursos recomendados abren en pestana nueva con rel seguro', async ({ page }) => {
    await abrirResultado(page)

    const cursos = page.locator('.course-card')
    await expect(cursos).toHaveCount(datos.CURSOS.length)

    const total = await cursos.count()
    for (let i = 0; i < total; i++) {
      const rel = await cursos.nth(i).getAttribute('rel')
      // Sin noopener, la pagina de destino puede manipular la pestana de REVO
      // a traves de window.opener.
      expect(rel, 'un curso externo sin rel="noopener"').toContain('noopener')
    }
  })
})

test.describe('Fuentes que pueden faltar', () => {
  test('sin cursos en el catalogo el resultado sigue siendo legible', async ({ page, vigilante }) => {
    await abrirResultado(page, {
      reglas: [reglaError(/\/api\/courses\/specialization\/\d+$/, 'GET', 404, { detail: 'Sin cursos' })],
    })

    await expect(titular(page)).toBeVisible()
    expect(vigilante.excepciones).toEqual([])
  })

  test('si la API de empleos externa cae, la pantalla no se entera', async ({ page, vigilante }) => {
    await instalarApiSimulada(page)
    // Remotive es un tercero fuera de nuestro control: su caida no puede
    // arrastrar la pantalla de resultado.
    await page.route(/remotive\.com/, (route) => route.abort('connectionfailed'))
    await iniciarSesion(page)
    await page.goto(`/results/${ID}`)
    await esperarEstable(page)

    await expect(titular(page)).toBeVisible()
    expect(vigilante.excepciones).toEqual([])
  })

  test('los pesos del modelo son de admin, y su 403 no rompe la vista del alumno', async ({ page, vigilante }) => {
    await abrirResultado(page, {
      reglas: [reglaError(/\/api\/predict\/model\/importances$/, 'GET', 403, { detail: 'Solo administradores' })],
    })

    await expect(titular(page)).toBeVisible()
    expect(vigilante.excepciones).toEqual([])
  })

  test('una prediccion inexistente lo dice en vez de quedarse en blanco', async ({ page }) => {
    await abrirResultado(page, {
      reglas: [reglaError(/\/api\/predict\/\d+$/, 'GET', 404, { detail: 'No existe' })],
    })

    await expect(page.getByText(/resultado no encontrado/i)).toBeVisible()
  })

  test('sin conexion lo dice y no se queda cargando indefinidamente', async ({ page }) => {
    await abrirResultado(page, {
      reglas: [reglaSinRed(/\/api\/predict\/\d+$/, 'GET')],
    })

    await expect(page.getByText(/cargando resultado/i)).toHaveCount(0, { timeout: 15_000 })
    // Sin red el resultado puede existir perfectamente: lo que fallo fue el
    // camino hasta el. Decir "no encontrado" aqui le hace creer al alumno
    // que perdio su evaluacion, asi que se exige el motivo real.
    await expect(page.getByText(/no hay conexion con el servidor/i)).toBeVisible()
  })

  test('una prediccion sin top3 ni probabilidades no rompe los graficos', async ({ page, vigilante }) => {
    await abrirResultado(page, {
      prediccion: { ...datos.PREDICCION, top3: [], all_probabilities: {} },
    })

    await expect(titular(page)).toBeVisible()
    sinErroresDeEjecucion(vigilante)
  })
})

test.describe('Valoracion del alumno', () => {
  test('las dos preguntas se encadenan y acaban en agradecimiento', async ({ page }) => {
    await abrirResultado(page)

    await page.getByRole('button', { name: /me define muy bien/i }).click()
    await expect(page.getByRole('heading', { name: /ya tenías en mente/i })).toBeVisible()

    await page.getByRole('button', { name: /me sorprendió/i }).click()
    await expect(page.getByRole('heading', { name: /gracias por entrenar/i })).toBeVisible()
  })

  test('la valoracion viaja con las dos respuestas', async ({ page }) => {
    const cuerpos = []
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/predict\/\d+\/feedback$/, 'POST',
        (route, _m, request) => {
          cuerpos.push(request.postDataJSON())
          return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' })
        },
      ]],
    })
    await iniciarSesion(page)
    await page.goto(`/results/${ID}`)

    await page.getByRole('button', { name: /me define muy bien/i }).click()
    await page.getByRole('button', { name: /ya lo sospechaba/i }).click()
    await expect(page.getByRole('heading', { name: /gracias por entrenar/i })).toBeVisible()

    expect(cuerpos).toHaveLength(1)
    expect(cuerpos[0]).toEqual({ diagnostic_affinity: true, discovery_level: 'known' })
  })

  test('si el envio de la valoracion falla, el alumno igual ve el cierre', async ({ page }) => {
    await abrirResultado(page, {
      reglas: [reglaError(/\/api\/predict\/\d+\/feedback$/, 'POST', 500, { detail: 'Error' })],
    })

    await page.getByRole('button', { name: /me define muy bien/i }).click()
    await page.getByRole('button', { name: /me sorprendió/i }).click()

    // Un fallo al guardar la valoracion no puede dejar al alumno atrapado en
    // el formulario sin saber si se envio.
    await expect(page.getByRole('heading', { name: /gracias por entrenar/i })).toBeVisible()
  })
})

test.describe('Maquetacion', () => {
  test('el resultado cabe en un movil', async ({ page }) => {
    await instalarApiSimulada(page)
    await iniciarSesion(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`/results/${ID}`)
    await esperarEstable(page)

    const desbordes = await elementosDesbordados(page, 2)
    expect(desbordes, detallar('El resultado se sale de la ventana en movil', desbordes)).toEqual([])
  })

  test('el resultado se pinta sin errores de ejecucion', async ({ page, vigilante }) => {
    await abrirResultado(page)
    sinErroresDeEjecucion(vigilante)
  })
})
