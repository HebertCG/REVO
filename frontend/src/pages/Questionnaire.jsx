import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { surveyApi } from '../services/api'
import '../theme/app.css'
import './Questionnaire.css'

// Cada categoria trae su propio color de ambiente. Solo se ve una a la
// vez, asi que no compiten entre si: el cambio de color es lo que hace
// que 25 preguntas no se sientan iguales.
const CATEGORIAS = {
  academic:    { label: 'Académico',    icon: '📚', color: '#7AA7F0' },
  skills:      { label: 'Habilidades',  icon: '🛠️', color: '#34D399' },
  interests:   { label: 'Intereses',    icon: '❤️', color: '#F472B6' },
  personality: { label: 'Personalidad', icon: '🧠', color: '#A78BFA' },
}
const COLOR_BASE = '#7AA7F0'

// Etiquetas de la escala. Van sobre el propio botón, no en una fila
// aparte: antes había que cruzar la mirada entre el número y su
// significado, que es justo lo que hace lento un test de 25 preguntas.
// El circulo crece con el valor, asi que la escala se entiende antes
// de leer: el tamano comunica la intensidad y la palabra la confirma.
const ESCALA = [
  { v: 1, corta: 'Para nada',  larga: 'No tiene nada que ver conmigo' },
  { v: 2, corta: 'Poco',       larga: 'Me representa poco' },
  { v: 3, corta: 'A medias',   larga: 'Ni sí ni no' },
  { v: 4, corta: 'Bastante',   larga: 'Me representa bastante' },
  { v: 5, corta: 'Totalmente', larga: 'Soy exactamente así' },
]

// Reserva local por si la base de datos no responde. La fuente real
// son las 40 preguntas de psychometric_questions.
const FASE3_RESERVA = [
  {
    id: 'p3_fb_1',
    question: 'Acabas de terminar un módulo de trabajo. ¿Cuál es tu reacción natural?',
    options: [
      { key: 'A', text: 'Lo reviso buscando posibles errores antes de entregarlo' },
      { key: 'B', text: 'Lo entrego y si hay correcciones, las ajusto sobre la marcha' },
      { key: 'C', text: 'Lo comparto con mi equipo para recibir retroalimentación primero' },
      { key: 'D', text: 'Lo optimizo para que sea más limpio y eficiente antes de entregarlo' },
    ],
  },
  {
    id: 'p3_fb_2',
    question: 'Un proceso falla inesperadamente. ¿Qué haces primero?',
    options: [
      { key: 'A', text: 'Construyo un diagnóstico completo antes de intervenir' },
      { key: 'B', text: 'Implemento una solución temporal y luego investigo la causa raíz' },
      { key: 'C', text: 'Escalo al líder del equipo de inmediato' },
      { key: 'D', text: 'No actúo hasta tener certeza sobre la causa exacta' },
    ],
  },
  {
    id: 'p3_fb_3',
    question: '¿Cómo prefieres aprender algo nuevo en tu área?',
    options: [
      { key: 'A', text: 'Con documentación oficial, paso a paso y de forma estructurada' },
      { key: 'B', text: 'Construyendo un proyecto real desde el primer día' },
      { key: 'C', text: 'En equipo, con mentores o grupos de estudio colaborativos' },
      { key: 'D', text: 'Con materiales curados y tomando notas detalladas para repasar' },
    ],
  },
  {
    id: 'p3_fb_4',
    question: 'Descríbete en un equipo de trabajo:',
    options: [
      { key: 'A', text: 'El estratega: diseño la estructura general antes de ejecutar' },
      { key: 'B', text: 'El ejecutor: soy el primero en tener resultados en mano' },
      { key: 'C', text: 'El conector: facilito la comunicación y coordinación del equipo' },
      { key: 'D', text: 'El revisor: nada sale sin que yo lo haya validado previamente' },
    ],
  },
]

function calcArchetype(answers) {
  const cuenta = { A: 0, B: 0, C: 0, D: 0 }
  Object.values(answers).forEach((v) => { if (cuenta[v] !== undefined) cuenta[v]++ })
  const max = Math.max(...Object.values(cuenta))
  const ganadores = Object.entries(cuenta).filter(([, c]) => c === max).map(([k]) => k)
  return ganadores[Math.floor(Math.random() * ganadores.length)]
}

/** Pantalla a pantalla completa para esperas y transiciones. */
function Pantalla({ icono, titulo, texto, aviso }) {
  return (
    <div className="rv quiz-espera">
      <div className="quiz-espera-caja">
        <div className="quiz-espera-icono" aria-hidden="true">{icono}</div>
        <h2>{titulo}</h2>
        <p className="rv-sub">{texto}</p>
        {aviso && <p className="quiz-aviso">{aviso}</p>}
        <div className="quiz-puntos" aria-hidden="true"><span /><span /><span /></div>
      </div>
    </div>
  )
}

export default function Questionnaire() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [answers, setAnswers] = useState({})
  const [current, setCurrent] = useState(0)
  const [phase, setPhase] = useState(1)
  const [phase3Answers, setPhase3Answers] = useState({})
  const [phase3Current, setPhase3Current] = useState(0)
  const [phase3Questions, setPhase3Questions] = useState(FASE3_RESERVA)

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError] = useState('')
  const cardRef = useRef(null)

  useEffect(() => {
    if (!user) return
    let sid = null
    surveyApi.createSession()
      .then((sRes) => { sid = sRes.data.id; setSessionId(sid); return surveyApi.getSessionQuestions(sid) })
      .then((qRes) => setQuestions(qRes.data))
      .catch(() => setError('No se pudo iniciar el cuestionario. Revisa tu conexión.'))
      .finally(() => setLoading(false))
  }, [user])

  const loadPhase2 = async (sid) => {
    setTransitioning(true)
    try {
      const qRes = await surveyApi.getSessionQuestions(sid)
      setQuestions(qRes.data)
      setCurrent(0)
      setPhase(2)
    } catch {
      setError('Error al cargar las preguntas de la fase 2.')
    } finally {
      setTransitioning(false)
    }
  }

  const triggerPhase3 = async (specName, specId) => {
    let qs = null
    if (specId) {
      try {
        const res = await surveyApi.getPsychometricQuestions(specId)
        if (res.data && res.data.length > 0) {
          qs = res.data.map((q) => ({
            id: `p3_db_${q.id}`,
            question: q.question_text,
            options: [
              { key: 'A', text: q.option_a },
              { key: 'B', text: q.option_b },
              { key: 'C', text: q.option_c },
              { key: 'D', text: q.option_d },
            ],
          }))
        }
      } catch (e) {
        console.warn('Preguntas psicométricas no disponibles, usando la reserva local', e)
      }
    }
    if (!qs) qs = FASE3_RESERVA
    setPhase3Questions(qs)
    setPhase(3)
    setPhase3Current(0)
    setPhase3Answers({})
  }

  const q = questions[current]
  const total = questions.length
  const respondidas = questions.filter((x) => answers[x.id] !== undefined).length
  const progreso = total ? Math.round((respondidas / total) * 100) : 0
  const isAnswered = q && answers[q.id] !== undefined
  const isLast = current === total - 1

  const setAnswer = (val) => setAnswers((a) => ({ ...a, [q.id]: val }))

  const next = async () => {
    if (!isAnswered) return
    surveyApi.saveAnswers(sessionId, {
      answers: [{ question_id: q.id, value: answers[q.id] }],
    }).catch(console.error)

    if (isLast) {
      setSubmitting(true)
      setError('')
      try {
        const todas = questions.map((q2) => ({ question_id: q2.id, value: answers[q2.id] || 3 }))
        await surveyApi.saveAnswers(sessionId, { answers: todas })
      } catch (e) {
        console.warn('El guardado masivo falló, se continúa con el envío', e)
      }

      const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

      const submitWithRetry = async (maxRetries = 3) => {
        for (let intento = 1; intento <= maxRetries; intento++) {
          try {
            const { data: t } = await surveyApi.submitPhase(sessionId)

            if (t.next_phase === 2) {
              setSubmitting(false)
              loadPhase2(sessionId)
              return
            }
            if (t.prediction_id) {
              setSubmitting(false)
              sessionStorage.setItem('revo_pending_result', t.prediction_id)
              sessionStorage.setItem('revo_winning_spec', t.primary_specialization || '')
              triggerPhase3(t.primary_specialization || '', t.primary_specialization_id || null)
              return
            }
            if (t.error && intento < maxRetries) {
              const s = intento * 10
              setError(`El servicio está despertando. Reintentando en ${s}s (${intento}/${maxRetries})`)
              await sleep(s * 1000)
              setError('')
            } else if (t.error) {
              setError('')
              setSubmitting(false)
              sessionStorage.removeItem('revo_pending_result')
              triggerPhase3('', null)
              return
            } else {
              setError('Respuesta inesperada del servidor. Intenta de nuevo.')
              setSubmitting(false)
              return
            }
          } catch {
            if (intento < maxRetries) {
              const s = intento * 10
              setError(`Conexión lenta. Reintentando en ${s}s (${intento}/${maxRetries})`)
              await sleep(s * 1000)
              setError('')
            } else {
              setError('No se pudo conectar. Comprueba que los servicios estén corriendo.')
              setSubmitting(false)
            }
          }
        }
      }
      await submitWithRetry()
    } else {
      if (cardRef.current) cardRef.current.dataset.saliendo = 'si'
      setTimeout(() => {
        setCurrent((c) => c + 1)
        if (cardRef.current) delete cardRef.current.dataset.saliendo
      }, 160)
    }
  }

  const prev = () => { if (current > 0) setCurrent((c) => c - 1) }

  // ── Atajos de teclado ────────────────────────────────────
  // Con 25 preguntas, responder con el teclado ahorra minutos
  // frente a apuntar y hacer clic en cada una.
  const enFase12 = !loading && !submitting && !transitioning && phase !== 3 && !!q
  const manejarTecla = useCallback((e) => {
    if (!enFase12) return
    if (e.target.matches('input, textarea, select')) return

    if (e.key >= '1' && e.key <= '5') {
      e.preventDefault()
      setAnswers((a) => ({ ...a, [q.id]: Number(e.key) }))
    } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
      if (answers[q.id] !== undefined) { e.preventDefault(); next() }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault(); prev()
    }
  }, [enFase12, q, answers, current, isLast])

  useEffect(() => {
    window.addEventListener('keydown', manejarTecla)
    return () => window.removeEventListener('keydown', manejarTecla)
  }, [manejarTecla])

  // ── Pantallas de espera ──────────────────────────────────
  if (loading) {
    return <Pantalla icono="🌱" titulo="Preparando tu cuestionario"
      texto="Estamos eligiendo tus primeras diez preguntas." />
  }

  if (submitting) {
    const textos = {
      1: ['Analizando tus respuestas', 'Buscamos las tres ramas que mejor encajan contigo.'],
      2: ['Calculando tu perfil', 'Combinamos todo lo que respondiste para generar la recomendación.'],
      3: ['Cerrando tu resultado', 'Un momento más.'],
    }
    const [t, s] = textos[phase] || textos[2]
    return <Pantalla icono="🧠" titulo={t} texto={s} aviso={error} />
  }

  if (transitioning) {
    return <Pantalla icono="🔥" titulo="Fase 2 desbloqueada"
      texto="Ya sabemos por dónde van tus intereses. Ahora vamos a profundizar en las tres ramas más prometedoras." />
  }

  const Ambiente = () => (
    <div className="quiz-ambiente" aria-hidden="true">
      <span className="quiz-mancha quiz-mancha-1" />
      <span className="quiz-mancha quiz-mancha-2" />
    </div>
  )

  // ── FASE 3: perfil profesional ───────────────────────────
  if (phase === 3) {
    const p3q = phase3Questions[phase3Current]
    const p3Sel = phase3Answers[p3q?.id]
    const p3Total = phase3Questions.length
    const p3Prog = Math.round((phase3Current / p3Total) * 100)
    const p3Ultima = phase3Current === p3Total - 1

    const elegir = (key) => setPhase3Answers((prev) => ({ ...prev, [p3q.id]: key }))

    const siguienteP3 = () => {
      if (!p3Sel) return
      if (p3Ultima) {
        setSubmitting(true)
        const finales = { ...phase3Answers, [p3q.id]: p3Sel }
        sessionStorage.setItem('revo_archetype', JSON.stringify(calcArchetype(finales)))
        const pendiente = sessionStorage.getItem('revo_pending_result')
        setTimeout(() => navigate(`/results/${pendiente}`), 3500)
      } else {
        setPhase3Current((c) => c + 1)
      }
    }

    return (
      <div className="rv quiz" style={{ '--cat': '#A78BFA' }}>
        <Ambiente />
        <div className="rv-ancho rv-ancho-est quiz-lienzo">
          <header className="quiz-cab rv-entra">
            <div className="quiz-cab-fila">
              <span className="rv-etiq quiz-fase">Fase 3 de 3 · Perfil profesional</span>
              <span className="rv-dato quiz-cuenta">
                {phase3Current + 1}<small>/{p3Total}</small>
              </span>
            </div>
            <div className="quiz-sendero">
              {phase3Questions.map((x, i) => (
                <span key={x.id}
                  className={'quiz-paso' + (phase3Answers[x.id] ? ' hecho' : '') + (i === phase3Current ? ' actual' : '')} />
              ))}
            </div>
            <span className="rv-menor quiz-cab-nota">
              Última etapa: aquí definimos tu estilo de trabajo.
            </span>
          </header>

          {p3q && (
            <section className="rv-tarjeta quiz-carta rv-entra" style={{ animationDelay: '.05s' }}>
              <h1 className="quiz-pregunta">{p3q.question}</h1>

              <div className="quiz-ops" role="radiogroup" aria-label="Opciones">
                {p3q.options.map((opt) => (
                  <button key={opt.key} type="button" role="radio"
                    aria-checked={p3Sel === opt.key}
                    onClick={() => elegir(opt.key)}
                    className={`quiz-op ${p3Sel === opt.key ? 'sel' : ''}`}>
                    <span className="quiz-op-letra" aria-hidden="true">{opt.key}</span>
                    <span className="quiz-op-txt">{opt.text}</span>
                  </button>
                ))}
              </div>

              <nav className="quiz-nav">
                <button onClick={() => phase3Current > 0 && setPhase3Current((c) => c - 1)}
                  disabled={phase3Current === 0} className="rv-btn rv-btn-g">
                  ← Anterior
                </button>
                <button onClick={siguienteP3} disabled={!p3Sel} className="rv-btn rv-btn-1">
                  {p3Ultima ? 'Ver mi resultado' : 'Siguiente →'}
                </button>
              </nav>
            </section>
          )}
        </div>
      </div>
    )
  }

  // ── FASES 1 y 2 ──────────────────────────────────────────
  const cat = CATEGORIAS[q?.category] || {}
  const color = cat.color || COLOR_BASE

  return (
    <div className="rv quiz" style={{ '--cat': color }}>
      <Ambiente />

      <div className="rv-ancho rv-ancho-est quiz-lienzo">

        <header className="quiz-cab rv-entra">
          <div className="quiz-cab-fila">
            <span className="rv-etiq quiz-fase">
              Fase {phase} de 3 · {phase === 1 ? 'Calibración' : 'Profundización'}
            </span>
            <span className="rv-dato quiz-cuenta">
              {current + 1}<small>/{total}</small>
            </span>
          </div>

          {/* Un punto por pregunta: se ve de un vistazo cuánto falta
              y cuáles quedaron sin responder. */}
          <div className="quiz-sendero" aria-hidden="true">
            {questions.map((x, i) => (
              <span key={x.id}
                className={
                  'quiz-paso' +
                  (answers[x.id] !== undefined ? ' hecho' : '') +
                  (i === current ? ' actual' : '')
                } />
            ))}
          </div>

          <span className="rv-menor quiz-cab-nota">
            {respondidas} de {total} respondidas · {progreso}%
          </span>
        </header>

        {q && (
          <section ref={cardRef} className="quiz-carta" key={q.id}>
            {cat.label && (
              <span className="rv-ficha quiz-cat">
                <span aria-hidden="true">{cat.icon}</span> {cat.label}
              </span>
            )}

            <h1 className="quiz-pregunta">{q.text}</h1>

            {error && <p className="quiz-error" role="alert">{error}</p>}

            <div className="quiz-escala" role="radiogroup" aria-label="Qué tanto te representa">
              {ESCALA.map(({ v, corta, larga }) => (
                <button key={v} type="button" role="radio" data-v={v}
                  aria-checked={answers[q.id] === v}
                  aria-label={`${v} de 5: ${larga}`}
                  onClick={() => setAnswer(v)}
                  className={`quiz-op-esc ${answers[q.id] === v ? 'sel' : ''}`}>
                  <span className="quiz-bolita" aria-hidden="true" />
                  <span className="quiz-esc-txt">{corta}</span>
                  <span className="quiz-esc-num" aria-hidden="true">{v}</span>
                </button>
              ))}
            </div>

            <nav className="quiz-nav">
              <button onClick={prev} disabled={current === 0} className="rv-btn rv-btn-g">
                ← Anterior
              </button>
              <button onClick={next} disabled={!isAnswered} className="rv-btn rv-btn-1">
                {isLast
                  ? (phase === 1 ? 'Ir a la fase 2' : 'Ir al perfil profesional')
                  : 'Siguiente →'}
              </button>
            </nav>

            <p className="quiz-atajos">
              Responde con <kbd>1</kbd>–<kbd>5</kbd> y muévete con <kbd>←</kbd> <kbd>→</kbd>
            </p>
          </section>
        )}
      </div>
    </div>
  )
}
