import test from 'node:test'
import assert from 'node:assert/strict'

import {
  advanceRoadState,
  chooseQuestionnaireMiniGame,
  createRoadState,
  getRoadTargetLane,
  resolveQuestionnaireEntryView,
} from './questionnaireMiniGames.js'

test('elige de forma determinista uno de los dos minijuegos', () => {
  assert.equal(chooseQuestionnaireMiniGame(0.12), 'cards')
  assert.equal(chooseQuestionnaireMiniGame(0.72), 'road')
})

test('evita repetir el mismo minijuego dos entradas seguidas', () => {
  assert.equal(chooseQuestionnaireMiniGame(0.12, 'cards'), 'road')
  assert.equal(chooseQuestionnaireMiniGame(0.72, 'road'), 'cards')
})

test('muestra primero el selector aunque las preguntas sigan cargando', () => {
  assert.equal(resolveQuestionnaireEntryView({
    stage: 'selecting',
    miniGame: null,
    loading: true,
    hasQuestion: false,
  }), 'selector')
})

test('espera el boton Jugar antes de abrir el banner del minijuego', () => {
  assert.equal(resolveQuestionnaireEntryView({
    stage: 'selected',
    miniGame: 'road',
    loading: false,
    hasQuestion: true,
  }), 'selected')
  assert.equal(resolveQuestionnaireEntryView({
    stage: 'intro',
    miniGame: 'road',
    loading: false,
    hasQuestion: true,
  }), 'intro')
  assert.equal(resolveQuestionnaireEntryView({
    stage: 'playing',
    miniGame: 'road',
    loading: false,
    hasQuestion: true,
  }), 'game')
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
