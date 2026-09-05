import { Component } from 'react'
import { Link } from 'react-router-dom'

/**
 * Red de seguridad de pintado.
 *
 * Sin un limite de error, cualquier excepcion durante el render desmonta el
 * arbol entero: React deja `#root` vacio y el alumno se queda ante una
 * pagina en blanco, sin barra de navegacion y sin un solo enlace desde el
 * que salir. La unica salida es recargar a mano, y nada en pantalla se lo
 * dice.
 *
 * El limite envuelve las rutas y no la barra: asi la navegacion sigue en pie
 * y el fallo queda acotado a la pantalla que lo provoco.
 *
 * No ofrece "reintentar" sin mas: si el fallo viene de los datos que la
 * pantalla acaba de recibir, volver a pintar la rompe otra vez. Se ofrece
 * recargar (que vuelve a pedir los datos) o irse a otra pantalla.
 */
export default class LimiteDeError extends Component {
  state = { fallo: null, ubicacion: null }

  static getDerivedStateFromError(fallo) {
    return { fallo }
  }

  /**
   * Al cambiar de ruta se olvida el fallo anterior.
   *
   * Antes esto se conseguia poniendo `key={pathname}` en el limite, pero esa
   * clave remonta TODO lo que envuelve en cada navegacion: el Suspense de las
   * rutas diferidas volvia a empezar y la pantalla parpadeaba en su hueco de
   * carga antes de pintar nada. Reiniciar solo el estado del limite consigue
   * lo mismo sin tirar el arbol.
   */
  static getDerivedStateFromProps(props, estado) {
    if (props.ubicacion === estado.ubicacion) return null
    return { fallo: null, ubicacion: props.ubicacion }
  }

  componentDidCatch(fallo, informacion) {
    // En produccion esto es lo unico que queda del incidente: sin la traza no
    // hay forma de saber que pantalla se rompio ni con que datos.
    console.error('Fallo de pintado en una ruta de REVO', fallo, informacion)
  }

  render() {
    if (!this.state.fallo) return this.props.children

    return (
      <div className="page" role="alert">
        <div className="container" style={{ maxWidth: 560, paddingTop: 80, textAlign: 'center' }}>
          <p style={{ fontSize: '2.5rem', margin: 0 }} aria-hidden="true">🧩</p>
          <h1 style={{ marginTop: 12 }}>Esta pantalla se quedó a medias</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>
            No pudimos terminar de dibujarla con los datos que llegaron. Tu
            sesión sigue abierta: vuelve a cargarla o continúa desde otra
            pantalla.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginTop: 24 }}>
            <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
              Volver a cargar
            </button>
            <Link to="/dashboard" className="btn btn-secondary">Ir a mi panel</Link>
          </div>
        </div>
      </div>
    )
  }
}
