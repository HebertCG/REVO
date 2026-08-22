import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import personaDashboard from '../assets/persona-dashboard-revo.png'
import { useAuth } from '../context/AuthContext'
import { mlApi } from '../services/api'
import {
  calcularScore, fechaCorta, nivelDe, siguienteNivel, specMeta,
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
      .then((response) => setHistorial(response.data || []))
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
  const confianzaMedia = historial.length
    ? Math.round(historial.reduce((total, item) => total + item.confidence_pct, 0) / historial.length)
    : 0
  const nombre = user?.full_name?.split(' ')[0] || 'estudiante'

  return (
    <div className="rv dash">
      <main className="rv-ancho dash-contenido">
        <header className="dash-barra rv-entra">
          <div className="dash-identidad">
            <strong>Hola, {nombre}</strong>
            <span aria-hidden="true">·</span>
            <p>
              {user?.semester ? `Ciclo ${user.semester}` : 'Estudiante'}
              {user?.student_code ? ` · ${user.student_code}` : ''}
            </p>
          </div>
          <button type="button" className="rv-btn rv-btn-1 dash-accion-principal" onClick={() => navigate('/questionnaire')}>
            Nueva evaluación <span aria-hidden="true">→</span>
          </button>
        </header>

        {cargando ? (
          <div className="dash-esqueleto" aria-label="Cargando tu dashboard">
            <div className="rv-esq dash-esqueleto-heroe" />
            <div className="rv-esq dash-esqueleto-linea" />
            <div className="rv-esq dash-esqueleto-linea" />
          </div>
        ) : !ultima ? (
          <section className="dash-vacio rv-entra">
            <img
              className="dash-vacio-imagen"
              src={personaDashboard}
              alt="Personaje REVO colocando la primera señal de una ruta profesional"
            />
            <div className="dash-vacio-sombra" aria-hidden="true" />
            <div className="dash-vacio-copy">
              <p className="dash-contexto">Tu recorrido empieza aquí</p>
              <h1>Descubre qué rutas se parecen más a ti.</h1>
              <p className="rv-sub">
                Son 25 preguntas y unos seis minutos. Al terminar conocerás las tres
                ramas de Ingeniería de Sistemas con mayor afinidad y la confianza de
                cada resultado.
              </p>
              <Link to="/questionnaire" className="rv-btn rv-btn-1">
                Empezar el test <span aria-hidden="true">→</span>
              </Link>
            </div>
          </section>
        ) : (
          <>
            <section
              className="dash-heroe rv-entra"
              style={{ '--dash-spec-color': meta.color }}
              aria-labelledby="dash-resultado-titulo"
            >
              <img
                className="dash-heroe-imagen"
                src={personaDashboard}
                alt="Personaje REVO colocando una nueva señal sobre su recorrido profesional"
              />
              <div className="dash-heroe-sombra" aria-hidden="true" />

              <div className="dash-heroe-txt">
                <p className="dash-contexto">Actualizado el {fechaCorta(ultima.created_at)}</p>
                <h1 className="dash-senal-titulo" id="dash-resultado-titulo">
                  Lo que más encaja contigo hoy:
                  <span className="dash-senal-ruta">
                    <span className="dash-heroe-icono" aria-hidden="true">{meta.icon}</span>
                    {ultima.specialization}
                  </span>
                </h1>

                <div className="dash-confianza">
                  <p>
                    <span className="rv-dato dash-cifra">{ultima.confidence_pct}</span>
                    <span className="rv-dato dash-cifra-pct">%</span>
                  </p>
                  <span>Coincidencia estimada. Es una referencia, no una nota.</span>
                </div>

                <div
                  className="rv-pista dash-heroe-pista"
                  role="progressbar"
                  aria-label="Compatibilidad de la última evaluación"
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-valuenow={ultima.confidence_pct}
                >
                  <div
                    className="rv-relleno"
                    style={{ width: `${ultima.confidence_pct}%`, background: meta.color }}
                  />
                </div>

                <div className="dash-heroe-acc">
                  <Link to={`/results/${ultima.prediction_id}`} className="rv-btn rv-btn-1">
                    Abrir mi resultado <span aria-hidden="true">→</span>
                  </Link>
                  <Link to="/history" className="rv-btn rv-btn-2">Comparar historial</Link>
                </div>
              </div>
            </section>

            <dl className="dash-metricas rv-entra" style={{ animationDelay: '.05s' }}>
              <div>
                <dt>Evaluaciones</dt>
                <dd className="rv-dato">{historial.length}</dd>
                <dd className="dash-metrica-nota">{historial.length === 1 ? 'Tu primera señal registrada' : 'Tu recorrido hasta hoy'}</dd>
              </div>
              <div>
                <dt>Confianza media</dt>
                <dd className="rv-dato">{confianzaMedia}<span>%</span></dd>
                <dd className="dash-metrica-nota">Promedio de tus evaluaciones</dd>
              </div>
              <div>
                <dt>REVO Score</dt>
                <dd className="rv-dato">{score}</dd>
                <dd className="dash-metrica-nota"><span className="rv-marca" style={{ background: nivel.color }} /> Nivel {nivel.label}</dd>
              </div>
            </dl>

            <section className="dash-nivel rv-entra" style={{ animationDelay: '.09s' }} aria-labelledby="dash-nivel-titulo">
              <div className="dash-nivel-copy">
                <p className="dash-contexto">Tu siguiente hito</p>
                <h2 id="dash-nivel-titulo">
                  {proximo ? `De ${nivel.label} a ${proximo.label}` : `Nivel ${nivel.label} completado`}
                </h2>
                <p className="rv-sub">
                  {historial.length < 3
                    ? 'Mantén una señal consistente durante tres evaluaciones y suma 150 puntos extra.'
                    : 'Cada evaluación aporta 100 puntos, más el doble de tu confianza media.'}
                </p>
              </div>

              <div className="dash-nivel-recorrido">
                <div className="dash-nivel-cab">
                  <span className="rv-ficha"><span aria-hidden="true">{nivel.icon}</span> {nivel.label}</span>
                  {proximo ? (
                    <p>Faltan <strong className="rv-dato">{faltan}</strong> pts</p>
                  ) : (
                    <p>Nivel máximo alcanzado</p>
                  )}
                </div>
                <div
                  className="rv-pista dash-nivel-pista"
                  role="progressbar"
                  aria-label={`Progreso hacia ${proximo?.label || nivel.label}`}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-valuenow={Math.round(avance)}
                >
                  <div className="rv-relleno" style={{ width: `${avance}%`, background: nivel.color }} />
                  <span className="dash-nivel-marca" style={{ left: `${avance}%`, borderColor: nivel.color }} aria-hidden="true" />
                </div>
                <div className="dash-nivel-extremos" aria-hidden="true">
                  <span>{nivel.min} pts</span>
                  <span>{proximo ? `${proximo.min} pts` : `${score} pts`}</span>
                </div>
              </div>
            </section>

            <section className="dash-recientes rv-entra" style={{ animationDelay: '.13s' }} aria-labelledby="dash-recientes-titulo">
              <div className="dash-lista-cab">
                <div>
                  <h2 id="dash-recientes-titulo">Evaluaciones recientes</h2>
                  <p className="rv-sub">Revisa cómo ha cambiado tu señal con el tiempo.</p>
                </div>
                {historial.length > 4 && (
                  <Link to="/history" className="dash-enlace">Ver las {historial.length} evaluaciones →</Link>
                )}
              </div>

              <ul className="dash-lista">
                {historial.slice(0, 4).map((item, index) => {
                  const itemMeta = specMeta(item.specialization)
                  return (
                    <li key={item.prediction_id}>
                      <Link to={`/results/${item.prediction_id}`} className="dash-fila">
                        <span className="dash-fila-indice rv-dato">{String(index + 1).padStart(2, '0')}</span>
                        <span className="rv-marca" style={{ background: itemMeta.color }} aria-hidden="true" />
                        <span className="dash-fila-nom">{item.specialization}</span>
                        <span className="rv-menor dash-fila-fecha">{fechaCorta(item.created_at)}</span>
                        <span className="rv-dato dash-fila-pct">{item.confidence_pct}%</span>
                        <span className="dash-fila-flecha" aria-hidden="true">→</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
