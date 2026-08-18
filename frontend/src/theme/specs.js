/**
 * Identidad visual de las 10 especializaciones.
 *
 * IMPORTANTE — estos colores NO son una paleta categórica de gráficos.
 * Son acentos de identidad: aparecen de uno en uno y SIEMPRE junto al
 * nombre de la especialidad, así que el color nunca es el único portador
 * de la identidad. Diez colores mutuamente distinguibles no son
 * alcanzables (la separación perceptual no es uniforme en el círculo de
 * matices), por eso los gráficos de la aplicación usan una sola serie.
 */

export const SPECS = {
  'Desarrollo de Software':     { color: '#3B82F6', icon: '💻', short: 'Desarrollo' },
  'Data Science & IA':          { color: '#10B981', icon: '🧠', short: 'Data & IA' },
  'Infraestructura & Cloud':    { color: '#8B5CF6', icon: '☁️', short: 'Infra & Cloud' },
  'Ciberseguridad':             { color: '#EF4444', icon: '🔐', short: 'Ciberseguridad' },
  'Soporte Técnico & IT Ops':   { color: '#F59E0B', icon: '🛠️', short: 'Soporte IT' },
  'QA & Testing':               { color: '#EC4899', icon: '🧪', short: 'QA & Testing' },
  'Gestión y Producto':         { color: '#6366F1', icon: '📈', short: 'Gestión' },
  'Diseño UX/UI':               { color: '#F43F5E', icon: '🎨', short: 'UX/UI' },
  'Sistemas Empresariales':     { color: '#14B8A6', icon: '🏢', short: 'Sist. Empresariales' },
  // #64748B leía como gris puro sobre el fondo oscuro (croma 0.04);
  // se le subió el croma conservando el matiz pizarra.
  'Investigación e Innovación': { color: '#7C8CF8', icon: '🔬', short: 'Investigación' },
}

const POR_DEFECTO = { color: '#6C63FF', icon: '🎓', short: '' }

export const specMeta = (nombre) => SPECS[nombre] || POR_DEFECTO
export const specColor = (nombre) => specMeta(nombre).color
export const specIcon = (nombre) => specMeta(nombre).icon

/** Color único de serie para los gráficos. Un solo trazo, sin leyenda. */
export const SERIE = '#7AA7F0'

/** Estados semánticos. Nunca se reutilizan como color de serie. */
export const ESTADO = {
  bueno:    '#34D399',
  aviso:    '#FBBF24',
  critico:  '#F87171',
  neutro:   '#94A3B8',
}

/** Niveles de progreso del REVO Score. */
export const NIVELES = [
  { min: 0,   label: 'Explorador',    icon: '🌱', color: '#94A3B8' },
  { min: 201, label: 'Emergente',     icon: '🔥', color: '#FBBF24' },
  { min: 501, label: 'Consolidado',   icon: '⚡', color: '#7AA7F0' },
  { min: 801, label: 'Élite',         icon: '🏆', color: '#34D399' },
]

export function nivelDe(score) {
  return [...NIVELES].reverse().find((n) => score >= n.min) || NIVELES[0]
}

export function siguienteNivel(score) {
  return NIVELES.find((n) => n.min > score) || null
}

/**
 * REVO Score: 100 pts por evaluación + confianza media ×2 + bono de
 * consistencia si las tres últimas coinciden en especialidad.
 */
export function calcularScore(historial) {
  if (!historial.length) return 0
  const porEvaluacion = historial.length * 100
  const confMedia = historial.reduce((a, h) => a + (h.confidence_pct || 0), 0) / historial.length
  const porConfianza = Math.round(confMedia * 2)
  let bono = 0
  if (historial.length >= 3) {
    const ultimas = historial.slice(0, 3).map((h) => h.specialization)
    if (ultimas.every((s) => s === ultimas[0])) bono = 150
  }
  return porEvaluacion + porConfianza + bono
}

/** Fecha corta y legible: "15 ago 2026". */
export const fechaCorta = (iso) =>
  new Date(iso).toLocaleDateString('es-PE', { day: 'numeric', month: 'short', year: 'numeric' })

/** Fecha larga: "sábado, 15 de agosto". */
export const fechaLarga = (iso) =>
  new Date(iso).toLocaleDateString('es-PE', { weekday: 'long', day: 'numeric', month: 'long' })
