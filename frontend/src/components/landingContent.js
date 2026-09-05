export const LANDING_PHASES = [
  {
    id: 'explora',
    number: '01',
    name: 'Explora',
    subtitle: 'Calibración',
    questions: 10,
    countLabel: '10 preguntas',
    description: 'Una señal por cada especialización para detectar tus tres áreas con mayor afinidad.',
    example: 'Te dan un problema sin instrucciones claras. ¿Lo conviertes en datos, lo prototipas o lo conversas con el equipo?',
    outcome: 'El sistema conserva tus tres rutas más fuertes y descarta el ruido inicial.',
    accent: '#e10600',
  },
  {
    id: 'afina',
    number: '02',
    name: 'Afina',
    subtitle: 'Profundización',
    questions: 15,
    countLabel: '15 preguntas',
    description: 'Cinco preguntas específicas por cada ruta detectada. Aquí la curiosidad se separa del interés real.',
    example: 'Un modelo funciona bien en pruebas y falla en producción. ¿Qué revisarías primero?',
    outcome: 'Tus respuestas comparan tareas reales de las tres especializaciones finalistas.',
    accent: '#bd0c06',
  },
  {
    id: 'revela',
    number: '03',
    name: 'Revela',
    subtitle: 'Perfil profesional',
    questions: 4,
    countLabel: '4 escenarios',
    description: 'Situaciones de equipo revelan cómo analizas, colaboras, ejecutas y cuidas los detalles.',
    example: 'Faltan dos días para la entrega y el módulo de otro compañero no compila. ¿Qué haces?',
    outcome: 'Tu estilo de trabajo ajusta la recomendación final sin reemplazar tus afinidades.',
    accent: '#970400',
  },
]

export const LANDING_BRANCHES = [
  { code: '01', name: 'Desarrollo de Software' },
  { code: '02', name: 'Data Science e IA' },
  { code: '03', name: 'Infraestructura y Cloud' },
  { code: '04', name: 'Ciberseguridad' },
  { code: '05', name: 'Soporte Técnico e IT Ops' },
  { code: '06', name: 'QA y Testing' },
  { code: '07', name: 'Gestión y Producto' },
  { code: '08', name: 'Diseño UX/UI' },
  { code: '09', name: 'Sistemas Empresariales' },
  { code: '10', name: 'Investigación e Innovación' },
]

export const LANDING_ROUTE_GROUPS = [
  {
    number: '01',
    verb: 'Crear',
    description: 'Convertir ideas en productos que otras personas puedan usar.',
    routes: ['Desarrollo de Software', 'Diseño UX/UI'],
  },
  {
    number: '02',
    verb: 'Entender',
    description: 'Encontrar patrones, formular preguntas y producir conocimiento nuevo.',
    routes: ['Data Science e IA', 'Investigación e Innovación'],
  },
  {
    number: '03',
    verb: 'Sostener',
    description: 'Mantener la tecnología disponible, conectada y funcionando.',
    routes: ['Infraestructura y Cloud', 'Soporte Técnico e IT Ops'],
  },
  {
    number: '04',
    verb: 'Proteger',
    description: 'Reducir riesgos y comprobar que cada entrega responda como debe.',
    routes: ['Ciberseguridad', 'QA y Testing'],
  },
  {
    number: '05',
    verb: 'Coordinar',
    description: 'Conectar tecnología, negocio, procesos y equipos.',
    routes: ['Gestión y Producto', 'Sistemas Empresariales'],
  },
]

export const LANDING_OUTCOMES = [
  {
    number: '01',
    title: 'Una comparativa honesta',
    description: 'Tus tres rutas más probables, con porcentajes visibles y sin fingir una certeza absoluta.',
  },
  {
    number: '02',
    title: 'Un plan que empieza hoy',
    description: 'Acciones para esta semana, este mes, los próximos tres meses y tu etapa de egreso.',
  },
  {
    number: '03',
    title: 'Cursos y empleos con contexto',
    description: 'Recursos y vacantes relacionados con tu perfil para conocer el trabajo antes de elegir.',
  },
  {
    number: '04',
    title: 'Una trayectoria que evoluciona',
    description: 'Repite la evaluación cada semestre y observa qué intereses se mantienen o cambian.',
  },
]

export function getQuestionBreakdown() {
  const total = LANDING_PHASES.reduce((sum, phase) => sum + phase.questions, 0)
  const bank = 100
  return { total, bank, skipped: bank - total }
}

export function getLandingCta(isAuthenticated) {
  return isAuthenticated
    ? { to: '/questionnaire', label: 'Continuar al cuestionario' }
    : { to: '/register', label: 'Crear cuenta y empezar' }
}
