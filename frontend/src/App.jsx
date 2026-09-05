import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { useAuth } from './context/contextoAuth'
import LimiteDeError from './components/LimiteDeError'
import Navbar from './components/Navbar'

const Landing = lazy(() => import('./pages/Landing'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Questionnaire = lazy(() => import('./pages/Questionnaire'))
const Results = lazy(() => import('./pages/Results'))
const History = lazy(() => import('./pages/History'))
const Admin = lazy(() => import('./pages/Admin'))

function CargandoRuta() {
  return (
    <div
      className="page"
      role="status"
      aria-live="polite"
      // Marca estable para que las pruebas sepan que la ruta todavia no ha
      // llegado, en vez de medir este hueco creyendo que es la pantalla.
      data-cargando-ruta="si"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <span
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: '1.5rem',
          fontWeight: 800,
          letterSpacing: '-0.03em',
          animation: 'pulse 1.4s ease-in-out infinite',
        }}
        aria-hidden="true"
      >
        REVO
      </span>
      <span className="sr-only">Cargando pantalla</span>
    </div>
  )
}

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <CargandoRuta />
  return user ? children : <Navigate to="/login" />
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <CargandoRuta />
  return user?.role === 'admin' ? children : <Navigate to="/dashboard" />
}

function AppRoutes() {
  // El limite se reinicia al cambiar de ruta: sin eso, una pantalla rota deja
  // el aviso de fallo puesto y las siguientes navegaciones no pintan nada,
  // aunque la pantalla a la que se va este perfectamente.
  const { pathname } = useLocation()

  return (
    <>
      <Navbar />
      <LimiteDeError ubicacion={pathname}>
        <Suspense fallback={<CargandoRuta />}>
          <Routes>
            <Route path="/"              element={<Landing />} />
            <Route path="/login"         element={<Login />} />
            <Route path="/register"      element={<Register />} />
            <Route path="/dashboard"     element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/questionnaire" element={<PrivateRoute><Questionnaire /></PrivateRoute>} />
            <Route path="/results/:id"   element={<PrivateRoute><Results /></PrivateRoute>} />
            <Route path="/history"       element={<PrivateRoute><History /></PrivateRoute>} />
            <Route path="/admin"         element={<AdminRoute><Admin /></AdminRoute>} />
            <Route path="*"              element={<Navigate to="/" />} />
          </Routes>
        </Suspense>
      </LimiteDeError>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
