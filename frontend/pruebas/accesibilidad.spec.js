import AxeBuilder from '@axe-core/playwright'
import { test, expect, RUTAS, esperarEstable } from './utiles/fixtures.js'
import {
  encabezados, camposSinEtiqueta, botonesSinNombre, imagenesSinAlt, detallar,
} from './utiles/inspector.js'

/**
 * Accesibilidad.
 *
 * Dos capas que no se solapan:
 *
 *   - axe-core cubre lo mecanico y medible (contraste, roles, atributos ARIA
 *     mal usados). Es exhaustivo y no hace falta reimplementarlo.
 *   - Las sondas propias cubren lo que axe no puede decidir solo: si el orden
 *     de encabezados cuenta una historia, si el foco se ve, si el teclado
 *     llega a todo.
 *
 * Se ejecuta contra las mismas rutas que el resto de la bateria para que un
 * fallo se pueda cruzar con el resto del informe.
 */

const TODAS_LAS_RUTAS = [...RUTAS.publicas, ...RUTAS.privadas]

const analizar = (page) =>
  new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()

const resumir = (violaciones) =>
  violaciones.map((v) => ({
    regla: v.id,
    impacto: v.impact,
    descripcion: v.help,
    elementos: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
  }))

test.describe('Analisis automatico (axe-core)', () => {
  for (const ruta of TODAS_LAS_RUTAS) {
    test(`${ruta.nombre} cumple WCAG 2.1 A y AA`, async ({ paginaAlumno }) => {
      const { page } = paginaAlumno
      await page.goto(ruta.camino)
      await esperarEstable(page)

      const { violations } = await analizar(page)
      const resumen = resumir(violations)

      expect(resumen, detallar(`${ruta.nombre}: incumplimientos WCAG`, resumen)).toEqual([])
    })
  }

  test('la pantalla de registro con sus casillas legales cumple WCAG', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/register')
    await esperarEstable(page)

    const { violations } = await analizar(page)
    const resumen = resumir(violations)
    expect(resumen, detallar('Registro: incumplimientos WCAG', resumen)).toEqual([])
  })
})

test.describe('Estructura del documento', () => {
  for (const ruta of TODAS_LAS_RUTAS) {
    test(`${ruta.nombre} tiene un solo h1 y no se salta niveles`, async ({ paginaAlumno }) => {
      const { page } = paginaAlumno
      await page.goto(ruta.camino)
      await esperarEstable(page)

      const estructura = await encabezados(page)

      expect(estructura.h1, `${ruta.nombre}: se esperaba exactamente un h1, hay ${estructura.h1}`).toBe(1)
      expect(
        estructura.saltos,
        detallar(`${ruta.nombre}: saltos en la jerarquia de encabezados`, estructura.saltos),
      ).toEqual([])
    })
  }

  test('las regiones de navegacion se distinguen entre si', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await esperarEstable(page)

    const navs = page.getByRole('navigation')
    const total = await navs.count()

    // Con mas de un <nav> en la pagina, cada uno necesita nombre propio: si
    // no, un lector de pantalla anuncia cuatro veces "navegacion" y el
    // usuario no sabe cual es el menu principal.
    const sinNombre = []
    for (let i = 0; i < total; i++) {
      const nombre = await navs.nth(i).evaluate((el) =>
        el.getAttribute('aria-label')
        || (el.getAttribute('aria-labelledby')
          && document.getElementById(el.getAttribute('aria-labelledby'))?.textContent?.trim()),
      )
      if (!nombre) sinNombre.push(await navs.nth(i).evaluate((el) => el.className))
    }

    expect(
      sinNombre,
      `Hay ${total} regiones de navegacion y estas no tienen nombre: ${JSON.stringify(sinNombre)}`,
    ).toEqual([])
  })
})

test.describe('Formularios', () => {
  for (const camino of ['/login', '/register']) {
    test(`todos los campos de ${camino} tienen etiqueta`, async ({ paginaPublica }) => {
      const { page } = paginaPublica
      await page.goto(camino)
      await esperarEstable(page)

      const huerfanos = await camposSinEtiqueta(page)
      expect(huerfanos, detallar(`${camino}: campos sin etiqueta accesible`, huerfanos)).toEqual([])
    })
  }

  test('el error de acceso se anuncia como alerta', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/login')

    // El mensaje llega despues del envio: sin role="alert" un lector de
    // pantalla no lo lee y el usuario se queda sin saber que paso.
    await expect(page.locator('[role="alert"]')).toHaveCount(0)
  })
})

test.describe('Nombres accesibles', () => {
  for (const ruta of TODAS_LAS_RUTAS) {
    test(`${ruta.nombre}: cada control tiene nombre`, async ({ paginaAlumno }) => {
      const { page } = paginaAlumno
      await page.goto(ruta.camino)
      await esperarEstable(page)

      const sinNombre = await botonesSinNombre(page)
      expect(
        sinNombre,
        detallar(`${ruta.nombre}: controles sin nombre accesible (solo icono o flecha)`, sinNombre),
      ).toEqual([])
    })
  }

  test('todas las imagenes declaran alt, aunque sea vacio', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno

    for (const ruta of TODAS_LAS_RUTAS) {
      await page.goto(ruta.camino)
      await esperarEstable(page)

      const sinAlt = await imagenesSinAlt(page)
      expect(sinAlt, detallar(`${ruta.nombre}: imagenes sin atributo alt`, sinAlt)).toEqual([])
    }
  })
})

test.describe('Teclado', () => {
  test('se puede recorrer la portada entera con el tabulador', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await esperarEstable(page)

    const visitados = []
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('Tab')
      const actual = await page.evaluate(() => {
        const el = document.activeElement
        if (!el || el === document.body) return null
        return {
          etiqueta: el.tagName.toLowerCase(),
          texto: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 30),
        }
      })
      if (!actual) break
      visitados.push(actual)
    }

    expect(visitados.length, 'el tabulador no llega a ningun control').toBeGreaterThan(3)
  })

  test('el foco se ve en los controles de la barra', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await esperarEstable(page)

    await page.keyboard.press('Tab')

    const contorno = await page.evaluate(() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const estilo = getComputedStyle(el)
      return {
        outlineStyle: estilo.outlineStyle,
        outlineWidth: estilo.outlineWidth,
        boxShadow: estilo.boxShadow,
      }
    })

    expect(contorno, 'nada recibio el foco al pulsar Tab').not.toBeNull()

    // Un `outline: none` sin sustituto deja al usuario de teclado sin saber
    // donde esta. Vale outline propio o una sombra que lo sustituya.
    const tieneIndicador = (contorno.outlineStyle !== 'none' && contorno.outlineWidth !== '0px')
      || (contorno.boxShadow && contorno.boxShadow !== 'none')

    expect(tieneIndicador, `El primer elemento enfocable no muestra el foco: ${JSON.stringify(contorno)}`).toBe(true)
  })

  test('el menu movil se puede abrir con el teclado', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/dashboard')

    const hamburguesa = page.locator('nav.navbar').getByRole('button', { name: /menú/i })
    await hamburguesa.focus()
    await page.keyboard.press('Enter')

    await expect(hamburguesa).toHaveAttribute('aria-expanded', 'true')
  })
})

test.describe('Movimiento reducido', () => {
  test('con la preferencia activa la portada no anima sin parar', async ({ browser }) => {
    const contexto = await browser.newContext({ reducedMotion: 'reduce' })
    const pagina = await contexto.newPage()
    const { instalarApiSimulada } = await import('./utiles/apiSimulada.js')
    await instalarApiSimulada(pagina)

    await pagina.goto('/')
    await esperarEstable(pagina)

    const infinitas = await pagina.evaluate(() =>
      [...document.querySelectorAll('body *')]
        .filter((el) => {
          const estilo = getComputedStyle(el)
          return estilo.animationIterationCount === 'infinite'
            && estilo.animationName !== 'none'
            && estilo.animationDuration !== '0s'
        })
        .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]}`)
        .slice(0, 10),
    )

    expect(
      infinitas,
      `Con prefers-reduced-motion siguen animandose sin fin: ${JSON.stringify(infinitas)}`,
    ).toEqual([])

    await contexto.close()
  })
})
