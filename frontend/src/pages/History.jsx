import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'
import { specMeta, SERIE, ESTADO, fechaCorta, fechaLarga } from '../theme/specs'
import '../theme/app.css'
import './History.css'

/**
 * Lectura del patrón del estudiante a partir de sus últimas evaluaciones.
 * Se apoya en la repetición, que es la única señal fiable con pocos datos.
 */
function leerPatron(historial) {
  if (historial.length < 2) return null
  const ultimas = historial.slice(0, 3).map((h) => h.specialization)

  if (ultimas.length >= 3 && ultimas.every((s) => s === ultimas[0])) {
    return {
      color: ESTADO.bueno,
      titulo: 'Perfil consolidado',
      texto: `Tres evaluaciones seguidas apuntan a ${ultimas[0]}. Cuando el resultado se repite así, la recomendación es sólida.`,
    }
  }
  if (ultimas[0] === ultimas[1]) {
    return {
      color: ESTADO.aviso,
      titulo: 'Perfil emergente',
      texto: `Tus dos últimas evaluaciones coinciden en ${ultimas[0]}. Haz una más para confirmar la tendencia.`,
    }
  }
  return {
    color: ESTADO.neutro,
    titulo: 'Perfil en exploración',
    texto: 'Tus resultados todavía cambian entre evaluaciones. Es lo normal en los primeros ciclos: aún estás descubriendo qué te engancha.',
  }
}

export default function History() {
  const { user } = useAuth()
  const [historial, setHistorial] = useState([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    if (!user) return
    mlApi.getHistory(user.id)
      .then((r) => setHistorial(r.data || []))
      .catch(() => setHistorial([]))
      .finally(() => setCargando(false))
  }, [user])

  // Orden cronológico ascendente para el eje temporal.
  const serie = [...historial].reverse().map((h, i) => ({
    n: i + 1,
    confianza: h.confidence_pct,
    spec: h.specialization,
    fecha: fechaCorta(h.created_at),
  }))

  const patron = leerPatron(historial)
  const media = historial.length
    ? Math.round(historial.reduce((a, h) => a + h.confidence_pct, 0) / historial.length)
    : 0

  const primera = serie[0]
  const ultima = serie[serie.length - 1]
  const delta = serie.length >= 2 ? ultima.confianza - primera.confianza : 0

  const Globo = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    const d = payload[0].payload
    return (
      <div className="hist-globo">
        <p className="hist-globo-spec">
          <span className="rv-marca" style={{ background: specMeta(d.spec).color }} />
          {d.spec}
        </p>
        <p className="rv-menor">{d.fecha}</p>
        <p className="rv-dato hist-globo-num">{d.confianza}%</p>
      </div>
    )
  }

  return (
    <div className="rv hist">
      <div className="rv-ancho rv-ancho-est">

        <header className="hist-cab rv-entra">
          <p className="rv-etiq">Tu trayectoria</p>
          <h1>Historial de evaluaciones</h1>
          <p className="rv-sub">
            Cómo ha cambiado tu perfil desde que empezaste a usar REVO.
          </p>
        </header>

        {cargando ? (
          <div style={{ display: 'grid', gap: 14 }}>
            {[0, 1, 2].map((i) => <div key={i} className="rv-esq" style={{ height: 86 }} />)}
          </div>
        ) : historial.length === 0 ? (
          <section className="rv-tarjeta rv-vacio rv-entra">
            <div className="rv-vacio-icono">📋</div>
            <h2>Todavía no hay nada que mostrar</h2>
            <p className="rv-sub" style={{ maxWidth: '44ch', margin: '10px auto 22px' }}>
              Cuando completes tu primera evaluación aparecerá aquí, y a partir de
              la segunda podrás ver cómo evoluciona tu perfil.
            </p>
            <Link to="/questionnaire" className="rv-btn rv-btn-1">Hacer mi primera evaluación</Link>
          </section>
        ) : (
          <>
            {/* ── Resumen del patrón ─────────────────────── */}
            {patron && (
              <section className="rv-tarjeta hist-patron rv-entra">
                <span className="rv-marca-l" style={{ background: patron.color }} aria-hidden="true" />
                <div>
                  <h2 style={{ marginBottom: 6 }}>{patron.titulo}</h2>
                  <p className="rv-sub">{patron.texto}</p>
                </div>
              </section>
            )}

            {/* ── Evolución ──────────────────────────────────
                Con menos de tres puntos una línea no dice nada:
                se muestra la comparación directa en su lugar. */}
            {serie.length >= 3 ? (
              <section className="rv-tarjeta rv-entra" style={{ animationDelay: '.06s' }}>
                <div className="hist-gr-cab">
                  <div>
                    <h2>Evolución de tu confianza</h2>
                    <p className="rv-menor">
                      Qué tan seguro estuvo el modelo en cada evaluación
                    </p>
                  </div>
                  <div className="hist-gr-media">
                    <p className="rv-dato hist-gr-media-num">{media}%</p>
                    <p className="rv-menor">promedio</p>
                  </div>
                </div>

                <div className="hist-grafico">
                  <ResponsiveContainer width="100%" height={210}>
                    <LineChart data={serie} margin={{ left: -18, right: 12, top: 12, bottom: 0 }}>
                      <CartesianGrid stroke="var(--linea-sutil)" vertical={false} />
                      <XAxis
                        dataKey="fecha"
                        tick={{ fill: 'var(--tinta-3)', fontSize: 11 }}
                        axisLine={false} tickLine={false} dy={6}
                      />
                      <YAxis
                        domain={[0, 100]} ticks={[0, 25, 50, 75, 100]}
                        tick={{ fill: 'var(--tinta-3)', fontSize: 11 }}
                        axisLine={false} tickLine={false}
                      />
                      <ReferenceLine y={media} stroke="var(--linea)" strokeDasharray="4 4" />
                      <Tooltip content={<Globo />} cursor={{ stroke: 'var(--linea)' }} />
                      {/* Una sola serie: sin leyenda, el título la nombra. */}
                      <Line
                        type="monotone" dataKey="confianza"
                        stroke={SERIE} strokeWidth={2}
                        dot={{ r: 4, fill: SERIE, stroke: 'var(--sup)', strokeWidth: 2 }}
                        activeDot={{ r: 6, fill: SERIE, stroke: 'var(--sup)', strokeWidth: 2 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
            ) : serie.length === 2 && (
              <section className="rv-tarjeta rv-entra" style={{ animationDelay: '.06s' }}>
                <h2 style={{ marginBottom: 4 }}>Tus dos evaluaciones</h2>
                <p className="rv-menor" style={{ marginBottom: 18 }}>
                  Con una tercera evaluación aparecerá aquí tu curva de evolución.
                </p>
                <div className="hist-comp">
                  {serie.map((d, i) => (
                    <div key={i} className="hist-comp-col">
                      <p className="rv-menor">{d.fecha}</p>
                      <p className="rv-dato hist-comp-num">{d.confianza}%</p>
                      <div className="rv-pista">
                        <div className="rv-relleno"
                          style={{ width: `${d.confianza}%`, background: specMeta(d.spec).color }} />
                      </div>
                      <p className="hist-comp-spec">{d.spec}</p>
                    </div>
                  ))}
                </div>
                {delta !== 0 && (
                  <p className="rv-menor hist-comp-delta">
                    Tu confianza {delta > 0 ? 'subió' : 'bajó'}{' '}
                    <strong className="rv-dato" style={{ color: 'var(--tinta)' }}>
                      {Math.abs(delta).toFixed(1)} puntos
                    </strong>{' '}
                    entre ambas.
                  </p>
                )}
              </section>
            )}

            {/* ── Listado ────────────────────────────────── */}
            <section className="rv-entra" style={{ animationDelay: '.1s' }}>
              <h3 className="hist-lista-tit">
                {historial.length} {historial.length === 1 ? 'evaluación' : 'evaluaciones'}
              </h3>

              <ol className="hist-lista">
                {historial.map((h, i) => {
                  const m = specMeta(h.specialization)
                  return (
                    <li key={h.prediction_id}>
                      <Link to={`/results/${h.prediction_id}`} className="hist-item">
                        <span className="rv-marca-l hist-item-barra"
                          style={{ background: m.color }} aria-hidden="true" />

                        <span className="hist-item-icono" aria-hidden="true">{m.icon}</span>

                        <span className="hist-item-cuerpo">
                          <span className="hist-item-fila">
                            <span className="hist-item-nom">{h.specialization}</span>
                            {i === 0 && <span className="hist-item-ultimo">Más reciente</span>}
                          </span>
                          <span className="rv-menor">{fechaLarga(h.created_at)}</span>
                          <span className="rv-pista hist-item-pista">
                            <span className="rv-relleno"
                              style={{ width: `${h.confidence_pct}%`, background: m.color }} />
                          </span>
                        </span>

                        <span className="hist-item-pct">
                          <span className="rv-dato hist-item-num">{h.confidence_pct}%</span>
                          <span className="rv-menor">confianza</span>
                        </span>
                      </Link>
                    </li>
                  )
                })}
              </ol>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
