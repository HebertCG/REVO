import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'
import './Dashboard.css'

const SPEC_COLORS = {
  'Desarrollo de Software': '#3B82F6',
  'Data Science & IA': '#10B981',
  'Infraestructura & Cloud': '#8B5CF6',
  'Ciberseguridad': '#EF4444',
  'Soporte Técnico & IT Ops': '#F59E0B',
  'QA & Testing': '#EC4899',
  'Gestión y Producto': '#6366F1',
  'Diseño UX/UI': '#F43F5E',
  'Sistemas Empresariales': '#14B8A6',
  'Investigación e Innovación': '#64748B',
  // Legacy
  'Desarrollo Web & Móvil': '#6C63FF',
  'Data Science & Inteligencia Artificial': '#00D4FF',
  'Redes e Infraestructura': '#F59E0B',
  'Ingeniería de Software': '#10B981',
  'Cloud Computing & DevOps': '#8B5CF6',
}

const SCORE_LEVELS = [
  { min: 0,   max: 200, label: 'Explorador Inicial',        icon: '🌱', color: '#64748B' },
  { min: 201, max: 500, label: 'Perfil Emergente',           icon: '🔥', color: '#F59E0B' },
  { min: 501, max: 800, label: 'Técnico en Consolidación',   icon: '⚡', color: '#6C63FF' },
  { min: 801, max: Infinity, label: 'Perfil Elite',          icon: '🏆', color: '#10B981' },
]

function calcREVOScore(history) {
  if (!history.length) return 0
  const evalPoints = history.length * 100
  const avgConf = history.reduce((acc, h) => acc + (h.confidence_pct || 0), 0) / history.length
  const confPoints = Math.round(avgConf * 2)
  // Bonus de consistencia: si los últimos 3 tests son la misma especialización
  let consistencyBonus = 0
  if (history.length >= 3) {
    const last3 = history.slice(0, 3).map(h => h.specialization)
    if (last3.every(s => s === last3[0])) consistencyBonus = 150
  }
  return evalPoints + confPoints + consistencyBonus
}

function getLevel(score) {
  return SCORE_LEVELS.find(l => score >= l.min && score <= l.max) || SCORE_LEVELS[0]
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
  const revoScore = calcREVOScore(history)
  const level = getLevel(revoScore)
  const nextLevel = SCORE_LEVELS.find(l => l.min > revoScore)
  const pointsToNext = nextLevel ? nextLevel.min - revoScore : 0

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
          {/* REVO Score — Reemplaza la tarjeta del DT */}
          <div className="stat-card glass" style={{ cursor: 'default', position: 'relative', overflow: 'hidden' }}>
            <div className="stat-icon" style={{ background: level.color + '22', color: level.color, fontSize: '1.4rem' }}>{level.icon}</div>
            <div>
              <div className="stat-val" style={{ color: level.color }}>{revoScore} pts</div>
              <div className="stat-lbl text-muted text-sm">REVO Score · {level.label}</div>
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

        {/* REVO Score Progress Banner */}
        {!loading && (
          <div className="glass animate-fade" style={{ padding: '16px 24px', marginBottom: 20, animationDelay: '0.15s', display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontWeight: 700, color: level.color }}>{level.icon} {level.label}</span>
                {nextLevel && <span className="text-muted text-sm">+{pointsToNext} pts para {nextLevel.label}</span>}
                {!nextLevel && <span style={{ color: '#10B981', fontWeight: 700 }}>🏆 Nivel máximo alcanzado</span>}
              </div>
              <div style={{ height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 8, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: nextLevel ? `${Math.min(((revoScore - level.min) / (nextLevel.min - level.min)) * 100, 100)}%` : '100%',
                  background: `linear-gradient(90deg, ${level.color}, ${nextLevel?.color || level.color})`,
                  borderRadius: 8,
                  transition: 'width 1s ease'
                }} />
              </div>
            </div>
            <div className="text-sm text-muted" style={{ maxWidth: 280 }}>
              {history.length === 0
                ? '🌱 Haz tu primera evaluación para empezar a acumular puntos.'
                : history.length < 3
                  ? '💡 Haz 3 evaluaciones seguidas con el mismo resultado para ganar +150 pts de consistencia.'
                  : '⚡ El árbol aprende más con cada evaluación que haces. ¡Sigue evaluándote!'}
            </div>
          </div>
        )}

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
                <Link to="/history" className="text-sm" style={{ color: '#6C63FF' }}>Ver todo →</Link>
              </div>
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 64, marginBottom: 12, borderRadius: 12 }} />
                ))
              ) : history.length === 0 ? (
                <p className="text-muted text-sm text-center" style={{ padding: '20px 0' }}>Sin evaluaciones aún</p>
              ) : (
                history.slice(0, 5).map((h, i) => (
                  <Link to={`/results/${h.prediction_id}`} key={i} className="history-item">
                    <div className="history-dot" style={{ background: SPEC_COLORS[h.specialization] || '#6C63FF' }} />
                    <div className="history-info">
                      <div className="history-spec font-semibold text-sm">{h.specialization}</div>
                      <div className="text-xs text-muted">{new Date(h.created_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
                    </div>
                    <div className="history-conf text-sm font-bold" style={{ color: SPEC_COLORS[h.specialization] || '#6C63FF' }}>
                      {h.confidence_pct}%
                    </div>
                  </Link>
                ))
              )}
            </div>

            {/* CTA */}
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
