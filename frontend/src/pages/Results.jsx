import { useState, useEffect } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { mlApi } from '../services/api'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, Cell } from 'recharts'
import './Results.css'

const CAREERS = {
  'Desarrollo de Software':               { paths: ['Frontend Developer', 'Backend Developer', 'Full Stack Developer', 'Mobile Developer', 'Software Architect'], color:'#3B82F6' },
  'Data Science & IA':                    { paths: ['Data Scientist', 'Machine Learning Engineer', 'Data Analyst', 'AI Engineer', 'Computer Vision Engineer'], color:'#10B981' },
  'Infraestructura & Cloud':              { paths: ['DevOps Engineer', 'Cloud Engineer', 'SysAdmin', 'Network Engineer', 'SRE'], color:'#8B5CF6' },
  'Ciberseguridad':                       { paths: ['Ethical Hacker / Pentester', 'Security Analyst (SOC)', 'Digital Forensics', 'Security Engineer'], color:'#EF4444' },
  'Soporte Técnico & IT Ops':             { paths: ['IT Support Specialist', 'Soporte Técnico', 'Field Support Technician', 'IT Operations'], color:'#F59E0B' },
  'QA & Testing':                         { paths: ['QA Automation Engineer', 'Performance Tester', 'SDET', 'QA Analyst'], color:'#EC4899' },
  'Gestión y Producto':                   { paths: ['Product Manager', 'Scrum Master', 'Project Manager (PM)', 'Product Owner'], color:'#6366F1' },
  'Diseño UX/UI':                         { paths: ['UX Designer', 'UI Designer', 'Product Designer', 'UX Researcher'], color:'#F43F5E' },
  'Sistemas Empresariales':               { paths: ['ERP Consultant (SAP/Oracle)', 'CRM Specialist', 'Business Intelligence', 'IT Consultant'], color:'#14B8A6' },
  'Investigación e Innovación':           { paths: ['Blockchain Developer', 'IoT Engineer', 'AR/VR Developer', 'Investigador en IA'], color:'#64748B' },
}

export default function Results() {
  const { id } = useParams()
  const { state } = useLocation()
  const [data, setData] = useState(state || null)
  const [importances, setImportances] = useState([])
  const [loading, setLoading] = useState(!state)

  useEffect(() => {
    if (!state && id) {
      mlApi.getPrediction(id).then(r => setData(r.data)).finally(() => setLoading(false))
    }
    mlApi.importances().then(r => setImportances(r.data.slice(0, 8))).catch(() => {})
  }, [id])

  if (loading) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center"><div style={{ fontSize:'3rem', animation:'float 2s ease-in-out infinite' }}>🌳</div>
        <p className="text-muted">Cargando resultado...</p>
      </div>
    </div>
  )
  if (!data) return <div className="page"><div className="container"><p className="text-muted">Resultado no encontrado.</p></div></div>

  const primary = data.primary
  const color = primary?.color || CAREERS[primary?.name]?.color || '#6C63FF'
  const careers = CAREERS[primary?.name]?.paths || []

  // Radar data (top3 como datos del radar)
  const radarData = (data.top3 || []).map(s => ({
    subject: s.name?.split(' ')[0] || s.name,
    value: Math.round((s.confidence || s.score || 0) * 100),
    fullMark: 100,
  }))

  // Bar chart data (todas las probabilidades)
  const barData = Object.entries(data.all_probabilities || {}).map(([name, val]) => ({
    name: name.split(' ')[0],
    value: val,
    color: CAREERS[name]?.color || '#6C63FF',
  })).sort((a, b) => b.value - a.value)

  return (
    <div className="page results-page">
      <div className="container">
        {/* Hero resultado */}
        <div className="result-hero glass animate-fade" style={{ '--c': color }}>
          <div className="result-hero-bg" />
          <div className="result-hero-content">
            <div className="result-hero-left">
              <span className="badge badge-purple">Tu Especialización Recomendada</span>
              <h1 className="result-main-name">{primary?.name}</h1>
              <div className="result-conf-row">
                <span className="result-conf-big" style={{ color }}>{primary?.confidence_pct}%</span>
                <span className="text-muted">de compatibilidad</span>
              </div>
              <div className="progress-track result-bar">
                <div className="progress-fill" style={{ width:`${primary?.confidence_pct}%`, background: color }} />
              </div>
              <p className="text-muted text-sm result-model-tag">🌳 Árbol de Decisión · v{data.model_version}</p>

              {/* Rutas de carrera */}
              <div className="career-paths">
                {careers.map((c, i) => (
                  <span key={i} className="career-path-chip" style={{ borderColor: color+'44', color }}>
                    {c}
                  </span>
                ))}
              </div>
            </div>

            <div className="result-hero-right">
              <div className="conf-circle" style={{ '--c': color }}>
                <svg viewBox="0 0 120 120" width="120" height="120">
                  <circle cx="60" cy="60" r="50" fill="none" strokeWidth="8" stroke="rgba(255,255,255,0.06)" />
                  <circle cx="60" cy="60" r="50" fill="none" strokeWidth="8" stroke={color}
                    strokeDasharray={`${(primary?.confidence_pct || 0) * 3.14} 314`}
                    strokeLinecap="round" transform="rotate(-90 60 60)" />
                </svg>
                <div className="conf-circle-text">
                  <span style={{ color }}>{primary?.confidence_pct}%</span>
                  <small>match</small>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="results-grid">
          {/* Top 3 */}
          <div className="glass results-panel animate-fade" style={{ animationDelay:'0.1s' }}>
            <h3 className="panel-title">Top 3 Especializaciones</h3>
            {(data.top3 || []).map((s, i) => {
              const c = s.color || CAREERS[s.name]?.color || '#6C63FF'
              return (
                <div key={i} className="top3-item">
                  <div className="top3-rank" style={{ color: c }}>#{i+1}</div>
                  <div className="top3-info">
                    <div className="top3-name font-semibold">{s.name}</div>
                    <div className="progress-track" style={{ marginTop: 6 }}>
                      <div className="progress-fill" style={{ width:`${s.confidence_pct}%`, background: c }} />
                    </div>
                  </div>
                  <div className="top3-pct font-bold" style={{ color: c }}>{s.confidence_pct}%</div>
                </div>
              )
            })}
          </div>

          {/* Radar Chart */}
          {radarData.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.2s' }}>
              <h3 className="panel-title">Distribución de Aptitudes</h3>
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.08)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#94A3B8', fontSize: 11 }} />
                  <Radar name="Score" dataKey="value" stroke={color} fill={color} fillOpacity={0.25} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Bar Chart */}
          {barData.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.3s' }}>
              <h3 className="panel-title">Probabilidades del Árbol</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={barData} margin={{ left: -20 }}>
                  <XAxis dataKey="name" tick={{ fill:'#94A3B8', fontSize:10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background:'#111827', border:'1px solid rgba(255,255,255,0.08)', borderRadius:10, color:'#F1F5F9' }}
                    formatter={(v) => [`${v}%`, 'Probabilidad']}
                  />
                  <Bar dataKey="value" radius={[6,6,0,0]}>
                    {barData.map((d,i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Feature importances */}
          {importances.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.4s' }}>
              <h3 className="panel-title">Preguntas más influyentes</h3>
              {importances.slice(0,6).map((f, i) => (
                <div key={i} className="importance-item">
                  <span className="importance-label text-sm">{f.feature.toUpperCase()}</span>
                  <div className="importance-bar-wrap">
                    <div className="progress-track" style={{ height: 6 }}>
                      <div className="progress-fill" style={{ width:`${f.pct * 5}%`, background: color }} />
                    </div>
                  </div>
                  <span className="importance-pct text-xs text-muted">{f.pct}%</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="result-actions animate-fade" style={{ animationDelay: '0.5s' }}>
          <Link to="/questionnaire" className="btn btn-primary">Nueva evaluación</Link>
          <Link to="/history" className="btn btn-secondary">Ver historial</Link>
          <Link to="/dashboard" className="btn btn-ghost">Volver al dashboard</Link>
        </div>
      </div>
    </div>
  )
}
