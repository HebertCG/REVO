import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { enlaceBarra, pie, abrirMenuSiHaceFalta } from './utiles/localizadores.js'
import * as datos from './utiles/datos.js'

/**
 * Enrutado y control de acceso.
 *
 * El enrutado de REVO decide quien ve que: `PrivateRoute` protege el panel y
 * `AdminRoute` el laboratorio del modelo. Un fallo aqui no se ve en la
 * pantalla, se ve cuando un alumno abre /admin y le funciona.
 */

test.describe('Rutas protegidas', () => {
  const PRIVADAS = ['/dashboard', '/questionnaire', '/history', '/results/903']

  for (const camino of PRIVADAS) {
    test(`sin sesion, ${camino} manda a iniciar sesion`, async ({ paginaPublica }) => {
      const { page } = paginaPublica
      await page.goto(camino)
      await expect(page).toHaveURL(/\/login$/)
    })
  }

  test('sin sesion, /admin manda a iniciar sesion y no filtra nada del modelo', async ({ paginaPublica }) => {
    const { page, registro } = paginaPublica
    await page.goto('/admin')

    // AdminRoute manda al panel y PrivateRoute de ahi al login: se comprueba
    // el destino final, no el salto intermedio.
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByText(/laboratorio científico/i)).toHaveCount(0)

    const rutasAdmin = registro.llamadas.filter((l) => /\/stats\//.test(l.ruta))
    expect(rutasAdmin, `Se pidieron rutas de admin sin sesion: ${JSON.stringify(rutasAdmin)}`).toEqual([])
  })

  test('un alumno no entra en /admin', async ({ paginaAlumno }) => {
    const { page, registro } = paginaAlumno
    await page.goto('/admin')

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByText(/laboratorio científico/i)).toHaveCount(0)

    // Lo importante no es solo el redirigido: es que el navegador no llegue
    // a pedir las rutas de administracion.
    const rutasAdmin = registro.llamadas.filter((l) => /\/stats\//.test(l.ruta))
    expect(rutasAdmin, `Se pidieron rutas de admin siendo alumno: ${JSON.stringify(rutasAdmin)}`).toEqual([])
  })

  test('un administrador si entra en /admin', async ({ paginaAdmin }) => {
    const { page } = paginaAdmin
    await page.goto('/admin')

    await expect(page).toHaveURL(/\/admin$/)
    await expect(page.getByRole('heading', { name: /laboratorio científico/i })).toBeVisible()
  })
})

test.describe('Rutas publicas', () => {
  test('la portada carga con su titulo principal', async ({ paginaPublica, vigilante }) => {
    const { page } = paginaPublica
    await page.goto('/')

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page).toHaveTitle(/REVO/)
    sinErroresDeEjecucion(vigilante)
  })

  test('una ruta inventada vuelve a la portada', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/una-ruta-que-no-existe')
    // El comodin de App.jsx redirige a la portada en vez de dejar un hueco.
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  test('/login y /register abren la pestana que les toca', async ({ paginaPublica }) => {
    const { page } = paginaPublica

    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /bienvenido de vuelta/i })).toBeVisible()

    await page.goto('/register')
    await expect(page.getByRole('heading', { name: /crea tu cuenta/i })).toBeVisible()
  })

  test('cambiar de pestana cambia la URL, y el boton atras la respeta', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/login')

    await page.getByRole('button', { name: 'Crear cuenta' }).click()
    await expect(page).toHaveURL(/\/register$/)
    await expect(page.getByRole('heading', { name: /crea tu cuenta/i })).toBeVisible()

    await page.goBack()
    await expect(page).toHaveURL(/\/login$/)
    // La pestana tiene que seguir a la URL: si no, el usuario ve el
    // formulario de registro en la direccion de login.
    await expect(page.getByRole('heading', { name: /bienvenido de vuelta/i })).toBeVisible()
  })
})

test.describe('Barra de navegacion', () => {
  test('sin sesion ofrece entrar y registrarse, no el panel', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await abrirMenuSiHaceFalta(page)

    await expect(enlaceBarra(page, 'Iniciar Sesión')).toBeVisible()
    await expect(enlaceBarra(page, 'Registrarse')).toBeVisible()
    await expect(enlaceBarra(page, 'Dashboard')).toHaveCount(0)
  })

  test('con sesion muestra el nombre y las rutas del alumno', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.goto('/dashboard')
    await abrirMenuSiHaceFalta(page)

    await expect(page.getByText('Ana', { exact: true }).first()).toBeVisible()
    await expect(enlaceBarra(page, 'Dashboard')).toBeVisible()
    // Un alumno no debe ver ni el enlace a administracion.
    await expect(enlaceBarra(page, 'Admin')).toHaveCount(0)
  })

  test('un administrador si ve el enlace de administracion', async ({ paginaAdmin }) => {
    const { page } = paginaAdmin
    await page.goto('/dashboard')
    await abrirMenuSiHaceFalta(page)
    await expect(enlaceBarra(page, 'Admin')).toBeVisible()
  })

  test('salir borra la sesion y devuelve a la portada', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.goto('/dashboard')

    await abrirMenuSiHaceFalta(page)
    await page.getByRole('button', { name: 'Salir' }).click()
    await expect(page).toHaveURL(/\/$/)

    const token = await page.evaluate(() => sessionStorage.getItem('revo_token'))
    expect(token, 'salir tiene que borrar el token de sessionStorage').toBeNull()

    // Y volver atras no puede devolver la sesion.
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('el logo vuelve a la portada desde cualquier pantalla', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.goto('/history')
    await page.locator('nav.navbar').getByRole('link').first().click()
    await expect(page).toHaveURL(/\/$/)
  })
})

test.describe('Pie de pagina', () => {
  test('los enlaces del pie llevan a rutas que existen', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await esperarEstable(page)

    const destinos = await pie(page).getByRole('link').evaluateAll((enlaces) =>
      enlaces.map((a) => a.getAttribute('href')).filter(Boolean),
    )

    expect(destinos.length, 'el pie deberia tener enlaces').toBeGreaterThan(0)

    const RUTAS_CONOCIDAS = ['/', '/login', '/register', '/dashboard', '/questionnaire', '/history', '/admin']
    const rotos = destinos.filter((href) => {
      if (href.startsWith('http') || href.startsWith('#')) return false
      return !RUTAS_CONOCIDAS.includes(href)
    })

    expect(rotos, `Enlaces del pie hacia rutas inexistentes: ${JSON.stringify(rotos)}`).toEqual([])
  })

  test('los anclas del pie llevan a secciones que existen en la portada', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')
    await esperarEstable(page)

    const anclas = await pie(page).getByRole('link').evaluateAll((enlaces) =>
      enlaces.map((a) => a.getAttribute('href')).filter((h) => h?.startsWith('#')),
    )

    const perdidas = []
    for (const ancla of anclas) {
      const existe = await page.locator(ancla).count()
      if (!existe) perdidas.push(ancla)
    }

    expect(perdidas, `Anclas del pie sin destino en la pagina: ${JSON.stringify(perdidas)}`).toEqual([])
  })

  test('el enlace externo se abre con rel de seguridad', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/')

    const externos = pie(page).locator('a[target="_blank"]')
    const total = await externos.count()

    for (let i = 0; i < total; i++) {
      const rel = await externos.nth(i).getAttribute('rel')
      const href = await externos.nth(i).getAttribute('href')
      expect(rel, `${href} se abre en pestana nueva sin rel="noopener"`).toContain('noopener')
    }
  })
})

test.describe('Enlaces profundos', () => {
  test('un resultado se puede abrir directo por su URL', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.goto(`/results/${datos.PREDICCION.prediction_id}`)

    await expect(page.locator('h1.result-main-name')).toHaveText(datos.PREDICCION.primary.name)
  })

  test('recargar una ruta privada mantiene la sesion', async ({ paginaAlumno }) => {
    const { page } = paginaAlumno
    await page.goto('/history')
    await page.reload()

    await expect(page).toHaveURL(/\/history$/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})
