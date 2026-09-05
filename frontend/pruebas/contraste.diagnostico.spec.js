import AxeBuilder from '@axe-core/playwright'
import { test, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion } from './utiles/apiSimulada.js'

/**
 * Diagnostico de contraste: no afirma nada, imprime el color real de texto y
 * de fondo que axe calcula en cada elemento que incumple, con su ratio.
 *
 * Sin esto hay que adivinar sobre que fondo acaba pintado cada texto, y en
 * una interfaz con capas translucidas la respuesta casi nunca es el color
 * que declara la hoja de estilos.
 */
const RUTAS = [
  ['portada', '/', false],
  ['acceso', '/login', false],
  ['registro', '/register', false],
  ['panel', '/dashboard', true],
  ['historial', '/history', true],
  ['resultado', '/results/903', true],
]

test('vuelca los contrastes que incumplen', async ({ page }) => {
  test.slow()
  await instalarApiSimulada(page)
  await iniciarSesion(page)

  for (const [nombre, camino] of RUTAS) {
    await page.goto(camino)
    await esperarEstable(page)

    const { violations } = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()

    const contraste = violations.find((v) => v.id === 'color-contrast')
    if (!contraste) {
      console.log(`\n=== ${nombre} (${camino}): sin incumplimientos de contraste`)
      continue
    }
    console.log(`\n=== ${nombre} (${camino}) ===`)
    for (const nodo of contraste.nodes) {
      const d = nodo.any?.[0]?.data || {}
      console.log([
        `  ${nodo.target.join(' ')}`,
        `texto=${d.fgColor} fondo=${d.bgColor}`,
        `ratio=${d.contrastRatio} minimo=${d.expectedContrastRatio}`,
        `fuente=${d.fontSize} ${d.fontWeight}`,
        `| ${(nodo.html || '').replace(/\s+/g, ' ').slice(0, 90)}`,
      ].join(' '))
    }
  }
})
