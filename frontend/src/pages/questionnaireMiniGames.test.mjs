import test from 'node:test'
import assert from 'node:assert/strict'

import {
  advanceRoadState,
  chooseQuestionnaireMiniGame,
  createRoadState,
  getRoadObstacles,
  getRoadTargetLane,
  resolveQuestionnaireEntryView,
} from './questionnaireMiniGames.js'

test('elige de forma determinista uno de los tres minijuegos', () => {
  assert.equal(chooseQuestionnaireMiniGame(0.12), 'cards')
  assert.equal(chooseQuestionnaireMiniGame(0.45), 'road')
  assert.equal(chooseQuestionnaireMiniGame(0.85), 'arcade')
})

test('evita repetir el mismo minijuego dos entradas seguidas', () => {
  assert.equal(chooseQuestionnaireMiniGame(0.12, 'cards'), 'road')
  assert.equal(chooseQuestionnaireMiniGame(0.45, 'road'), 'arcade')
  assert.equal(chooseQuestionnaireMiniGame(0.85, 'arcade'), 'cards')
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

test('usa arriba y abajo para cambiar entre los tres carriles', () => {
  const initial = createRoadState()
  const up = advanceRoadState(initial, 'up', 0)
  const down = advanceRoadState(up, 'down', 0)

  assert.equal(up.lane, 0)
  assert.equal(down.lane, 1)
})

test('usa derecha para avanzar e izquierda para frenar o retroceder', () => {
  const initial = createRoadState()
  const forward = advanceRoadState(initial, 'right', 0)
  const reverse = advanceRoadState(forward, 'left', 0)

  assert.ok(forward.progress > initial.progress)
  assert.ok(reverse.progress < forward.progress)
})

test('genera obstaculos variados y penaliza una colision', () => {
  const obstacles = getRoadObstacles(0)
  const obstacle = obstacles[0]
  const state = { ...createRoadState(), lane: obstacle.lane, progress: obstacle.progress - 8 }
  const crashed = advanceRoadState(state, 'right', 0, obstacles)

  assert.equal(obstacles.length, 3)
  assert.equal(crashed.collision, true)
  assert.ok(crashed.progress < obstacle.progress)
})

test('detiene el carrito en el control si esta en el carril incorrecto', () => {
  const state = { ...createRoadState(), lane: 1, progress: 82 }
  const blocked = advanceRoadState(state, 'right', 2)

  assert.equal(blocked.progress, 84)
  assert.equal(blocked.blocked, true)
  assert.equal(blocked.completed, false)
})

test('alcanza la parada y completa la ruta desde el carril correcto', () => {
  const state = { ...createRoadState(), lane: 2, progress: 84 }
  let driven = state
  while (!driven.completed) {
    driven = advanceRoadState(driven, 'right', 2)
  }

  assert.equal(driven.progress, 100)
  assert.equal(driven.completed, true)
  assert.equal(driven.blocked, false)
})
