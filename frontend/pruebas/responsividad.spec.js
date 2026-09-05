import { test, expect, ANCHOS, RUTAS, esperarEstable } from './utiles/fixtures.js'
import {
  desplazamientoHorizontal,
  elementosDesbordados,
  objetivosTactilesPequenos,
  textoRecortado,
  imagenesSinReserva,
  imagenesRotas,
  controlesTapados,
  detallar,
} from './utiles/inspector.js'
import { botonMenu, enlaceBarra } from './utiles/localizadores.js'

/**
 * Responsividad.
 *
 * Se recorren diez anchuras donde el diseno de REVO cambia de forma, no
 * las tres habituales. Los fallos de maquetacion no viven en 375 ni en 1440:
 * viven en los bordes (320, donde ya no cabe nada) y en el salto de columna
 * (768 -> 1024), que es donde `grid-template-columns` cambia de valor.
 *
 * Todo lo que se mide aqui es geometria: pixeles que se salen, texto que se
 * corta, dedos que no alcanzan. Nada de capturas comparadas, que fallan por
 * el antialiasing de la fuente y acaban desactivadas.
 */

const TODAS_LAS_RUTAS = [...RUTAS.publicas, ...RUTAS.privadas]

test.describe('Matriz responsiva', () => {
  for (const { ancho, alto, nombre } of ANCHOS) {
    for (const ruta of TODAS_LAS_RUTAS) {
      test(`${ruta.nombre} se adapta a ${ancho}px (${nombre})`, async ({ paginaAlumno }) => {
        const { page } = paginaAlumno
        await page.setViewportSize({ width: ancho, height: alto })
        await page.goto(ruta.camino, { waitUntil: 'domcontentloaded' })
        await esperarEstable(page)

        const scroll = await desplazamientoHorizontal(page)
        const culpables = await elementosDesbordados(page)
        expect.soft(
          scroll.exceso,
          `${ruta.nombre} a ${ancho}px se desplaza ${scroll.exceso}px en horizontal.\n` +
          detallar('Elementos que sobresalen', culpables),
        ).toBeLessThanOrEqual(1)
        expect.soft(
          culpables,
          detallar(`${ruta.nombre} a ${ancho}px: elementos fuera de la ventana`, culpables),
        ).toEqual([])

        if (ancho <= 768) {
          const pequenos = await objetivosTactilesPequenos(page, 24)
          expect.soft(
            pequenos,
            detallar(`${ruta.nombre} a ${ancho}px: controles por debajo de 24x24 px`, pequenos),
          ).toEqual([])
        }

        if (ancho <= 1024) {
          const recortados = await textoRecortado(page, 3)
          expect.soft(
            recortados,
            detallar(`${ruta.nombre} a ${ancho}px: texto cortado sin manera de leerlo`, recortados),
          ).toEqual([])
        }
      })
    }
  }
})

test.describe('Menu de navegacion', () => {
  test('en movil el menu se abre y se cierra solo al cambiar de ruta', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/dashboard')

    const hamburguesa = botonMenu(page)
    await expect(hamburguesa, 'en movil debe existir el boton de menu').toBeVisible()
    await expect(hamburguesa).toHaveAttribute('aria-expanded', 'false')

    await hamburguesa.click()
    await expect(hamburguesa).toHaveAttribute('aria-expanded', 'true')

    const enlaceHistorial = enlaceBarra(page, 'Historial')
    await expect(enlaceHistorial).toBeVisible()
    await enlaceHistorial.click()

    await expect(page).toHaveURL(/\/history$/)
    // Si el menu no se cierra al navegar, queda tapando la pagina nueva.
    await expect(botonMenu(page)).toHaveAttribute('aria-expanded', 'false')
  })

  test('en escritorio los enlaces estan a la vista sin abrir nada', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/dashboard')

    for (const nombre of ['Dashboard', 'Cuestionario', 'Historial']) {
      await expect(enlaceBarra(page, nombre)).toBeVisible()
    }
    await expect(botonMenu(page), 'el boton de menu no pinta nada en escritorio').toBeHidden()
  })

  test('la barra fija no tapa el contenido al bajar', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')
    await esperarEstable(page)

    await page.mouse.wheel(0, 600)
    await page.waitForTimeout(300)

    const tapados = await controlesTapados(page)
    // La barra flotante se superpone a proposito; lo que no puede pasar es
    // que deje debajo un control que el usuario necesita pulsar.
    const tapadosPorLaBarra = tapados.filter((t) => /navbar/.test(t.tapadoPor))
    expect(
      tapadosPorLaBarra,
      detallar('Controles tapados por la barra de navegacion', tapadosPorLaBarra),
    ).toEqual([])
  })
})

test.describe('Imagenes', () => {
  test('todas las imagenes cargan', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno

    for (const ruta of TODAS_LAS_RUTAS) {
      await page.goto(ruta.camino)
      await esperarEstable(page)
      await page.waitForLoadState('load')

      const rotas = await imagenesRotas(page)
      expect(rotas, detallar(`${ruta.nombre}: imagenes que no cargaron`, rotas)).toEqual([])
    }
  })

  test('las imagenes reservan su hueco y no provocan saltos', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.setViewportSize({ width: 375, height: 812 })

    const problemas = []
    for (const ruta of TODAS_LAS_RUTAS) {
      await page.goto(ruta.camino)
      await esperarEstable(page)
      const sinReserva = await imagenesSinReserva(page)
      if (sinReserva.length) problemas.push({ ruta: ruta.nombre, imagenes: sinReserva })
    }

    expect(
      problemas,
      detallar('Imagenes sin ancho/alto ni aspect-ratio (provocan CLS)', problemas),
    ).toEqual([])
  })
})

test.describe('Zoom y ampliacion', () => {
  test('la portada sigue siendo usable con el texto al 200%', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    // Ampliar el texto sin ampliar la ventana es lo que hace un lector con
    // baja vision, y es donde se rompen las alturas fijas.
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/')
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' })
    await esperarEstable(page)

    const scroll = await desplazamientoHorizontal(page)
    expect(
      scroll.exceso,
      `Con el texto al 200% la portada se desplaza ${scroll.exceso}px en horizontal`,
    ).toBeLessThanOrEqual(1)
  })

  test('el formulario de registro cabe en una ventana corta', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    // 1024x600 es un portatil de aula tipico. El formulario declara
    // min-height:688px, que ya no cabe: se comprueba que al menos se pueda
    // llegar al boton desplazandose.
    await page.setViewportSize({ width: 1024, height: 600 })
    await page.goto('/register')
    await esperarEstable(page)

    const boton = page.getByRole('button', { name: /crear cuenta y empezar/i })
    await boton.scrollIntoViewIfNeeded()
    await expect(boton).toBeVisible()
  })
})
