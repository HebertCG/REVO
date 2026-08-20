import { useEffect } from 'react'
import PanelInformativo from '../components/PanelInformativo'
import Footer from '../components/Footer'
import './Landing.css'

export default function Landing() {
  useEffect(() => {
    const previo = document.body.style.background
    document.body.style.background = '#0a1020'
    return () => { document.body.style.background = previo }
  }, [])

  return (
    <div className="landing landing-light">
      <PanelInformativo />
      <Footer />
    </div>
  )
}
