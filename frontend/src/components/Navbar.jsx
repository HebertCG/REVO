import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => { logout(); navigate('/') }
  const isActive = (path) => location.pathname === path ? 'active' : ''

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <span className="logo-icon">⚡</span>
          <span className="logo-text">REVO<span className="logo-dot">.</span></span>
        </Link>

        {user ? (
          <div className="navbar-right">
            <Link to="/dashboard" className={`nav-link ${isActive('/dashboard')}`}>Dashboard</Link>
            <Link to="/questionnaire" className={`nav-link ${isActive('/questionnaire')}`}>Cuestionario</Link>
            <Link to="/history" className={`nav-link ${isActive('/history')}`}>Historial</Link>
            {user.role === 'admin' && (
              <Link to="/admin" className={`nav-link ${isActive('/admin')}`}>Admin</Link>
            )}
            <div className="navbar-user">
              <div className="user-avatar">{user.full_name?.[0]?.toUpperCase() || 'U'}</div>
              <span className="user-name">{user.full_name?.split(' ')[0]}</span>
              <button className="btn btn-sm btn-ghost" onClick={handleLogout}>Salir</button>
            </div>
          </div>
        ) : (
          <div className="navbar-right">
            <Link to="/login" className="btn btn-secondary btn-sm">Iniciar Sesión</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Registrarse</Link>
          </div>
        )}
      </div>
    </nav>
  )
}
