import { useEffect, useRef, useState } from 'react'
import { legalApi } from '../../services/api'
import './consentimiento.css'

/**
 * Ventana con el texto completo de un documento legal.
 *
 * Se abre desde el enlace "Leer mas" de cada casilla. El texto se pide al
 * servidor en ese momento y no se empaqueta con la aplicacion: asi, cuando
 * se publique una version nueva del documento, el alumno lee la vigente sin
 * que haya que volver a desplegar el frontend.
 */
export default function ModalDocumentoLegal({ tipo, onCerrar }) {
  const [documento, setDocumento] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const cajaRef = useRef(null)
  const cerrarRef = useRef(null)

  useEffect(() => {
    let vivo = true

    // No se llama a setCargando(true) aqui: el estado ya nace en true y una
    // asignacion sincrona dentro del efecto provoca un render en cascada.
    legalApi
      .documento(tipo)
      .then(({ data }) => { if (vivo) setDocumento(data) })
      .catch((err) => { if (vivo) setError(err.mensajeUsuario || 'No se pudo cargar el documento.') })
      .finally(() => { if (vivo) setCargando(false) })

    return () => { vivo = false }
  }, [tipo])

  // El foco entra al dialogo al abrirlo y Escape lo cierra. Sin esto, quien
  // navega con teclado se queda con el foco detras de la ventana y no puede
  // salir ni leer el documento.
  useEffect(() => {
    cerrarRef.current?.focus()

    const alPulsar = (evento) => {
      if (evento.key === 'Escape') onCerrar()
    }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [onCerrar])

  const alClicarFuera = (evento) => {
    if (evento.target === cajaRef.current) onCerrar()
  }

  return (
    <div
      className="rv-legal-fondo"
      ref={cajaRef}
      onClick={alClicarFuera}
      role="presentation"
    >
      <div
        className="rv-legal-caja"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rv-legal-titulo"
      >
        <header className="rv-legal-cabecera">
          <h2 id="rv-legal-titulo">{documento?.title || 'Documento legal'}</h2>
          <button
            type="button"
            ref={cerrarRef}
            onClick={onCerrar}
            className="rv-legal-cerrar"
            aria-label="Cerrar el documento"
          >
            ✕
          </button>
        </header>

        <div className="rv-legal-cuerpo" tabIndex={0}>
          {cargando && <p className="rv-legal-estado">Cargando el documento…</p>}
          {error && <p className="rv-legal-estado rv-legal-error">{error}</p>}
          {documento && <TextoLegal markdown={documento.body_md} />}
        </div>

        {documento && (
          <footer className="rv-legal-pie">
            Version {documento.version}
            {documento.is_required && ' · Aceptacion obligatoria'}
          </footer>
        )}
      </div>
    </div>
  )
}

/**
 * Pinta el documento.
 *
 * Se recorre el texto linea a linea y se construyen elementos de React en
 * lugar de inyectar HTML. El contenido viene de la base de datos, y usar
 * dangerouslySetInnerHTML con algo que un administrador puede editar
 * convierte el panel de administracion en un vector de XSS contra todos los
 * alumnos que abran el documento.
 */
function TextoLegal({ markdown }) {
  const lineas = (markdown || '').split('\n')
  const bloques = []
  let lista = []

  const cerrarLista = (clave) => {
    if (lista.length === 0) return
    bloques.push(<ul key={`lista-${clave}`}>{lista}</ul>)
    lista = []
  }

  lineas.forEach((linea, i) => {
    const limpia = linea.trim()

    if (limpia.startsWith('### ')) {
      cerrarLista(i)
      bloques.push(<h4 key={i}>{limpia.slice(4)}</h4>)
    } else if (limpia.startsWith('## ')) {
      cerrarLista(i)
      bloques.push(<h3 key={i}>{limpia.slice(3)}</h3>)
    } else if (limpia.startsWith('# ')) {
      cerrarLista(i)
      bloques.push(<h2 key={i}>{limpia.slice(2)}</h2>)
    } else if (limpia.startsWith('- ')) {
      lista.push(<li key={i}>{conNegritas(limpia.slice(2))}</li>)
    } else if (limpia === '') {
      cerrarLista(i)
    } else {
      cerrarLista(i)
      bloques.push(<p key={i}>{conNegritas(limpia)}</p>)
    }
  })
  cerrarLista('final')

  return <>{bloques}</>
}

/** Convierte **texto** en <strong>, sin pasar por HTML. */
function conNegritas(texto) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((trozo, i) =>
    trozo.startsWith('**') && trozo.endsWith('**')
      ? <strong key={i}>{trozo.slice(2, -2)}</strong>
      : trozo,
  )
}
