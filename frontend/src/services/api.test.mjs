import test from 'node:test'
import assert from 'node:assert/strict'
import axios from 'axios'

const almacenamiento = new Map()
globalThis.sessionStorage = {
  getItem: (clave) => almacenamiento.get(clave) ?? null,
  setItem: (clave, valor) => almacenamiento.set(clave, valor),
  removeItem: (clave) => almacenamiento.delete(clave),
}
globalThis.window = new EventTarget()

const { default: cliente } = await import('./api.js')

const respuesta = (config, status = 200, data = {}) => ({
  config,
  data,
  headers: {},
  status,
  statusText: status === 200 ? 'OK' : 'Bad Gateway',
})

const fallo = (config, status = 502) => {
  throw new axios.AxiosError(
    'Bad Gateway',
    axios.AxiosError.ERR_BAD_RESPONSE,
    config,
    null,
    respuesta(config, status),
  )
}

test('un GET con corte pasajero se reintenta exactamente una vez', async () => {
  let llamadas = 0
  const adapterAnterior = cliente.defaults.adapter

  cliente.defaults.adapter = async (config) => {
    llamadas += 1
    if (llamadas === 1) fallo(config)
    return respuesta(config)
  }

  try {
    const resultado = await cliente.get('/prueba-reintento')
    assert.equal(resultado.status, 200)
    assert.equal(llamadas, 2)
  } finally {
    cliente.defaults.adapter = adapterAnterior
  }
})

test('un GET deja de reintentarse despues del segundo fallo', async () => {
  let llamadas = 0
  const adapterAnterior = cliente.defaults.adapter

  cliente.defaults.adapter = async (config) => {
    llamadas += 1
    fallo(config)
  }

  try {
    await assert.rejects(cliente.get('/prueba-agotada'))
    assert.equal(llamadas, 2)
  } finally {
    cliente.defaults.adapter = adapterAnterior
  }
})

test('un POST nunca se repite automaticamente', async () => {
  let llamadas = 0
  const adapterAnterior = cliente.defaults.adapter

  cliente.defaults.adapter = async (config) => {
    llamadas += 1
    fallo(config)
  }

  try {
    await assert.rejects(cliente.post('/auth/login', {}))
    assert.equal(llamadas, 1)
  } finally {
    cliente.defaults.adapter = adapterAnterior
  }
})
