import { Link } from 'react-router-dom'
import './Landing.css'

const SPECS = [
  { icon: '💻', name: 'Desarrollo de Software',       color: '#3B82F6', desc: 'Sistemas web, móviles y arquitecturas' },
  { icon: '🧠', name: 'Data Science & IA',            color: '#10B981', desc: 'Modelos predictivos y aprendizaje' },
  { icon: '☁️', name: 'Infraestructura & Cloud',      color: '#8B5CF6', desc: 'Orquestación y escalabilidad AWS/Azure' },
  { icon: '🔐', name: 'Ciberseguridad',               color: '#EF4444', desc: 'Protección de datos y redes globales' },
  { icon: '🛠️', name: 'Soporte & IT Ops',             color: '#F59E0B', desc: 'Gestión de hardware y mesa de ayuda' },
  { icon: '🧪', name: 'QA & Testing',                 color: '#EC4899', desc: 'Automatización y calidad de software' },
  { icon: '📈', name: 'Gestión y Producto',           color: '#6366F1', desc: 'Liderazgo de proyectos y agilismo' },
  { icon: '🎨', name: 'Diseño UX/UI',                 color: '#F43F5E', desc: 'Interfaces intuitivas centradas en el usuario' },
  { icon: '🏢', name: 'Sistemas Empresariales',       color: '#14B8A6', desc: 'Ecosistemas ERP corporativos' },
  { icon: '🔬', name: 'Investigación e Innovación',   color: '#64748B', desc: 'IoT, VR, Web3 y ciencia computacional' },
]

const STEPS = [
  { n:'01', icon:'📝', title:'Completa el cuestionario', desc:'20 preguntas sobre tus aptitudes, intereses y personalidad académica.' },
  { n:'02', icon:'🌳', title:'El árbol de decisión analiza tu perfil', desc:'Nuestro modelo ML procesa tus respuestas y encuentra tu mejor camino.' },
  { n:'03', icon:'🎯', title:'Recibe tu recomendación', desc:'Obtén tu especialización ideal con porcentaje de compatibilidad y rutas de carrera.' },
]

export default function Landing() {
  return (
    <div className="landing">
      {/* Hero */}
      <section className="hero">
        <div className="hero-bg">
          <div className="hero-orb orb-1" />
          <div className="hero-orb orb-2" />
          <div className="hero-orb orb-3" />
        </div>
        <div className="container hero-content animate-fade">
          <div className="hero-badge badge badge-purple">⚡ Powered by Machine Learning</div>
          <h1 className="hero-title">
            Descubre tu camino en<br/>
            <span className="gradient-text">Ingeniería de Sistemas</span>
          </h1>
          <p className="hero-sub">
            Nuestro sistema basado en <strong>Árbol de Decisión</strong> analiza tu perfil académico,
            habilidades e intereses para recomendarte la especialización ideal.
          </p>
          <div className="hero-cta">
            <Link to="/register" className="btn btn-primary btn-lg">
              Comenzar ahora →
            </Link>
            <Link to="/login" className="btn btn-secondary btn-lg">
              Ya tengo cuenta
            </Link>
          </div>
          <div className="hero-stats">
            <div className="stat"><strong>10</strong><span>Especializaciones</span></div>
            <div className="stat-div" />
            <div className="stat"><strong>20</strong><span>Preguntas</span></div>
            <div className="stat-div" />
            <div className="stat"><strong>ML</strong><span>Árbol de Decisión</span></div>
          </div>
        </div>
      </section>

      {/* Especializaciones */}
      <section className="section">
        <div className="container">
          <div className="section-header text-center">
            <span className="badge badge-cyan">Especializaciones</span>
            <h2 className="section-title">¿Hacia dónde quieres ir?</h2>
            <p className="text-muted">Descubre cuál de estas 10 ramas es la más adecuada para tu perfil</p>
          </div>
          <div className="specs-grid">
            {SPECS.map((s, i) => (
              <div key={i} className="spec-card glass animate-fade" style={{ '--c': s.color, animationDelay: `${i * 0.08}s` }}>
                <div className="spec-icon">{s.icon}</div>
                <h3 className="spec-name">{s.name}</h3>
                <p className="spec-desc">{s.desc}</p>
                <div className="spec-line" style={{ background: s.color }} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="section section-dark">
        <div className="container">
          <div className="section-header text-center">
            <span className="badge badge-purple">Proceso</span>
            <h2 className="section-title">¿Cómo funciona?</h2>
          </div>
          <div className="steps-grid">
            {STEPS.map((s, i) => (
              <div key={i} className="step-card glass animate-fade" style={{ animationDelay: `${i * 0.15}s` }}>
                <div className="step-num gradient-text">{s.n}</div>
                <div className="step-icon">{s.icon}</div>
                <h3 className="step-title">{s.title}</h3>
                <p className="text-muted text-sm">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Final */}
      <section className="section cta-section">
        <div className="container text-center">
          <div className="cta-card glass">
            <div className="cta-orb" />
            <h2 className="section-title">¿Listo para encontrar<br/><span className="gradient-text">tu especialización?</span></h2>
            <p className="text-muted" style={{ maxWidth: 480, margin: '0 auto 32px' }}>
              Toma el cuestionario ahora y obtén tu recomendación personalizada en menos de 5 minutos.
            </p>
            <Link to="/register" className="btn btn-primary btn-lg">Empezar mi evaluación →</Link>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="container text-center">
          <p className="text-muted text-sm">© 2025 REVO · Sistema de Recomendación de Especialización · Ingeniería de Sistemas</p>
        </div>
      </footer>
    </div>
  )
}
