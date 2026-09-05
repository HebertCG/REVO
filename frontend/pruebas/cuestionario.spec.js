import { test, expect, sinErroresDeEjecucion, esperarEstable } from './utiles/fixtures.js'
import { instalarApiSimulada, iniciarSesion, reglaError, reglaSinRed } from './utiles/apiSimulada.js'
import {
  MINI_GAMES, forzarMinijuego, entrarAlJuego, destaparCarta,
  responderEscala, avanzar, responderFaseCompleta, esperarManoLista,
  esperarPregunta, completarRuta,
} from './utiles/cuestionario.js'
import { elementosDesbordados, objetivosTactilesPequenos, detallar } from './utiles/inspector.js'
import * as datos from './utiles/datos.js'

/**
 * Cuestionario.
 *
 * Es la pantalla mas grande de REVO (1400 lineas) y la unica con maquina de
 * estados: sorteo de minijuego -> introduccion -> partida -> fase 2 -> perfil
 * profesional. Cada transicion depende de temporizadores, de tres respuestas
 * distintas del servidor y de una animacion, y es donde un alumno se puede
 * quedar encallado a mitad del test sin manera de salir.
 *
 * El sorteo del minijuego se fija en cada prueba (ver utiles/cuestionario.js):
 * sin eso, la misma prueba recorre un camino distinto cada vez.
 */

const abrirCuestionario = async (page, opciones = {}, juego = MINI_GAMES.CARDS) => {
  const { registro } = await instalarApiSimulada(page, opciones)
  await iniciarSesion(page)
  await forzarMinijuego(page, juego)
  await page.goto('/questionnaire')
  return registro
}

test.describe('Arranque de la partida', () => {
  test('crea una sesion y pide las preguntas de esa sesion, no el banco entero', async ({ page }) => {
    const registro = await abrirCuestionario(page)
    await entrarAlJuego(page)

    const rutas = registro.llamadas.map((l) => `${l.metodo} ${l.ruta}`)
    expect(rutas).toContain('POST /api/sessions/')
    expect(rutas.some((r) => /GET \/api\/sessions\/\d+\/questions/.test(r))).toBe(true)

    // Pedir /questions/ entero descargaria el banco de 100 preguntas al
    // navegador, que es justo lo que la seleccion por sesion evita.
    expect(rutas).not.toContain('GET /api/questions/')
  })

  test('el sorteo termina siempre en un minijuego jugable', async ({ page }) => {
    await abrirCuestionario(page)

    await expect(page.getByText('Desafío seleccionado')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('button', { name: 'Jugar' })).toBeEnabled({ timeout: 20_000 })
  })

  test('la introduccion explica el minijuego antes de empezar', async ({ page }) => {
    await abrirCuestionario(page)

    await expect(page.getByRole('button', { name: 'Jugar' })).toBeEnabled({ timeout: 20_000 })
    await page.getByRole('button', { name: 'Jugar' }).click()

    await expect(page.locator('.quiz-intro-pasos li')).not.toHaveCount(0)
    await expect(page.locator('.quiz-intro-boton')).toBeVisible()
  })

  test('mientras se preparan las preguntas el boton lo dice y no engana', async ({ page }) => {
    // El retardo tiene que superar el minimo de 3,2 s de la pantalla de
    // carga; con menos, las preguntas ya han llegado cuando el boton aparece
    // y no queda ventana que observar.
    await abrirCuestionario(page, { retardoMs: 6000 })

    // No puede quedar habilitado antes de tiempo: pulsarlo entonces lleva a
    // una partida sin preguntas.
    const boton = page.getByRole('button', { name: /preparando preguntas/i })
    await expect(boton).toBeVisible({ timeout: 15_000 })
    await expect(boton).toBeDisabled()
  })
})

test.describe('Responder la fase 1', () => {
  test('la carta destapa la pregunta y la escala acepta una respuesta', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)
    await destaparCarta(page, 1)

    const pregunta = page.locator('h1.quiz-pregunta')
    await expect(pregunta).toContainText(datos.PREGUNTAS_FASE1[0].text)

    // Sin responder, avanzar tiene que estar bloqueado.
    await expect(page.locator('.quiz-btn-pri')).toBeDisabled()

    await responderEscala(page, 4)
    await expect(page.locator('.quiz-escala button[data-v="4"]')).toHaveAttribute('aria-checked', 'true')
    await expect(page.locator('.quiz-btn-pri')).toBeEnabled()
  })

  test('cada respuesta se guarda en el servidor segun se contesta', async ({ page }) => {
    const registro = await abrirCuestionario(page)
    await entrarAlJuego(page)
    await destaparCarta(page, 1)
    await responderEscala(page, 5)
    await avanzar(page)

    await expect.poll(() =>
      registro.llamadas.filter((l) => /\/sessions\/\d+\/answers$/.test(l.ruta)).length,
    ).toBeGreaterThan(0)
  })

  test('el marcador avanza con cada pregunta', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)

    await destaparCarta(page, 1)
    await responderEscala(page, 3)
    await avanzar(page)

    await destaparCarta(page, 2)
    await expect(page.locator('.quiz-marcador')).toHaveAttribute('aria-label', /Carta 2 de 10/)
  })

  test('se puede volver a la pregunta anterior y la respuesta sigue ahi', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)

    await destaparCarta(page, 1)
    await responderEscala(page, 2)
    await avanzar(page)

    await destaparCarta(page, 2)
    await page.locator('.quiz-btn-sec').click()
    await esperarPregunta(page, 1)

    // Una pregunta ya respondida no se vuelve a esconder tras la carta.
    await expect(page.locator('h1.quiz-pregunta')).toContainText(datos.PREGUNTAS_FASE1[0].text)
    await expect(page.locator('.quiz-escala button[data-v="2"]')).toHaveAttribute('aria-checked', 'true')
  })

  test('en la primera pregunta el boton anterior esta desactivado', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)
    await destaparCarta(page, 1)

    await expect(page.locator('.quiz-btn-sec')).toBeDisabled()
  })
})

test.describe('Atajos de teclado', () => {
  test('los numeros 1 a 5 eligen en la escala y Enter avanza', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)
    await esperarManoLista(page)

    // Con la mano lista, un numero elige carta. Hay que esperar a que la
    // carta acabe de girar antes de que el mismo atajo signifique otra cosa.
    await page.keyboard.press('1')
    await expect(page.locator('h1.quiz-pregunta')).toBeVisible()

    await page.keyboard.press('5')
    await expect(page.locator('.quiz-escala button[data-v="5"]')).toHaveAttribute('aria-checked', 'true')

    await page.keyboard.press('Enter')
    await esperarPregunta(page, 2)
  })

  test('la flecha izquierda vuelve a la pregunta anterior', async ({ page }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)
    await esperarManoLista(page)

    await page.keyboard.press('1')
    await expect(page.locator('h1.quiz-pregunta')).toBeVisible()
    await page.keyboard.press('4')
    await expect(page.locator('.quiz-escala button[data-v="4"]')).toHaveAttribute('aria-checked', 'true')
    await page.keyboard.press('Enter')
    await esperarPregunta(page, 2)

    // `manejarTecla` descarta cualquier tecla que no sea 1-5 mientras la
    // pregunta siga escondida tras el minijuego, y al avanzar la siguiente
    // SIEMPRE nace escondida. Asi que el atajo de retroceso solo funciona si
    // se destapa antes la carta.
    await page.keyboard.press('ArrowLeft')
    await esperarPregunta(page, 1)
  })
})

test.describe('Paso de fase', () => {
  test('al terminar la fase 1 se anuncia la fase 2 y llegan preguntas nuevas', async ({ page }) => {
    test.slow()
    await abrirCuestionario(page)
    await entrarAlJuego(page)

    await responderFaseCompleta(page, datos.PREGUNTAS_FASE1.length)

    await expect(page.getByText('Nueva ronda desbloqueada')).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.quiz-fases')).toBeVisible({ timeout: 20_000 })
  })

  test('el cuestionario completo termina en el perfil profesional', async ({ page }) => {
    test.slow()
    // Fase 2 devuelve preguntas distintas: si el simulador repitiera las de
    // fase 1, esta prueba pasaria sin comprobar el cambio de banco.
    await instalarApiSimulada(page, { preguntas: datos.PREGUNTAS_FASE1 })
    await iniciarSesion(page)
    await forzarMinijuego(page, MINI_GAMES.CARDS)
    await page.goto('/questionnaire')

    await entrarAlJuego(page)
    await responderFaseCompleta(page, datos.PREGUNTAS_FASE1.length)

    // Fase 2, mismo banco simulado.
    await expect(page.locator('.quiz-fases')).toBeVisible({ timeout: 25_000 })
    await responderFaseCompleta(page, datos.PREGUNTAS_FASE1.length)

    // Fase 3: preguntas psicometricas con opciones A-D. El sello
    // "Perfil profesional" solo se pinta con la pregunta ya destapada, asi
    // que primero se comprueba la fase por el paso activo del HUD.
    await expect(page.locator('.quiz-fases')).toHaveAttribute('aria-label', 'Fase 3 de 3', { timeout: 30_000 })
    await destaparCarta(page, 1)
    await expect(page.locator('.quiz-ops button[role="radio"]')).toHaveCount(4)
  })
})

test.describe('Cuando el servidor falla', () => {
  /**
   * Un fallo al preparar la partida tiene que dejar al alumno con dos cosas:
   * saber que ha pasado, y poder hacer algo. Quedarse mirando un boton
   * apagado no es ninguna de las dos.
   *
   * El cuestionario tiene una pantalla escrita justo para esto ("No pudimos
   * repartir las cartas", con instruccion de recargar), pero solo se pinta
   * cuando `miniGameStage` vale 'playing', y a ese estado solo se llega
   * pulsando Jugar, que en este caso esta deshabilitado. La pantalla existe
   * y es inalcanzable.
   */
  const exigirSalida = async (page) => {
    await expect(
      page.getByText(/no se pudo preparar|no pudimos repartir las cartas/i),
      'la pantalla no dice que ha fallado',
    ).toBeVisible({ timeout: 20_000 })

    await expect(
      page.getByText(/recarga|vuelve a intentar|revisa tu conexión|inténtalo/i),
      'la pantalla dice que fallo pero no dice que hacer a continuacion',
    ).toBeVisible()
  }

  test('si no se puede crear la sesion se explica y se ofrece salida', async ({ page }) => {
    await abrirCuestionario(page, {
      reglas: [reglaError(/\/api\/sessions\/?$/, 'POST', 500, { detail: 'Servicio caido' })],
    })
    await exigirSalida(page)
  })

  test('sin conexion el cuestionario avisa y ofrece salida', async ({ page }) => {
    await abrirCuestionario(page, {
      reglas: [reglaSinRed(/\/api\/sessions\/?$/, 'POST')],
    })
    await exigirSalida(page)
  })

  test('una sesion sin preguntas no deja al alumno encallado', async ({ page }) => {
    await abrirCuestionario(page, { preguntas: [] })
    await exigirSalida(page)
  })

  test('si fallan las preguntas psicometricas se usa el banco de reserva', async ({ page }) => {
    test.slow()
    await instalarApiSimulada(page, {
      preguntas: datos.PREGUNTAS_FASE1.slice(0, 2),
      reglas: [reglaError(/\/api\/psychometric\/specialization\/\d+$/, 'GET', 500, { detail: 'Caido' })],
    })
    await iniciarSesion(page)
    await forzarMinijuego(page, MINI_GAMES.CARDS)
    await page.goto('/questionnaire')

    await entrarAlJuego(page)
    await responderFaseCompleta(page, 2)
    await expect(page.locator('.quiz-fases')).toBeVisible({ timeout: 25_000 })
    await responderFaseCompleta(page, 2)

    // El banco local de reserva tiene cuatro preguntas: la fase 3 no puede
    // quedarse vacia porque falle una llamada.
    await expect(page.locator('.quiz-fases')).toHaveAttribute('aria-label', 'Fase 3 de 3', { timeout: 30_000 })
    await expect(page.locator('.quiz-marcador')).toHaveAttribute('aria-label', /de 4$/)
    await destaparCarta(page, 1)
    await expect(page.locator('.quiz-ops button[role="radio"]')).toHaveCount(4)
  })
})

test.describe('Minijuegos alternativos', () => {
  test('la ruta llega a su meta con el teclado y destapa la pregunta', async ({ page }) => {
    await abrirCuestionario(page, {}, MINI_GAMES.ROAD)
    await entrarAlJuego(page)

    await expect(page.locator('.quiz-ruta')).toBeVisible()
    await completarRuta(page, 0)
  })

  test('el arcade tiene controles alcanzables con el dedo', async ({ page }) => {
    await abrirCuestionario(page, {}, MINI_GAMES.ARCADE)
    await page.setViewportSize({ width: 375, height: 812 })
    await entrarAlJuego(page)

    await expect(page.locator('.quiz-arcade')).toBeVisible()
    const pequenos = await objetivosTactilesPequenos(page, 24)
    expect(pequenos, detallar('Controles del arcade demasiado pequenos', pequenos)).toEqual([])
  })

  test('los tres minijuegos anuncian su estado a un lector de pantalla', async ({ page }) => {
    for (const juego of [MINI_GAMES.CARDS, MINI_GAMES.ROAD, MINI_GAMES.ARCADE]) {
      const contexto = page
      await abrirCuestionario(contexto, {}, juego)
      await entrarAlJuego(contexto)
      await expect(contexto.locator('[role="status"][aria-live="polite"]').first()).toBeVisible()
    }
  })
})

test.describe('Maquetacion del cuestionario', () => {
  for (const ancho of [320, 375, 768, 1440]) {
    test(`la partida cabe en ${ancho}px`, async ({ page }) => {
      await abrirCuestionario(page)
      await page.setViewportSize({ width: ancho, height: 800 })
      await entrarAlJuego(page)
      await destaparCarta(page, 1)
      await esperarEstable(page)

      const desbordes = await elementosDesbordados(page, 2)
      expect(desbordes, detallar(`El cuestionario se sale a ${ancho}px`, desbordes)).toEqual([])
    })
  }

  test('la escala de respuesta se puede pulsar con el dedo', async ({ page }) => {
    await abrirCuestionario(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await entrarAlJuego(page)
    await destaparCarta(page, 1)

    const pequenos = await objetivosTactilesPequenos(page, 24)
    expect(pequenos, detallar('Controles del cuestionario demasiado pequenos', pequenos)).toEqual([])
  })
})

test.describe('Higiene', () => {
  test('la partida se juega sin errores de ejecucion', async ({ page, vigilante }) => {
    await abrirCuestionario(page)
    await entrarAlJuego(page)
    await destaparCarta(page, 1)
    await responderEscala(page, 4)
    await avanzar(page)
    await esperarEstable(page)

    sinErroresDeEjecucion(vigilante)
  })
})
