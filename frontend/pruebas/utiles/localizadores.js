/**
 * Localizadores compartidos.
 *
 * Casi todo se busca por rol y texto accesible, que es como lo encuentra un
 * usuario. Las dos excepciones son la barra superior y el pie, y estan aqui
 * a proposito:
 *
 * La portada pinta cuatro elementos <nav> (la barra y las tres columnas del
 * pie) y solo las del pie declaran nombre accesible. Sin nombre, la barra no
 * se puede distinguir por rol, y `getByRole('link', { name: 'Historial' })`
 * encuentra dos enlaces distintos. Se acota por clase mientras la barra no
 * tenga su `aria-label`; en cuanto lo tenga, esto se sustituye por
 * `getByRole('navigation', { name: ... })`.
 */

export const barra = (page) => page.locator('nav.navbar')
export const pie = (page) => page.locator('footer.site-footer')

export const enlaceBarra = (page, nombre) => barra(page).getByRole('link', { name: nombre, exact: true })
export const botonMenu = (page) => barra(page).getByRole('button', { name: /menú/i })

/** Contenido principal de la pagina, sin la barra ni el pie. */
export const contenido = (page) => page.locator('.page, main, .rv').first()

/**
 * Los graficos de verdad, sin los iconos de la leyenda.
 *
 * recharts pinta cada simbolo de la leyenda con su propio
 * `svg.recharts-surface` de 14x14. Contarlos como graficos hace que la
 * comprobacion de "el grafico tiene tamano" falle siempre, y por el motivo
 * equivocado.
 */
export const graficos = (page, dentroDe = '') =>
  page.locator(`${dentroDe} svg.recharts-surface:not(.recharts-legend-item *)`.trim())

/**
 * Abre el menu si la ventana es estrecha.
 *
 * En movil los enlaces y el boton de salir viven dentro del panel plegado.
 * Una prueba que los pulse directamente falla por el tamano de la ventana y
 * no por un fallo de la aplicacion.
 */
export async function abrirMenuSiHaceFalta(page) {
  const boton = botonMenu(page)
  if (!(await boton.isVisible())) return
  if ((await boton.getAttribute('aria-expanded')) === 'true') return
  await boton.click()
}
