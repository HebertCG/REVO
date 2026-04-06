import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { surveyApi, mlApi } from '../services/api'
import './Questionnaire.css'

const CATEGORY_META = {
  academic:    { label: 'Académico',    icon: '📚', color: '#6C63FF' },
  skills:      { label: 'Habilidades',  icon: '🛠️', color: '#00D4FF' },
  interests:   { label: 'Intereses',    icon: '❤️',  color: '#FF6B9D' },
  personality: { label: 'Personalidad', icon: '🧠', color: '#10B981' },
}

// Preguntas de la Fase 3 Psicométrica (puramente frontend)
const PHASE3_QUESTIONS = [
  {
    id: 'p3_1',
    question: 'Acabas de terminar un módulo de código. ¿Cuál es tu reacción natural?',
    options: [
      { key: 'A', text: 'Lo analizo buscando posibles bugs antes de entregarlo' },
      { key: 'B', text: 'Lo entrego y si hay bugs, los corrijo sobre la marcha' },
      { key: 'C', text: 'Lo comparto con mi equipo para recibir retroalimentación' },
      { key: 'D', text: 'Lo refactorizo para que sea más limpio y eficiente' },
    ]
  },
  {
    id: 'p3_2',
    question: 'Un sistema falla en producción a las 2am. ¿Qué haces primero?',
    options: [
      { key: 'A', text: 'Reviso los logs con calma y construyo un diagnóstico completo' },
      { key: 'B', text: 'Implemento un hotfix temporal y lo resuelvo en profundidad mañana' },
      { key: 'C', text: 'Escalo al líder técnico del equipo inmediatamente' },
      { key: 'D', text: 'No lo publico hasta tener total certeza de la causa raíz' },
    ]
  },
  {
    id: 'p3_3',
    question: '¿Cómo prefieres aprender algo nuevo en tecnología?',
    options: [
      { key: 'A', text: 'Con documentación técnica oficial, paso a paso' },
      { key: 'B', text: 'Construyendo un proyecto real desde el día 1' },
      { key: 'C', text: 'En equipo, con pair programming o grupo de estudio' },
      { key: 'D', text: 'Con video tutoriales, tomando notas y repasando' },
    ]
  },
  {
    id: 'p3_4',
    question: 'Descíbete en un equipo de trabajo de software:',
    options: [
      { key: 'A', text: 'El arquitecto: diseño la estructura del sistema' },
      { key: 'B', text: 'El ejecutor: soy el primero en entregar resultados' },
      { key: 'C', text: 'El conector: coordino y comunico entre áreas' },
      { key: 'D', text: 'El revisor: nada sale sin pasar por mis manos' },
    ]
  },
]

function calcArchetype(answers) {
  const counts = { A: 0, B: 0, C: 0, D: 0 }
  Object.values(answers).forEach(v => { if (counts[v] !== undefined) counts[v]++ })
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
}

export default function Questionnaire() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [answers, setAnswers] = useState({})     // { questionId: value }
  const [current, setCurrent] = useState(0)       // index pregunta actual
  const [phase, setPhase] = useState(1)           // 1, 2 o 3
  const [phase3Answers, setPhase3Answers] = useState({}) // respuestas psicométricas
  const [phase3Current, setPhase3Current] = useState(0)  // índice dentro de Fase 3
  
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError] = useState('')
  const cardRef = useRef(null)

  useEffect(() => {
    if (!user) return
    let sid = null
    surveyApi.createSession()
      .then(sRes => {
        sid = sRes.data.id
        setSessionId(sid)
        return surveyApi.getSessionQuestions(sid)
      })
      .then(qRes => {
        setQuestions(qRes.data)
      })
      .catch(e => {
        console.error("Error cargando cuestionario", e)
        setError('Error cargando el cuestionario')
      })
      .finally(() => setLoading(false))
  }, [user])

  const loadPhase2 = async (sid) => {
    setTransitioning(true)
    try {
      const qRes = await surveyApi.getSessionQuestions(sid)
      setQuestions(qRes.data)
      setCurrent(0)
      setPhase(2)
    } catch(e) {
      setError('Error al cargar preguntas avanzadas.')
    } finally {
      setTransitioning(false)
    }
  }

  const triggerPhase3 = () => {
    setPhase(3)
    setPhase3Current(0)
    setPhase3Answers({})
  }

  const q = questions[current]
  const progress = questions.length ? Math.round((current / questions.length) * 100) : 0
  const isAnswered = q && answers[q.id] !== undefined
  const isLast = current === questions.length - 1

  const setAnswer = (val) => setAnswers(a => ({ ...a, [q.id]: val }))

  const next = async () => {
    if (!isAnswered) return
    // Guardar respuesta actual en bd
    surveyApi.saveAnswers(sessionId, {
      answers: [{ question_id: q.id, value: answers[q.id] }]
    }).catch(console.error)

    if (isLast) { 
      setSubmitting(true)
      try {
        // Enviar bloque de validación
        const allPhaseAnswers = questions.map(q2 => ({ question_id: q2.id, value: answers[q2.id] || 3 }))
        await surveyApi.saveAnswers(sessionId, { answers: allPhaseAnswers })
        
        // Finalizar la Fase
        const { data: transitionData } = await surveyApi.submitPhase(sessionId)
        
        if (transitionData.next_phase === 2) {
          // Motor Adaptativo: Nos envía a Fase 2 Profundización
          setSubmitting(false)
          loadPhase2(sessionId)
        } else if (transitionData.prediction_id) {
          // Fase Finalizada — Lanzar Fase 3 Psicométrica antes de ir a resultados
          setSubmitting(false)
          sessionStorage.setItem('revo_pending_result', transitionData.prediction_id)
          triggerPhase3()
        } else {
          setError('Respuesta no reconocida al procesar encuesta.')
          setSubmitting(false)
        }
      } catch (e) {
        setError('Error al procesar tus respuestas. Intenta de nuevo.')
        setSubmitting(false)
      }
    } else {
      // Siguiente pregunta animada
      if (cardRef.current) { cardRef.current.style.opacity = '0'; cardRef.current.style.transform = 'translateX(30px)' }
      setTimeout(() => {
        setCurrent(c => c + 1)
        if (cardRef.current) { cardRef.current.style.opacity = '1'; cardRef.current.style.transform = 'translateX(0)' }
      }, 200)
    }
  }

  const prev = () => {
    if (current > 0) setCurrent(c => c - 1)
  }

  if (loading) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center">
        <div className="loading-tree">🌳</div>
        <p className="text-muted">Iniciando Fase 1: Calibración General...</p>
      </div>
    </div>
  )

  if (submitting) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center analyzing">
        <div className="analyzing-icon">🧠</div>
        <h2 className="gradient-text" style={{ fontFamily:'Space Grotesk', fontSize:'1.8rem', fontWeight:800 }}>
          {phase === 1 ? 'Calculando Inteligencia Adaptativa...' : 'Ejecutando Árbol de ML...'}
        </h2>
        <p className="text-muted">
          {phase === 1 ? 'Encontrando tus mejores 3 ramas y generando preguntas avanzadas.' : 'El algoritmo está decidiendo tu futuro ideal.'}
        </p>
        <div className="analyzing-dots"><span/><span/><span/></div>
      </div>
    </div>
  )
  
  if (transitioning) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center analyzing">
        <div className="analyzing-icon">🔥</div>
        <h2 className="gradient-text" style={{ fontFamily:'Space Grotesk', fontSize:'1.8rem', fontWeight:800 }}>
          ¡Fase 2 Desbloqueada!
        </h2>
        <p className="text-muted">Hemos descubierto para qué eres bueno. Ahora, a profundizar.</p>
        <div className="analyzing-dots"><span/><span/><span/></div>
      </div>
    </div>
  )

  // ── FASE 3: Cuestionario Psicométrico ──────────────────────────────────────
  if (phase === 3) {
    const p3q = PHASE3_QUESTIONS[phase3Current]
    const p3Progress = Math.round(((phase3Current) / PHASE3_QUESTIONS.length) * 100)
    const p3Selected = phase3Answers[p3q?.id]
    const isLastP3 = phase3Current === PHASE3_QUESTIONS.length - 1

    const handleP3Select = (key) => {
      setPhase3Answers(prev => ({ ...prev, [p3q.id]: key }))
    }

    const handleP3Next = () => {
      if (!p3Selected) return
      if (isLastP3) {
        // Calcular arquetipo y navegar a resultados
        const finalAnswers = { ...phase3Answers, [p3q.id]: p3Selected }
        const archetype = calcArchetype(finalAnswers)
        sessionStorage.setItem('revo_archetype', JSON.stringify(archetype))
        const pendingId = sessionStorage.getItem('revo_pending_result')
        navigate(`/results/${pendingId}`)
      } else {
        setPhase3Current(c => c + 1)
      }
    }

    return (
      <div className="page quiz-page">
        <div className="container quiz-container">
          <div className="quiz-header animate-fade">
            <div className="quiz-progress-info">
              <span className="text-sm text-muted">🧠 Fase 3/3 — Perfil Profesional · Pregunta {phase3Current + 1} de {PHASE3_QUESTIONS.length}</span>
              <span className="text-sm font-semibold" style={{ color: '#10B981' }}>{p3Progress}%</span>
            </div>
            <div className="progress-track" style={{ height: 8 }}>
              <div className="progress-fill" style={{ width: `${p3Progress}%`, background: '#10B981' }} />
            </div>
            <div style={{ marginTop: 12, padding: '8px 14px', background: 'rgba(16,185,129,0.08)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)' }}>
              <span className="text-sm" style={{ color: '#10B981' }}>🎉 ¡El árbol toma de decisión ya calculó tu especialización! Ahora descubramos tu Arquetipo Profesional.</span>
            </div>
          </div>

          {p3q && (
            <div className="glass question-card animate-scale" style={{ transition: 'opacity 0.2s, transform 0.2s' }}>
              <div className="q-category-badge" style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981' }}>
                🧠 Perfil Psicométrico
              </div>
              <h2 className="q-text">{p3q.question}</h2>

              {/* Opciones tipo card en lugar de escala numérica */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, margin: '24px 0' }}>
                {p3q.options.map(opt => (
                  <button
                    key={opt.key}
                    onClick={() => handleP3Select(opt.key)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                      padding: '14px 18px', borderRadius: 12, cursor: 'pointer',
                      border: p3Selected === opt.key ? '2px solid #10B981' : '1px solid rgba(255,255,255,0.08)',
                      background: p3Selected === opt.key ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.03)',
                      color: p3Selected === opt.key ? '#F1F5F9' : '#94A3B8',
                      transition: 'all 0.2s ease', fontFamily: 'inherit', fontSize: '0.95rem',
                    }}
                  >
                    <span style={{
                      width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: '0.85rem', flexShrink: 0,
                      background: p3Selected === opt.key ? '#10B981' : 'rgba(255,255,255,0.08)',
                      color: p3Selected === opt.key ? '#fff' : '#64748B',
                    }}>
                      {opt.key}
                    </span>
                    {opt.text}
                  </button>
                ))}
              </div>

              <div className="quiz-nav">
                <button onClick={() => phase3Current > 0 && setPhase3Current(c => c - 1)} disabled={phase3Current === 0} className="btn btn-secondary">
                  ← Anterior
                </button>
                <button onClick={handleP3Next} disabled={!p3Selected} className="btn btn-primary"
                  style={{ background: '#10B981', borderColor: '#10B981' }}>
                  {isLastP3 ? '🎯 Ver mi Resultado Completo →' : 'Siguiente →'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── FASES 1 y 2: Cuestionario normal ───────────────────────────────────────
  return (
    <div className="page quiz-page">
      <div className="container quiz-container">
        {/* Progress header */}
        <div className="quiz-header animate-fade">
          <div className="quiz-progress-info">
            <span className="text-sm text-muted"> Fase {phase}/3 — Pregunta {current + 1} de {questions.length}</span>
            <span className="text-sm font-semibold" style={{ color: '#6C63FF' }}>{progress}%</span>
          </div>
          <div className="progress-track" style={{ height: 8 }}>
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          {/* Categoría indicator */}
          {q && (
            <div className="quiz-categories">
              {Object.entries(CATEGORY_META).map(([key, meta]) => (
                <div key={key} className={`cat-chip ${q.category === key ? 'active' : ''}`}
                  style={{ '--cc': meta.color }}>
                  {meta.icon} {meta.label}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Question card */}
        {q && (
          <div className="glass question-card animate-scale" ref={cardRef}
            style={{ transition: 'opacity 0.2s, transform 0.2s' }}>
            <div className="q-category-badge" style={{ background: CATEGORY_META[q.category]?.color + '22', color: CATEGORY_META[q.category]?.color }}>
              {CATEGORY_META[q.category]?.icon} {CATEGORY_META[q.category]?.label}
            </div>
            <h2 className="q-text">{q.text}</h2>
            {error && <div className="auth-error text-sm">{error}</div>}

            {/* Scale 1-5 */}
            <div className="scale-container">
              <span className="scale-label">{q.min_label}</span>
              <div className="scale-buttons">
                {[1,2,3,4,5].map(v => (
                  <button key={v} onClick={() => setAnswer(v)}
                    className={`scale-btn ${answers[q.id] === v ? 'selected' : ''}`}
                    style={ answers[q.id] === v ? { background: CATEGORY_META[q.category]?.color, borderColor: CATEGORY_META[q.category]?.color } : {} }>
                    {v}
                  </button>
                ))}
              </div>
              <span className="scale-label">{q.max_label}</span>
            </div>

            {/* Scale descriptors */}
            <div className="scale-desc">
              {[
                { v:1, l:'Muy bajo' }, { v:2, l:'Bajo'}, { v:3, l:'Regular'},
                { v:4, l:'Bueno'}, { v:5, l:'Excelente'}
              ].map(d => (
                <span key={d.v} className={`scale-desc-item ${answers[q.id] === d.v ? 'sel' : ''}`}>{d.l}</span>
              ))}
            </div>

            {/* Navigation */}
            <div className="quiz-nav">
              <button onClick={prev} disabled={current === 0} className="btn btn-secondary">
                ← Anterior
              </button>
              <button onClick={next} disabled={!isAnswered} className="btn btn-primary">
                {isLast ? (phase === 1 ? '🔥 Ir a Fase 2 →' : '🧠 Ir a Perfil Profesional →') : 'Siguiente →'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
