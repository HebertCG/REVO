import { Link } from 'react-router-dom'
import './Footer.css'

const RAMAS = [
  'Desarrollo de Software', 'Data Science e IA', 'Ciberseguridad',
  'Infraestructura y Cloud', 'Diseño UX/UI', 'QA y Testing',
]

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="footer-logo">
            <span className="footer-logo-text">REVO<span className="footer-logo-dot">.</span></span>
          </div>
          <p className="footer-tagline">
            Orientación de especialización para estudiantes de Ingeniería de Sistemas.
            Un cuestionario que se adapta a tus respuestas y te devuelve tus tres
            ramas más probables, con el nivel de confianza de cada una.
          </p>
          {/*
            Atribución obligatoria, no decorativa: la base O*NET se publica
            bajo CC BY 4.0, que exige citar la fuente, enlazar la licencia e
            indicar que se modificó.

            Hasta la Fase 2 esta frase afirmaba el anclaje sin que existiera
            ni un dato de O*NET en el repositorio. Ahora es cierta: los
            perfiles RIASEC de las diez ramas salen de
            database/onet/perfiles_ramas.json.
          */}
          <p className="footer-meta">
            Especializaciones ancladas al catálogo ocupacional{' '}
            <a
              href="https://www.onetcenter.org/database.html"
              target="_blank"
              rel="noopener noreferrer"
            >
              O*NET&nbsp;31.0
            </a>{' '}
            del Departamento de Trabajo de EE.&nbsp;UU. (USDOL/ETA).
            O*NET® es marca registrada del USDOL/ETA. Datos usados bajo licencia{' '}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CC&nbsp;BY&nbsp;4.0
            </a>{' '}
            y agregados por especialización.
          </p>
        </div>

        <nav className="footer-col" aria-labelledby="footer-producto">
          <h3 className="footer-title" id="footer-producto">Producto</h3>
          <Link to="/questionnaire">Hacer el test</Link>
          <Link to="/dashboard">Mi panel</Link>
          <Link to="/history">Mi historial</Link>
          <a href="#revo-como">Cómo funciona</a>
          <a href="#revo-ofrece">Qué incluye</a>
        </nav>

        <nav className="footer-col" aria-labelledby="footer-ramas">
          <h3 className="footer-title" id="footer-ramas">Especializaciones</h3>
          {RAMAS.map((r) => (
            <span key={r} className="footer-rama">{r}</span>
          ))}
          <span className="footer-rama footer-rama-mas">y 4 más</span>
        </nav>

        <nav className="footer-col" aria-labelledby="footer-cuenta">
          <h3 className="footer-title" id="footer-cuenta">Cuenta</h3>
          <Link to="/login">Iniciar sesión</Link>
          <Link to="/register">Crear cuenta</Link>
          <a href="https://github.com/HebertCG/REVO" target="_blank" rel="noopener noreferrer">
            Repositorio
          </a>
        </nav>
      </div>

      <div className="footer-bottom">
        <p>© 2026 REVO · Proyecto académico de Ingeniería de Sistemas</p>
        <p className="footer-engine">
          <span className="footer-dot" aria-hidden="true" />
          Motor v1.0 · Regresión Logística Multinomial
        </p>
      </div>
    </footer>
  )
}
