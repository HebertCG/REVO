import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Auth.css'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email:'', password:'', full_name:'', student_code:'', semester:'' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k, v) => setForm(f => ({...f, [k]: v}))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const payload = { ...form, semester: form.semester ? parseInt(form.semester) : null }
      await register(payload)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrarse')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-orb orb-1"/><div className="auth-orb orb-2"/>
      <div className="auth-card glass animate-scale">
        <div className="auth-logo">⚡ <span className="gradient-text">REVO</span></div>
        <h1 className="auth-title">Crea tu cuenta</h1>
        <p className="text-muted text-sm text-center">Empieza a descubrir tu especialización ideal</p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label">Nombre Completo</label>
            <input className="form-input" type="text" placeholder="Juan Pérez" required
              value={form.full_name} onChange={e => set('full_name', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Email Institucional</label>
            <input className="form-input" type="email" placeholder="tu@universidad.edu" required
              value={form.email} onChange={e => set('email', e.target.value)} />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Código de Estudiante</label>
              <input className="form-input" type="text" placeholder="SIS-2024-001"
                value={form.student_code} onChange={e => set('student_code', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Semestre</label>
              <select className="form-input" value={form.semester} onChange={e => set('semester', e.target.value)}>
                <option value="">Seleccionar</option>
                {[...Array(10)].map((_,i) => <option key={i+1} value={i+1}>{i+1}° Semestre</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Contraseña</label>
            <input className="form-input" type="password" placeholder="Mínimo 6 caracteres" required
              value={form.password} onChange={e => set('password', e.target.value)} />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={loading}>
            {loading ? 'Creando cuenta...' : 'Crear Cuenta →'}
          </button>
        </form>

        <div className="auth-footer">
          ¿Ya tienes cuenta? <Link to="/login" className="auth-link">Iniciar Sesión</Link>
        </div>
      </div>
    </div>
  )
}
