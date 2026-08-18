import { useEffect } from 'react'
import PanelInformativo from '../components/PanelInformativo'
import Footer from '../components/Footer'
import './Landing.css'

/**
 * Pagina de inicio.
 *
 * El contenido lo aporta <PanelInformativo />, portado desde el diseno de
 * Claude Design. El <Navbar /> lo monta App.jsx para todas las rutas.
 */
export default function Landing() {
  // El resto de la aplicacion usa tema oscuro y el body arrastra ese color
  // desde index.css. Como esta pagina es clara, el fondo del body asomaba
  // por cualquier franja que el contenido no llegara a pintar. Se cambia
  // mientras la landing esta montada y se restaura al salir.
  useEffect(() => {
    const previo = document.body.style.background
    document.body.style.background = '#ffffff'
    return () => { document.body.style.background = previo }
  }, [])

  return (
    <div className="landing landing-light">
      <PanelInformativo />
      <Footer />
    </div>
  )
}
