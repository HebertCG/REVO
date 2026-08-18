import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'
import {
  specMeta, calcularScore, nivelDe, siguienteNivel, fechaCorta,
} from '../theme/specs'
import '../theme/app.css'
import './Dashboard.css'

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [historial, setHistorial] = useState([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    if (!user) return
    mlApi.getHistory(user.id)
      .then((r) => setHistorial(r.data || []))
      .catch(() => setHistorial([]))
      .finally(() => setCargando(false))
  }, [user])

  const ultima = historial[0] || null
  const meta = ultima ? specMeta(ultima.specialization) : null
  const score = calcularScore(historial)
  const nivel = nivelDe(score)
  const proximo = siguienteNivel(score)
  const faltan = proximo ? proximo.min - score : 0
  const avance = proximo
    ? Math.min(((score - nivel.min) / (proximo.min - nivel.min)) * 100, 100)
    : 100

  const nombre = user?.full_name?.split(' ')[0] || 'estudiante'

  return (
    <div className="rv dash">
      <div className="rv-ancho">

        {/* ── Encabezado ───────────────────────────────── */}
        <header className="dash-cab rv-entra">
          <div>
            <p className="rv-etiq">Tu panel</p>
            <h1>Hola, {nombre}</h1>
            <p className="rv-sub">
              {user?.semester ? `Ciclo ${user.semester}` : 'Estudiante'}
              {user?.student_code ? ` · ${user.student_code}` : ''}
            </p>
          </div>
          <button className="rv-btn rv-btn-1" onClick={() => navigate('/questionnaire')}>
            Nueva evaluación
          </button>
        </header>

        {cargando ? (
          <div className="dash-esqueleto">
            <div className="rv-esq" style={{ height: 260 }} />
            <div className="rv-esq" style={{ height: 260 }} />
          </div>
        ) : !ultima ? (
          /* ── Sin evaluaciones ───────────────────────── */
          <section className="rv-tarjeta rv-vacio rv-entra">
            <div className="rv-vacio-icono">🎯</div>
            <h2>Aún no tienes ninguna evaluación</h2>
            <p className="rv-sub" style={{ maxWidth: '46ch', margin: '10px auto 22px' }}>
              Son 25 preguntas y unos seis minutos. Al terminar sabrás qué tres
              ramas de Ingeniería de Sistemas encajan mejor contigo, con el nivel
              de confianza de cada una.
            </p>
            <Link to="/questionnaire" className="rv-btn rv-btn-1">
              Empezar el test
            </Link>
          </section>
        ) : (
          <>
            {/* ── El resultado manda: ocupa el lugar principal ── */}
            <section className="dash-heroe rv-tarjeta rv-entra">
              <div className="dash-heroe-txt">
                <p className="rv-etiq">Tu última recomendación</p>

                <div className="dash-heroe-spec">
                  <span className="dash-heroe-icono" aria-hidden="true">{meta.icon}</span>
                  <h2>{ultima.specialization}</h2>
                </div>

                <div className="dash-heroe-num">
                  <span className="rv-dato dash-cifra">{ultima.confidence_pct}</span>
                  <span className="dash-cifra-pct rv-dato">%</span>
                  <span className="rv-sub">de compatibilidad</span>
                </div>

                <div className="rv-pista" style={{ margin: '4px 0 20px' }}>
                  <div
                    className="rv-relleno"
                    style={{ width: `${ultima.confidence_pct}%`, background: meta.color }}
                  />
                </div>

                <div className="dash-heroe-acc">
                  <Link to={`/results/${ultima.prediction_id}`} className="rv-btn rv-btn-1">
                    Ver mi resultado completo
                  </Link>
                  <Link to="/history" className="rv-btn rv-btn-2">Ver historial</Link>
                </div>

                <p className="rv-menor" style={{ marginTop: 14 }}>
                  Evaluado el {fechaCorta(ultima.created_at)}
                </p>
              </div>

              {/* Barra de color de la especialidad: el acento va aquí,
                  no en el texto, que se mantiene legible siempre. */}
              <div
                className="dash-heroe-borde"
                style={{ background: meta.color }}
                aria-hidden="true"
              />
            </section>

            {/* ── Métricas secundarias ───────────────────── */}
            <section className="dash-metricas rv-entra" style={{ animationDelay: '.06s' }}>
              <article className="rv-tarjeta dash-met">
                <p className="rv-etiq">Evaluaciones</p>
                <p className="rv-dato dash-met-num">{historial.length}</p>
                <p className="rv-menor">
                  {historial.length === 1 ? 'La primera de muchas' : 'Repite cada ciclo'}
                </p>
              </article>

              <article className="rv-tarjeta dash-met">
                <p className="rv-etiq">Confianza media</p>
                <p className="rv-dato dash-met-num">
                  {Math.round(
                    historial.reduce((a, h) => a + h.confidence_pct, 0) / historial.length
                  )}<span className="dash-met-pct">%</span>
                </p>
                <p className="rv-menor">Entre todas tus evaluaciones</p>
              </article>

              <article className="rv-tarjeta dash-met dash-met-nivel">
                <p className="rv-etiq">REVO Score</p>
                <p className="rv-dato dash-met-num">{score}</p>
                <p className="rv-menor">
                  <span className="rv-marca" style={{ background: nivel.color }} />{' '}
                  Nivel {nivel.label}
                </p>
              </article>
            </section>

            {/* ── Progreso de nivel ──────────────────────── */}
            <section className="rv-tarjeta dash-nivel rv-entra" style={{ animationDelay: '.1s' }}>
              <div className="dash-nivel-cab">
                <span className="rv-ficha">
                  <span aria-hidden="true">{nivel.icon}</span> {nivel.label}
                </span>
                {proximo ? (
                  <p className="rv-menor">
                    Te faltan <strong className="rv-dato" style={{ color: 'var(--tinta)' }}>{faltan}</strong> pts
                    {' '}para {proximo.label}
                  </p>
                ) : (
                  <p className="rv-menor">Has llegado al nivel máximo</p>
                )}
              </div>

              <div className="rv-pista" style={{ height: 8 }}>
                <div className="rv-relleno" style={{ width: `${avance}%`, background: nivel.color }} />
              </div>

              <p className="rv-menor dash-nivel-tip">
                {historial.length < 3
                  ? 'Consigue el mismo resultado en tres evaluaciones seguidas y ganas 150 puntos de consistencia.'
                  : 'Cada evaluación aporta 100 puntos, más el doble de tu confianza media.'}
              </p>
            </section>

            {/* ── Evaluaciones recientes ─────────────────── */}
            <section className="rv-entra" style={{ animationDelay: '.14s' }}>
              <div className="dash-lista-cab">
                <h3>Evaluaciones recientes</h3>
                {historial.length > 4 && (
                  <Link to="/history" className="dash-enlace">Ver las {historial.length}</Link>
                )}
              </div>

              <ul className="dash-lista">
                {historial.slice(0, 4).map((h) => {
                  const m = specMeta(h.specialization)
                  return (
                    <li key={h.prediction_id}>
                      <Link to={`/results/${h.prediction_id}`} className="dash-fila">
                        <span className="rv-marca" style={{ background: m.color }} aria-hidden="true" />
                        <span className="dash-fila-nom">{h.specialization}</span>
                        <span className="rv-menor dash-fila-fecha">{fechaCorta(h.created_at)}</span>
                        <span className="rv-dato dash-fila-pct">{h.confidence_pct}%</span>
                        <span className="dash-fila-flecha" aria-hidden="true">→</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
