/**
 * Datos de prueba con la forma exacta que devuelven los servicios.
 *
 * Se copian de los esquemas Pydantic de cada servicio (schemas.py). Si un campo
 * cambia alli y no aqui, las pruebas siguen pasando contra una forma que ya
 * no existe: por eso cada bloque anota de que endpoint sale.
 */

export const USUARIO = {
  id: 42,
  email: 'ana.quispe@universidad.edu.pe',
  full_name: 'Ana Quispe Mamani',
  student_code: 'U20231234',
  semester: 5,
  role: 'student',
  is_active: true,
  avatar_url: null,
  created_at: '2026-03-01T10:00:00',
}

export const ADMIN = { ...USUARIO, id: 1, email: 'admin@revo.pe', full_name: 'Rosa Admin', role: 'admin' }

export const TOKEN = 'token-de-prueba-no-valido'

export const SESION_TOKEN = {
  access_token: TOKEN,
  token_type: 'bearer',
  expires_in: 3600,
  user: USUARIO,
}

// GET /predict/user/{uid}/history
export const HISTORIAL = [
  { prediction_id: 903, session_id: 303, specialization: 'Data Science & IA', icon: '🧠', color: '#10B981', confidence_pct: 87.4, created_at: '2026-08-20T15:30:00' },
  { prediction_id: 902, session_id: 302, specialization: 'Data Science & IA', icon: '🧠', color: '#10B981', confidence_pct: 81.2, created_at: '2026-07-11T12:05:00' },
  { prediction_id: 901, session_id: 301, specialization: 'Desarrollo de Software', icon: '💻', color: '#3B82F6', confidence_pct: 72.9, created_at: '2026-06-02T09:45:00' },
]

// El historial mas largo prueba el enlace "ver las N evaluaciones" del panel,
// que solo aparece con mas de cuatro registros.
export const HISTORIAL_LARGO = Array.from({ length: 7 }, (_, i) => ({
  prediction_id: 800 + i,
  session_id: 200 + i,
  specialization: i % 2 === 0 ? 'Ciberseguridad' : 'QA & Testing',
  icon: '🔐',
  color: '#EF4444',
  confidence_pct: 60 + i * 3.5,
  created_at: `2026-0${(i % 8) + 1}-1${i % 9}T10:00:00`,
}))

// GET /predict/{id}
export const PREDICCION = {
  prediction_id: 903,
  session_id: 303,
  primary: {
    specialization_id: 2,
    name: 'Data Science & IA',
    icon: '🧠',
    color: '#10B981',
    confidence: 0.874,
    confidence_pct: 87.4,
  },
  primary_specialization: 'Data Science & IA',
  primary_specialization_id: 2,
  top3: [
    { specialization_id: 2, name: 'Data Science & IA', icon: '🧠', color: '#10B981', confidence: 0.874, confidence_pct: 87.4 },
    { specialization_id: 1, name: 'Desarrollo de Software', icon: '💻', color: '#3B82F6', confidence: 0.081, confidence_pct: 8.1 },
    { specialization_id: 3, name: 'Infraestructura & Cloud', icon: '☁️', color: '#8B5CF6', confidence: 0.045, confidence_pct: 4.5 },
  ],
  all_probabilities: {
    'Data Science & IA': 87.4,
    'Desarrollo de Software': 8.1,
    'Infraestructura & Cloud': 4.5,
    'Ciberseguridad': 0.0,
  },
  model_version: '1.4.0',
}

// GET /predict/model/importances
export const IMPORTANCIAS = Array.from({ length: 10 }, (_, i) => ({
  feature: `aff_${i + 1}`,
  importance: Number((0.3 - i * 0.02).toFixed(3)),
  pct: Number((30 - i * 2).toFixed(1)),
}))

// GET /courses/specialization/{id}
export const CURSOS = [
  { id: 1, title: 'Python para ciencia de datos', platform: 'Coursera', url: 'https://example.org/curso-1', level: 'Básico', is_free: true },
  { id: 2, title: 'Machine Learning aplicado', platform: 'edX', url: 'https://example.org/curso-2', level: 'Intermedio', is_free: false },
]

// GET /sessions/{id}/questions — fase 1 y 2
const CATEGORIAS_BANCO = ['programming', 'data', 'infra', 'security', 'design']

export const preguntas = (cantidad, desde = 1) =>
  Array.from({ length: cantidad }, (_, i) => ({
    id: desde + i,
    text: `Pregunta ${desde + i}: ¿Qué tanto te representa resolver problemas del área ${CATEGORIAS_BANCO[i % 5]}?`,
    category: CATEGORIAS_BANCO[i % 5],
    question_type: 'likert',
    options: null,
    min_label: 'Nada',
    max_label: 'Mucho',
    weight: 1,
    order_index: desde + i,
  }))

export const PREGUNTAS_FASE1 = preguntas(10, 1)
export const PREGUNTAS_FASE2 = preguntas(15, 101)

// GET /psychometric/specialization/{id}
export const PREGUNTAS_PSICOMETRICAS = Array.from({ length: 4 }, (_, i) => ({
  id: i + 1,
  question_text: `¿Cómo actúas ante el escenario profesional número ${i + 1}?`,
  option_a: 'Diseño la estructura general antes de ejecutar',
  option_b: 'Empiezo a construir y ajusto sobre la marcha',
  option_c: 'Convoco al equipo y repartimos el trabajo',
  option_d: 'Reviso todo dos veces antes de publicar',
}))

// POST /sessions/{id}
export const SESION_CUESTIONARIO = {
  id: 777,
  user_id: USUARIO.id,
  status: 'in_progress',
  started_at: '2026-08-27T10:00:00',
  completed_at: null,
  duration_seconds: null,
}

// GET /legal/documents
export const DOCUMENTOS_LEGALES = [
  { doc_type: 'terms', version: '1.0', title: 'Términos y Condiciones', summary: 'Acepto los Términos y Condiciones y la Política de Privacidad de REVO.', is_required: true },
  { doc_type: 'privacy', version: '1.0', title: 'Política de Privacidad', summary: 'Tratamos tus datos según la Ley 29733.', is_required: true },
  { doc_type: 'data_commercial', version: '1.0', title: 'Datos agregados', summary: 'Autorizo compartir información agregada y seudonimizada con universidades.', is_required: false },
  { doc_type: 'ai_training', version: '1.0', title: 'Entrenamiento del modelo', summary: 'Autorizo que mis respuestas entrenen el modelo de REVO.', is_required: false },
]

export const DOCUMENTO_COMPLETO = (tipo) => ({
  ...(DOCUMENTOS_LEGALES.find((d) => d.doc_type === tipo) || DOCUMENTOS_LEGALES[0]),
  body_md: '## Documento de prueba\n\nContenido legal simulado para la bateria de pruebas.',
})

// GET /stats/overview
export const RESUMEN_ADMIN = {
  total_predictions: 1284,
  avg_confidence_pct: 78.3,
  specialization_dist: [
    { name: 'Data Science & IA', icon: '🧠', color: '#10B981', total: 412 },
    { name: 'Desarrollo de Software', icon: '💻', color: '#3B82F6', total: 388 },
    { name: 'Ciberseguridad', icon: '🔐', color: '#EF4444', total: 205 },
  ],
  last_training: { model_version: '1.4.0', accuracy: 0.914, f1: 0.902, trained_at: '2026-08-15T08:00:00', samples: 5400 },
  new_predictions: 62,
  data_sources: { synthetic: 5000, human: 400, total: 5400 },
  feedback: { total: 210, affinity_rate: 82.4, discovery_rate: 41.9 },
}

// GET /stats/training-history
export const HISTORIAL_ENTRENAMIENTO = Array.from({ length: 5 }, (_, i) => ({
  model_version: `1.${4 - i}.0`,
  accuracy: 0.9 - i * 0.02,
  f1: 0.89 - i * 0.02,
  training_samples: 5400 - i * 300,
  tree_depth: 8,
  trained_at: `2026-0${8 - i}-15T08:00:00`,
}))
