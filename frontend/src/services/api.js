import axios from 'axios'

import {
  MENSAJE_ARRANQUE,
  esArranqueEnFrio,
  esReintentable,
  esperaAntesDeReintentar,
} from './arranqueEnFrio'

/**
 * Cliente HTTP de REVO.
 *
 * Cambio principal: antes habia tres clientes axios apuntando a tres URLs
 * distintas (VITE_AUTH_URL, VITE_SURVEY_URL, VITE_ML_URL). Eso obligaba a
 * publicar los tres microservicios en internet y dejaba la topologia del
 * sistema escrita en el bundle de JavaScript, que cualquiera puede leer.
 *
 * Ahora hay UN solo origen: la pasarela. Ella decide por recurso a que
 * servicio va cada peticion. Si manana el cuestionario se parte en dos
 * servicios, este archivo no cambia.
 */
const BASE = import.meta.env.VITE_API_URL || '/api'

const CLAVE_TOKEN = 'revo_token'

export const guardarToken = (token) => sessionStorage.setItem(CLAVE_TOKEN, token)
export const leerToken = () => sessionStorage.getItem(CLAVE_TOKEN)
export const borrarToken = () => sessionStorage.removeItem(CLAVE_TOKEN)

/**
 * Aviso de sesion caducada.
 *
 * El interceptor no puede llamar a `AuthContext` (es un modulo, no un
 * componente), asi que anuncia el hecho y el proveedor decide que hacer. Sin
 * este puente, borrar el token dejaba el objeto `user` vivo en memoria: el
 * alumno seguia viendo su nombre en la barra y navegando entre pantallas
 * mientras TODAS las peticiones respondian 401, asi que cada pantalla se
 * caia a su estado vacio y parecia que no tenia datos, no que su sesion
 * habia terminado.
 */
export const EVENTO_SESION_CADUCADA = 'revo:sesion-caducada'

const anunciarSesionCaducada = () => {
  borrarToken()
  window.dispatchEvent(new Event(EVENTO_SESION_CADUCADA))
}

/**
 * Aviso de servicio dormido.
 *
 * Cuando una peticion se reintenta por arranque en frio, la pantalla tiene
 * que poder decirlo. Sin esto el alumno ve un boton girando durante un
 * minuto sin ninguna explicacion, que es indistinguible de una pagina rota.
 *
 * Se avisa una sola vez por episodio, no en cada reintento: lo que le
 * interesa a la interfaz es "estamos esperando" y "se acabo la espera", no
 * la cuenta de intentos.
 *
 * EVENTO_DESPIERTO significa que la espera termino, no que saliera bien:
 * tambien se lanza al agotar los reintentos, para que el aviso se quite y
 * deje sitio al mensaje de error.
 */
export const EVENTO_DESPERTANDO = 'revo:despertando'
export const EVENTO_DESPIERTO = 'revo:despierto'

// Se cuentan las esperas en curso en vez de guardar un si/no. Con un
// booleano, cualquier respuesta correcta apagaba el aviso aunque otra
// peticion siguiera reintentando: basta que la pantalla pida dos cosas a
// la vez y una viaje al servicio ya despierto para que el cartel
// desaparezca mientras todavia se esta esperando a la otra.
let esperasEnCurso = 0

const empezarEspera = () => {
  esperasEnCurso += 1
  if (esperasEnCurso === 1) window.dispatchEvent(new Event(EVENTO_DESPERTANDO))
}

const terminarEspera = () => {
  if (esperasEnCurso === 0) return
  esperasEnCurso -= 1
  if (esperasEnCurso === 0) window.dispatchEvent(new Event(EVENTO_DESPIERTO))
}

const dormir = (ms) => new Promise((listo) => setTimeout(listo, ms))

const cliente = axios.create({
  baseURL: BASE,
  // Por encima de los ~30s que espera el proxy de Vercel, a proposito. Con
  // 30 justos los dos relojes vencen a la vez y gana el nuestro: axios
  // aborta con un error de red generico y perdemos el 502, que es la unica
  // pista de que el servicio estaba arrancando y no caido.
  timeout: 35000,
  headers: { 'Content-Type': 'application/json' },
})

// El token se adjunta en un interceptor y no en cada llamada: antes cada
// metodo repetia `{ headers: authHeader() }`, y bastaba olvidarlo una vez
// para tener una ruta que fallaba con 401 sin motivo aparente.
cliente.interceptors.request.use((config) => {
  const token = leerToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/**
 * Traduce los errores de red a algo que el usuario pueda entender.
 *
 * El 429 merece trato propio: es el unico caso en que se sabe exactamente
 * cuanto hay que esperar, y decirselo al alumno evita que recargue en bucle
 * (que es justo lo que alarga el bloqueo).
 */
cliente.interceptors.response.use(
  (respuesta) => respuesta,
  async (error) => {
    const estado = error.response?.status
    const config = error.config

    // Arranque en frio: se repite la peticion en vez de darla por perdida.
    // El intento que acaba de fallar no fue en balde: desperto al servicio.
    if (config && esReintentable(error, config.revoReintentos || 0)) {
      const hechos = config.revoReintentos || 0
      config.revoReintentos = hechos + 1

      // La espera se abre y se cierra en el primer reintento de esta
      // peticion. Los siguientes vuelven a entrar aqui por recursion, y
      // contar cada uno dejaria el contador descuadrado; el `finally` de
      // este marco es el que ve terminar la cadena entera.
      const abreLaEspera = hechos === 0
      if (abreLaEspera) empezarEspera()

      await dormir(esperaAntesDeReintentar(hechos))
      try {
        return await cliente(config)
      } finally {
        if (abreLaEspera) terminarEspera()
      }
    }

    if (estado === 429) {
      const segundos = Number(error.response.headers['retry-after']) || 60
      error.mensajeUsuario = `Demasiadas peticiones. Vuelve a intentarlo en ${segundos} segundos.`
      error.reintentarEn = segundos
    } else if (estado === 401) {
      anunciarSesionCaducada()
      error.mensajeUsuario = 'Tu sesion expiro. Vuelve a entrar.'
    } else if (estado === 403) {
      error.mensajeUsuario = 'No tienes permiso para hacer esto.'
    } else if (esArranqueEnFrio(error)) {
      // Se separa del 5xx generico porque no es lo mismo: aqui no hay nada
      // roto, hay que esperar. Cae por aqui el registro y el login, que no
      // se reintentan solos por no ser idempotentes.
      error.mensajeUsuario = MENSAJE_ARRANQUE
      error.esArranqueEnFrio = true
    } else if (estado >= 500) {
      error.mensajeUsuario = 'El servicio no esta disponible ahora mismo.'
    } else if (!error.response) {
      error.mensajeUsuario = 'No hay conexion con el servidor.'
    } else {
      error.mensajeUsuario = error.response.data?.detail || 'Ocurrio un error.'
    }

    return Promise.reject(error)
  },
)

// ── Autenticacion ─────────────────────────────────────────
export const authApi = {
  register: (datos) => cliente.post('/auth/register', datos),
  login: (datos) => cliente.post('/auth/login', datos),
  me: () => cliente.get('/auth/me'),
  actualizarPerfil: (datos) => cliente.put('/auth/me', datos),
  verify: () => cliente.get('/auth/verify'),
  misConsentimientos: () => cliente.get('/auth/me/consents'),
  cambiarConsentimiento: (docType, granted) =>
    cliente.put('/auth/me/consents', { doc_type: docType, granted }),
}

// ── Documentos legales (publicos) ─────────────────────────
export const legalApi = {
  documentos: () => cliente.get('/legal/documents'),
  documento: (tipo) => cliente.get(`/legal/documents/${tipo}`),
}

// ── Cuestionario ──────────────────────────────────────────
export const surveyApi = {
  getQuestions: () => cliente.get('/questions/'),
  getSessionQuestions: (sid) => cliente.get(`/sessions/${sid}/questions`),
  getCategories: () => cliente.get('/questions/categories/list'),
  createSession: () => cliente.post('/sessions/', {}),
  saveAnswers: (sid, cuerpo) => cliente.post(`/sessions/${sid}/answers`, cuerpo),
  submitPhase: (sid) => cliente.post(`/sessions/${sid}/submit_phase`, {}),
  getHistory: () => cliente.get('/sessions/'),
  getRecommendedCourses: (specId) => cliente.get(`/courses/specialization/${specId}`),
  getRecommendedJobs: (specId) => cliente.get(`/jobs/specialization/${specId}`),
  getPsychometricQuestions: (specId) => cliente.get(`/psychometric/specialization/${specId}`),
}

// ── Modelo ────────────────────────────────────────────────
export const mlApi = {
  predict: (cuerpo) => cliente.post('/predict/', cuerpo),
  getPrediction: (id) => cliente.get(`/predict/${id}`),
  getHistory: (uid) => cliente.get(`/predict/user/${uid}/history`),
  sendFeedback: (predId, cuerpo) => cliente.post(`/predict/${predId}/feedback`, cuerpo),

  // Requieren rol admin.
  importances: () => cliente.get('/predict/model/importances'),
  treeViz: () => cliente.get('/predict/model/tree'),
  overview: () => cliente.get('/stats/overview'),
  trainingHistory: () => cliente.get('/stats/training-history'),
  retrain: () => cliente.post('/stats/train', {}),

  /**
   * Descarga el dataset.
   *
   * Antes esto devolvia una URL suelta que se ponia en un <a href>. Esa
   * peticion sale del navegador SIN la cabecera Authorization, asi que la
   * descarga siempre respondia 401: la funcion estaba rota desde el dia en
   * que la ruta paso a exigir rol admin. Ahora se pide con el cliente (que
   * si adjunta el token) y el fichero se arma en memoria.
   */
  descargarDataset: async () => {
    const { data } = await cliente.get('/stats/export-csv', { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = 'revo_dataset.csv'
    enlace.click()
    URL.revokeObjectURL(url)
  },
}

export default cliente
