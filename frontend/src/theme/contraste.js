/**
 * Contraste segun la WCAG.
 *
 * Existe porque REVO pinta varios elementos con el color de la
 * especializacion, que viene del dato y no de la hoja de estilos: el boton
 * "Ver oferta" usa ese color de fondo con texto blanco, y el porcentaje del
 * top 3 lo usa como texto sobre la tarjeta oscura. Ninguna regla CSS puede
 * arreglar eso, porque el color no se conoce hasta que llega la prediccion.
 *
 * De las diez especializaciones, nueve no llegaban a 4,5:1 con texto blanco
 * encima. En vez de retocar la paleta a mano (y volver a hacerlo cada vez que
 * se anada una rama), el color se ajusta al pintarlo.
 */

const aCanal = (valor) => {
  const c = valor / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

const aRgb = (hex) => {
  const limpio = hex.replace('#', '')
  const completo = limpio.length === 3
    ? limpio.split('').map((c) => c + c).join('')
    : limpio
  return [0, 2, 4].map((i) => parseInt(completo.slice(i, i + 2), 16))
}

const aHex = ([r, g, b]) => '#' + [r, g, b]
  .map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0'))
  .join('')

/** Luminancia relativa (WCAG 2.x, 1.4.3). */
export function luminancia(hex) {
  const [r, g, b] = aRgb(hex)
  return 0.2126 * aCanal(r) + 0.7152 * aCanal(g) + 0.0722 * aCanal(b)
}

/** Relacion de contraste entre dos colores: de 1 (iguales) a 21 (blanco/negro). */
export function relacionDeContraste(uno, otro) {
  const a = luminancia(uno)
  const b = luminancia(otro)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/**
 * Devuelve el `color` desplazado hacia negro o hacia blanco —lo que aumente
 * el contraste— hasta alcanzar `minimo` frente a `fondo`.
 *
 * Se conserva el tono: el ajuste es una interpolacion hacia negro o blanco,
 * asi que el verde de Data Science sigue siendo verde, solo mas oscuro. Si
 * el color ya cumple, se devuelve intacto.
 */
export function ajustarParaContraste(color, fondo, minimo = 4.5) {
  if (!color || !fondo) return color
  if (relacionDeContraste(color, fondo) >= minimo) return color

  // Se oscurece si el fondo es claro y se aclara si es oscuro.
  const destino = luminancia(fondo) > 0.18 ? [0, 0, 0] : [255, 255, 255]
  const base = aRgb(color)

  for (let paso = 1; paso <= 20; paso++) {
    const mezcla = paso / 20
    const candidato = aHex(base.map((v, i) => v + (destino[i] - v) * mezcla))
    if (relacionDeContraste(candidato, fondo) >= minimo) return candidato
  }
  return aHex(destino)
}
