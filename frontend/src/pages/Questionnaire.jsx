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

export default function Questionnaire() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [answers, setAnswers] = useState({})     // { questionId: value }
  const [current, setCurrent] = useState(0)       // index pregunta actual (dentro de la fase actual)
  const [phase, setPhase] = useState(1)           // 1 o 2
  
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
          // Fase Finalizada (Predicción Completada)
          navigate(`/results/${transitionData.prediction_id}`)
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

  return (
    <div className="page quiz-page">
      <div className="container quiz-container">
        {/* Progress header */}
        <div className="quiz-header animate-fade">
          <div className="quiz-progress-info">
            <span className="text-sm text-muted"> Fase {phase}/2 — Pregunta {current + 1} de {questions.length}</span>
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
                {isLast ? (phase === 1 ? '🔥 Ir a Fase 2 →' : '🌳 Descubrir mi Futuro →') : 'Siguiente →'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
