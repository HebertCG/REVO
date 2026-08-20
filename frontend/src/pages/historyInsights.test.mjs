import test from 'node:test'
import assert from 'node:assert/strict'

import { buildHistorySeries, buildHistorySummary } from './historyInsights.js'

const history = [
  {
    prediction_id: 3,
    specialization: 'Data Science & IA',
    confidence_pct: 64,
    created_at: '2026-08-20T10:00:00',
  },
  {
    prediction_id: 2,
    specialization: 'Desarrollo de Software',
    confidence_pct: 50,
    created_at: '2026-08-19T10:00:00',
  },
  {
    prediction_id: 1,
    specialization: 'Diseño UX/UI',
    confidence_pct: 40,
    created_at: '2026-08-18T10:00:00',
  },
]

test('resume la trayectoria sin alterar el orden recibido por la API', () => {
  assert.deepEqual(buildHistorySummary(history), {
    total: 3,
    average: 51,
    latestConfidence: 64,
    delta: 24,
    trend: 'up',
  })
  assert.deepEqual(history.map((item) => item.prediction_id), [3, 2, 1])
})

test('construye la serie de la gráfica de antiguo a reciente', () => {
  const series = buildHistorySeries(history)

  assert.deepEqual(series.map((item) => item.id), [1, 2, 3])
  assert.deepEqual(series.map((item) => item.confidence), [40, 50, 64])
})

test('devuelve un resumen estable cuando todavía no hay evaluaciones', () => {
  assert.deepEqual(buildHistorySummary([]), {
    total: 0,
    average: 0,
    latestConfidence: 0,
    delta: 0,
    trend: 'steady',
  })
})
