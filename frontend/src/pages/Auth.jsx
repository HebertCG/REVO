import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import personaImg from '../assets/login-persona.png'
import './Auth.css'

// El diseno ofrece el ciclo por rangos; el backend guarda un entero
// entre 1 y 12, asi que se toma el extremo inferior de cada rango.
const CICLOS = { '1 – 2': 1, '3 – 4': 3, '5 – 6': 5, '7 – 8': 7, '9 – 10': 9, 'Egresado': 12 }

const VACIO = { full_name: '', email: '', password: '', student_code: '', semester: '5 – 6' }

/**
 * Pantalla de acceso: login y registro en un solo componente con pestanas.
 *
 * Se usa en las dos rutas. `modoInicial` decide cual pestana abre, y al
 * cambiar de pestana se navega a la ruta correspondiente para que la URL
 * y el boton "atras" del navegador sigan siendo coherentes.
 */
export default function Auth({ modoInicial = 'login', mostrarSSO = false }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [modo, setModo] = useState(modoInicial)
  const [verPass, setVerPass] = useState(false)
  const [recordar, setRecordar] = useState(true)
  const [form, setForm] = useState(VACIO)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // La ruta manda: si el usuario llega por /register o pulsa atras,
  // la pestana se sincroniza sola.
  useEffect(() => {
    setModo(location.pathname === '/register' ? 'registro' : 'login')
    setError('')
  }, [location.pathname])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const esRegistro = modo === 'registro'
  const esLogin = !esRegistro

  const irA = (destino) => { setError(''); navigate(destino) }
  const verLogin = () => irA('/login')
  const verRegistro = () => irA('/register')
  const alternar = (e) => { e.preventDefault(); irA(esRegistro ? '/login' : '/register') }

  const togglePassword = () => setVerPass((v) => !v)
  const toggleRecordar = () => setRecordar((r) => !r)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (esRegistro) {
        await register({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          password: form.password,
          student_code: form.student_code.trim() || null,
          semester: CICLOS[form.semester] ?? null,
        })
        navigate('/dashboard')
      } else {
        const usuario = await login(form.email.trim(), form.password)
        navigate(usuario.role === 'admin' ? '/admin' : '/dashboard')
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        (esRegistro ? 'No se pudo crear la cuenta' : 'Credenciales incorrectas')
      )
    } finally {
      setLoading(false)
    }
  }

  // ── Valores derivados que el diseno espera ──────────────────
  const tab = (activo) => ({
    flex: '1', padding: '11px', border: 0, borderRadius: '9px',
    fontFamily: 'inherit', fontSize: '13.5px', fontWeight: 700, cursor: 'pointer',
    transition: 'background .15s ease, color .15s ease',
    ...(activo
      ? { background: '#fff', color: '#0d1220', boxShadow: '0 1px 3px rgba(13,18,32,.12)' }
      : { background: 'transparent', color: '#5a6478' }),
  })

  const largo = form.password.length
  const nivel = largo === 0 ? 0 : largo < 8 ? 1 : largo < 12 ? 2 : 3

  const titulo = esRegistro ? 'Crea tu cuenta REVO' : 'Bienvenido de vuelta'
  const subtitulo = esRegistro
    ? 'Guarda cada test que hagas y mira cómo cambia tu perfil semestre a semestre.'
    : 'Entra para ver tu recomendación y seguir tu plan de acción.'
  const textoBoton = esRegistro ? 'Crear cuenta y empezar' : 'Iniciar sesión'
  const textoCargando = esRegistro ? 'Creando cuenta…' : 'Entrando…'
  const textoCheck = esRegistro
    ? 'Acepto el uso de mis respuestas para el modelo'
    : 'Mantener sesión abierta'
  const piePagina = esRegistro ? '¿Ya tienes cuenta?' : '¿Primera vez en REVO?'
  const pieAccion = esRegistro ? 'Inicia sesión' : 'Crea tu cuenta gratis'
  const tabLoginStyle = tab(esLogin)
  const tabRegistroStyle = tab(esRegistro)
  const tipoPassword = verPass ? 'text' : 'password'
  const labelPassword = verPass ? 'Ocultar' : 'Ver'
  const fuerzaPct = ['0%', '34%', '67%', '100%'][nivel]
  const fuerzaColor = ['#e6eaf3', '#e2574c', '#f2a93b', '#2f9e5e'][nivel]
  const fuerzaTexto = ['', 'Débil', 'Media', 'Fuerte'][nivel]

  return (
    <div className="revo-auth">
      {error && <div className="revo-auth-error" role="alert">{error}</div>}
        <div style={{fontFamily: "'Plus Jakarta Sans',system-ui,-apple-system,sans-serif", color: "#0d1220", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "68px 0 0", background: "#eef2fb"}}>
          <div style={{position: "relative", width: "100%", minHeight: "calc(100vh - 68px)", display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(420px,100%),1fr))", background: "#fff", borderRadius: "0", overflow: "hidden", boxShadow: "none"}}>
            <div style={{position: "relative", overflow: "hidden", background: "#2f5fe8", color: "#fff", padding: "clamp(26px,3.4vw,44px)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "26px", minHeight: "clamp(330px,38vw,620px)", borderRadius: "0 30% 30% 0 / 0 50% 50% 0", zIndex: "1"}}>
              <div style={{position: "absolute", right: "-22%", top: "-16%", width: "74%", aspectRatio: "1", borderRadius: "999px", background: "#1e46bd", opacity: ".55", pointerEvents: "none"}}></div>
              <div style={{position: "absolute", left: "-30%", bottom: "-26%", width: "80%", aspectRatio: "1", borderRadius: "999px", background: "#5b86ff", opacity: ".35", pointerEvents: "none"}}></div>
              <div style={{position: "relative", display: "flex", alignItems: "center", gap: "9px"}}>
                <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "26px", height: "26px", borderRadius: "8px", background: "#fff", color: "#2f5fe8", fontSize: "14px", fontWeight: "800"}}>
                  ⚡
                </span>
                <span style={{fontSize: "19px", fontWeight: "800", letterSpacing: "-.02em"}}>
                  REVO
                  <span style={{color: "#c9d9ff"}}>
                    .
                  </span>
                </span>
              </div>
              <div style={{position: "relative", flex: "1", display: "flex", alignItems: "center", justifyContent: "center"}}>
                <img src={personaImg} alt="Estudiante haciendo el test de REVO en su escritorio" style={{display: "block", width: "100%", maxWidth: "460px", height: "auto", maxHeight: "clamp(320px,36vw,560px)", objectFit: "contain"}} />
              </div>
            </div>
            <div style={{position: "relative", display: "flex", alignItems: "center", justifyContent: "center", padding: "clamp(28px,4vw,56px) clamp(20px,4vw,44px)"}}>
              <div style={{width: "100%", maxWidth: "392px", minHeight: "688px", display: "flex", flexDirection: "column", justifyContent: "center", animation: "revoRise .6s .08s ease both"}}>
                <div style={{display: "flex", padding: "4px", borderRadius: "12px", background: "#f2f4f9", border: "1px solid rgba(13,18,32,.07)"}}>
                  <button type="button" onClick={verLogin} style={tabLoginStyle}>
                    Iniciar sesión
                  </button>
                  <button type="button" onClick={verRegistro} style={tabRegistroStyle}>
                    Crear cuenta
                  </button>
                </div>
                <h1 style={{margin: "28px 0 0", fontSize: "clamp(23px,2.4vw,28px)", lineHeight: "1.15", letterSpacing: "-.025em", fontWeight: "800"}}>
                  {titulo}
                </h1>
                <p style={{margin: "9px 0 0", fontSize: "14.5px", lineHeight: "1.55", color: "#5a6478"}}>
                  {subtitulo}
                </p>
                <form onSubmit={handleSubmit} style={{display: "flex", flexDirection: "column", gap: "16px", marginTop: "26px"}}>
                  {esRegistro && (
                    <>
                    <div style={{display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "12px"}}>
                      <label style={{display: "flex", flexDirection: "column", gap: "7px", minWidth: "0"}}>
                        <span style={{fontSize: "12.5px", fontWeight: "700", color: "#3b465c"}}>
                          Nombre completo
                        </span>
                        <input type="text" placeholder="Ana Quispe" required={esRegistro} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} autoComplete="name" style={{width: "100%", boxSizing: "border-box", padding: "14px 15px", borderRadius: "11px", border: "1.5px solid #e2e6ef", background: "#fff", fontFamily: "inherit", fontSize: "14.5px", color: "#0d1220", transition: "border-color .15s ease,box-shadow .15s ease"}} />
                      </label>
                      <label style={{display: "flex", flexDirection: "column", gap: "7px", minWidth: "0"}}>
                        <span style={{fontSize: "12.5px", fontWeight: "700", color: "#3b465c"}}>
                          Ciclo
                        </span>
                        <select className="rvl-f1" value={form.semester} onChange={(e) => set("semester", e.target.value)} style={{width: "100%", boxSizing: "border-box", padding: "14px 12px", borderRadius: "11px", border: "1.5px solid #e2e6ef", background: "#fff", fontFamily: "inherit", fontSize: "14.5px", color: "#0d1220", cursor: "pointer"}}>
                          <option>
                            1 – 2
                          </option>
                          <option>
                            3 – 4
                          </option>
                          <option>
                            5 – 6
                          </option>
                          <option>
                            7 – 8
                          </option>
                          <option>
                            9 – 10
                          </option>
                          <option>
                            Egresado
                          </option>
                        </select>
                      </label>
                    </div>
                    </>
                  )}
                  <label style={{display: "flex", flexDirection: "column", gap: "7px"}}>
                    <span style={{fontSize: "12.5px", fontWeight: "700", color: "#3b465c"}}>
                      Correo institucional
                    </span>
                    <input className="rvl-f1" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required autoComplete="email" placeholder="tunombre@universidad.edu.pe" style={{width: "100%", boxSizing: "border-box", padding: "14px 15px", borderRadius: "11px", border: "1.5px solid #e2e6ef", background: "#fff", fontFamily: "inherit", fontSize: "14.5px", color: "#0d1220", transition: "border-color .15s ease,box-shadow .15s ease"}} />
                  </label>
                  <label style={{display: "flex", flexDirection: "column", gap: "7px"}}>
                    <span style={{display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "12.5px", fontWeight: "700", color: "#3b465c"}}>
                      Contraseña
                      {esLogin && (
                        <>
                        <a href="#recuperar" onClick={(e) => e.preventDefault()} style={{fontSize: "12.5px", fontWeight: "600"}}>
                          ¿La olvidaste?
                        </a>
                        </>
                      )}
                    </span>
                    <span style={{position: "relative", display: "block"}}>
                      <input className="rvl-f1" type={tipoPassword} value={form.password} onChange={(e) => set("password", e.target.value)} required minLength={6} autoComplete={esRegistro ? "new-password" : "current-password"} placeholder="Mínimo 8 caracteres" style={{width: "100%", boxSizing: "border-box", padding: "14px 62px 14px 15px", borderRadius: "11px", border: "1.5px solid #e2e6ef", background: "#fff", fontFamily: "inherit", fontSize: "14.5px", color: "#0d1220", transition: "border-color .15s ease,box-shadow .15s ease"}} />
                      <button className="rvl-h2" type="button" onClick={togglePassword} style={{position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", padding: "6px 9px", border: "0", borderRadius: "8px", background: "#f2f4f9", color: "#3b465c", fontFamily: "inherit", fontSize: "11.5px", fontWeight: "700", cursor: "pointer"}}>
                        {labelPassword}
                      </button>
                    </span>
                    {esRegistro && (
                      <>
                      <span style={{display: "flex", alignItems: "center", gap: "8px", marginTop: "2px"}}>
                        <span style={{flex: "1", height: "4px", borderRadius: "999px", background: "#e6eaf3", overflow: "hidden"}}>
                          <span style={{display: "block", width: fuerzaPct, height: "100%", borderRadius: "999px", background: fuerzaColor, transition: "width .25s ease"}}></span>
                        </span>
                        <span style={{fontSize: "11.5px", fontWeight: "600", color: "#5a6478", minWidth: "52px"}}>
                          {fuerzaTexto}
                        </span>
                      </span>
                      </>
                    )}
                  </label>
                  <label style={{display: "flex", alignItems: "center", gap: "9px", fontSize: "13.5px", color: "#3b465c", cursor: "pointer", userSelect: "none"}}>
                    <input type="checkbox" checked={recordar} onChange={toggleRecordar} style={{width: "17px", height: "17px", accentColor: "#2f5fe8", cursor: "pointer"}} />
                    {textoCheck}
                  </label>
                  <button className="rvl-h3 rvl-a4" type="submit" disabled={loading} style={{display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", width: "100%", padding: "16px", border: "0", borderRadius: "12px", background: "#2f5fe8", color: "#fff", fontFamily: "inherit", fontSize: "15px", fontWeight: "700", cursor: "pointer", boxShadow: "0 8px 20px rgba(47,95,232,.28)", transition: "background .15s ease,transform .15s ease"}}>
                    {loading ? textoCargando : textoBoton}
                    <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "22px", height: "22px", borderRadius: "999px", background: "rgba(255,255,255,.2)", fontSize: "13px"}}>
                      →
                    </span>
                  </button>
                </form>
                  {mostrarSSO && (
                    <>
                    <div style={{display: "flex", flexDirection: "column", gap: "12px"}}>
                      <div style={{display: "flex", alignItems: "center", gap: "12px"}}>
                        <span style={{flex: "1", height: "1px", background: "rgba(13,18,32,.1)"}}></span>
                        <span style={{fontSize: "11.5px", fontWeight: "600", color: "#8a93a6"}}>
                          o continúa con
                        </span>
                        <span style={{flex: "1", height: "1px", background: "rgba(13,18,32,.1)"}}></span>
                      </div>
                      <button className="rvl-h5" type="button" style={{display: "flex", alignItems: "center", justifyContent: "center", gap: "9px", width: "100%", padding: "14px", border: "1.5px solid #e2e6ef", borderRadius: "11px", background: "#fff", fontFamily: "inherit", fontSize: "13.5px", fontWeight: "600", color: "#0d1220", cursor: "pointer", transition: "border-color .15s ease"}}>
                        <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "14px", fontWeight: "600"}}>
                          G
                        </span>
                        Continuar con Google
                      </button>
                    </div>
                    </>
                  )}
                  <p style={{margin: "4px 0 0", fontSize: "12.5px", lineHeight: "1.55", color: "#8a93a6"}}>
                    {piePagina}
                    <a href={esRegistro ? "/login" : "/register"} onClick={alternar} style={{fontWeight: "700"}}>
                      {pieAccion}
                    </a>
                  </p>
              </div>
            </div>
          </div>
        </div>
    </div>
  )
}
