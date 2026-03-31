import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'

const SPEC_COLORS = {
  'Desarrollo Web & Móvil':'#6C63FF', 'Data Science & Inteligencia Artificial':'#00D4FF',
  'Ciberseguridad':'#FF6B6B','Redes e Infraestructura':'#F59E0B',
  'Ingeniería de Software':'#10B981','Cloud Computing & DevOps':'#8B5CF6'
}

export default function History() {
  const { user } = useAuth()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    mlApi.getHistory(user.id).then(r => setHistory(r.data || [])).finally(() => setLoading(false))
  }, [user])

  return (
    <div className="page" style={{ paddingBottom: 80 }}>
      <div className="container" style={{ maxWidth: 800 }}>
        <div className="animate-fade" style={{ marginBottom: 36 }}>
          <h1 style={{ fontFamily:'Space Grotesk', fontSize:'2rem', fontWeight:800, letterSpacing:'-0.02em', marginBottom:8 }}>
            Historial de Evaluaciones
          </h1>
          <p className="text-muted">Todas tus evaluaciones con el Árbol de Decisión</p>
        </div>

        {loading ? (
          [...Array(4)].map((_,i) => (
            <div key={i} className="skeleton" style={{ height: 80, marginBottom: 16, borderRadius: 16 }} />
          ))
        ) : history.length === 0 ? (
          <div className="glass" style={{ padding:'60px 32px', textAlign:'center' }}>
            <div style={{ fontSize:'3rem', marginBottom:16 }}>📋</div>
            <h3 style={{ marginBottom:8 }}>Sin evaluaciones aún</h3>
            <p className="text-muted text-sm" style={{ marginBottom:24 }}>Completa tu primer cuestionario para ver tu historial</p>
            <Link to="/questionnaire" className="btn btn-primary">Comenzar evaluación →</Link>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {history.map((h, i) => {
              const color = SPEC_COLORS[h.specialization] || '#6C63FF'
              return (
                <Link to={`/results/${h.prediction_id}`} key={i} className="glass animate-fade"
                  style={{ padding:'20px 24px', display:'flex', alignItems:'center', gap:20, textDecoration:'none', color:'inherit', animationDelay:`${i*0.07}s` }}>
                  <div style={{ width:48, height:48, borderRadius:14, background: color+'22', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'1.4rem', flexShrink:0 }}>
                    🌳
                  </div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontWeight:700, fontSize:'1rem', marginBottom:4, color:'#F1F5F9' }}>{h.specialization}</div>
                    <div style={{ fontSize:'0.8rem', color:'#64748B' }}>
                      {new Date(h.created_at).toLocaleDateString('es-ES', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
                    </div>
                    <div className="progress-track" style={{ marginTop:8, height:4, maxWidth:300 }}>
                      <div className="progress-fill" style={{ width:`${h.confidence_pct}%`, background:color }} />
                    </div>
                  </div>
                  <div style={{ textAlign:'right', flexShrink:0 }}>
                    <div style={{ fontFamily:'Space Grotesk', fontSize:'1.5rem', fontWeight:900, color }}>
                      {h.confidence_pct}%
                    </div>
                    <div style={{ fontSize:'0.75rem', color:'#64748B' }}>compatibilidad</div>
                  </div>
                  <div style={{ color:'#475569', fontSize:'1.2rem' }}>→</div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
