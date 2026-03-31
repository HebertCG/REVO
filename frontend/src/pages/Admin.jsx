import { useState, useEffect } from 'react'
import { mlApi, authApi } from '../services/api'
import { BarChart, Bar, XAxis, Tooltip, Cell, ResponsiveContainer, PieChart, Pie, Legend } from 'recharts'
import './Admin.css'

const SPEC_COLORS = {
  'Desarrollo de Software':'#3B82F6',
  'Data Science & IA':'#10B981',
  'Infraestructura & Cloud':'#8B5CF6',
  'Ciberseguridad':'#EF4444',
  'Soporte Técnico & IT Ops':'#F59E0B',
  'QA & Testing':'#EC4899',
  'Gestión y Producto':'#6366F1',
  'Diseño UX/UI':'#F43F5E',
  'Sistemas Empresariales':'#14B8A6',
  'Investigación e Innovación':'#64748B',
}

export default function Admin() {
  const [overview, setOverview]       = useState(null)
  const [trainHistory, setTrainHistory] = useState([])
  const [training, setTraining]       = useState(false)
  const [trainResult, setTrainResult] = useState(null)
  const [loading, setLoading]         = useState(true)

  const fetchData = () => {
    Promise.all([mlApi.overview(), mlApi.trainingHistory()])
      .then(([o, t]) => { setOverview(o.data); setTrainHistory(t.data) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchData() }, [])

  const handleRetrain = async () => {
    setTraining(true); setTrainResult(null)
    try {
      const { data } = await mlApi.retrain()
      setTrainResult(data)
      fetchData()
    } catch (e) {
      setTrainResult({ error: e.response?.data?.detail || 'Error al reentrenar' })
    } finally { setTraining(false) }
  }

  const dist = overview?.specialization_dist || []
  const pieData = dist.map(d => ({
    name: d.name.split(' ')[0], value: d.total, color: SPEC_COLORS[d.name] || '#6C63FF'
  }))

  return (
    <div className="page admin-page">
      <div className="container">
        <div className="admin-header animate-fade">
          <div>
            <h1 className="admin-title">Panel de Administración</h1>
            <p className="text-muted">Gestión del modelo ML y estadísticas del sistema</p>
          </div>
          <button onClick={handleRetrain} disabled={training} className="btn btn-primary">
            {training ? '⏳ Entrenando...' : '🌳 Re-entrenar Modelo'}
          </button>
        </div>

        {/* Train result alert */}
        {trainResult && !trainResult.error && (
          <div className="admin-alert success animate-scale">
            <strong>Modelo re-entrenado exitosamente</strong>
            <span>Accuracy: {(trainResult.accuracy * 100).toFixed(1)}% · F1: {(trainResult.f1 * 100).toFixed(1)}% · Profundidad: {trainResult.tree_depth} · Hojas: {trainResult.n_leaves}</span>
          </div>
        )}
        {trainResult?.error && (
          <div className="admin-alert error animate-scale"><strong>Error:</strong> {trainResult.error}</div>
        )}

        {/* Stats overview */}
        <div className="admin-stats animate-fade" style={{ animationDelay:'0.1s' }}>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background:'rgba(108,99,255,0.15)', color:'#6C63FF' }}>📊</div>
            <div><div className="stat-val">{overview?.total_predictions || 0}</div><div className="stat-lbl text-muted text-sm">Predicciones</div></div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background:'rgba(0,212,255,0.1)', color:'#00D4FF' }}>🎯</div>
            <div><div className="stat-val">{overview?.avg_confidence_pct || 0}%</div><div className="stat-lbl text-muted text-sm">Confianza Promedio</div></div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background:'rgba(16,185,129,0.1)', color:'#10B981' }}>🌳</div>
            <div><div className="stat-val">{overview?.last_training?.model_version || 'N/A'}</div><div className="stat-lbl text-muted text-sm">Versión del Modelo</div></div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon" style={{ background:'rgba(245,158,11,0.1)', color:'#F59E0B' }}>📈</div>
            <div>
              <div className="stat-val">{overview?.last_training ? (overview.last_training.accuracy * 100).toFixed(1) + '%' : 'N/A'}</div>
              <div className="stat-lbl text-muted text-sm">Accuracy del Modelo</div>
            </div>
          </div>
        </div>

        <div className="admin-grid animate-fade" style={{ animationDelay:'0.2s' }}>
          {/* Distribution chart */}
          <div className="glass admin-panel">
            <h3 className="panel-title">Distribución de Especializaciones</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={dist.map(d => ({ name: d.name.split(' ')[0], total: d.total, color: SPEC_COLORS[d.name] || '#6C63FF' }))} margin={{ left:-20 }}>
                <XAxis dataKey="name" tick={{ fill:'#94A3B8', fontSize:10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background:'#111827', border:'1px solid rgba(255,255,255,0.08)', borderRadius:10, color:'#F1F5F9' }} />
                <Bar dataKey="total" radius={[6,6,0,0]}>
                  {dist.map((_,i) => <Cell key={i} fill={Object.values(SPEC_COLORS)[i] || '#6C63FF'} fillOpacity={0.8} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Training history */}
          <div className="glass admin-panel">
            <h3 className="panel-title">Historial de Entrenamientos</h3>
            {trainHistory.length === 0 ? (
              <p className="text-muted text-sm text-center" style={{ padding:'20px 0' }}>Sin entrenamientos registrados</p>
            ) : (
              <div className="train-list">
                {trainHistory.slice(0,6).map((t, i) => (
                  <div key={i} className="train-item">
                    <div>
                      <div className="text-sm font-semibold">{t.model_version}</div>
                      <div className="text-xs text-muted">{t.trained_at ? new Date(t.trained_at).toLocaleString('es-ES') : '—'}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div className="text-sm font-bold" style={{ color: '#10B981' }}>
                        {t.accuracy ? (t.accuracy * 100).toFixed(1) + '%' : '—'}
                      </div>
                      <div className="text-xs text-muted">{t.training_samples} muestras · depth {t.tree_depth}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Last training info */}
        {overview?.last_training && (
          <div className="glass admin-panel animate-fade" style={{ animationDelay:'0.3s', padding:28 }}>
            <h3 className="panel-title">Modelo Actual</h3>
            <div className="model-info-grid">
              {[
                { l:'Versión',   v: overview.last_training.model_version },
                { l:'Accuracy',  v: (overview.last_training.accuracy * 100).toFixed(1) + '%' },
                { l:'F1 Score',  v: (overview.last_training.f1 * 100).toFixed(1) + '%' },
                { l:'Muestras',  v: overview.last_training.samples },
                { l:'Algoritmo', v: 'DecisionTreeClassifier' },
                { l:'Entrenado', v: overview.last_training.trained_at ? new Date(overview.last_training.trained_at).toLocaleDateString('es-ES') : '—' },
              ].map((item, i) => (
                <div key={i} className="model-info-item">
                  <div className="text-xs text-muted font-semibold" style={{ textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:4 }}>{item.l}</div>
                  <div className="font-bold">{item.v}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
