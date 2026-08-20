import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ARCADE_ENEMY_COUNT,
  ARCADE_MIN_PLAY_MS,
  advanceArcadeWave,
  createArcadeState,
  fireArcadeShot,
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

test('esperar mueve a los enemigos pero no suma progreso automaticamente', () => {
  const initial = createArcadeState()
  const firstAdvance = advanceArcadeWave(initial)
  let advanced = firstAdvance
  for (let tick = 0; tick < 20; tick += 1) advanced = advanceArcadeWave(advanced)

  assert.equal(advanced.score, 0)
  assert.equal(advanced.enemies.length, ARCADE_ENEMY_COUNT)
  assert.notDeepEqual(firstAdvance.enemies, initial.enemies)
  assert.equal(advanced.completed, false)
})

test('la formacion enemiga genera sus propios disparos', () => {
  const firstAdvance = advanceArcadeWave(createArcadeState())
  const secondAdvance = advanceArcadeWave(firstAdvance)

  assert.equal(secondAdvance.enemyShots.length, 1)
})

test('disparar alineado destruye una nave y activa la recarga', () => {
  const initial = createArcadeState()
  const fired = fireArcadeShot(initial)
  const repeated = fireArcadeShot(fired)

  assert.equal(fired.enemies.length, ARCADE_ENEMY_COUNT - 1)
  assert.equal(fired.score, 1)
  assert.equal(fired.shotsFired, 1)
  assert.equal(repeated.shotsFired, 1)
})

test('los enemigos disparan y un impacto reduce el escudo sin provocar game over', () => {
  const initial = {
    ...createArcadeState(),
    shield: 1,
    enemyShots: [{ id: 'impacto', column: 2, row: 2 }],
  }
  const hit = advanceArcadeWave(initial)

  assert.equal(hit.hits, 1)
  assert.equal(hit.shield, 1)
  assert.equal(hit.assist, true)
  assert.equal(hit.completed, false)
})

test('solo derrotar toda la flota completa la oleada y no altera respuestas', () => {
  let state = createArcadeState()
  while (!state.completed) {
    state = { ...state, column: state.enemies[0].column, shotCooldown: 0 }
    state = fireArcadeShot(state)
  }

  assert.equal(state.score, ARCADE_ENEMY_COUNT)
  assert.equal(state.enemies.length, 0)
  assert.equal(state.completed, true)
  assert.equal('answer' in state, false)
})
