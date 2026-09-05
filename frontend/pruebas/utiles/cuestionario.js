import { expect } from '@playwright/test'
import {
  MINI_GAMES,
  advanceRoadState,
  createRoadState,
  getRoadObstacles,
  getRoadTargetLane,
} from '../../src/pages/questionnaireMiniGames.js'

/**
 * Utilidades para conducir el cuestionario desde una prueba.
 *
 * Dos problemas que resolver, los dos de la misma naturaleza:
 *
 * 1. El cuestionario sortea uno de tres minijuegos con `Math.random()`. Una
 *    prueba que dependa del sorteo pasa dos de cada tres veces, que es peor
 *    que no tenerla. Aqui se fija el sorteo antes de que arranque React.
 *
 * 2. Entre una pregunta y la siguiente hay animaciones y temporizadores. Si
 *    la prueba mira "hay una pregunta en pantalla" puede estar viendo la
 *    ANTERIOR, todavia saliendo. Por eso todo se ancla al marcador
 *    (`aria-label="Carta 3 de 10"`), que es el unico dato de la pantalla que
 *    identifica sin ambiguedad en que pregunta estamos.
 */

const VALOR_ALEATORIO = {
  [MINI_GAMES.CARDS]: 0.1,
  [MINI_GAMES.ROAD]: 0.5,
  [MINI_GAMES.ARCADE]: 0.9,
}

// Cualquiera distinto del elegido sirve para no disparar la rama que evita
// repetir minijuego dos veces seguidas.
const ANTERIOR_DISTINTO = {
  [MINI_GAMES.CARDS]: MINI_GAMES.ROAD,
  [MINI_GAMES.ROAD]: MINI_GAMES.ARCADE,
  [MINI_GAMES.ARCADE]: MINI_GAMES.CARDS,
}

export { MINI_GAMES }

/** Fija el minijuego que va a salir en el sorteo. */
export async function forzarMinijuego(page, juego = MINI_GAMES.CARDS) {
  await page.addInitScript(({ valor, anterior }) => {
    Math.random = () => valor
    sessionStorage.setItem('revo_last_minigame', anterior)
  }, { valor: VALOR_ALEATORIO[juego], anterior: ANTERIOR_DISTINTO[juego] })
}

/**
 * Recorre selector -> introduccion -> partida.
 *
 * La pantalla de carga tiene un minimo de 3,2 s por diseno
 * (`CARGA_INICIAL_MIN_MS`), asi que la espera es generosa a proposito.
 */
export async function entrarAlJuego(page) {
  const jugar = page.getByRole('button', { name: 'Jugar' })
  await expect(jugar).toBeEnabled({ timeout: 25_000 })
  await jugar.click()

  const empezar = page.locator('.quiz-intro-boton')
  await expect(empezar).toBeVisible()
  await empezar.click()
}

/** Espera a que el marcador anuncie la pregunta numero `numero` (desde 1). */
export async function esperarPregunta(page, numero) {
  await expect(page.locator('.quiz-marcador')).toHaveAttribute(
    'aria-label',
    new RegExp(`\\b${numero} de \\d+$`),
    { timeout: 25_000 },
  )
}

/** Espera a que la mano acabe de barajar y las cartas se puedan pulsar. */
export async function esperarManoLista(page) {
  await expect(page.locator('.quiz-carta-pregunta').first()).toBeEnabled({ timeout: 20_000 })
}

/**
 * Deja a la vista la pregunta numero `numero`.
 *
 * Una pregunta ya respondida no vuelve a esconderse tras la carta, asi que
 * primero se comprueba el marcador y solo se destapa si hace falta.
 */
export async function destaparCarta(page, numero = 1) {
  await esperarPregunta(page, numero)

  const pregunta = page.locator('h1.quiz-pregunta')
  if (await pregunta.isVisible()) return

  await esperarManoLista(page)
  await page.locator('.quiz-carta-pregunta').first().click()
  await expect(pregunta).toBeVisible({ timeout: 15_000 })
}

/** Responde la pregunta visible con un valor de la escala 1..5. */
export async function responderEscala(page, valor = 4) {
  const opcion = page.locator(`.quiz-escala button[data-v="${valor}"]`)
  await opcion.click()
  await expect(opcion).toHaveAttribute('aria-checked', 'true')
}

/** Pulsa el boton que avanza (su texto cambia segun el minijuego y la fase). */
export async function avanzar(page) {
  const boton = page.locator('.quiz-btn-pri')
  await expect(boton).toBeEnabled()
  await boton.click()
}

/** Contesta una fase entera de escala Likert, pregunta a pregunta. */
export async function responderFaseCompleta(page, total, valor = 4) {
  for (let numero = 1; numero <= total; numero++) {
    await destaparCarta(page, numero)
    await responderEscala(page, valor)
    await avanzar(page)
  }
}

/**
 * Calcula la secuencia de acciones que lleva el coche a la meta.
 *
 * En vez de pulsar "acelerar" a ciegas y esperar suerte, se simula la misma
 * maquina de estados que usa la pantalla (`advanceRoadState`, ya cubierta por
 * las pruebas unitarias) hasta encontrar un camino que esquive los obstaculos
 * y llegue al carril correcto. Asi la prueba comprueba que la interfaz
 * responde a los controles, no que el azar la deje pasar.
 */
export function resolverRuta(questionIndex = 0) {
  const objetivo = getRoadTargetLane(questionIndex)
  const obstaculos = getRoadObstacles(questionIndex)
  const acciones = []
  let estado = createRoadState()

  for (let paso = 0; paso < 200 && !estado.completed; paso++) {
    const carrilLibre = [0, 1, 2].find((carril) => {
      const prueba = advanceRoadState({ ...estado, lane: carril }, 'accelerate', objetivo, obstaculos)
      return !prueba.collision && !prueba.blocked
    })

    if (carrilLibre === undefined) {
      throw new Error(`Ruta sin salida en el paso ${paso} de la pregunta ${questionIndex}`)
    }

    while (estado.lane !== carrilLibre) {
      const accion = estado.lane > carrilLibre ? 'up' : 'down'
      acciones.push(accion)
      estado = advanceRoadState(estado, accion, objetivo, obstaculos)
    }

    acciones.push('accelerate')
    estado = advanceRoadState(estado, 'accelerate', objetivo, obstaculos)
  }

  if (!estado.completed) throw new Error(`No se llego a la meta en la pregunta ${questionIndex}`)
  return acciones
}

const BOTON_RUTA = {
  up: 'button.arriba',
  down: 'button.abajo',
  accelerate: 'button.acelerar',
  reverse: 'button.frenar',
}

/** Conduce hasta la meta y deja la pregunta a la vista. */
export async function completarRuta(page, questionIndex = 0) {
  for (const accion of resolverRuta(questionIndex)) {
    await page.locator(`.quiz-controles-ruta ${BOTON_RUTA[accion]}`).click()
  }
  await expect(page.locator('h1.quiz-pregunta')).toBeVisible({ timeout: 15_000 })
}
