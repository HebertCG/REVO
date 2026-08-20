import test from 'node:test'
import assert from 'node:assert/strict'

import {
  advanceRoadState,
  chooseQuestionnaireMiniGame,
  createRoadState,
  getRoadTargetLane,
} from './questionnaireMiniGames.js'

test('elige de forma determinista uno de los dos minijuegos', () => {
  assert.equal(chooseQuestionnaireMiniGame(0.12), 'cards')
  assert.equal(chooseQuestionnaireMiniGame(0.72), 'road')
})

test('distribuye las paradas entre los tres carriles', () => {
  assert.deepEqual([0, 1, 2, 3, 4].map(getRoadTargetLane), [0, 1, 2, 0, 1])
})

test('permite dirigir el carrito con izquierda y derecha', () => {
  const initial = createRoadState()
  const left = advanceRoadState(initial, 'left', 0)
  const right = advanceRoadState(left, 'right', 0)

  assert.equal(left.lane, 0)
  assert.equal(right.lane, 1)
})

test('detiene el carrito en el control si esta en el carril incorrecto', () => {
  const state = { ...createRoadState(), lane: 1, progress: 82 }
  const blocked = advanceRoadState(state, 'accelerate', 2)

  assert.equal(blocked.progress, 84)
  assert.equal(blocked.blocked, true)
  assert.equal(blocked.completed, false)
})

test('alcanza la parada y completa la ruta desde el carril correcto', () => {
  const state = { ...createRoadState(), lane: 2, progress: 84 }
  let driven = state
  while (!driven.completed) {
    driven = advanceRoadState(driven, 'accelerate', 2)
  }

  assert.equal(driven.progress, 100)
  assert.equal(driven.completed, true)
  assert.equal(driven.blocked, false)
})
