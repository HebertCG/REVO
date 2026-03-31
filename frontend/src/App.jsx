import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Questionnaire from './pages/Questionnaire'
import Results from './pages/Results'
import History from './pages/History'
import Admin from './pages/Admin'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
    <div style={{ fontSize:'2rem', animation:'float 2s ease-in-out infinite' }}>⚡</div>
  </div>
  return user ? children : <Navigate to="/login" />
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user?.role === 'admin' ? children : <Navigate to="/dashboard" />
}

function AppRoutes() {
  return (
    <>
      <Navbar />
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
