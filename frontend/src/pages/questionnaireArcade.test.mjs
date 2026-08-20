import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ARCADE_TARGET_SCORE,
  ARCADE_MIN_PLAY_MS,
  activateArcadePulse,
  advanceArcadeWave,
  createArcadeState,
  getArcadeThreats,
  getArcadeRemainingPlayMs,
  moveArcadeShip,
} from './questionnaireArcade.js'

test('mantiene la oleada visible un tiempo minimo antes de abrir la pregunta', () => {
  assert.equal(ARCADE_MIN_PLAY_MS >= 10000, true)
  assert.equal(getArcadeRemainingPlayMs(900), ARCADE_MIN_PLAY_MS - 900)
  assert.equal(getArcadeRemainingPlayMs(ARCADE_MIN_PLAY_MS + 500), 0)
})

test('mueve la nave en las cuatro direcciones sin salir de la arena', () => {
  const initial = createArcadeState()
  const up = moveArcadeShip(initial, 'up')
  const left = moveArcadeShip(up, 'left')
  const down = moveArcadeShip(left, 'down')
  const right = moveArcadeShip(down, 'right')

  assert.deepEqual({ column: up.column, row: up.row }, { column: 2, row: 2 })
  assert.deepEqual({ column: left.column, row: left.row }, { column: 1, row: 2 })
  assert.deepEqual({ column: down.column, row: down.row }, { column: 1, row: 3 })
  assert.deepEqual({ column: right.column, row: right.row }, { column: 2, row: 3 })
})

test('crea amenazas deterministas que cambian entre preguntas', () => {
  assert.notDeepEqual(getArcadeThreats(0, 0), getArcadeThreats(1, 0))
  assert.equal(getArcadeThreats(0, 0).length, 2)
})

test('un impacto reduce escudo pero nunca provoca game over', () => {
  const initial = { ...createArcadeState(), shield: 1 }
  const hit = advanceArcadeWave(initial, [{ column: initial.column, row: initial.row }])

  assert.equal(hit.hits, 1)
  assert.equal(hit.shield, 1)
  assert.equal(hit.assist, true)
  assert.equal(hit.completed, false)
})

test('el pulso evita una amenaza y entra en enfriamiento', () => {
  const initial = createArcadeState()
  const pulsed = activateArcadePulse(initial)
  const advanced = advanceArcadeWave(pulsed, [{ column: initial.column, row: initial.row }])

  assert.equal(pulsed.pulseCooldown > 0, true)
  assert.equal(advanced.hits, 0)
})

test('la oleada termina por puntuacion y no altera ninguna respuesta', () => {
  let state = createArcadeState()
  while (!state.completed) state = advanceArcadeWave(state, [])

  assert.equal(state.score, ARCADE_TARGET_SCORE)
  assert.equal(state.completed, true)
  assert.equal('answer' in state, false)
})
