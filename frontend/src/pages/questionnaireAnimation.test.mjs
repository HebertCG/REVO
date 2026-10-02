import test from 'node:test'
import assert from 'node:assert/strict'

import {
  PHASE_TRANSITION_MIN_MS,
  getRemainingPhaseTransitionMs,
  shouldStartPhaseShuffle,
} from './questionnaireAnimation.js'

test('no inicia el reparto mientras la pantalla de carga sigue visible', () => {
  assert.equal(shouldStartPhaseShuffle({
    loading: true,
    submitting: false,
    transitioning: false,
    phase: 1,
    unlocked: false,
  }), false)
})

test('inicia un unico reparto al comenzar una fase bloqueada', () => {
  assert.equal(shouldStartPhaseShuffle({
    loading: false,
    submitting: false,
    transitioning: false,
    phase: 1,
    unlocked: false,
  }), true)
})

test('no reinicia el reparto dentro de una fase ya desbloqueada', () => {
  assert.equal(shouldStartPhaseShuffle({
    loading: false,
    submitting: false,
    transitioning: false,
    phase: 1,
    unlocked: true,
  }), false)

  assert.equal(shouldStartPhaseShuffle({
    loading: false,
    submitting: false,
    transitioning: true,
    phase: 2,
    unlocked: false,
  }), false)
})

test('mantiene visible la transicion de fase durante al menos 2.6 segundos', () => {
  assert.equal(PHASE_TRANSITION_MIN_MS, 2600)
  assert.equal(getRemainingPhaseTransitionMs(180), 2420)
})

test('no agrega espera cuando la carga de la fase ya supero el minimo', () => {
  assert.equal(getRemainingPhaseTransitionMs(3100), 0)
})
