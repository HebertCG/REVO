import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Landing.css'

const SPECS = [
  { icon: '💻', name: 'Desarrollo de Software', color: '#3B82F6', desc: 'Sistemas web, móviles y arquitecturas a gran escala.' },
  { icon: '🧠', name: 'Data Science & IA', color: '#10B981', desc: 'Modelos predictivos, Deep Learning y analítica avanzada.' },
  { icon: '☁️', name: 'Infraestructura & Cloud', color: '#8B5CF6', desc: 'Orquestación serverless, Docker y AWS/Azure.' },
  { icon: '🔐', name: 'Ciberseguridad', color: '#EF4444', desc: 'Protección de datos globales, criptografía y pentesting.' },
  { icon: '🛠️', name: 'Soporte & IT Ops', color: '#F59E0B', desc: 'Gestión de hardware, automatización y mesa de ayuda ITIL.' },
  { icon: '🧪', name: 'QA & Testing', color: '#EC4899', desc: 'Aseguramiento de automatización y calidad de software (SDET).' },
  { icon: '📈', name: 'Gestión y Producto', color: '#6366F1', desc: 'Liderazgo de proyectos tecnológicos y marcos ágiles (Scrum).' },
  { icon: '🎨', name: 'Diseño UX/UI', color: '#F43F5E', desc: 'Mapeo de interfaces intuitivas y experiencia de usuario.' },
  { icon: '🏢', name: 'Sistemas Empresariales', color: '#14B8A6', desc: 'Arquitectura de ecosistemas ERP y CRM corporativos.' },
  { icon: '🔬', name: 'Investigación e Innovación', color: '#64748B', desc: 'Internet of Things (IoT), Realidad Virtual y Web3.' },
]

const STEPS = [
  { n: '01', icon: '📝', title: 'Extracción de Datos', desc: 'Responde un cuestionario algorítmico diseñado para capturar tus aptitudes e intereses en variables puras.' },
  { n: '02', icon: '🧠', title: 'Regresión Logística', desc: 'El modelo matemático pesa tus respuestas mediante descenso de gradiente para generar tu Vector de Afinidad.' },
  { n: '03', icon: '🎯', title: 'Puntaje de Confianza', desc: 'Obtén tu especialización con una exactitud probabilística milimétrica y un plan de acción a largo plazo.' },
]

export default function Landing() {
  const { user } = useAuth()

  return (
    <div className="landing">
      {/* Hero */}
      <section className="hero">
        <div className="hero-grid" />
        <div className="hero-bg">
          <div className="hero-orb orb-1" />
          <div className="hero-orb orb-2" />
          <div className="hero-orb orb-3" />
        </div>

        <div className="container hero-content animate-fade">
          <div className="hero-badge">
            <div className="ping" /> Powered by Regresión Logística Multinomial
          </div>
          <h1 className="hero-title">
            No decidas a ciegas.<br />
            <span className="gradient-text">Calcula tu futuro en IT.</span>
          </h1>
          <p className="hero-sub">
            Descubre tu camino en la Ingeniería de Sistemas mediante un <strong>Modelo de Machine Learning</strong> que cruza tus habilidades cognitivas con las demandas exactas del ecosistema tecnológico global.
          </p>
          <div className="hero-cta">
            {user ? (
              <Link to={user.role === 'admin' ? '/admin' : '/dashboard'} className="btn btn-primary btn-lg">
                Ir a mi Dashboard →
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn btn-primary btn-lg" style={{ boxShadow: '0 0 20px rgba(108,99,255,0.4)' }}>
                  Registrarse →
                </Link>
                <Link to="/login" className="btn btn-secondary btn-lg">
                  Iniciar Sesión
                </Link>
              </>
            )}
          </div>
          <div className="hero-stats">
            <div className="stat">
              <strong className="accent">10</strong>
              <span>Clases Vectoriales</span>
            </div>
            <div className="stat-div" />
            <div className="stat">
              <strong>90%</strong>
              <span>Precisión Logística</span>
            </div>
            <div className="stat-div" />
            <div className="stat">
              <strong className="accent">25</strong>
              <span>Nodos de Evaluación</span>
            </div>
          </div>
        </div>
      </section>

      {/* The Tech Edge */}
      <section className="section section-dark">
        <div className="container tech-container">
          <div className="tech-content animate-fade">
            <span className="badge badge-purple" style={{ marginBottom: 16 }}>Nuestra Tecnología</span>
            <h2 className="section-title">Matemática predictiva,<br />no intuición.</h2>
            <p className="text-muted" style={{ marginBottom: 24, fontSize: '1.1rem', lineHeight: 1.7 }}>
              Los tests vocacionales tradicionales fracasan porque usan reglas rígidas.
              REVO no es un test, es un <strong>motor predictivo</strong>.
            </p>
            <p className="text-muted" style={{ marginBottom: 32, fontSize: '1rem', lineHeight: 1.6 }}>
              Implementamos un modelo de <em>Regresión Logística Multinomial</em> entrenado con miles de perfiles.
              Cada respuesta que das altera los pesos de un vector matemático iterativo. Si tus perfiles son híbridos (Ej. te gusta el código y también el diseño), el modelo no te encasilla: interpola las probabilidades para revelarte trayectorias como <em>Ingeniería Frontend UX</em> o <em>Arquitectura Cloud</em>.
            </p>
          </div>
          <div className="tech-visual animate-fade" style={{ animationDelay: '0.2s' }}>
            <div className="hero-orb" style={{ width: 300, height: 300, background: '#00D4FF', opacity: 0.1, filter: 'blur(50px)', top: '10%', left: '10%' }} />
            <div className="code-window">
              <pre>
                <span className="code-comment"># Inicializando convergencia probabilística</span><br />
                <span className="code-keyword">import</span> numpy <span className="code-keyword">as</span> np<br />
                <br />
                <span className="code-keyword">def</span> <span className="code-number">extract_features</span>(user_answers):<br />
                &nbsp;&nbsp;&nbsp;&nbsp;<span className="code-comment"># Mapeando pesos sinápticos [w1...w10]</span><br />
                &nbsp;&nbsp;&nbsp;&nbsp;W = model.coef_<br />
                &nbsp;&nbsp;&nbsp;&nbsp;X = np.array(user_answers)<br />
                <br />
                &nbsp;&nbsp;&nbsp;&nbsp;<span className="code-comment"># Calculando función Sigmoide Multiclase</span><br />
                &nbsp;&nbsp;&nbsp;&nbsp;logits = np.dot(X, W.T) + model.intercept_<br />
                &nbsp;&nbsp;&nbsp;&nbsp;probs = np.exp(logits) / np.sum(np.exp(logits))<br />
                &nbsp;&nbsp;&nbsp;&nbsp;<br />
                &nbsp;&nbsp;&nbsp;&nbsp;<span className="code-keyword">return</span> np.argmax(probs) <span className="code-string"># Especialidad Ideal</span>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Especializaciones */}
      <section className="section">
        <div className="container">
          <div className="section-header text-center">
            <span className="badge badge-cyan">Taxonomía del Sistema</span>
            <h2 className="section-title">El Ecosistema <span className="gradient-text">Ingenieril</span></h2>
            <p className="text-muted">A qué clústeres tecnológicos emparejará tu vector final</p>
          </div>
          <div className="specs-grid">
            {SPECS.map((s, i) => (
              <div key={i} className="spec-card animate-fade" style={{ '--c': s.color, animationDelay: `${i * 0.05}s` }}>
                <div className="spec-icon">{s.icon}</div>
                <h3 className="spec-name">{s.name}</h3>
                <p className="spec-desc">{s.desc}</p>
                <div className="spec-line" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="section section-dark" style={{ position: 'relative', zIndex: 1 }}>
        <div className="hero-orb" style={{ width: 400, height: 400, background: '#6C63FF', opacity: 0.05, filter: 'blur(80px)', top: '20%', right: '-10%' }} />
        <div className="container">
          <div className="section-header text-center">
            <span className="badge badge-purple">Pipeline de Extracción</span>
            <h2 className="section-title">El Algoritmo en Acción</h2>
          </div>
          <div className="steps-grid" style={{ marginTop: 48 }}>
            {STEPS.map((s, i) => (
              <div key={i} className="step-card glass animate-fade" style={{ animationDelay: `${i * 0.15}s` }}>
                <div className="step-num">{s.n}</div>
                <div className="step-icon">{s.icon}</div>
                <h3 className="step-title">{s.title}</h3>
                <p className="step-desc">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Filosofía */}
      <section className="section about-section">
        <div className="container">
          <div className="section-header text-center">
            <span className="badge badge-cyan">Singularidad</span>
            <h2 className="section-title">Conoce a <span className="gradient-text">REVO</span></h2>
            <p className="text-muted">Erradicando el abandono universitario mediante métricas puras</p>
          </div>

          <div className="about-grid">
            <div className="about-card glass animate-fade" style={{ animationDelay: '0.1s' }}>
              <div className="about-icon">🚀</div>
              <h3 className="about-title">Sobre Nosotros</h3>
              <p className="text-muted" style={{ lineHeight: 1.7, fontSize: '0.95rem' }}>
                La deserción en Ingeniería de Sistemas es crítica debido al desconocimiento de sus inmensas ramas. REVO fusiona Machine Learning paramétrico y psicometría estructural para emparejar el cerebro humano con la demanda algorítmica de la industria 4.0.
              </p>
            </div>

            <div className="about-card glass animate-fade" style={{ animationDelay: '0.2s' }}>
              <div className="about-icon">👁️</div>
              <h3 className="about-title">Nuestra Visión</h3>
              <p className="text-muted" style={{ lineHeight: 1.7, fontSize: '0.95rem' }}>
                Establecernos como la "Singularidad" en la orientación universitaria. Queremos que el 100% de estudiantes inviertan sus horas de estudio precisamente en las sub-ramas de TI donde biológica y técnicamente brillan por naturaleza.
              </p>
            </div>

            <div className="about-card glass animate-fade" style={{ animationDelay: '0.3s' }}>
              <div className="about-icon">🎯</div>
              <h3 className="about-title">Nuestra Misión</h3>
              <p className="text-muted" style={{ lineHeight: 1.7, fontSize: '0.95rem' }}>
                Acabar con la intuición ciega. Suministrando rutas de carreras (certificaciones AWS, arquitecturas Node, Pentesting) que alineen matemática estricta a perfiles emocionales reales. Un ingeniero, un ecosistema.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Final */}
      <section className="section cta-section">
        <div className="container text-center">
          <div className="cta-card glass">
            <div className="cta-orb" />
            <div style={{ position: 'relative', zIndex: 1 }}>
              <h2 className="section-title">Inicia la <span className="gradient-text">Propagación Mágica</span></h2>
              <p className="text-muted" style={{ maxWidth: 540, margin: '0 auto 40px', fontSize: '1.2rem', lineHeight: 1.6 }}>
                Extrae tu vector de afinidad y obtén un Plan de Acción a meses y años, procesado con 90% de exactitud probabilística.
              </p>
              {user ? (
                <Link to="/questionnaire" className="btn btn-primary btn-lg" style={{ padding: '16px 40px', fontSize: '1.2rem', boxShadow: '0 0 20px rgba(108,99,255,0.5)' }}>Inicializar Cuestionario →</Link>
              ) : (
                <Link to="/register" className="btn btn-primary btn-lg" style={{ padding: '16px 40px', fontSize: '1.2rem', boxShadow: '0 0 20px rgba(108,99,255,0.5)' }}>Registrarse →</Link>
              )}
            </div>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="container text-center">
          <p className="text-muted text-sm" style={{ letterSpacing: '0.05em' }}>
            © 2026 REVO · ENGINE v1.0 (Logistic Regression) · INGENIERÍA DE SISTEMAS
          </p>
        </div>
      </footer>
    </div>
  )
}
