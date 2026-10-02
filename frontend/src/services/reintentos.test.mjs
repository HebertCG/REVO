import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ESPERA_MS,
  MAX_REINTENTOS,
  esFalloPasajero,
  esReintentable,
} from './reintentos.js'

const conEstado = (status, method = 'get') => ({
  response: { status },
  config: { method },
})

const sinRespuesta = (code, method = 'get') => ({ code, config: { method } })

test('reconoce cortes pasajeros del proxy y timeouts', () => {
  assert.equal(esFalloPasajero(conEstado(502)), true)
  assert.equal(esFalloPasajero(conEstado(503)), true)
  assert.equal(esFalloPasajero(conEstado(504)), true)
  assert.equal(esFalloPasajero(sinRespuesta('ECONNABORTED')), true)
})

test('no confunde errores de aplicacion o de red con un corte pasajero', () => {
  assert.equal(esFalloPasajero(conEstado(500)), false)
  assert.equal(esFalloPasajero(conEstado(401)), false)
  assert.equal(esFalloPasajero(conEstado(429)), false)
  assert.equal(esFalloPasajero(sinRespuesta('ERR_NETWORK')), false)
})

test('reintenta una lectura como maximo una vez', () => {
  assert.equal(MAX_REINTENTOS, 1)
  assert.equal(esReintentable(conEstado(502), 0), true)
  assert.equal(esReintentable(conEstado(502), MAX_REINTENTOS), false)
})

test('nunca repite operaciones que pueden modificar datos', () => {
  assert.equal(esReintentable(conEstado(502, 'post'), 0), false)
  assert.equal(esReintentable(conEstado(502, 'put'), 0), false)
  assert.equal(esReintentable(conEstado(502, 'delete'), 0), false)
})

test('la espera es corta y no simula un arranque en frio', () => {
  assert.ok(ESPERA_MS > 0)
  assert.ok(ESPERA_MS <= 2000)
})
