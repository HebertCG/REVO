import { useState, useEffect, startTransition } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/contextoAuth'
import './Navbar.css'

// Distancia de scroll a partir de la cual la barra se contrae.
const UMBRAL_SCROLL = 24

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  // Al bajar, la barra se despega del borde y se convierte en una píldora
  // flotante. Se usa passive porque el listener no cancela el scroll, y
  // requestAnimationFrame para no tocar el estado en cada evento.
  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        setScrolled(window.scrollY > UMBRAL_SCROLL)
        ticking = false
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Cerrar el menú móvil al cambiar de ruta evita que quede abierto encima.
  // Se ajusta durante el pintado y no dentro de un efecto: con el efecto,
  // React pintaba primero el menú abierto sobre la pantalla nueva y lo cerraba
  // en un segundo render, que es el parpadeo que se veía al navegar en móvil.
  const [rutaDelMenu, setRutaDelMenu] = useState(location.pathname)
  if (rutaDelMenu !== location.pathname) {
    setRutaDelMenu(location.pathname)
    setIsOpen(false)
  }

  // Salir tiene que dejar al alumno en la portada, no en el formulario de
  // acceso.
  //
  // No es cuestion de orden. React Router marca la navegacion como
  // transicion, mientras que cerrar la sesion es una actualizacion normal:
  // React confirma la segunda antes que la primera, y en ese render
  // intermedio la ruta sigue siendo /dashboard con el usuario ya en null,
  // asi que `PrivateRoute` pinta su <Navigate to="/login"> y ese redirigido
  // gana la carrera.
  //
  // Metiendo las dos en la MISMA transicion, React las confirma juntas: en
  // el unico render que se ve, la ruta ya es la portada y no hay ruta
  // privada montada que redirija. `replace` evita ademas dejar la pantalla
  // privada en el historial del navegador.
  const handleLogout = () => {
    startTransition(() => {
      logout()
      navigate('/', { replace: true })
    })
    setIsOpen(false)
  }
  const isActive = (path) => location.pathname === path ? 'active' : ''
  const closeMenu = () => setIsOpen(false)

  return (
    <div className={`navbar-shell ${scrolled ? 'scrolled' : ''}`}>
      <nav className="navbar" aria-label="Navegación principal">
        <div className="navbar-inner">
          <Link to="/" className="navbar-logo" onClick={closeMenu}>
            <span className="logo-text">REVO<span className="logo-dot">.</span></span>
          </Link>

          <button
            className={`hamburger ${isOpen ? 'open' : ''}`}
            onClick={() => setIsOpen(!isOpen)}
            aria-label={isOpen ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={isOpen}
          >
            <span className="hamburger-bar" />
            <span className="hamburger-bar" />
            <span className="hamburger-bar" />
          </button>

          {user ? (
            <div className={`navbar-right ${isOpen ? 'open' : ''}`}>
              <Link to="/dashboard" className={`nav-link ${isActive('/dashboard')}`} onClick={closeMenu}>Dashboard</Link>
              <Link to="/questionnaire" className={`nav-link ${isActive('/questionnaire')}`} onClick={closeMenu}>Cuestionario</Link>
              <Link to="/history" className={`nav-link ${isActive('/history')}`} onClick={closeMenu}>Historial</Link>
              {user.role === 'admin' && (
                <Link to="/admin" className={`nav-link ${isActive('/admin')}`} onClick={closeMenu}>Admin</Link>
              )}
              <div className="navbar-user">
                <div className="user-avatar">{user.full_name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user.full_name?.split(' ')[0]}</span>
                <button className="btn btn-sm btn-ghost" onClick={handleLogout}>Salir</button>
              </div>
            </div>
          ) : (
            <div className={`navbar-right ${isOpen ? 'open' : ''}`}>
              <Link to="/login" className="btn btn-secondary btn-sm" onClick={closeMenu}>Iniciar Sesión</Link>
              <Link to="/register" className="btn btn-primary btn-sm" onClick={closeMenu}>Registrarse</Link>
            </div>
          )}
        </div>
      </nav>
    </div>
  )
}
