import test from 'node:test'
import assert from 'node:assert/strict'

import { relacionDeContraste, ajustarParaContraste } from './contraste.js'

const CERCA = (a, b, tolerancia = 0.02) => Math.abs(a - b) <= tolerancia

test('mide el contraste como lo define la WCAG', () => {
  // Los dos extremos conocidos anclan la formula.
  assert.ok(CERCA(relacionDeContraste('#000000', '#ffffff'), 21))
  assert.ok(CERCA(relacionDeContraste('#7f7f7f', '#7f7f7f'), 1))
})

test('reproduce los ratios que reporta axe-core', () => {
  // Valores tomados del informe de axe sobre la pantalla de resultado.
  assert.ok(CERCA(relacionDeContraste('#ffffff', '#10b981'), 2.53, 0.03))
  assert.ok(CERCA(relacionDeContraste('#6c63ff', '#33364d'), 2.74, 0.03))
})

test('deja intacto el color que ya cumple', () => {
  const gris = '#64748b'
  assert.equal(ajustarParaContraste(gris, '#ffffff'), gris)
})

test('oscurece sobre fondo claro y aclara sobre fondo oscuro', () => {
  const sobreBlanco = ajustarParaContraste('#10b981', '#ffffff')
  const sobreOscuro = ajustarParaContraste('#8b5cf6', '#141823')

  assert.ok(relacionDeContraste(sobreBlanco, '#ffffff') >= 4.5)
  assert.ok(relacionDeContraste(sobreOscuro, '#141823') >= 4.5)

  // Oscurecer baja la luminancia; aclarar la sube.
  assert.ok(luminanciaDe(sobreBlanco) < luminanciaDe('#10b981'))
  assert.ok(luminanciaDe(sobreOscuro) > luminanciaDe('#8b5cf6'))
})

test('las diez especializaciones admiten texto blanco tras el ajuste', () => {
  // Nueve de las diez no llegaban a 4,5:1: es el motivo de que exista el modulo.
  const PALETA = [
    '#3B82F6', '#10B981', '#8B5CF6', '#EF4444', '#F59E0B',
    '#EC4899', '#6366F1', '#F43F5E', '#14B8A6', '#64748B',
  ]
  for (const color of PALETA) {
    const fondo = ajustarParaContraste(color, '#ffffff')
    assert.ok(
      relacionDeContraste('#ffffff', fondo) >= 4.5,
      `${color} -> ${fondo} no alcanza 4.5:1 con texto blanco`,
    )
  }
})

test('acepta la forma corta de tres digitos', () => {
  assert.ok(CERCA(relacionDeContraste('#fff', '#ffffff'), 1))
  assert.ok(CERCA(relacionDeContraste('#000', '#fff'), 21))
})

function luminanciaDe(hex) {
  const canal = (v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const limpio = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(limpio.slice(i, i + 2), 16))
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)
}
