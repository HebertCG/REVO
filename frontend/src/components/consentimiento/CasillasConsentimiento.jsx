import { useEffect, useState } from 'react'
import { legalApi } from '../../services/api'
import ModalDocumentoLegal from './ModalDocumentoLegal'
import './consentimiento.css'

/**
 * Casillas de consentimiento del formulario de registro.
 *
 * Por que hay tres casillas y no una:
 *
 * Usar REVO, vender datos agregados a universidades y entrenar el modelo son
 * tres finalidades distintas. Bajo la Ley 29733 el consentimiento para las
 * dos ultimas tiene que ser libre y especifico, y no puede condicionarse a
 * poder usar la plataforma. Una sola casilla que lo agrupe todo es
 * impugnable, y ademas obliga al alumno a aceptar la venta de sus datos para
 * poder hacer un test de orientacion.
 *
 * Las dos opcionales nacen DESMARCADAS a proposito. Una casilla premarcada
 * no es consentimiento: es una suposicion.
 *
 * @param {object} props
 * @param {{terms: boolean, dataCommercial: boolean, aiTraining: boolean}} props.valores
 * @param {(clave: string, valor: boolean) => void} props.onCambio
 * @param {string} [props.error]
 */
export default function CasillasConsentimiento({ valores, onCambio, error }) {
  const [documentos, setDocumentos] = useState([])
  const [abierto, setAbierto] = useState(null)

  useEffect(() => {
    let vivo = true
    legalApi
      .documentos()
      .then(({ data }) => { if (vivo) setDocumentos(data) })
      // Si el catalogo no carga, se usan los textos de reserva de abajo: el
      // registro no puede quedarse bloqueado porque falle una llamada
      // secundaria, pero el alumno tiene que ver siempre que esta aceptando.
      .catch(() => { if (vivo) setDocumentos([]) })
    return () => { vivo = false }
  }, [])

  const resumen = (tipo, reserva) =>
    documentos.find((d) => d.doc_type === tipo)?.summary || reserva

  return (
    <div className="rv-consent">
      <Casilla
        id="consent-terms"
        obligatoria
        marcada={valores.terms}
        onCambio={(v) => onCambio('terms', v)}
        onLeerMas={() => setAbierto('terms')}
        texto={resumen(
          'terms',
          'Acepto los Terminos y Condiciones y la Politica de Privacidad de REVO.',
        )}
        enlaceSecundario={{ etiqueta: 'Ver privacidad', tipo: 'privacy' }}
        onEnlaceSecundario={() => setAbierto('privacy')}
      />

      <p className="rv-consent-separador">
        Lo siguiente es <strong>opcional</strong>. REVO funciona igual si lo dejas sin marcar,
        y puedes cambiarlo cuando quieras desde tu perfil.
      </p>

      <Casilla
        id="consent-comercial"
        marcada={valores.dataCommercial}
        onCambio={(v) => onCambio('dataCommercial', v)}
        onLeerMas={() => setAbierto('data_commercial')}
        texto={resumen(
          'data_commercial',
          'Autorizo que REVO comparta informacion agregada y seudonimizada de mis resultados con universidades y academias.',
        )}
      />

      <Casilla
        id="consent-ia"
        marcada={valores.aiTraining}
        onCambio={(v) => onCambio('aiTraining', v)}
        onLeerMas={() => setAbierto('ai_training')}
        texto={resumen(
          'ai_training',
          'Autorizo que mis respuestas se usen para entrenar y mejorar el modelo de recomendacion de REVO.',
        )}
      />

      {error && (
        <p className="rv-consent-error" role="alert">
          {error}
        </p>
      )}

      {abierto && (
        <ModalDocumentoLegal tipo={abierto} onCerrar={() => setAbierto(null)} />
      )}
    </div>
  )
}

function Casilla({
  id,
  texto,
  marcada,
  onCambio,
  onLeerMas,
  obligatoria = false,
  enlaceSecundario,
  onEnlaceSecundario,
}) {
  return (
    <div className={`rv-consent-fila ${obligatoria ? 'rv-consent-obligatoria' : ''}`}>
      <input
        id={id}
        type="checkbox"
        checked={marcada}
        onChange={(e) => onCambio(e.target.checked)}
        className="rv-consent-check"
        aria-describedby={`${id}-texto`}
      />
      <div className="rv-consent-texto" id={`${id}-texto`}>
        <label htmlFor={id}>
          {texto}
          {obligatoria && <span className="rv-consent-marca" aria-label="obligatorio"> *</span>}
        </label>
        <span className="rv-consent-enlaces">
          {/* Un <button> y no un <a href="#">: no navega a ninguna parte,
              abre una ventana. Un enlace falso rompe el "abrir en pestana
              nueva" y confunde a los lectores de pantalla. */}
          <button type="button" onClick={onLeerMas}>Leer mas</button>
          {enlaceSecundario && (
            <>
              <span aria-hidden="true"> · </span>
              <button type="button" onClick={onEnlaceSecundario}>
                {enlaceSecundario.etiqueta}
              </button>
            </>
          )}
        </span>
      </div>
    </div>
  )
}
