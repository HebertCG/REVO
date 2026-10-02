import test from 'node:test'
import assert from 'node:assert/strict'

import {
  MAXIMO_OCUPACIONES,
  avisoDeCautela,
  etiquetaDeParecido,
  ocupacionesAfines,
} from './resultadoConfianza.js'

const conCautela = {
  presentacion: {
    cautela: true,
    mensaje: 'Tus respuestas apuntan a esta rama, pero tu perfil se parece poco a los que el sistema conoce.',
  },
  incertidumbre: { lectura: 'perfil_poco_visto', explicacion: 'Tu combinación de respuestas se parece poco...' },
}

const ocupacion = (codigo, titulo, correlacion) => ({ codigo_soc: codigo, titulo, correlacion })

test('una prediccion antigua, sin detalle, no muestra aviso', () => {
  assert.equal(avisoDeCautela({ primary: {} }), null)
})

test('sin cautela no hay aviso', () => {
  assert.equal(avisoDeCautela({ presentacion: { cautela: false, mensaje: 'Claro.' } }), null)
})

test('con cautela devuelve el mensaje y el porque', () => {
  const aviso = avisoDeCautela(conCautela)

  assert.match(aviso.mensaje, /se parece poco/)
  assert.match(aviso.explicacion, /combinación/)
})

test('una prediccion antigua no tiene ocupaciones', () => {
  assert.deepEqual(ocupacionesAfines({ primary: {} }), [])
})

test('convierte cada ocupacion en titulo, etiqueta y enlace a O*NET', () => {
  const [primera] = ocupacionesAfines({
    ocupaciones_afines: [ocupacion('15-1212.00', 'Information Security Analysts', 0.996)],
  })

  assert.deepEqual(primera, {
    codigo: '15-1212.00',
    titulo: 'Information Security Analysts',
    parecido: 'Muy parecido',
    enlace: 'https://www.onetonline.org/link/summary/15-1212.00',
  })
})

test('descarta lo que no tiene forma de codigo SOC: con el se construye un enlace', () => {
  const lista = ocupacionesAfines({
    ocupaciones_afines: [
      ocupacion('javascript:alert(1)', 'Trampa', 0.9),
      ocupacion('15-1212.00', '', 0.9),
      ocupacion('15-1252.00', 'Software Developers', 0.95),
    ],
  })

  assert.deepEqual(lista.map((o) => o.codigo), ['15-1252.00'])
})

test(`no muestra mas de ${MAXIMO_OCUPACIONES}`, () => {
  const muchas = Array.from({ length: 9 }, (_, i) =>
    ocupacion(`15-12${String(i).padStart(2, '0')}.00`, `Ocupacion ${i}`, 0.9))

  assert.equal(ocupacionesAfines({ ocupaciones_afines: muchas }).length, MAXIMO_OCUPACIONES)
})

test('la etiqueta es cualitativa: una correlacion no es un porcentaje de acierto', () => {
  assert.equal(etiquetaDeParecido(0.97), 'Muy parecido')
  assert.equal(etiquetaDeParecido(0.8), 'Parecido')
  assert.equal(etiquetaDeParecido(0.5), 'Algo parecido')
  assert.equal(etiquetaDeParecido(Number.NaN), null)
})
