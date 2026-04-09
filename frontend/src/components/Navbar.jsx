import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)

  const handleLogout = () => { logout(); navigate('/'); setIsOpen(false) }
  const isActive = (path) => location.pathname === path ? 'active' : ''
  const closeMenu = () => setIsOpen(false)

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo" onClick={closeMenu}>
          <span className="logo-icon">⚡</span>
          <span className="logo-text">REVO<span className="logo-dot">.</span></span>
        </Link>

        {/* Botón Hamburguesa Móvil */}
        <button className="hamburger" onClick={() => setIsOpen(!isOpen)} aria-label="Toggle Menu">
          {isOpen ? '✕' : '☰'}
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
  )
}
