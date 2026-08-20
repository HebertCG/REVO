import test from 'node:test'
import assert from 'node:assert/strict'

import { shouldStartQuestionShuffle } from './questionnaireAnimation.js'

test('no inicia el reparto mientras la pantalla de carga sigue visible', () => {
  assert.equal(shouldStartQuestionShuffle({
    loading: true,
    submitting: false,
    transitioning: false,
    questionId: 1,
    answered: false,
  }), false)
})

test('inicia el reparto de la primera carta al cerrar la carga', () => {
  assert.equal(shouldStartQuestionShuffle({
    loading: false,
    submitting: false,
    transitioning: false,
    questionId: 1,
    answered: false,
  }), true)
})

test('no reinicia el reparto de preguntas ya respondidas ni durante transiciones', () => {
  assert.equal(shouldStartQuestionShuffle({
    loading: false,
    submitting: false,
    transitioning: false,
    questionId: 1,
    answered: true,
  }), false)

  assert.equal(shouldStartQuestionShuffle({
    loading: false,
    submitting: false,
    transitioning: true,
    questionId: 1,
    answered: false,
  }), false)
})
