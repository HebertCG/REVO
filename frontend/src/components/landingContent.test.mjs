import test from 'node:test'
import assert from 'node:assert/strict'

import {
  LANDING_BRANCHES,
  LANDING_PHASES,
  LANDING_ROUTE_GROUPS,
  getLandingCta,
  getQuestionBreakdown,
} from './landingContent.js'

test('mantiene las tres fases y las 29 preguntas del cuestionario', () => {
  assert.equal(LANDING_PHASES.length, 3)
  assert.deepEqual(LANDING_PHASES.map((phase) => phase.questions), [10, 15, 4])
  assert.deepEqual(getQuestionBreakdown(), {
    total: 29,
    bank: 100,
    skipped: 71,
  })
})

test('presenta las diez rutas profesionales sin duplicados', () => {
  assert.equal(LANDING_BRANCHES.length, 10)
  assert.equal(new Set(LANDING_BRANCHES.map((branch) => branch.name)).size, 10)
})

test('el mapa editorial incluye cada especialización exactamente una vez', () => {
  const mappedRoutes = LANDING_ROUTE_GROUPS.flatMap((group) => group.routes)
  const expectedRoutes = LANDING_BRANCHES.map((branch) => branch.name)

  assert.equal(LANDING_ROUTE_GROUPS.length, 5)
  assert.deepEqual([...mappedRoutes].sort(), [...expectedRoutes].sort())
  assert.equal(new Set(mappedRoutes).size, 10)
})

test('envía a registro a visitantes y al cuestionario a usuarios con sesión', () => {
  assert.deepEqual(getLandingCta(false), {
    to: '/register',
    label: 'Crear cuenta y empezar',
  })
  assert.deepEqual(getLandingCta(true), {
    to: '/questionnaire',
    label: 'Continuar al cuestionario',
  })
})
