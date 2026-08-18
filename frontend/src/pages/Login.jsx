import Auth from './Auth'

// Las dos rutas comparten el mismo componente: el diseño resuelve
// login y registro con pestañas, y `modoInicial` decide cuál abre.
export default function Login() {
  return <Auth modoInicial="login" />
}
