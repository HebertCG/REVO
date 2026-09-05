import { createContext, useContext } from 'react'

/**
 * Contexto de sesion y el hook que lo lee.
 *
 * Viven fuera de AuthContext.jsx porque un fichero que exporta a la vez un
 * componente y otras cosas rompe la recarga en caliente de Vite: al tocar el
 * proveedor, React no puede sustituirlo en sitio y recarga la pagina entera,
 * con lo que se pierde el estado de la pantalla que se estaba probando.
 */
export const AuthContext = createContext(null)

export const useAuth = () => useContext(AuthContext)
