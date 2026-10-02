import axios from 'axios'

import {
  ESPERA_MS,
  MENSAJE_NO_DISPONIBLE,
  esFalloPasajero,
  esReintentable,
} from './reintentos.js'

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
const BASE = import.meta.env?.VITE_API_URL || '/api'

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

// Aqui vivia el aviso de "servicio dormido": dos eventos de ventana, un
// contador de esperas en curso y un `hayEsperaEnCurso()` para las pantallas
// que montaban tarde. Todo eso existia para pintar el cartel de
// "Despertando el servidor" mientras Render levantaba un contenedor
// dormido. En un VPS los servicios no se duermen, asi que el cartel no
// tenia nada que anunciar y solo servia para asustar.

const dormir = (ms) => new Promise((listo) => setTimeout(listo, ms))

const cliente = axios.create({
  baseURL: BASE,
  // 15s. Antes eran 35, elegidos para quedar por encima de los ~30 que
  // esperaba el proxy de Vercel delante de Render. Sin ese proxy y sin
  // arranques en frio, una peticion que tarda mas de 15 segundos no esta
  // arrancando: esta rota, y conviene decirlo pronto.
  timeout: 15000,
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
    const esPeticionDeAcceso = config?.url === '/auth/login' || config?.url === '/auth/register'

    // Corte pasajero (un contenedor reiniciandose): se repite UNA vez tras
    // una espera corta. No se avisa al usuario porque no le da tiempo a
    // notarlo, y un cartel para 1,2 segundos preocupa mas de lo que informa.
    if (config && esReintentable(error, config.revoReintentos || 0)) {
      config.revoReintentos = (config.revoReintentos || 0) + 1
      await dormir(ESPERA_MS)
      return cliente(config)
    }

    if (estado === 429) {
      const segundos = Number(error.response.headers['retry-after']) || 60
      error.mensajeUsuario = `Demasiadas peticiones. Vuelve a intentarlo en ${segundos} segundos.`
      error.reintentarEn = segundos
    } else if (estado === 401 && !esPeticionDeAcceso) {
      anunciarSesionCaducada()
      error.mensajeUsuario = 'Tu sesion expiro. Vuelve a entrar.'
    } else if (estado === 401) {
      error.mensajeUsuario = error.response.data?.detail || 'Credenciales incorrectas.'
    } else if (estado === 403) {
      error.mensajeUsuario = 'No tienes permiso para hacer esto.'
    } else if (esFalloPasajero(error)) {
      // Se separa del 5xx generico porque la accion del usuario es distinta:
      // aqui tiene sentido volver a intentarlo en unos segundos. Cae por
      // aqui el registro y el login, que no se reintentan solos por no ser
      // idempotentes.
      error.mensajeUsuario = MENSAJE_NO_DISPONIBLE
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

// Aqui vivian `despertarAutenticacion`, `despertarCuestionario` y
// `despertarServicios`: tres peticiones de mentira que se lanzaban al abrir
// la aplicacion contra la ruta publica mas barata de cada servicio, solo
// para que Render los fuera levantando mientras el alumno tecleaba.
//
// En un VPS los tres estan siempre en pie, asi que eran tres peticiones por
// carga que no pedian nada que nadie fuera a usar. Se retiran.

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
  // getRecommendedJobs se retiro: estaba declarado y no lo llamaba nadie.
  // Results.jsx consulta la API de Remotive en tiempo real, y la tabla
  // `jobs` que servia esta ruta se elimino en la migracion 20.
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
  resumenModelo: () => cliente.get('/predict/model/resumen'),
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
