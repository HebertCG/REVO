import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

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

function getInsight(history) {
  if (history.length < 2) return null
  const specs = history.map(h => h.specialization)
  const last3 = specs.slice(0, 3)

  // Consolidado: últimos 3 iguales
  if (last3.length >= 3 && last3.every(s => s === last3[0])) {
    return { type: 'consolidated', color: '#10B981', text: `🎯 Perfil consolidado en "${last3[0]}". Alta certeza del árbol — llevas 3 evaluaciones seguidas con el mismo resultado.` }
  }
  // Semi-consolidado: últimos 2 iguales
  if (last3.length >= 2 && last3[0] === last3[1]) {
    return { type: 'emerging', color: '#6C63FF', text: `⚡ Perfil emergente en "${last3[0]}". El árbol detecta una tendencia clara. Haz una evaluación más para consolidarlo.` }
  }
  // Explorando
  return { type: 'exploring', color: '#F59E0B', text: `🔄 Perfil en exploración activa — es completamente normal en los primeros semestres. El árbol está aprendiendo tu patrón.` }
}

export default function History() {
  const { user } = useAuth()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    mlApi.getHistory(user.id).then(r => setHistory(r.data || [])).finally(() => setLoading(false))
  }, [user])

  // Preparar datos del gráfico (cronológico ascendente)
  const chartData = [...history].reverse().map((h, i) => ({
    name: `Test ${i + 1}`,
    confianza: h.confidence_pct,
    spec: h.specialization,
    date: new Date(h.created_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' }),
    color: SPEC_COLORS[h.specialization] || '#6C63FF',
  }))

  const insight = getInsight(history)
  const avgConf = history.length ? Math.round(history.reduce((a, h) => a + h.confidence_pct, 0) / history.length) : 0

  const CustomDot = (props) => {
    const { cx, cy, payload } = props
    return <circle cx={cx} cy={cy} r={6} fill={payload.color} stroke="#0F172A" strokeWidth={2} />
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    const d = payload[0].payload
    return (
      <div style={{ background: '#0F172A', border: `1px solid ${d.color}44`, borderRadius: 10, padding: '10px 14px' }}>
        <div style={{ fontWeight: 700, color: d.color, marginBottom: 4 }}>{d.spec}</div>
        <div style={{ color: '#94A3B8', fontSize: '0.85rem' }}>{d.date}</div>
        <div style={{ fontSize: '1.2rem', fontWeight: 900, color: '#F1F5F9' }}>{d.confianza}%</div>
      </div>
    )
  }

  return (
    <div className="page" style={{ paddingBottom: 80 }}>
      <div className="container" style={{ maxWidth: 860 }}>
        <div className="animate-fade" style={{ marginBottom: 32 }}>
          <h1 style={{ fontFamily: 'Space Grotesk', fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 8 }}>
            Historial de Evaluaciones
          </h1>
          <p className="text-muted">Tu trayectoria de compatibilidad a lo largo del tiempo</p>
        </div>

        {/* Gráfica Evolutiva */}
        {!loading && history.length >= 2 && (
          <div className="glass animate-fade" style={{ padding: '24px', marginBottom: 24, animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
              <div>
                <h3 style={{ fontFamily: 'Space Grotesk', fontWeight: 700, margin: 0 }}>📈 Evolución de tu Perfil</h3>
                <p className="text-muted text-sm" style={{ marginTop: 4 }}>Cómo ha cambiado tu compatibilidad con el Árbol de Decisión en cada evaluación</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'Space Grotesk', fontSize: '1.8rem', fontWeight: 900, color: '#6C63FF' }}>{avgConf}%</div>
                <div className="text-muted text-xs">confianza promedio</div>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748B', fontSize: 11 }} axisLine={false} tickLine={false} />
                <ReferenceLine y={avgConf} stroke="rgba(108,99,255,0.3)" strokeDasharray="4 4" />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone"
                  dataKey="confianza"
                  stroke="#6C63FF"
                  strokeWidth={3}
                  dot={<CustomDot />}
                  activeDot={{ r: 8 }}
                />
              </LineChart>
            </ResponsiveContainer>

            {/* Insight dinámico */}
            {insight && (
              <div style={{ marginTop: 16, padding: '12px 16px', borderRadius: 10, background: insight.color + '11', border: `1px solid ${insight.color}33` }}>
                <p className="text-sm" style={{ color: insight.color, fontWeight: 600, margin: 0 }}>{insight.text}</p>
              </div>
            )}
          </div>
        )}

        {/* Lista de tests */}
        {loading ? (
          [...Array(4)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 80, marginBottom: 16, borderRadius: 16 }} />
          ))
        ) : history.length === 0 ? (
          <div className="glass" style={{ padding: '60px 32px', textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>📋</div>
            <h3 style={{ marginBottom: 8 }}>Sin evaluaciones aún</h3>
            <p className="text-muted text-sm" style={{ marginBottom: 24 }}>Completa tu primer cuestionario para ver tu historial</p>
            <Link to="/questionnaire" className="btn btn-primary">Comenzar evaluación →</Link>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {history.map((h, i) => {
              const color = SPEC_COLORS[h.specialization] || '#6C63FF'
              const isFirst = i === 0
              return (
                <Link to={`/results/${h.prediction_id}`} key={i} className="glass animate-fade"
                  style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 20, textDecoration: 'none', color: 'inherit', animationDelay: `${i * 0.07}s`, position: 'relative', overflow: 'hidden' }}>
                  {isFirst && (
                    <div style={{ position: 'absolute', top: 8, right: 12, background: color + '22', color, fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20, border: `1px solid ${color}44` }}>
                      ÚLTIMO
                    </div>
                  )}
                  <div style={{ width: 48, height: 48, borderRadius: 14, background: color + '22', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem', flexShrink: 0 }}>
                    🌳
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: 4, color: '#F1F5F9' }}>{h.specialization}</div>
                    <div style={{ fontSize: '0.8rem', color: '#64748B' }}>
                      {new Date(h.created_at).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                    </div>
                    <div className="progress-track" style={{ marginTop: 8, height: 4 }}>
                      <div className="progress-fill" style={{ width: `${h.confidence_pct}%`, background: color }} />
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontFamily: 'Space Grotesk', fontSize: '1.5rem', fontWeight: 900, color }}>
                      {h.confidence_pct}%
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748B' }}>compatibilidad</div>
                  </div>
                  <div style={{ color: '#475569', fontSize: '1.2rem' }}>→</div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
