import { useState, useEffect } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { mlApi, surveyApi } from '../services/api'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, Cell } from 'recharts'
import './Results.css'

const CAREERS = {
  'Desarrollo de Software':               { paths: ['Frontend Developer', 'Backend Developer', 'Full Stack Developer', 'Mobile Developer', 'Software Architect'], color:'#3B82F6' },
  'Data Science & IA':                    { paths: ['Data Scientist', 'Machine Learning Engineer', 'Data Analyst', 'AI Engineer', 'Computer Vision Engineer'], color:'#10B981' },
  'Infraestructura & Cloud':              { paths: ['DevOps Engineer', 'Cloud Engineer', 'SysAdmin', 'Network Engineer', 'SRE'], color:'#8B5CF6' },
  'Ciberseguridad':                       { paths: ['Ethical Hacker / Pentester', 'Security Analyst (SOC)', 'Digital Forensics', 'Security Engineer'], color:'#EF4444' },
  'Soporte Técnico & IT Ops':             { paths: ['IT Support Specialist', 'Soporte Técnico', 'Field Support Technician', 'IT Operations'], color:'#F59E0B' },
  'QA & Testing':                         { paths: ['QA Automation Engineer', 'Performance Tester', 'SDET', 'QA Analyst'], color:'#EC4899' },
  'Gestión y Producto':                   { paths: ['Product Manager', 'Scrum Master', 'Project Manager (PM)', 'Product Owner'], color:'#6366F1' },
  'Diseño UX/UI':                         { paths: ['UX Designer', 'UI Designer', 'Product Designer', 'UX Researcher'], color:'#F43F5E' },
  'Sistemas Empresariales':               { paths: ['ERP Consultant (SAP/Oracle)', 'CRM Specialist', 'Business Intelligence', 'IT Consultant'], color:'#14B8A6' },
  'Investigación e Innovación':           { paths: ['Blockchain Developer', 'IoT Engineer', 'AR/VR Developer', 'Investigador en IA'], color:'#64748B' },
}

// Mapeo REVO → categoría slug de Remotive API
const REMOTIVE_CATEGORY = {
  'Desarrollo de Software':     'software-dev',
  'Data Science & IA':          'ai-ml',
  'Infraestructura & Cloud':    'devops',
  'Ciberseguridad':             'software-dev',
  'Soporte Técnico & IT Ops':   'software-dev',
  'QA & Testing':               'qa',
  'Gestión y Producto':         'product',
  'Diseño UX/UI':               'design',
  'Sistemas Empresariales':     'software-dev',
  'Investigación e Innovación': 'ai-ml',
}

// Plan de Acción personalizado por especialización
const ACTION_PLAN = {
  'Desarrollo de Software': [
    { time: '🗓️ Esta Semana',   text: 'Instala VS Code y crea tu primer proyecto en GitHub. Empieza con HTML/CSS si eres principiante o un proyecto en Python/JavaScript si ya tienes base.' },
    { time: '🏕️ Este Mes',      text: 'Completa el curso gratuito "CS50x" de Harvard (edX) o el de JavaScript de freeCodeCamp. Son los mejores puntos de partida para Software.' },
    { time: '📅 3 Meses',      text: 'Publica al menos 1 proyecto real en GitHub. Puede ser un CRUD simple, una app de tareas o una landing page. El portafolio abre más puertas que el CV.' },
    { time: '🎓 Al Graduarte', text: 'Busca la certificación AWS Developer Associate o Google Cloud Professional. Son las más valoradas por empresas como Rappi, Bancolombia y Globant.' },
  ],
  'Data Science & IA': [
    { time: '🗓️ Esta Semana',   text: 'Instala Anaconda y abre Jupyter Notebook. Practica los primeros pasos de Python con NumPy y Pandas — son las herramientas base del científico de datos.' },
    { time: '🏕️ Este Mes',      text: 'Toma el curso "Python for Data Science" de IBM en Coursera (tiene versión gratuita). Cubre estadística, visualización y machine learning básico.' },
    { time: '📅 3 Meses',      text: 'Participa en una competencia de Kaggle nivel beginner. Aprenderás con datos reales y podrás mostrar resultados concretos en tu portafolio.' },
    { time: '🎓 Al Graduarte', text: 'Certifícate en TensorFlow Developer (Google) o IBM Data Science Professional. El mercado de IA en Latam crece 35% anual — hay escasez de talento.' },
  ],
  'Infraestructura & Cloud': [
    { time: '🗓️ Esta Semana',   text: 'Crea una cuenta gratuita en AWS Free Tier o Google Cloud y despliega tu primera máquina virtual. Ver un servidor correr en la nube cambia la perspectiva.' },
    { time: '🏕️ Este Mes',      text: 'Estudia Linux desde cero con "The Linux Command Line" (libro gratuito) o el curso de Linux de LinuxFoundation en edX.' },
    { time: '📅 3 Meses',      text: 'Aprende Docker y Kubernetes con un proyecto real: dockeriza una app existente y despliégala en la nube. Es el skill más buscado en DevOps hoy.' },
    { time: '🎓 Al Graduarte', text: 'La certificación AWS Solutions Architect Associate es la más demandada de la industria Cloud. Con ella, el salario Junior en Colombia arranca 30% más alto.' },
  ],
  'Ciberseguridad': [
    { time: '🗓️ Esta Semana',   text: 'Crea una cuenta en TryHackMe.com y completa el path "Pre-Security". Es la plataforma #1 para aprender hacking ético de forma legal y práctica.' },
    { time: '🏕️ Este Mes',      text: 'Estudia redes con el libro "Computer Networking: A Top-Down Approach" o el curso de Cisco NetAcad (gratis). Sin entender redes no hay Ciberseguridad.' },
    { time: '📅 3 Meses',      text: 'Completa el camino de Pentester en TryHackMe o HackTheBox. Podrás documentar una máquina vulnerable y mostrarla como portafolio real.' },
    { time: '🎓 Al Graduarte', text: 'Obtén el CompTIA Security+ o el CEH (Certified Ethical Hacker). Son reconocidos por empresas como Bancolombia, EPM y el MinTIC.' },
  ],
  'Soporte Técnico & IT Ops': [
    { time: '🗓️ Esta Semana',   text: 'Instala VirtualBox y monta una máquina con Windows Server. Practica la gestión de usuarios, permisos y red local. Es el día a día del rol.' },
    { time: '🏕️ Este Mes',      text: 'Haz el curso gratuito de Google IT Support en Coursera. Cubre hardware, redes, sistemas operativos y seguridad básica. Muy reconocido por empresas.' },
    { time: '📅 3 Meses',      text: 'Aprende a usar herramientas de tickets como Jira Service Management o Freshdesk. Son estándar en empresas para gestionar incidentes. Hay demos gratuitas.' },
    { time: '🎓 Al Graduarte', text: 'La certificación CompTIA A+ valida habilidades de soporte. Para escalar a IT Manager, suma el ITIL Foundation v4 que enseña procesos de servicio.' },
  ],
  'QA & Testing': [
    { time: '🗓️ Esta Semana',   text: 'Aprende los conceptos base de testing: casos de prueba, niveles (unitario, integración, E2E) y escribe tu primer test manual para una app web.' },
    { time: '🏕️ Este Mes',      text: 'Instala Selenium con Python y automatiza el login de cualquier página web. Es el ejercicio clásico para entrar al mundo de QA Automation.' },
    { time: '📅 3 Meses',      text: 'Aprende Cypress o Playwright para testing E2E. Son las herramientas más modernas y buscarás en LinkedIn — están en el 60% de las ofertas Junior.' },
    { time: '🎓 Al Graduarte', text: 'El ISTQB Foundation Level es la certificación internacional de testing más reconocida. Abre puertas en empresas como Perficient, Globant y Lulo Bank.' },
  ],
  'Gestión y Producto': [
    { time: '🗓️ Esta Semana',   text: 'Crea una cuenta en Notion y diseña el roadmap de un proyecto imaginario siguiendo metodología Scrum. Practica los artefactos: Sprint, Backlog y Daily.' },
    { time: '🏕️ Este Mes',      text: 'Lee "Inspired" de Marty Cagan o "Sprint" de Jake Knapp — los dos libros fundamentales de Product Management. Están en formato digital gratuito.' },
    { time: '📅 3 Meses',      text: 'Gestiona un proyecto real con un equipo de compañeros (de cualquier materia). Practica Kanban en Trello y documenta el proceso. Eso es tu portafolio PM.' },
    { time: '🎓 Al Graduarte', text: 'Busca el PSM I (Professional Scrum Master) de Scrum.org o el PMP. En Colombia, un PM certificado gana entre 4M y 10M COP. Alta demanda en Bancolombia y Rappi.' },
  ],
  'Diseño UX/UI': [
    { time: '🗓️ Esta Semana',   text: 'Crea una cuenta gratis en Figma y reproduce el diseño de la pantalla de login de tu app favorita. Es el ejercicio #1 para entrar al mundo del diseño digital.' },
    { time: '🏕️ Este Mes',      text: 'Lee "Don\'t Make Me Think" de Steve Krug — el libro más accesible sobre UX. Cúbrelo en un fin de semana y cambiará cómo ves cualquier interfaz.' },
    { time: '📅 3 Meses',      text: 'Diseña el flujo completo (wireframe → prototipo → mockup) de una app de tu idea. Publícalo en Behance o Dribbble. Es el portafolio que piden las empresas.' },
    { time: '🎓 Al Graduarte', text: 'El Google UX Design Certificate (Coursera, 6 meses) es el acceso más reconocido al mercado. Equipos como los de Rappi, MercadoLibre y Bancolombia lo exigen.' },
  ],
  'Sistemas Empresariales': [
    { time: '🗓️ Esta Semana',   text: 'Descarga SAP Learning Hub o accede a la demo gratuita de ERPNext. Navega el módulo de inventarios — así empieza el aprendizaje de sistemas ERP.' },
    { time: '🏕️ Este Mes',      text: 'Estudia SQL avanzado con el curso de Mode Analytics (gratis). Los Sistemas Empresariales dependen de bases de datos relacionales complejas.' },
    { time: '📅 3 Meses',      text: 'Implementa un ERPNext local con datos inventados de una empresa ficticia. Parametriza compras, ventas y facturación. Eso es un portafolio de ERP Consultant.' },
    { time: '🎓 Al Graduarte', text: 'El SAP Certified Associate es el sello de oro para consultores ERP. Empresas petroleras, industriales y bancarias en Colombia lo exigen como requisito.' },
  ],
  'Investigación e Innovación': [
    { time: '🗓️ Esta Semana',   text: 'Lee las últimas publicaciones de ArXiv.org sobre tu tema de interés (IA, IoT, Blockchain). La investigación comienza por consumir papers actuales.' },
    { time: '🏕️ Este Mes',      text: 'Replica un paper de investigación en código propio. Escoge uno de tamaño razonable en Papers With Code — es la plataforma que conecta investigación y código.' },
    { time: '📅 3 Meses',      text: 'Presenta un paper propio o propuesta de investigación en una convocatoria universitaria o de MinCiencias. Las empresas valoran el pensamiento innovador documentado.' },
    { time: '🎓 Al Graduarte', text: 'Aplica a programas de doctorado o a centros de I+D como el Grupo de Investigación de IBM Research Latam o el Centro de IA de la U. de los Andes.' },
  ],
}

// Arquetipos profesionales (usados por Fase 3 del cuestionario)
const ARCHETYPES = {
  A: { name: 'El Arquitecto Analítico', icon: '🏗️', desc: 'Piensas antes de actuar. Diseñas sistemas robustos y documentados. Ideal para roles de Arquitectura de Software, Data Engineering o Security.', color: '#3B82F6' },
  B: { name: 'El Ejecutor Pragmático',  icon: '⚡', desc: 'Tu prioridad es entregar resultados rápidos. Sobresales bajo presión. Altamente compatible con roles de DevOps, Soporte Crítico o Desarrollo Ágil.', color: '#F59E0B' },
  C: { name: 'El Colaborador Creativo', icon: '🎨', desc: 'Aprendes mejor en equipo y con proyectos reales. Tu perfil encaja perfectamente en UX/UI, Gestión de Producto y roles de comunicación técnica.', color: '#EC4899' },
  D: { name: 'El Perfeccionista Técnico', icon: '🔬', desc: 'La calidad es tu obsesión. Revisas todo antes de publicar. Este perfil es el núcleo de QA, Investigación y Ciberseguridad.', color: '#10B981' },
}

// Matriz de Fusión: Especialidad Técnica (ML) + Arquetipo Psicométrico -> Rol Definitivo
const FUSION_MATRIX = {
  'Desarrollo de Software': {
    A: 'Ingeniero de Backend / Arquitecto de Software',
    B: 'Desarrollador Full-Stack / Startup Hacker',
    C: 'Tech Lead / Scrum Master Técnico',
    D: 'Desarrollador de Sistemas Críticos y Rendimiento'
  },
  'Data Science & IA': {
    A: 'Machine Learning Engineer / Consultor de Datos',
    B: 'Inteligencia de Negocios (BI) / Analista de Datos',
    C: 'Traductor de Datos (Data Product Manager)',
    D: 'Investigador de IA / Arquitecto de Datos'
  },
  'Infraestructura & Cloud': {
    A: 'Arquitecto Cloud (AWS/Azure)',
    B: 'DevOps Engineer (Despliegues Ágiles)',
    C: 'Site Reliability Engineer (SRE) Colaborativo',
    D: 'Administrador de Alta Disponibilidad & Redes'
  },
  'Ciberseguridad': {
    A: 'Auditor de Seguridad Informática',
    B: 'Pentester / Hacker Ético (Red Team)',
    C: 'Consultor de Compliance en Seguridad',
    D: 'Especialista en Defensa de Redes (Blue Team)'
  },
  'QA & Testing': {
    A: 'Arquitecto de Automatización QA (SDET)',
    B: 'Especialista en Pruebas Exploratorias',
    C: 'QA Lead / Gestor de Calidad de Producto',
    D: 'Performance & Load Testing Engineer'
  },
  'Gestión y Producto': {
    A: 'Technical Product Manager',
    B: 'Agile Coach / Scrum Master Orientado a Entregas',
    C: 'Product Owner',
    D: 'Analista de Requerimientos de Software'
  },
  'Diseño UX/UI': {
    A: 'Arquitecto de Información / UX Researcher',
    B: 'Prototipador Web Rápido para Startups',
    C: 'Diseñador de Producto (Product Designer)',
    D: 'Design Systems Manager / Especialista en Accesibilidad'
  }
}

const getDefinitiveRole = (careerName, archetypeKey) => {
  if (FUSION_MATRIX[careerName] && FUSION_MATRIX[careerName][archetypeKey]) {
    return FUSION_MATRIX[careerName][archetypeKey];
  }
  // Fallback inteligente para especializaciones menos comunes
  const archDesc = {
    A: 'con Enfoque en Arquitectura',
    B: 'con Enfoque en Agilidad y Ejecución',
    C: 'con Visión de Liderazgo y Equipo',
    D: 'con Enfoque Analítico y de Alta Precisión'
  };
  return `Especialista en ${careerName} ${archDesc[archetypeKey] || ''}`;
}

export default function Results() {
  const { id } = useParams()
  const { state } = useLocation()
  const [data, setData] = useState(state || null)
  const [importances, setImportances] = useState([])
  const [courses, setCourses] = useState([])
  const [jobs, setJobs] = useState([])          // empleos de Remotive (tiempo real)
  const [jobsLoading, setJobsLoading] = useState(false)
  const [loading, setLoading] = useState(!state)
  // Arquetipo profesional calculado en Fase 3
  const [archetype, setArchetype] = useState(() => {
    const stored = sessionStorage.getItem('revo_archetype')
    return stored ? JSON.parse(stored) : null
  })

  // Fetch empleos reales desde Remotive API (sin API key)
  const fetchRemotiveJobs = async (specName) => {
    const category = REMOTIVE_CATEGORY[specName]
    if (!category) return
    setJobsLoading(true)
    try {
      const res = await fetch(`https://remotive.com/api/remote-jobs?category=${category}&limit=6`)
      const json = await res.json()
      setJobs(json.jobs || [])
    } catch (e) {
      console.warn('Remotive API error:', e)
    } finally {
      setJobsLoading(false)
    }
  }

  useEffect(() => {
    if (!state && id) {
      mlApi.getPrediction(id).then(r => {
        setData(r.data)
        if (r.data.primary?.specialization_id) {
          surveyApi.getRecommendedCourses(r.data.primary.specialization_id).then(c => setCourses(c.data)).catch(()=>{})
        }
        if (r.data.primary?.name) fetchRemotiveJobs(r.data.primary.name)
      }).finally(() => setLoading(false))
    } else if (state?.primary?.specialization_id) {
      surveyApi.getRecommendedCourses(state.primary.specialization_id).then(c => setCourses(c.data)).catch(()=>{})
    }
    if (state?.primary?.name) fetchRemotiveJobs(state.primary.name)
    mlApi.importances().then(r => setImportances(r.data.slice(0, 8))).catch(() => {})
  }, [id, state])

  if (loading) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center"><div style={{ fontSize:'3rem', animation:'float 2s ease-in-out infinite' }}>🌳</div>
        <p className="text-muted">Cargando resultado...</p>
      </div>
    </div>
  )
  if (!data) return <div className="page"><div className="container"><p className="text-muted">Resultado no encontrado.</p></div></div>

  const primary = data.primary
  const color = primary?.color || CAREERS[primary?.name]?.color || '#6C63FF'
  const careers = CAREERS[primary?.name]?.paths || []

  // Radar data (top3 como datos del radar)
  const radarData = (data.top3 || []).map(s => ({
    subject: s.name?.split(' ')[0] || s.name,
    value: Math.round((s.confidence || s.score || 0) * 100),
    fullMark: 100,
  }))

  // Bar chart data (todas las probabilidades)
  const barData = Object.entries(data.all_probabilities || {}).map(([name, val]) => ({
    name: name.split(' ')[0],
    value: val,
    color: CAREERS[name]?.color || '#6C63FF',
  })).sort((a, b) => b.value - a.value)

  return (
    <div className="page results-page">
      <div className="container">
        {/* Hero resultado */}
        <div className="result-hero glass animate-fade" style={{ '--c': color }}>
          <div className="result-hero-bg" />
          <div className="result-hero-content">
            <div className="result-hero-left">
              <span className="badge badge-purple">Tu Especialización Recomendada</span>
              <h1 className="result-main-name">{primary?.name}</h1>
              <div className="result-conf-row">
                <span className="result-conf-big" style={{ color }}>{primary?.confidence_pct}%</span>
                <span className="text-muted">de compatibilidad</span>
              </div>
              <div className="progress-track result-bar">
                <div className="progress-fill" style={{ width:`${primary?.confidence_pct}%`, background: color }} />
              </div>
              <p className="text-muted text-sm result-model-tag">🌳 Árbol de Decisión · v{data.model_version}</p>

              {/* Rutas de carrera */}
              <div className="career-paths">
                {careers.map((c, i) => (
                  <span key={i} className="career-path-chip" style={{ borderColor: color+'44', color }}>
                    {c}
                  </span>
                ))}
              </div>
            </div>

            <div className="result-hero-right">
              <div className="conf-circle" style={{ '--c': color }}>
                <svg viewBox="0 0 120 120" width="120" height="120">
                  <circle cx="60" cy="60" r="50" fill="none" strokeWidth="8" stroke="rgba(255,255,255,0.06)" />
                  <circle cx="60" cy="60" r="50" fill="none" strokeWidth="8" stroke={color}
                    strokeDasharray={`${(primary?.confidence_pct || 0) * 3.14} 314`}
                    strokeLinecap="round" transform="rotate(-90 60 60)" />
                </svg>
                <div className="conf-circle-text">
                  <span style={{ color }}>{primary?.confidence_pct}%</span>
                  <small>match</small>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="results-grid">
          {/* Top 3 */}
          <div className="glass results-panel animate-fade" style={{ animationDelay:'0.1s' }}>
            <h3 className="panel-title">Top 3 Especializaciones</h3>
            {(data.top3 || []).map((s, i) => {
              const c = s.color || CAREERS[s.name]?.color || '#6C63FF'
              return (
                <div key={i} className="top3-item">
                  <div className="top3-rank" style={{ color: c }}>#{i+1}</div>
                  <div className="top3-info">
                    <div className="top3-name font-semibold">{s.name}</div>
                    <div className="progress-track" style={{ marginTop: 6 }}>
                      <div className="progress-fill" style={{ width:`${s.confidence_pct}%`, background: c }} />
                    </div>
                  </div>
                  <div className="top3-pct font-bold" style={{ color: c }}>{s.confidence_pct}%</div>
                </div>
              )
            })}
          </div>

          {/* Radar Chart */}
          {radarData.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.2s' }}>
              <h3 className="panel-title">Distribución de Aptitudes</h3>
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.08)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#94A3B8', fontSize: 11 }} />
                  <Radar name="Score" dataKey="value" stroke={color} fill={color} fillOpacity={0.25} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Bar Chart */}
          {barData.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.3s' }}>
              <h3 className="panel-title">Probabilidades del Árbol</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={barData} margin={{ left: -20 }}>
                  <XAxis dataKey="name" tick={{ fill:'#94A3B8', fontSize:10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background:'#111827', border:'1px solid rgba(255,255,255,0.08)', borderRadius:10, color:'#F1F5F9' }}
                    formatter={(v) => [`${v}%`, 'Probabilidad']}
                  />
                  <Bar dataKey="value" radius={[6,6,0,0]}>
                    {barData.map((d,i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Feature importances */}
          {importances.length > 0 && (
            <div className="glass results-panel animate-fade" style={{ animationDelay:'0.4s' }}>
              <h3 className="panel-title">Áreas más influyentes en tu resultado</h3>
              {importances.slice(0,6).map((f, i) => {
                // Convierte "aff_1" → nombre de especialización real
                const AFF_NAMES = {
                  'aff_1':  'Desarrollo de Software',
                  'aff_2':  'Data Science & IA',
                  'aff_3':  'Infraestructura & Cloud',
                  'aff_4':  'Ciberseguridad',
                  'aff_5':  'Soporte Técnico & IT Ops',
                  'aff_6':  'QA & Testing',
                  'aff_7':  'Gestión y Producto',
                  'aff_8':  'Diseño UX/UI',
                  'aff_9':  'Sistemas Empresariales',
                  'aff_10': 'Investigación e Innovación',
                }
                const label = AFF_NAMES[f.feature.toLowerCase()] || f.feature
                return (
                  <div key={i} className="importance-item">
                    <span className="importance-label text-sm">{label}</span>
                    <div className="importance-bar-wrap">
                      <div className="progress-track" style={{ height: 6 }}>
                        <div className="progress-fill" style={{ width:`${f.pct * 5}%`, background: color }} />
                      </div>
                    </div>
                    <span className="importance-pct text-xs text-muted">{f.pct}%</span>
                  </div>
                )
              })}
            </div>
          )}

        </div>

        {/* Roadmap de Cursos Evolutivo */}
        {courses.length > 0 && (
          <div className="glass results-panel animate-fade course-panel" style={{ animationDelay:'0.45s', marginTop: '20px', gridColumn: '1 / -1' }}>
            <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🚀</span> Tu Roadmap de Aprendizaje ({primary?.name})
            </h3>
            <p className="text-muted text-sm" style={{ marginBottom: '32px' }}>
              Sigue este camino estructurado para ir desde cero hasta maestro en tu rama ideal.
            </p>
            <div className="roadmap-timeline">
              <div className="roadmap-line" style={{ background: `linear-gradient(to bottom, ${primary?.color}88, rgba(255,255,255,0.1))` }}></div>
              {courses.map((c, idx) => (
                <div key={c.id} className="roadmap-step">
                  <div className="roadmap-node" style={{ borderColor: primary?.color }}>
                    <div className="roadmap-dot" style={{ background: primary?.color }}>{idx + 1}</div>
                  </div>
                  <a href={c.url} target="_blank" rel="noopener noreferrer" className="course-card glass-hover roadmap-card" style={{ '--card-color': primary?.color || '#3B82F6' }}>
                    <div className="course-thumb" style={{ 
                        background: `linear-gradient(135deg, ${primary?.color}33 0%, rgba(15,23,42,1) 100%)`,
                        borderBottom: `2px solid ${primary?.color}44`
                    }}>
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '3rem', opacity: 0.15 }}>
                        {primary?.icon || '🎓'}
                      </div>
                      <span className="course-platform" style={{ boxShadow: `0 4px 12px ${primary?.color}33` }}>{c.platform}</span>
                    </div>
                    <div className="course-info">
                      <span className="badge" style={{ alignSelf: 'flex-start', background: `${primary?.color}22`, color: primary?.color, border: `1px solid ${primary?.color}44` }}>{c.level}</span>
                      <h4 className="course-title">{c.title}</h4>
                      <div className="course-meta">
                        <span className={`badge ${c.price_model === 'Gratis' ? 'badge-success' : 'badge-secondary'}`}>{c.price_model}</span>
                        <span className="action-text text-xs" style={{ color: primary?.color, marginLeft: 'auto', fontWeight: 'bold' }}>Empezar Nivel →</span>
                      </div>
                    </div>
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}


        {/* Bolsa de Empleo en Tiempo Real — Remotive API */}
        <div className="glass results-panel animate-fade job-panel" style={{ animationDelay:'0.55s', marginTop: '20px', gridColumn: '1 / -1' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
            <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <span>💼</span> Empleos Reales en Tu Campo
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block', boxShadow: '0 0 8px #10B981' }} />
              <span className="text-xs text-muted">En vivo · Remotive.com</span>
            </div>
          </div>
          <p className="text-muted text-sm" style={{ marginBottom: '20px' }}>
            Vacantes remotas 100% reales y activas a nivel mundial en tu área de especialización. Da clic para postularte directamente.
          </p>

          {jobsLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 72, borderRadius: 12 }} />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: 8 }}>🔍</div>
              <p className="text-muted text-sm">No se encontraron empleos activos en este momento. Intenta de nuevo más tarde.</p>
            </div>
          ) : (
            <div className="jobs-list">
              {jobs.map((j) => (
                <a
                  key={j.id}
                  href={j.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="job-card glass-hover"
                  style={{ textDecoration: 'none', color: 'inherit', display: 'flex' }}
                >
                  {/* Logo de empresa real */}
                  <div className="job-company-icon" style={{ flexShrink: 0 }}>
                    {j.company_logo ? (
                      <img
                        src={j.company_logo}
                        alt={j.company_name}
                        style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'contain', background: '#fff', padding: 4 }}
                        onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='flex' }}
                      />
                    ) : null}
                    <span style={{ display: j.company_logo ? 'none' : 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem' }}>🏢</span>
                  </div>
                  <div className="job-content" style={{ flex: 1, minWidth: 0 }}>
                    <h4 className="job-title" style={{ marginBottom: 4 }}>{j.title}</h4>
                    <div className="job-details">
                      <span className="job-company" style={{ fontWeight: 600 }}>{j.company_name}</span>
                      <span className="job-separator">•</span>
                      <span className="job-location">🌎 {j.candidate_required_location || 'Worldwide Remote'}</span>
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {j.tags?.slice(0, 3).map((tag, ti) => (
                        <span key={ti} style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 20, background: color + '22', color, border: `1px solid ${color}33` }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                  <div className="job-salary-apply" style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                    {j.salary ? (
                      <span className="job-salary font-bold" style={{ color: '#10B981', fontSize: '0.85rem' }}>{j.salary}</span>
                    ) : (
                      <span className="text-xs text-muted">Salario neg.</span>
                    )}
                    <span className="btn-apply" style={{ background: color, color: '#fff', padding: '6px 14px', borderRadius: 8, fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer' }}>
                      Ver oferta →
                    </span>
                  </div>
                </a>
              ))}
            </div>
          )}
          <p className="text-xs text-muted" style={{ marginTop: 16, textAlign: 'center' }}>
            Fuente: <a href="https://remotive.com" target="_blank" rel="noopener noreferrer" style={{ color, textDecoration: 'none' }}>Remotive.com</a> · Empleos remotos verificados y actualizados diariamente
          </p>
        </div>


        {/* Fusión: Arquetipo + Especialidad -> Rol Definitivo */}
        {archetype && primary && (() => {
          const arc = ARCHETYPES[archetype]
          const definitiveRole = getDefinitiveRole(primary.name, archetype);
          return arc ? (
            <div className="glass results-panel animate-fade" style={{ animationDelay: '0.6s', marginTop: 20, gridColumn: '1 / -1', borderLeft: `6px solid ${color}`, position: 'relative', overflow: 'hidden' }}>
              <div className="arc-icon-bg" style={{ position: 'absolute', top: -30, right: -20, fontSize: '12rem', opacity: 0.05, filter: 'grayscale(100%)', pointerEvents: 'none' }}>{arc.icon}</div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
                <span className="badge" style={{ background: color + '22', color: color, border: `1px solid ${color}44`, fontWeight: 700 }}>🏆 Tu Rol Definitivo (Visión 360°)</span>
                <span className="badge" style={{ background: arc.color + '22', color: arc.color, border: `1px solid ${arc.color}44` }}>🧠 Arquetipo: {arc.name.replace('El ', '')}</span>
              </div>
              
              <h3 style={{ fontFamily: 'Space Grotesk', fontWeight: 800, fontSize: '1.8rem', color: '#fff', marginBottom: 12, position: 'relative', zIndex: 1 }}>
                {definitiveRole}
              </h3>
              
              <p className="text-muted text-sm" style={{ lineHeight: 1.6, maxWidth: '90%', position: 'relative', zIndex: 1 }}>
                La Inteligencia Artificial determinó que tus habilidades técnicas son ideales para la <strong>{primary.name}</strong>, 
                pero tu prueba psicométrica revela que posees un enfoque marcado hacia la postura de <strong>{arc.name.replace('El ', '')}</strong>. 
                La máxima sinergia de estas dos áreas te ubica perfectamente en el puesto de {definitiveRole}.
              </p>
              
              <div style={{ marginTop: 16, padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: 12, display: 'flex', gap: 16, alignItems: 'center', border: '1px solid rgba(255,255,255,0.05)', position: 'relative', zIndex: 1 }}>
                <div style={{ fontSize: '2.5rem' }}>{arc.icon}</div>
                <div>
                  <div style={{ fontSize: '0.85rem', color: arc.color, fontWeight: 700, marginBottom: 4 }}>El "Por Qué" de tu Arquetipo</div>
                  <div style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)', lineHeight: 1.5 }}>{arc.desc}</div>
                </div>
              </div>
            </div>
          ) : null
        })()}

        {/* Plan de Acción Personalizado */}
        {(() => {
          const plan = ACTION_PLAN[primary?.name]
          if (!plan) return null
          return (
            <div className="glass results-panel animate-fade" style={{ animationDelay: '0.65s', marginTop: 20, gridColumn: '1 / -1' }}>
              <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span>🗺️</span> Plan de Acción Personalizado — ¿Qué hago ahora?
              </h3>
              <p className="text-muted text-sm" style={{ marginBottom: 24 }}>Pasos concretos basados en tu especialización. Sin excusas para empezar.</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
                {plan.map((step, i) => (
                  <div key={i} style={{ padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: 12, border: `1px solid ${color}22`, borderLeft: `3px solid ${color}` }}>
                    <div style={{ fontWeight: 700, color, marginBottom: 8, fontSize: '0.85rem' }}>{step.time}</div>
                    <p className="text-sm text-muted" style={{ lineHeight: 1.5, margin: 0 }}>{step.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )
        })()}

        {/* Actions */}
        <div className="result-actions animate-fade" style={{ animationDelay: '0.7s' }}>
          <Link to="/questionnaire" className="btn btn-primary">Nueva evaluación</Link>
          <Link to="/history" className="btn btn-secondary">Ver historial</Link>
          <Link to="/dashboard" className="btn btn-ghost">Volver al dashboard</Link>
        </div>
      </div>
    </div>
  )
}
