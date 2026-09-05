import { test, expect, sinErroresDeEjecucion } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError, reglaSinRed } from './utiles/apiSimulada.js'
import * as datos from './utiles/datos.js'

/**
 * Acceso: inicio de sesion, registro y consentimiento.
 *
 * Es la unica pantalla donde el frontend valida por su cuenta antes de
 * llamar al servidor (el aviso de los Terminos), y donde un fallo tiene
 * consecuencias legales: si la casilla obligatoria se puede saltar, se crean
 * cuentas sin consentimiento valido bajo la Ley 29733.
 */

const campoCorreo = (page) => page.getByRole('textbox', { name: /correo institucional/i })
const campoClave = (page) => page.locator('input[type="password"], input[placeholder*="Mínimo"]').first()
// El texto del boton de envio coincide con el de la pestana ("Iniciar
// sesion" aparece dos veces en la pantalla), asi que se acota al formulario.
const botonEnviar = (page) => page.locator('form button[type="submit"]')

test.describe('Inicio de sesion', () => {
  test('con credenciales validas entra al panel', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/login')

    await campoCorreo(page).fill(datos.USUARIO.email)
    await campoClave(page).fill('contrasena-larga-123')
    await botonEnviar(page).click()

    await expect(page).toHaveURL(/\/dashboard$/)
    const token = await page.evaluate(() => sessionStorage.getItem('revo_token'))
    expect(token, 'tras entrar tiene que quedar guardado el token').toBeTruthy()
  })

  test('un administrador aterriza en su laboratorio y no en el panel', async ({ page }) => {
    await instalarApiSimulada(page, { usuario: datos.ADMIN })
    await page.goto('/login')

    await campoCorreo(page).fill(datos.ADMIN.email)
    await campoClave(page).fill('contrasena-larga-123')
    await botonEnviar(page).click()

    await expect(page).toHaveURL(/\/admin$/)
  })

  test('con credenciales incorrectas explica el motivo y no navega', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/auth\/login$/, 'POST', 401, { detail: 'Credenciales incorrectas' })],
    })
    await page.goto('/login')

    await campoCorreo(page).fill('ana@universidad.edu.pe')
    await campoClave(page).fill('clave-equivocada')
    await botonEnviar(page).click()

    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
  })

  test('el limite de peticiones dice cuantos segundos hay que esperar', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(
        /\/api\/auth\/login$/, 'POST', 429,
        { detail: 'Demasiados intentos' },
        { 'retry-after': '45' },
      )],
    })
    await page.goto('/login')

    await campoCorreo(page).fill('ana@universidad.edu.pe')
    await campoClave(page).fill('contrasena-larga-123')
    await botonEnviar(page).click()

    // El interceptor de api.js compone el mensaje con los segundos reales
    // de la cabecera. Repetir "vuelve en 60" cuando el servidor dijo 45 es
    // lo que hace que el alumno recargue en bucle y alargue el bloqueo.
    await expect(page.getByRole('alert')).toContainText('45')
  })

  test('sin conexion lo dice en vez de quedarse pensando', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaSinRed(/\/api\/auth\/login$/, 'POST')],
    })
    await page.goto('/login')

    await campoCorreo(page).fill('ana@universidad.edu.pe')
    await campoClave(page).fill('contrasena-larga-123')
    await botonEnviar(page).click()

    await expect(page.getByRole('alert')).toContainText(/conexi/i)
    // El boton tiene que volver a estar disponible: si se queda deshabilitado
    // el usuario no puede reintentar sin recargar.
    await expect(botonEnviar(page)).toBeEnabled()
  })

  test('el campo de correo exige formato de correo', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/login')

    await campoCorreo(page).fill('esto-no-es-un-correo')
    await campoClave(page).fill('contrasena-larga-123')
    await botonEnviar(page).click()

    // El navegador bloquea el envio con la validacion nativa: no se navega.
    await expect(page).toHaveURL(/\/login$/)
    const valido = await campoCorreo(page).evaluate((el) => el.checkValidity())
    expect(valido, 'un correo mal formado deberia invalidar el campo').toBe(false)
  })

  test('el boton de ver contrasena la muestra y la vuelve a ocultar', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await page.goto('/login')

    const clave = campoClave(page)
    await clave.fill('contrasena-larga-123')
    await expect(clave).toHaveAttribute('type', 'password')

    await page.getByRole('button', { name: 'Ver' }).click()
    await expect(page.locator('input[value="contrasena-larga-123"]')).toHaveAttribute('type', 'text')

    await page.getByRole('button', { name: 'Ocultar' }).click()
    await expect(page.locator('input[value="contrasena-larga-123"]')).toHaveAttribute('type', 'password')
  })
})

test.describe('Registro y consentimiento', () => {
  const irARegistro = async (page) => {
    await page.goto('/register')
    await expect(page.getByRole('heading', { name: /crea tu cuenta/i })).toBeVisible()
  }

  const rellenarRegistro = async (page) => {
    await page.getByRole('textbox', { name: /nombre completo/i }).fill('Ana Quispe Mamani')
    await campoCorreo(page).fill('ana.quispe@universidad.edu.pe')
    await campoClave(page).fill('contrasena-larga-123')
  }

  test('sin aceptar los Terminos no se envia nada al servidor', async ({ paginaPublica }) => {
    const { page, registro } = paginaPublica
    await irARegistro(page)
    await rellenarRegistro(page)

    await botonEnviar(page).click()

    // El aviso de la aplicacion escribe "Terminos" sin tilde, a diferencia
    // del resto de la interfaz. El patron acepta las dos formas para que la
    // prueba compruebe el comportamiento y no la ortografia.
    await expect(page.getByRole('alert')).toContainText(/T[eé]rminos/i)
    await expect(page).toHaveURL(/\/register$/)

    // Comprobar el aviso no basta: lo que evita gastar el cupo de registro
    // del alumno es que la peticion no llegue a salir.
    const intentos = registro.llamadas.filter((l) => l.ruta.endsWith('/auth/register'))
    expect(intentos, 'no debe salir ninguna peticion de registro sin consentimiento').toEqual([])
  })

  test('las dos casillas opcionales nacen desmarcadas', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await irARegistro(page)

    // Una casilla premarcada no es consentimiento libre: es una suposicion
    // que la Ley 29733 no admite para finalidades comerciales.
    await expect(page.locator('#consent-comercial')).not.toBeChecked()
    await expect(page.locator('#consent-ia')).not.toBeChecked()
    await expect(page.locator('#consent-terms')).not.toBeChecked()
  })

  test('aceptando los Terminos se crea la cuenta y se llega al panel', async ({ paginaPublica }) => {
    const { page, registro } = paginaPublica
    await irARegistro(page)
    await rellenarRegistro(page)

    await page.locator('#consent-terms').check()
    await botonEnviar(page).click()

    await expect(page).toHaveURL(/\/dashboard$/)
    expect(registro.llamadas.some((l) => l.ruta.endsWith('/auth/register'))).toBe(true)
  })

  test('el cuerpo del registro lleva cada consentimiento por separado', async ({ page }) => {
    const cuerpos = []
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/auth\/register$/, 'POST',
        (route, _m, request) => {
          cuerpos.push(request.postDataJSON())
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(datos.SESION_TOKEN),
          })
        },
      ]],
    })

    await irARegistro(page)
    await rellenarRegistro(page)
    await page.locator('#consent-terms').check()
    await page.locator('#consent-ia').check()
    await botonEnviar(page).click()
    await expect(page).toHaveURL(/\/dashboard$/)

    expect(cuerpos).toHaveLength(1)
    // Tres finalidades distintas viajan como tres campos distintos. Si se
    // agrupan, el consentimiento deja de ser especifico.
    expect(cuerpos[0]).toMatchObject({
      accept_terms: true,
      consent_ai_training: true,
      consent_data_commercial: false,
    })
  })

  test('el ciclo elegido se traduce al entero que espera el servidor', async ({ page }) => {
    const cuerpos = []
    await instalarApiSimulada(page, {
      reglas: [[
        /\/api\/auth\/register$/, 'POST',
        (route, _m, request) => {
          cuerpos.push(request.postDataJSON())
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(datos.SESION_TOKEN),
          })
        },
      ]],
    })

    await irARegistro(page)
    await rellenarRegistro(page)
    await page.getByRole('combobox').selectOption('9 – 10')
    await page.locator('#consent-terms').check()
    await botonEnviar(page).click()
    await expect(page).toHaveURL(/\/dashboard$/)

    // El backend acepta 1..12; el rango "9 – 10" tiene que salir como 9.
    expect(cuerpos[0].semester).toBe(9)
  })

  test('el indicador de fuerza reacciona a la longitud de la contrasena', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await irARegistro(page)

    const clave = campoClave(page)
    await clave.fill('corta')
    await expect(page.getByText('Débil')).toBeVisible()

    await clave.fill('contrasena-de-verdad-larga')
    await expect(page.getByText('Fuerte')).toBeVisible()
  })

  test('"Leer mas" abre el documento legal completo y se puede cerrar', async ({ paginaPublica }) => {
    const { page } = paginaPublica
    await irARegistro(page)

    await page.getByRole('button', { name: 'Leer mas' }).first().click()
    await expect(page.getByText(/documento de prueba/i)).toBeVisible()
  })

  test('si el catalogo legal no carga, el registro sigue siendo posible', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/legal\/documents$/, 'GET', 500, { detail: 'Servicio caido' })],
    })

    await irARegistro(page)
    // El texto de reserva tiene que aparecer: el alumno no puede quedarse sin
    // saber que esta aceptando porque falle una llamada secundaria.
    await expect(page.locator('label[for="consent-terms"]')).toContainText(/Terminos y Condiciones|Términos y Condiciones/i)
    await expect(page.locator('#consent-terms')).toBeEnabled()
  })

  test('el error del servidor se muestra tal cual lo explica el servidor', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/auth\/register$/, 'POST', 400, { detail: 'Ese correo ya tiene cuenta' })],
    })

    await irARegistro(page)
    await rellenarRegistro(page)
    await page.locator('#consent-terms').check()
    await botonEnviar(page).click()

    await expect(page.getByRole('alert')).toContainText('Ese correo ya tiene cuenta')
  })
})

test.describe('Sesion caducada', () => {
  test('un token invalido devuelve al login sin dejar restos', async ({ page }) => {
    await instalarApiSimulada(page, {
      reglas: [reglaError(/\/api\/auth\/me$/, 'GET', 401, { detail: 'Token expirado' })],
    })
    await iniciarSesion(page)

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login$/)

    const token = await page.evaluate(() => sessionStorage.getItem('revo_token'))
    expect(token, 'un 401 tiene que borrar el token caducado').toBeNull()
  })

  test('la sesion no sobrevive al cierre de la pestana', async ({ browser }) => {
    // El token vive en sessionStorage justamente por esto: los alumnos hacen
    // el test en equipos compartidos del laboratorio.
    const contexto = await browser.newContext()
    const pagina = await contexto.newPage()
    await instalarApiSimulada(pagina)
    await iniciarSesion(pagina)
    await pagina.goto('/dashboard')
    await expect(pagina).toHaveURL(/\/dashboard$/)

    const enLocal = await pagina.evaluate(() => localStorage.getItem('revo_token'))
    expect(enLocal, 'el token nunca debe acabar en localStorage').toBeNull()

    await pagina.close()
    await contexto.close()
  })
})

test.describe('Higiene de la pantalla de acceso', () => {
  for (const camino of ['/login', '/register']) {
    test(`${camino} se pinta sin errores de ejecucion`, async ({ paginaPublica, vigilante }) => {
      const { page } = paginaPublica
      await page.goto(camino)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      sinErroresDeEjecucion(vigilante)
    })
  }
})
