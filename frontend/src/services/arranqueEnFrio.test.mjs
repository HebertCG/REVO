import test from 'node:test'
import assert from 'node:assert/strict'

import {
  MAX_REINTENTOS,
  esArranqueEnFrio,
  esReintentable,
  esperaAntesDeReintentar,
} from './arranqueEnFrio.js'

/** Error de axios con respuesta del servidor. */
const conEstado = (status, method = 'get') => ({
  response: { status },
  config: { method },
})

/** Error de axios sin respuesta (no llego nadie a contestar). */
const sinRespuesta = (code, method = 'get') => ({ code, config: { method } })

// ── Que cuenta como arranque en frio ──────────────────────

test('trata el 502 de Vercel como arranque en frio, no como servicio roto', () => {
  assert.equal(esArranqueEnFrio(conEstado(502)), true)
  assert.equal(esArranqueEnFrio(conEstado(503)), true)
  assert.equal(esArranqueEnFrio(conEstado(504)), true)
})

test('no confunde un fallo de la aplicacion con un arranque', () => {
  // El 500 sale de codigo que si se ejecuto: repetirlo da lo mismo.
  assert.equal(esArranqueEnFrio(conEstado(500)), false)
  assert.equal(esArranqueEnFrio(conEstado(401)), false)
  assert.equal(esArranqueEnFrio(conEstado(429)), false)
})

test('cuenta el timeout como arranque pero deja fuera al alumno sin conexion', () => {
  assert.equal(esArranqueEnFrio(sinRespuesta('ECONNABORTED')), true)
  assert.equal(esArranqueEnFrio(sinRespuesta('ERR_NETWORK')), false)
})

// ── Que se puede repetir ──────────────────────────────────

test('reintenta una lectura mientras queden intentos', () => {
  assert.equal(esReintentable(conEstado(502), 0), true)
  assert.equal(esReintentable(conEstado(502), MAX_REINTENTOS - 1), true)
})

test('se rinde al agotar los intentos en vez de reintentar para siempre', () => {
  assert.equal(esReintentable(conEstado(502), MAX_REINTENTOS), false)
})

test('nunca repite un registro: el primero pudo crear la cuenta', () => {
  assert.equal(esReintentable(conEstado(502, 'post'), 0), false)
  assert.equal(esReintentable(conEstado(502, 'put'), 0), false)
  assert.equal(esReintentable(conEstado(502, 'delete'), 0), false)
})

// ── Cuanto se espera ──────────────────────────────────────

test('espera cada vez mas, con un techo que no desespere al alumno', () => {
  assert.deepEqual(
    [0, 1, 2, 3].map(esperaAntesDeReintentar),
    [4000, 8000, 15000, 15000],
  )
})

test('los intentos cubren el arranque en frio mas lento de Render', () => {
  // Render tarda hasta ~60s, y aqui hay dos servicios encadenados. Cada
  // intento aguanta ~30s (lo que espera Vercel) mas la pausa siguiente.
  const esperas = Array.from({ length: MAX_REINTENTOS }, (_, i) => esperaAntesDeReintentar(i))
  const totalMs = esperas.reduce((a, b) => a + b, 0) + (MAX_REINTENTOS + 1) * 30000

  assert.ok(totalMs >= 120000, `los intentos solo cubren ${totalMs / 1000}s`)
})
