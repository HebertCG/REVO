import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { mlApi, surveyApi } from '../services/api'
import './Dashboard.css'

const SPEC_COLORS = {
  'Desarrollo Web & Móvil': '#6C63FF',
  'Data Science & Inteligencia Artificial': '#00D4FF',
  'Ciberseguridad': '#FF6B6B',
  'Redes e Infraestructura': '#F59E0B',
  'Ingeniería de Software': '#10B981',
  'Cloud Computing & DevOps': '#8B5CF6',
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    Promise.all([
      mlApi.getHistory(user.id).catch(() => ({ data: [] })),
      mlApi.overview().catch(() => ({ data: null })),
    ]).then(([h, o]) => {
      setHistory(h.data || [])
      setOverview(o.data)
    }).finally(() => setLoading(false))
  }, [user])

  const lastPred = history[0] || null
  const color = lastPred ? (SPEC_COLORS[lastPred.specialization] || '#6C63FF') : '#6C63FF'

  return (
    <div className="page dashboard">
      <div className="container">
        {/* Header */}
        <div className="dash-header animate-fade">
          <div>
            <h1 className="dash-greeting">
              ¡Hola, <span className="gradient-text">{user?.full_name?.split(' ')[0]}</span>! 👋
            </h1>
            <p className="text-muted">
              {user?.semester ? `${user.semester}° Semestre` : 'Estudiante'} · {user?.student_code || 'Sin código'}
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/questionnaire')}>
            + Nueva Evaluación
          </button>
        </div>

        {/* Stats row */}
        <div className="dash-stats animate-fade" style={{ animationDelay: '0.1s' }}>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background: 'rgba(108,99,255,0.15)', color: '#6C63FF' }}>📊</div>
            <div>
              <div className="stat-val">{history.length}</div>
              <div className="stat-lbl text-muted text-sm">Evaluaciones</div>
            </div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background: 'rgba(0,212,255,0.1)', color: '#00D4FF' }}>🎯</div>
            <div>
              <div className="stat-val">{lastPred ? `${lastPred.confidence_pct}%` : '—'}</div>
              <div className="stat-lbl text-muted text-sm">Última confianza</div>
            </div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.1)', color: '#10B981' }}>🌳</div>
            <div>
              <div className="stat-val">DT</div>
              <div className="stat-lbl text-muted text-sm">Árbol de Decisión</div>
            </div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.1)', color: '#F59E0B' }}>📚</div>
            <div>
              <div className="stat-val">{user?.semester || '—'}</div>
              <div className="stat-lbl text-muted text-sm">Semestre actual</div>
            </div>
          </div>
        </div>

        <div className="dash-grid">
          {/* Última predicción */}
          <div className="dash-main animate-fade" style={{ animationDelay: '0.2s' }}>
            {lastPred ? (
              <div className="result-preview glass" style={{ '--c': color }}>
                <div className="result-preview-bg" />
                <div className="result-preview-content">
                  <span className="badge badge-purple">Última Recomendación</span>
                  <h2 className="result-spec-name">{lastPred.specialization}</h2>
                  <div className="result-conf">
                    <span className="conf-num" style={{ color }}>{lastPred.confidence_pct}%</span>
                    <span className="text-muted text-sm">de compatibilidad</span>
                  </div>
                  <div className="progress-track" style={{ marginBottom: 24 }}>
                    <div className="progress-fill" style={{ width: `${lastPred.confidence_pct}%`, background: color }} />
                  </div>
                  <div className="flex gap-3 flex-wrap">
                    <Link to={`/results/${lastPred.prediction_id}`} className="btn btn-primary btn-sm">
                      Ver detalles →
                    </Link>
                    <button onClick={() => navigate('/questionnaire')} className="btn btn-secondary btn-sm">
                      Nueva evaluación
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state glass">
                <div className="empty-icon">🎯</div>
                <h3>¡Haz tu primera evaluación!</h3>
                <p className="text-muted text-sm">Responde el cuestionario y descubre tu especialización ideal.</p>
                <Link to="/questionnaire" className="btn btn-primary">Comenzar cuestionario →</Link>
              </div>
            )}
          </div>

          {/* Historial reciente */}
          <div className="dash-side animate-fade" style={{ animationDelay: '0.3s' }}>
            <div className="glass" style={{ padding: 24 }}>
              <div className="flex justify-between items-center" style={{ marginBottom: 20 }}>
                <h3 className="font-semibold">Historial reciente</h3>
                <Link to="/history" className="text-sm" style={{ color: '#6C63FF' }}>Ver todo</Link>
              </div>
              {loading ? (
                [...Array(3)].map((_,i) => (
                  <div key={i} className="skeleton" style={{ height: 64, marginBottom: 12, borderRadius: 12 }} />
                ))
              ) : history.length === 0 ? (
                <p className="text-muted text-sm text-center" style={{ padding: '20px 0' }}>Sin evaluaciones aún</p>
              ) : (
                history.slice(0,5).map((h, i) => (
                  <Link to={`/results/${h.prediction_id}`} key={i} className="history-item">
                    <div className="history-dot" style={{ background: SPEC_COLORS[h.specialization] || '#6C63FF' }} />
                    <div className="history-info">
                      <div className="history-spec font-semibold text-sm">{h.specialization}</div>
                      <div className="text-xs text-muted">{new Date(h.created_at).toLocaleDateString('es-ES', { day:'2-digit', month:'short', year:'numeric' })}</div>
                    </div>
                    <div className="history-conf text-sm font-bold" style={{ color: SPEC_COLORS[h.specialization] || '#6C63FF' }}>
                      {h.confidence_pct}%
                    </div>
                  </Link>
                ))
              )}
            </div>

            {/* CTA cuestionario */}
            <div className="glass cta-mini" style={{ padding: 20, textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: 8 }}>🌳</div>
              <p className="text-sm font-semibold" style={{ marginBottom: 4 }}>¿Quieres re-evaluar?</p>
              <p className="text-xs text-muted" style={{ marginBottom: 16 }}>El árbol aprende con cada evaluación</p>
              <Link to="/questionnaire" className="btn btn-ghost btn-sm w-full">Nuevo cuestionario</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
