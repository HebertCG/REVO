import { useEffect, useState } from 'react'
import { authApi, borrarToken, EVENTO_SESION_CADUCADA, guardarToken, leerToken } from '../services/api'
import { AuthContext } from './contextoAuth'

/**
 * Estado de sesion de la aplicacion.
 *
 * El token vive en sessionStorage y no en localStorage. La diferencia
 * importa en el caso de uso real de REVO: los alumnos hacen el test desde
 * los equipos compartidos del laboratorio. Con localStorage el token
 * sobrevive al cierre del navegador y el siguiente alumno que se sienta
 * entra en la cuenta del anterior. Con sessionStorage la sesion muere al
 * cerrar la pestana.
 *
 * (Lo ideal frente a XSS seria una cookie httpOnly, que JavaScript no puede
 * leer. Eso exige que el frontend y la API compartan dominio y anadir
 * proteccion CSRF; queda como el siguiente paso, no como algo pendiente de
 * este cambio.)
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // El estado inicial se deriva del token: si no hay ninguno, no hay nada que
  // esperar y arrancar en true para apagarlo dentro del efecto provoca un
  // render en cascada y un parpadeo del estado de carga.
  const [loading, setLoading] = useState(() => Boolean(leerToken()))

  useEffect(() => {
    if (!leerToken()) return

    authApi
      .me()
      .then((r) => setUser(r.data))
      .catch(() => borrarToken())
      .finally(() => setLoading(false))
  }, [])

  // Cuando el interceptor recibe un 401 borra el token y lo anuncia. Aqui se
  // completa el cierre: sin esto el objeto `user` sobrevivia al token y la
  // aplicacion se comportaba como si la sesion siguiera abierta hasta la
  // siguiente recarga completa de la pagina.
  useEffect(() => {
    const alCaducar = () => {
      setUser(null)
      setLoading(false)
    }
    window.addEventListener(EVENTO_SESION_CADUCADA, alCaducar)
    return () => window.removeEventListener(EVENTO_SESION_CADUCADA, alCaducar)
  }, [])

  const login = async (email, password) => {
    const { data } = await authApi.login({ email, password })
    guardarToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const register = async (payload) => {
    const { data } = await authApi.register(payload)
    guardarToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const logout = () => {
    borrarToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
