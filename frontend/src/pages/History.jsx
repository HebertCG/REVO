import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../context/contextoAuth'
import { mlApi } from '../services/api'
import { ESTADO, SERIE, fechaCorta, fechaLarga, specMeta } from '../theme/specs'
import personaHistorial from '../assets/persona-historial-revo.webp'
import { buildHistorySeries, buildHistorySummary } from './historyInsights'
import '../theme/app.css'
import './History.css'

function readPattern(history) {
  if (history.length < 2) {
    return {
      color: ESTADO.neutro,
      title: 'Primera señal registrada',
      text: 'Este es tu punto de partida. Las siguientes evaluaciones permitirán reconocer qué intereses se mantienen en el tiempo.',
    }
  }

  const latest = history.slice(0, 3).map((item) => item.specialization)

  if (latest.length >= 3 && latest.every((specialization) => specialization === latest[0])) {
    return {
      color: ESTADO.bueno,
      title: 'Perfil consolidado',
      text: `Tres evaluaciones seguidas apuntan a ${latest[0]}. La repetición hace que esta señal sea especialmente consistente.`,
    }
  }

  if (latest[0] === latest[1]) {
    return {
      color: ESTADO.aviso,
      title: 'Perfil emergente',
      text: `Tus dos últimas evaluaciones coinciden en ${latest[0]}. Una nueva partida ayudará a confirmar la tendencia.`,
    }
  }

  return {
    color: ESTADO.neutro,
    title: 'Perfil en exploración',
    text: 'Tus resultados todavía cambian entre evaluaciones. Es normal: estás probando rutas y descubriendo qué te engancha más.',
  }
}

function formatValue(value) {
  return Number(value).toLocaleString('es-PE', { maximumFractionDigits: 1 })
}

function HistoryTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload
  const meta = specMeta(data.specialization)

  return (
    <div className="hist-tooltip">
      <p className="hist-tooltip-spec">
        <span className="rv-marca" style={{ background: meta.color }} aria-hidden="true" />
        {data.specialization}
      </p>
      <p className="rv-menor">{data.date}</p>
      <p className="rv-dato hist-tooltip-value">{formatValue(data.confidence)}%</p>
    </div>
  )
}

function TrendMark({ trend }) {
  if (trend === 'up') return <span aria-hidden="true">↗</span>
  if (trend === 'down') return <span aria-hidden="true">↘</span>
  return <span aria-hidden="true">→</span>
}

export default function History() {
  const { user } = useAuth()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    mlApi.getHistory(user.id)
      // `|| []` solo descarta null: una respuesta 200 con un cuerpo que no es
      // JSON valido llega aqui como cadena, pasa el filtro y revienta en el
      // primer `.reduce`. Lo que hace falta comprobar es que sea una lista.
      .then((response) => setHistory(Array.isArray(response.data) ? response.data : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [user])

  const series = buildHistorySeries(history, fechaCorta)
  const summary = buildHistorySummary(history)
  const latest = history[0]
  const latestMeta = latest ? specMeta(latest.specialization) : null
  const pattern = history.length ? readPattern(history) : null
  const trendLabel = summary.total < 2
    ? 'Punto de partida'
    : summary.trend === 'up'
      ? 'En ascenso'
      : summary.trend === 'down'
        ? 'Nueva exploración'
        : 'Trayectoria estable'

  return (
    <div className="rv hist">
      <div className="hist-atmosphere" aria-hidden="true" />
      <div className="rv-ancho hist-shell">
        <header
          className="hist-hero rv-entra"
          style={{ '--hist-spec': latestMeta?.color || SERIE }}
        >
          <div className="hist-hero-copy">
            <p className="hist-kicker">
              <span aria-hidden="true">◆</span>
              Tu trayectoria REVO
            </p>
            <h1>Cada evaluación deja una señal.</h1>
            <p className="hist-hero-lead">
              Mira cómo evoluciona tu perfil, reconoce los intereses que se repiten
              y vuelve a jugar cuando quieras descubrir una ruta nueva.
            </p>

            <dl className="hist-hero-stats">
              <div>
                <dt>Evaluaciones</dt>
                <dd className="rv-dato">{loading ? '—' : summary.total}</dd>
              </div>
              <div>
                <dt>Confianza actual</dt>
                <dd className="rv-dato">
                  {loading || !summary.total ? '—' : `${formatValue(summary.latestConfidence)}%`}
                </dd>
              </div>
              <div>
                <dt>Desde el inicio</dt>
                <dd className={`rv-dato hist-trend hist-trend-${summary.trend}`}>
                  {!loading && summary.total >= 2 ? (
                    <>
                      <TrendMark trend={summary.trend} />
                      {summary.delta > 0 ? '+' : ''}{formatValue(summary.delta)} pts
                    </>
                  ) : 'Nueva ruta'}
                </dd>
              </div>
            </dl>

            <div className="hist-hero-actions">
              <Link to="/questionnaire" className="rv-btn hist-primary-action">
                Jugar otra evaluación
                <span aria-hidden="true">→</span>
              </Link>
              {latest && (
                <Link to={`/results/${latest.prediction_id}`} className="hist-text-link">
                  Ver último resultado
                </Link>
              )}
            </div>
          </div>

          <div className="hist-hero-visual">
            <div className="hist-orbit hist-orbit-one" aria-hidden="true" />
            <div className="hist-orbit hist-orbit-two" aria-hidden="true" />
            <img
              src={personaHistorial}
              width={887}
              height={1774}
              alt="Personaje REVO revisando los hitos de su trayectoria"
              decoding="async"
                  className="hist-mascot"
            />
            <div className="hist-live-signal">
              <span className="hist-live-dot" aria-hidden="true" />
              <span>
                <small>Señal actual</small>
                <strong>{latest?.specialization || 'Lista para comenzar'}</strong>
              </span>
            </div>
          </div>
        </header>

        {loading ? (
          <div className="hist-loading" aria-label="Cargando historial">
            <div className="rv-esq hist-loading-chart" />
            <div className="rv-esq hist-loading-side" />
            <div className="rv-esq hist-loading-row" />
            <div className="rv-esq hist-loading-row" />
          </div>
        ) : history.length === 0 ? (
          <section className="hist-empty rv-entra">
            <span className="hist-empty-mark" aria-hidden="true">01</span>
            <div>
              <p className="rv-etiq">Tu primer hito</p>
              <h2>Tu trayectoria empieza con una partida</h2>
              <p className="rv-sub">
                Completa las tres fases del cuestionario y aquí aparecerán tu primera
                señal, su nivel de confianza y el inicio de tu evolución.
              </p>
            </div>
            <Link to="/questionnaire" className="rv-btn rv-btn-2">Comenzar ahora</Link>
          </section>
        ) : (
          <main className="hist-content">
            <section className="hist-overview" aria-label="Resumen de trayectoria">
              <article className="hist-chart-panel rv-entra">
                <div className="hist-section-heading">
                  <div>
                    <p className="rv-etiq">Mapa de confianza</p>
                    <h2>Tu evolución, evaluación a evaluación</h2>
                  </div>
                  <div className="hist-average">
                    <span className="rv-dato">{summary.average}%</span>
                    <small>promedio</small>
                  </div>
                </div>

                {series.length >= 2 ? (
                  <div className="hist-chart" role="img" aria-label="Gráfica de la confianza de tus evaluaciones en orden cronológico">
                    <ResponsiveContainer width="100%" height={280}>
                      <AreaChart data={series} margin={{ left: -18, right: 12, top: 24, bottom: 0 }}>
                        <defs>
                          <linearGradient id="historyConfidenceFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={SERIE} stopOpacity={0.34} />
                            <stop offset="100%" stopColor={SERIE} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="var(--linea-sutil)" vertical={false} />
                        <XAxis
                          dataKey="date"
                          tick={{ fill: 'var(--tinta-3)', fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          dy={8}
                        />
                        <YAxis
                          domain={[0, 100]}
                          ticks={[0, 25, 50, 75, 100]}
                          tick={{ fill: 'var(--tinta-3)', fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <ReferenceLine y={summary.average} stroke="var(--linea)" strokeDasharray="5 5" />
                        <Tooltip content={<HistoryTooltip />} cursor={{ stroke: 'var(--linea)' }} />
                        <Area
                          type="monotone"
                          dataKey="confidence"
                          stroke={SERIE}
                          strokeWidth={3}
                          fill="url(#historyConfidenceFill)"
                          dot={{ r: 4, fill: SERIE, stroke: 'var(--sup)', strokeWidth: 3 }}
                          activeDot={{ r: 7, fill: '#EEF2FB', stroke: SERIE, strokeWidth: 3 }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="hist-first-point">
                    <span className="hist-first-line" aria-hidden="true" />
                    <span className="hist-first-node" aria-hidden="true" />
                    <div>
                      <strong>Primer punto guardado</strong>
                      <p>Con tu siguiente evaluación aparecerá la primera tendencia.</p>
                    </div>
                  </div>
                )}

                <div className="hist-chart-caption">
                  <span><i className="hist-caption-line" aria-hidden="true" />Confianza del modelo</span>
                  <span><i className="hist-caption-dash" aria-hidden="true" />Promedio histórico</span>
                </div>
              </article>

              <aside
                className="hist-insight rv-entra"
                style={{ '--hist-insight': pattern.color, animationDelay: '.06s' }}
              >
                <div className="hist-insight-top">
                  <span className="hist-insight-icon" aria-hidden="true">✦</span>
                  <span className="rv-etiq">Lectura de trayectoria</span>
                </div>
                <div>
                  <h2>{pattern.title}</h2>
                  <p>{pattern.text}</p>
                </div>
                <div className="hist-insight-route">
                  <span className="hist-route-node is-old" aria-hidden="true" />
                  <span className="hist-route-line" aria-hidden="true" />
                  <span className="hist-route-node is-current" aria-hidden="true" />
                </div>
                <div className="hist-insight-foot">
                  <span>
                    <small>Estado</small>
                    <strong>{trendLabel}</strong>
                  </span>
                  <span>
                    <small>Última afinidad</small>
                    <strong>{latest.specialization}</strong>
                  </span>
                </div>
              </aside>
            </section>

            <section className="hist-timeline rv-entra" style={{ animationDelay: '.1s' }}>
              <div className="hist-timeline-heading">
                <div>
                  <p className="rv-etiq">Bitácora de señales</p>
                  <h2>Tu recorrido completo</h2>
                  <p className="rv-sub">Abre cualquier hito para revisar el resultado de esa evaluación.</p>
                </div>
                <span className="hist-count rv-dato">
                  {summary.total.toString().padStart(2, '0')} / 10
                </span>
              </div>

              <ol className="hist-list">
                {history.map((item, index) => {
                  const meta = specMeta(item.specialization)
                  const sequence = history.length - index

                  return (
                    <li key={item.prediction_id} style={{ '--hist-item-color': meta.color }}>
                      <span className="hist-timeline-node rv-dato" aria-hidden="true">
                        {String(sequence).padStart(2, '0')}
                      </span>
                      <Link to={`/results/${item.prediction_id}`} className="hist-item">
                        <span className="hist-item-icon" aria-hidden="true">{meta.icon}</span>
                        <span className="hist-item-body">
                          <span className="hist-item-topline">
                            <strong>{item.specialization}</strong>
                            {index === 0 && <span className="hist-current-label">Más reciente</span>}
                          </span>
                          <span className="rv-menor">{fechaLarga(item.created_at)}</span>
                          <span className="rv-pista hist-item-progress" aria-hidden="true">
                            <span
                              className="rv-relleno"
                              style={{ width: `${item.confidence_pct}%`, background: meta.color }}
                            />
                          </span>
                        </span>
                        <span className="hist-item-confidence">
                          <span className="rv-dato">{formatValue(item.confidence_pct)}%</span>
                          <small>confianza</small>
                        </span>
                        <span className="hist-item-arrow" aria-hidden="true">↗</span>
                      </Link>
                    </li>
                  )
                })}
              </ol>
            </section>
          </main>
        )}
      </div>
    </div>
  )
}
