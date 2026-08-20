import { useState, useEffect, useRef, useEffectEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { surveyApi } from '../services/api'
import personaCelularGaming from '../assets/persona-celular-gaming.png'
import personaDiferenciaGaming from '../assets/persona-diferencia-gaming.png'
import '../theme/app.css'
import './Questionnaire.css'

// Cada categoria trae su propio color de ambiente. Solo se ve una a la
// vez, asi que no compiten entre si: el cambio de color es lo que hace
// que 25 preguntas no se sientan iguales.
const CATEGORIAS = {
  academic:    { label: 'Académico',    icon: 'AC', color: '#5BB8FF' },
  skills:      { label: 'Habilidades',  icon: 'HB', color: '#79D89B' },
  interests:   { label: 'Intereses',    icon: 'IN', color: '#FF756A' },
  personality: { label: 'Personalidad', icon: 'PR', color: '#D9B35B' },
}
const COLOR_BASE = '#5BB8FF'

const FASES = [
  { n: 1, nombre: 'Explora', detalle: 'Calibración' },
  { n: 2, nombre: 'Afina', detalle: 'Profundización' },
  { n: 3, nombre: 'Revela', detalle: 'Perfil profesional' },
]

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

function Ambiente() {
  return (
    <div className="quiz-ambiente" aria-hidden="true">
      <span className="quiz-tinta quiz-tinta-1" />
      <span className="quiz-tinta quiz-tinta-2" />
      <span className="quiz-grano" />
      <span className="quiz-orbita quiz-orbita-1" />
      <span className="quiz-orbita quiz-orbita-2" />
    </div>
  )
}

function FaseHud({ fase, actual, total }) {
  return (
    <header className="quiz-hud">
      <div className="quiz-partida">
        <span className="quiz-partida-marca" aria-hidden="true">R</span>
        <span>
          <strong>Partida de afinidad</strong>
          <small>Tu perfil se construye carta a carta</small>
        </span>
      </div>

      <ol className="quiz-fases" aria-label={`Fase ${fase} de 3`}>
        {FASES.map((item) => (
          <li
            key={item.n}
            className={item.n === fase ? 'activa' : item.n < fase ? 'superada' : ''}
            aria-current={item.n === fase ? 'step' : undefined}
          >
            <span>{item.n}</span>
            <div><strong>{item.nombre}</strong><small>{item.detalle}</small></div>
          </li>
        ))}
      </ol>

      <div className="quiz-marcador" aria-label={`Carta ${actual} de ${total}`}>
        <small>Carta</small>
        <strong>{String(actual).padStart(2, '0')}</strong>
        <span>/ {String(total).padStart(2, '0')}</span>
      </div>
    </header>
  )
}

function PanelMazo({ fase, items, respuestas, actual }) {
  const total = items.length
  const resueltas = items.filter((item) => respuestas[item.id] !== undefined).length
  const porcentaje = total ? Math.round((resueltas / total) * 100) : 0
  const textos = {
    1: 'Prueba distintos territorios. No hay respuestas correctas, solo señales.',
    2: 'El mazo se concentra en las áreas donde mostraste más afinidad.',
    3: 'Tus elecciones finales revelan cómo trabajas cuando toca decidir.',
  }

  return (
    <aside className="quiz-panel">
      <figure className="quiz-panel-visual">
        <img src={personaDiferenciaGaming} alt="" decoding="async" />
      </figure>
      <span className="quiz-ronda">Ronda {fase}</span>
      <h2>{FASES[fase - 1].nombre}</h2>
      <p>{textos[fase]}</p>

      <div
        className="quiz-mini-mazo"
        role="progressbar"
        aria-label="Cartas resueltas"
        aria-valuemin="0"
        aria-valuemax={total}
        aria-valuenow={resueltas}
      >
        {items.map((item, i) => (
          <span
            key={item.id}
            className={(respuestas[item.id] !== undefined ? 'resuelta ' : '') + (i === actual ? 'en-mesa' : '')}
          />
        ))}
      </div>

      <div className="quiz-panel-datos">
        <span><small>Resueltas</small><strong>{resueltas}/{total}</strong></span>
        <span><small>Avance</small><strong>{porcentaje}%</strong></span>
      </div>
    </aside>
  )
}

/** Pantalla completa para esperas y transiciones. */
function Pantalla({ titulo, texto, aviso, imagen = personaCelularGaming, etiqueta = 'Preparando la partida' }) {
  return (
    <div className="rv quiz-espera">
      <Ambiente />
      <div className="quiz-espera-tablero">
        <figure className="quiz-espera-visual">
          <img src={imagen} alt="Personaje de REVO preparando las cartas del cuestionario" decoding="async" />
          <div className="quiz-baraja" aria-hidden="true"><span /><span /><span /></div>
        </figure>
        <div className="quiz-espera-caja" role="status" aria-live="polite">
          <span className="quiz-espera-etiq">{etiqueta}</span>
          <h2>{titulo}</h2>
          <p>{texto}</p>
          {aviso && <p className="quiz-aviso">{aviso}</p>}
          <div className="quiz-cargando" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
        </div>
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
  const manejarTecla = useEffectEvent((e) => {
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
  })

  useEffect(() => {
    const onKeyDown = (event) => manejarTecla(event)
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // ── Pantallas de espera ──────────────────────────────────
  if (loading) {
    return <Pantalla titulo="Barajando tus primeras cartas"
      texto="Estamos eligiendo diez preguntas para descubrir dónde aparece tu primera señal." />
  }

  if (submitting) {
    const textos = {
      1: ['Analizando tus respuestas', 'Buscamos las tres ramas que mejor encajan contigo.'],
      2: ['Calculando tu perfil', 'Combinamos todo lo que respondiste para generar la recomendación.'],
      3: ['Cerrando tu resultado', 'Un momento más.'],
    }
    const [t, s] = textos[phase] || textos[2]
    return <Pantalla titulo={t} texto={s} aviso={error}
      imagen={personaDiferenciaGaming} etiqueta="Leyendo tu jugada" />
  }

  if (transitioning) {
    return <Pantalla titulo="Nueva ronda desbloqueada"
      texto="Ya encontramos señal. Ahora el mazo se concentra en tus tres ramas más prometedoras."
      imagen={personaDiferenciaGaming} etiqueta="Fase 2: Afina" />
  }

  if (phase !== 3 && !q) {
    return <Pantalla titulo="No pudimos repartir las cartas"
      texto="Revisa tu conexión y vuelve a cargar la página para intentarlo otra vez."
      aviso={error || 'El cuestionario no recibió preguntas.'}
      imagen={personaDiferenciaGaming} etiqueta="Partida interrumpida" />
  }

  // ── FASE 3: perfil profesional ───────────────────────────
  if (phase === 3) {
    const p3q = phase3Questions[phase3Current]
    const p3Sel = phase3Answers[p3q?.id]
    const p3Total = phase3Questions.length
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
      <div className="rv quiz" style={{ '--cat': '#D9B35B' }}>
        <Ambiente />
        <div className="quiz-lienzo">
          <FaseHud fase={3} actual={phase3Current + 1} total={p3Total} />

          <main className="quiz-mesa">
            <PanelMazo fase={3} items={phase3Questions} respuestas={phase3Answers} actual={phase3Current} />

            {p3q && (
              <section key={p3q.id} className="quiz-carta quiz-carta-final rv-entra" style={{ animationDelay: '.05s' }}>
                <div className="quiz-carta-borde" aria-hidden="true" />
                <div className="quiz-carta-cab">
                  <span className="quiz-sello"><b>PR</b> Perfil profesional</span>
                  <span className="quiz-instruccion">Elige una carta</span>
                </div>

                <h1 className="quiz-pregunta">{p3q.question}</h1>

                <div className="quiz-ops" role="radiogroup" aria-label="Opciones de perfil profesional">
                  {p3q.options.map((opt, i) => (
                    <button key={opt.key} type="button" role="radio"
                      aria-checked={p3Sel === opt.key}
                      onClick={() => elegir(opt.key)}
                      style={{ '--i': i }}
                      className={`quiz-op ${p3Sel === opt.key ? 'sel' : ''}`}>
                      <span className="quiz-op-letra" aria-hidden="true">{opt.key}</span>
                      <span className="quiz-op-txt">{opt.text}</span>
                      <span className="quiz-op-confirmacion" aria-hidden="true">Elegida</span>
                    </button>
                  ))}
                </div>

                <nav className="quiz-nav" aria-label="Navegación del cuestionario">
                  <button onClick={() => phase3Current > 0 && setPhase3Current((c) => c - 1)}
                    disabled={phase3Current === 0} className="quiz-btn quiz-btn-sec">
                    <span aria-hidden="true">←</span> Anterior
                  </button>
                  <button onClick={siguienteP3} disabled={!p3Sel} className="quiz-btn quiz-btn-pri">
                    {p3Ultima ? 'Revelar mi perfil' : 'Jugar esta carta'} <span aria-hidden="true">→</span>
                  </button>
                </nav>
              </section>
            )}
          </main>
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

      <div className="quiz-lienzo">
        <FaseHud fase={phase} actual={current + 1} total={total} />

        <main className="quiz-mesa">
          <PanelMazo fase={phase} items={questions} respuestas={answers} actual={current} />

        {q && (
          <section ref={cardRef} className="quiz-carta" key={q.id}>
            <div className="quiz-carta-borde" aria-hidden="true" />
            <div className="quiz-carta-cab">
            {cat.label && (
              <span className="quiz-sello">
                <b aria-hidden="true">{cat.icon}</b> {cat.label}
              </span>
            )}
              <span className="quiz-instruccion">Elige tu nivel</span>
            </div>

            <h1 className="quiz-pregunta">{q.text}</h1>

            {error && <p className="quiz-error" role="alert">{error}</p>}

            <div className="quiz-escala" role="radiogroup" aria-label="Qué tanto te representa">
              {ESCALA.map(({ v, corta, larga }, i) => (
                <button key={v} type="button" role="radio" data-v={v}
                  aria-checked={answers[q.id] === v}
                  aria-label={`${v} de 5: ${larga}`}
                  onClick={() => setAnswer(v)}
                  style={{
                    '--i': i,
                    '--spread': `${Math.abs(2 - i) * 4}px`,
                    '--rotation': `${(i - 2) * 1.6}deg`,
                  }}
                  className={`quiz-op-esc ${answers[q.id] === v ? 'sel' : ''}`}>
                  <span className="quiz-esc-num" aria-hidden="true">0{v}</span>
                  <span className="quiz-bolita" aria-hidden="true"><i /></span>
                  <span className="quiz-esc-txt"><strong>{corta}</strong><small>{larga}</small></span>
                  <span className="quiz-op-confirmacion" aria-hidden="true">Elegida</span>
                </button>
              ))}
            </div>

            <nav className="quiz-nav" aria-label="Navegación del cuestionario">
              <button onClick={prev} disabled={current === 0} className="quiz-btn quiz-btn-sec">
                <span aria-hidden="true">←</span> Anterior
              </button>
              <button onClick={next} disabled={!isAnswered} className="quiz-btn quiz-btn-pri">
                {isLast
                  ? (phase === 1 ? 'Desbloquear fase 2' : 'Ir al perfil profesional')
                  : 'Jugar esta carta'} <span aria-hidden="true">→</span>
              </button>
            </nav>

            <p className="quiz-atajos">
              Teclado: <kbd>1</kbd><span>-</span><kbd>5</kbd> para elegir, <kbd>Enter</kbd> para jugar
            </p>
          </section>
        )}
        </main>
      </div>
    </div>
  )
}
