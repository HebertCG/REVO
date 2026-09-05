import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import personaCelular from '../assets/persona-celular.png'
import personaDiferencia from '../assets/persona-diferencia.png'
import personaTrayectoria from '../assets/persona-historial-revo.png'
import {
  LANDING_OUTCOMES,
  LANDING_PHASES,
  LANDING_ROUTE_GROUPS,
  getLandingCta,
  getQuestionBreakdown,
} from './landingContent'
import './PanelInformativo.css'

function ArrowIcon() {
  return <span aria-hidden="true">→</span>
}

export default function PanelInformativo() {
  const { user } = useAuth()
  const [activePhaseId, setActivePhaseId] = useState(LANDING_PHASES[0].id)
  const activePhase = LANDING_PHASES.find((phase) => phase.id === activePhaseId)
  const questions = getQuestionBreakdown()
  const primaryCta = getLandingCta(Boolean(user))

  return (
    <main className="revo-panel">
      <section className="lp-hero" aria-labelledby="landing-title">
        <div className="lp-signal-path" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="lp-wrap lp-hero-layout">
          <div className="lp-hero-copy">
            <h1 id="landing-title">
              Tu carrera ya empezó.<br />
              Ahora encuentra <em>tu dirección.</em>
            </h1>
            <p className="lp-hero-lead">
              REVO convierte 29 preguntas en tres desafíos breves para descubrir
              qué especialización se parece más a ti y qué puedes hacer después.
            </p>

            <div className="lp-actions">
              <Link className="lp-button lp-button-primary" to={primaryCta.to}>
                {primaryCta.label}
                <ArrowIcon />
              </Link>
              <a className="lp-button lp-button-quiet" href="#revo-como">
                Ver cómo funciona
              </a>
            </div>

            <dl className="lp-hero-metrics" aria-label="Datos principales del cuestionario">
              <div>
                <dt>Preguntas</dt>
                <dd>{questions.total}</dd>
              </div>
              <div>
                <dt>Fases adaptativas</dt>
                <dd>03</dd>
              </div>
              <div>
                <dt>Tiempo estimado</dt>
                <dd>≈ 8 min</dd>
              </div>
            </dl>
          </div>

          <div className="lp-hero-visual">
            <div className="lp-hero-halo" aria-hidden="true" />
            <img
              className="lp-hero-person"
              src={personaTrayectoria}
              alt="Personaje REVO explorando una trayectoria de especialización"
            />
          </div>
        </div>
      </section>

      <section className="lp-routes lp-section" aria-labelledby="routes-title">
        <div className="lp-wrap">
          <header className="lp-routes-intro">
            <h2 id="routes-title">Diez rutas dentro de Sistemas. Cinco formas de mirar el trabajo.</h2>
            <p>
              REVO compara tu afinidad con las diez especializaciones. Aquí están
              agrupadas únicamente para que puedas entenderlas de un vistazo.
            </p>
          </header>

          <ol className="lp-route-map">
            {LANDING_ROUTE_GROUPS.map((group) => (
              <li key={group.number}>
                <span className="lp-route-number">{group.number}</span>
                <div className="lp-route-copy">
                  <h3>{group.verb}</h3>
                  <p>{group.description}</p>
                </div>
                <ul>
                  {group.routes.map((route) => <li key={route}>{route}</li>)}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="lp-process lp-section" id="revo-como" aria-labelledby="process-title">
        <div className="lp-wrap">
          <header className="lp-process-heading">
            <h2 id="process-title">Tres fases que se van enfocando contigo.</h2>
            <p>
              Primero observa las diez rutas, después profundiza en tus tres
              finalistas y al final incorpora tu forma de trabajar.
            </p>
          </header>

          <div className="lp-process-layout">
            <div className="lp-phase-tabs" role="tablist" aria-label="Fases del cuestionario">
              {LANDING_PHASES.map((phase) => {
                const isActive = phase.id === activePhaseId
                return (
                  <button
                    key={phase.id}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    aria-controls="landing-phase-detail"
                    className={isActive ? 'is-active' : ''}
                    style={{ '--phase-accent': phase.accent }}
                    onClick={() => setActivePhaseId(phase.id)}
                  >
                    <span className="lp-phase-number">{phase.number}</span>
                    <span>
                      <strong>{phase.name}</strong>
                      <small>{phase.countLabel}</small>
                    </span>
                  </button>
                )
              })}
            </div>

            <article
              key={activePhase.id}
              className="lp-phase-detail"
              id="landing-phase-detail"
              role="tabpanel"
              style={{ '--phase-accent': activePhase.accent }}
              aria-live="polite"
            >
              <span className="lp-phase-watermark" aria-hidden="true">{activePhase.number}</span>
              <div className="lp-phase-summary">
                <h3>{activePhase.name}</h3>
                <p>{activePhase.description}</p>
                <span>{activePhase.subtitle} · {activePhase.countLabel}</span>
              </div>
              <div className="lp-phase-example">
                <blockquote>“{activePhase.example}”</blockquote>
                <p className="lp-phase-outcome">
                  <span aria-hidden="true">↳</span>
                  {activePhase.outcome}
                </p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="lp-outcomes lp-section" id="revo-ofrece" aria-labelledby="outcomes-title">
        <div className="lp-wrap">
          <header className="lp-outcomes-heading">
            <h2 id="outcomes-title">Tu resultado se convierte en una ruta que puedes poner a prueba.</h2>
            <p>
              No terminas con un nombre bonito y nada más. REVO organiza la señal
              en decisiones pequeñas que puedes probar mientras todavía estudias.
            </p>
          </header>

          <div className="lp-outcomes-layout">
            <ol className="lp-outcome-list">
              {LANDING_OUTCOMES.map((outcome) => (
                <li key={outcome.number}>
                  <span>{outcome.number}</span>
                  <div>
                    <h3>{outcome.title}</h3>
                    <p>{outcome.description}</p>
                  </div>
                </li>
              ))}
            </ol>

            <figure className="lp-outcomes-visual">
              <div className="lp-visual-grid" aria-hidden="true" />
              <img
                src={personaCelular}
                alt="Personaje REVO analizando alternativas profesionales desde su computadora"
              />
              <figcaption>
                <span className="lp-status-dot" aria-hidden="true" />
                Del resultado a tu siguiente movimiento
              </figcaption>
            </figure>
          </div>

          <p className="lp-teacher-note">
            <span aria-hidden="true">◎</span>
            Para docentes: una lectura agregada permite orientar electivas y proyectos
            sin exponer respuestas individuales.
          </p>
        </div>
      </section>

      <section className="lp-trust lp-section" aria-labelledby="trust-title">
        <div className="lp-wrap">
          <div className="lp-trust-layout">
            <div className="lp-trust-copy">
              <p className="lp-section-index">Una brújula, no una sentencia</p>
              <h2 id="trust-title">REVO no decide por ti. Te muestra evidencia para decidir mejor.</h2>
              <div className="lp-comparison">
                <div>
                  <span>Test tradicional</span>
                  <p>“Esta es la única respuesta correcta para ti.”</p>
                </div>
                <div className="is-revo">
                  <span>REVO</span>
                  <p>“Estas son tus rutas más probables y esta es la confianza de cada una.”</p>
                </div>
              </div>
            </div>

            <figure className="lp-trust-visual">
              <div className="lp-trust-orbit" aria-hidden="true" />
              <img
                src={personaDiferencia}
                alt="Personaje REVO comparando distintas rutas profesionales"
              />
            </figure>
          </div>

          <dl className="lp-trust-facts">
            <div>
              <dt>29 / 100</dt>
              <dd>Pregunta solo donde encuentra afinidad.</dd>
            </div>
            <div>
              <dt>O*NET</dt>
              <dd>Rutas conectadas con ocupaciones reales.</dd>
            </div>
            <div>
              <dt>Confianza visible</dt>
              <dd>La incertidumbre también forma parte del resultado.</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="lp-final" aria-labelledby="final-title">
        <div className="lp-wrap lp-final-layout">
          <div>
            <h2 id="final-title">Empieza jugando. Termina con una dirección.</h2>
          </div>
          <div className="lp-final-action">
            <p>Puedes repetir la evaluación cada semestre y ver cómo cambia tu trayectoria.</p>
            <Link className="lp-button lp-button-dark" to={primaryCta.to}>
              {primaryCta.label}
              <ArrowIcon />
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
