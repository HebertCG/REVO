import { useState, useEffect } from 'react'
import { mlApi, authApi } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Cell, ResponsiveContainer, LineChart, Line, Legend, PieChart, Pie } from 'recharts'
import './Admin.css'

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
}

const DICTIONARY = {
  f1: { title: "⚡ Precisión F1 Base", content: "El F1 Score es la métrica de balance perfecta de la IA. Es la media armónica entre la Precisión (cuántos acertó) y el Recall (cuántos no omitió). Mide qué tan buena es la IA clasificando alumnos sin sesgos." },
  memory: { title: "🧠 Volumen de Memoria (N)", content: "Representa el total de perfiles de alumnos (Vectores de Características) con los que el Árbol de Decisión construyó su matriz de conocimiento empírico." },
  confidence: { title: "🎯 Confianza Algorítmica Global", content: "Es el promedio de probabilidad estocástica. Si es 87%, significa que estadísticamente, la IA está muy segura del camino recomendado y tiene poco margen de duda al predecir ramas." },
  hyperparam: { title: "🔬 Hiperparámetro (Max Depth)", content: "Es un limitador de sobreajuste (Overfitting). Evita que el Árbol de Decisión se vuelva hiper-complejo y asimile datos basura limitando sus ramificaciones a 8 saltos matemáticos." },
  chart_evol: { title: "📈 Evolución de Precisión (Time Series)", content: "Este análisis demuestra cómo mejora el algoritmo.<br/><br/><strong>Accuracy:</strong> Es el porcentaje total de veces que la IA atinó la carrera exacta de los alumnos.<br/><br/><strong>F1 Score:</strong> Es una métrica avanzada que castiga a la IA matemáticamente si comete errores graves al clasificar carreras que se parecen mucho entre sí." },
  chart_exp: { title: "⚖️ Explicabilidad (Feature Importances)", content: "Utiliza el Índice de Gini para auditar el Árbol.<br/><br/>¿Qué significan las 'aff'? Son tus variables. <strong>aff_1</strong> equivale a la <em>Afinidad hacia Desarrollo de Software</em>, <strong>aff_2</strong> a <em>Data Science</em>, y así hasta el 10.<br/><br/>La barra horizontal más larga indica qué aptitud técnica toma más el algoritmo para decidir el destino de un estudiante." },
}

const Modal = ({ isOpen, onClose, title, content }) => {
  if (!isOpen) return null;
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 999, backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', background: '#0F172A', border: '1px solid rgba(255,255,255,0.1)', padding: '24px', borderRadius: '16px', zIndex: 1000, maxWidth: '500px', width: '90%', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: '1.2rem', color: '#F1F5F9' }}>{title}</h3>
        <p style={{ margin: 0, color: '#94A3B8', lineHeight: '1.5', fontSize: '0.95rem' }} dangerouslySetInnerHTML={{ __html: content }}></p>
        <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', padding: '10px', borderRadius: '8px', marginTop: '24px', width: '100%', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>Entendido</button>
      </div>
    </>
  )
}

export default function Admin() {
  const [overview, setOverview] = useState(null)
  const [trainHistory, setTrainHistory] = useState([])
  const [importances, setImportances] = useState([])
  const [training, setTraining] = useState(false)
  const [trainResult, setTrainResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeModal, setActiveModal] = useState(null)

  const fetchData = () => {
    Promise.all([mlApi.overview(), mlApi.trainingHistory()])
      .then(([o, t]) => { setOverview(o.data); setTrainHistory(t.data) })
      .finally(() => setLoading(false))

    mlApi.importances().then(i => setImportances(i.data.slice(0, 5))).catch(() => { })
  }

  useEffect(() => { 
    fetchData() 
    // Polling en tiempo real: Actualiza los datos cada 5 segundos sin recargar la página
    const interval = setInterval(() => { fetchData() }, 5000)
    return () => clearInterval(interval)
  }, [])

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

  // Data for LineChart (Accuracy over time)
  const historyChartData = [...trainHistory].reverse().map((t, idx) => ({
    name: `V${idx + 1}`,
    accuracy: t.accuracy ? Number((t.accuracy * 100).toFixed(1)) : 0,
    f1: t.f1 ? Number((t.f1 * 100).toFixed(1)) : 0
  }))

  const pointerStyle = { cursor: 'pointer', transition: 'transform 0.2s ease', position: 'relative' }
  const hoverEffect = (e) => { e.currentTarget.style.transform = 'translateY(-2px) scale(1.02)' }
  const resetEffect = (e) => { e.currentTarget.style.transform = 'none' }

  return (
    <div className="page admin-page" style={{ paddingBottom: '100px' }}>
      <div className="container">

        <Modal
          isOpen={!!activeModal}
          onClose={() => setActiveModal(null)}
          title={activeModal ? DICTIONARY[activeModal].title : ''}
          content={activeModal ? DICTIONARY[activeModal].content : ''}
        />

        <div className="admin-header animate-fade">
          <div>
            <h1 className="admin-title">Laboratorio Científico de IA (Admin)</h1>
            <p className="text-muted">Centro de control académico para observar el crecimiento y reajuste del clasificador ML. <strong>Da clic a los paneles para ver la definición técnica.</strong></p>
          </div>
          <button onClick={handleRetrain} disabled={training || overview?.new_predictions === 0} className="btn btn-primary" style={{ boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)' }}>
            {training ? '⏳ Optimizando Árbol...' : '🌳 REENTRENAR MANUALMENTE'}
          </button>
        </div>

        {/* Train result alert */}
        {trainResult && !trainResult.error && (
          <div className="admin-alert success animate-scale">
            <strong>🚀 Nuevo Ciclo de Inteligencia Asimilado (Supervisado)</strong>
            <span>Accuracy Elevado a: {(trainResult.accuracy * 100).toFixed(1)}% | F1 Score: {(trainResult.f1 * 100).toFixed(1)}% | Muestras Totales: {trainResult.training_samples}</span>
          </div>
        )}
        {trainResult?.error && (
          <div className="admin-alert error animate-scale"><strong>Error en Backpropagation/Traning:</strong> {trainResult.error}</div>
        )}

        {/* Ciclo de Auto-Aprendizaje (Nuevas Muestras) */}
        <div className="glass admin-panel animate-fade" style={{ animationDelay: '0.1s', marginBottom: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h3 className="panel-title" style={{ margin: 0, fontSize: '1.2rem', color: '#F1F5F9' }}>⚡ Crecimiento Biológico del Dataset en Tiempo Real</h3>
              <p className="text-muted text-sm" style={{ marginTop: '4px' }}>Nuevas encuestas resueltas por alumnos desde el último entrenamiento.</p>
            </div>
            <div className="text-2xl font-black" style={{ color: '#00D4FF', textShadow: '0 0 10px rgba(0,212,255,0.3)' }}>
              {overview?.new_predictions || 0} <span className="text-sm font-normal text-muted" style={{ textShadow: 'none' }}>/ 50 predicciones recolectadas</span>
            </div>
          </div>
          <div style={{ width: '100%', height: '14px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', overflow: 'hidden', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.5)' }}>
            <div style={{
              width: `${Math.min(((overview?.new_predictions || 0) / 50) * 100, 100)}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #6C63FF, #00D4FF)',
              transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1)',
              boxShadow: '0 0 10px rgba(0,212,255,0.5)'
            }} />
          </div>
          <div className="text-sm" style={{ color: '#10B981', fontWeight: '800', marginTop: '4px' }}>
            ✅ Al llegar a 50 respuestas de alumnos, el sistema ejecuta un Re-entrenamiento Automano.
          </div>
        </div>

        {/* Stats overview */}
        <div className="admin-stats animate-fade" style={{ animationDelay: '0.2s', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>

          <div className="stat-card glass" style={pointerStyle} onClick={() => setActiveModal('f1')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <div className="stat-icon" style={{ background: 'rgba(108,99,255,0.15)', color: '#6C63FF' }}>📈</div>
            <div>
              <div className="stat-val">{overview?.last_training ? (overview.last_training.accuracy * 100).toFixed(1) + '%' : 'N/A'}</div>
              <div className="stat-lbl text-muted text-sm">Precisión F1 Base ℹ️</div>
            </div>
          </div>

          <div className="stat-card glass" style={pointerStyle} onClick={() => setActiveModal('memory')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.1)', color: '#10B981' }}>🧠</div>
            <div>
              <div className="stat-val">{overview?.last_training?.samples || 0}</div>
              <div className="stat-lbl text-muted text-sm">Volumen de Memoria (N) ℹ️</div>
            </div>
          </div>

          <div className="stat-card glass" style={pointerStyle} onClick={() => setActiveModal('confidence')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.1)', color: '#F59E0B' }}>🎯</div>
            <div>
              <div className="stat-val">{overview?.avg_confidence_pct || 0}%</div>
              <div className="stat-lbl text-muted text-sm">Confianza Algorítmica ℹ️</div>
            </div>
          </div>

          <div className="stat-card glass" style={pointerStyle} onClick={() => setActiveModal('hyperparam')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <div className="stat-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#EF4444' }}>🔬</div>
            <div>
              <div className="stat-val">Prof. 8</div>
              <div className="stat-lbl text-muted text-sm">Max Depth ℹ️</div>
            </div>
          </div>

        </div>

        <div className="admin-grid animate-fade" style={{ animationDelay: '0.3s', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', marginTop: '24px' }}>

          {/* Evolución Continua del Modelo */}
          <div className="glass admin-panel" style={pointerStyle} onClick={() => setActiveModal('chart_evol')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              Evolución de Precisión (Time Series) ℹ️
            </h3>
            <p className="text-muted text-xs" style={{ marginBottom: '20px' }}>Trayectoria del F1 Score y Accuracy a lo largo de todos los re-entrenamientos ejecutados.</p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={historyChartData} margin={{ left: -20, right: 10, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#94A3B8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis domain={['auto', 100]} tick={{ fill: '#94A3B8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <RechartsTooltip contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, color: '#F1F5F9' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <Line type="monotone" name="Accuracy" dataKey="accuracy" stroke="#00D4FF" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />
                <Line type="monotone" name="F1 Score" dataKey="f1" stroke="#6C63FF" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Pesos Decisionales */}
          <div className="glass admin-panel" style={pointerStyle} onClick={() => setActiveModal('chart_exp')} onMouseEnter={hoverEffect} onMouseLeave={resetEffect}>
            <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              Explicabilidad (Feature Importances) ℹ️
            </h3>
            <p className="text-muted text-xs" style={{ marginBottom: '20px' }}>Atributos/Habilidades con el peso matemático más crítico al hacer los cortes de entropía del modelo.</p>
            {importances.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={importances} layout="vertical" margin={{ left: 0, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={true} vertical={false} />
                  <XAxis type="number" domain={[0, 'auto']} hide />
                  <YAxis type="category" dataKey="feature" width={60} tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 700 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} contentStyle={{ background: '#111827', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 10 }} />
                  <Bar dataKey="pct" name="Peso (%)" fill="#10B981" radius={[0, 6, 6, 0]} barSize={24} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '260px', display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="text-muted">Cargando métricas de explicabilidad...</div>
            )}
          </div>

        </div>

        {/* ── Fila 3: Data Source + Feedback + Exportar CSV ── */}
        <div className="admin-grid animate-fade" style={{ animationDelay: '0.4s', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', marginTop: '24px' }}>

          {/* Inteligencia Sintética vs Humana */}
          {(() => {
            const ds = overview?.data_sources
            const total = ds?.total || 1
            const data = [
              { name: 'Sintético (Base)', value: ds?.synthetic || 0, color: '#6C63FF' },
              { name: 'Humano (Real)', value: ds?.human || 0, color: '#10B981' },
            ]
            return (
              <div className="glass admin-panel">
                <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>🧬 Inteligencia Sintética vs Humana</h3>
                <p className="text-muted text-xs" style={{ marginBottom: 16 }}>Proporción del dataset de entrenamiento generado por máquina vs. dato real de universitarios.</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <ResponsiveContainer width={160} height={160}>
                    <PieChart>
                      <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3}>
                        {data.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                      </Pie>
                      <RechartsTooltip contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ flex: 1 }}>
                    {data.map((d, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: '50%', background: d.color }} />
                          <span className="text-sm text-muted">{d.name}</span>
                        </div>
                        <div style={{ fontWeight: 800, color: d.color }}>
                          {d.value} <span style={{ color: '#64748B', fontWeight: 400, fontSize: '0.8rem' }}>({total ? Math.round(d.value/total*100) : 0}%)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })()}

          {/* Tasa de Afinidad + Descubrimiento */}
          {(() => {
            const fb = overview?.feedback
            return (
              <div className="glass admin-panel">
                <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>📡 Validación Estudiantil</h3>
                <p className="text-muted text-xs" style={{ marginBottom: 20 }}>Retroalimentación de alumnos sobre la calidad del diagnóstico. Total de respuestas: <strong style={{ color: '#F1F5F9' }}>{fb?.total || 0}</strong></p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span className="text-sm text-muted">🎯 Tasa de Afinidad (IA te “leyó” bien)</span>
                      <span style={{ fontWeight: 800, color: '#10B981' }}>{fb?.affinity_rate || 0}%</span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.05)', borderRadius: 8, overflow: 'hidden' }}>
                      <div style={{ width: `${fb?.affinity_rate || 0}%`, height: '100%', background: 'linear-gradient(90deg, #10B981, #00D4FF)', borderRadius: 8, transition: 'width 1s ease' }} />
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span className="text-sm text-muted">🚀 Tasa de Descubrimiento Vocacional</span>
                      <span style={{ fontWeight: 800, color: '#6C63FF' }}>{fb?.discovery_rate || 0}%</span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.05)', borderRadius: 8, overflow: 'hidden' }}>
                      <div style={{ width: `${fb?.discovery_rate || 0}%`, height: '100%', background: 'linear-gradient(90deg, #6C63FF, #EC4899)', borderRadius: 8, transition: 'width 1s ease' }} />
                    </div>
                    <p className="text-xs text-muted" style={{ marginTop: 8, fontStyle: 'italic' }}>Alumnos que descubrieron una rama que no tenían en mente antes de REVO.</p>
                  </div>
                </div>
              </div>
            )
          })()}

          {/* Exportar Dataset CSV */}
          <div className="glass admin-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>📊 Exportar Dataset Completo</h3>
              <p className="text-muted text-xs" style={{ marginBottom: 16, lineHeight: 1.6 }}>
                Descarga el dataset de entrenamiento completo (sintético + datos humanos reales) como archivo CSV para análisis externo, presentaciones académicas o auditoría de la IA.
              </p>
              <div style={{ padding: '12px 16px', background: 'rgba(16,185,129,0.05)', borderRadius: 10, border: '1px solid rgba(16,185,129,0.1)', marginBottom: 16 }}>
                <p className="text-xs" style={{ color: '#10B981', margin: 0, lineHeight: 1.5 }}>
                  ✓ Incluye vectores de afinidad (aff_1...aff_10)<br/>
                  ✓ Columna de fuente: <code>synthetic</code> vs <code>human</code><br/>
                  ✓ Columna de especialización objetivo (ground truth)
                </p>
              </div>
            </div>
            <a
              href={mlApi.exportCsvUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              style={{ textAlign: 'center', boxShadow: '0 0 15px rgba(16,185,129,0.3)', background: 'linear-gradient(135deg, #10B981, #00D4FF)' }}
            >
              ↓ Descargar Dataset (CSV)
            </a>
          </div>

        </div>
      </div>
    </div>
  )
}
