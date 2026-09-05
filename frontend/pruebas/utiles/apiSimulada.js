import * as datos from './datos.js'

/**
 * Interceptor de red para las pruebas de interfaz.
 *
 * Todo lo que sale del navegador hacia /api o hacia terceros se responde
 * aqui. Dos razones:
 *
 *   1. Una prueba que necesita los tres microservicios arriba no falla
 *      cuando el frontend se rompe, falla cuando alguien apago Docker.
 *   2. Los casos que interesan (429, 500, sin conexion, respuesta lenta)
 *      no se pueden provocar contra un backend real sin romperlo.
 *
 * El interceptor responde 404 a lo que no reconoce y lo apunta en
 * `noReconocidas`, para que una ruta nueva sin simular se note en vez de
 * quedarse colgada hasta el tiempo limite.
 */

const json = (route, cuerpo, status = 200, headers = {}) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*', ...headers },
    body: JSON.stringify(cuerpo),
  })

/** Rutas por defecto: el camino feliz de un alumno con historial. */
function tablaPorDefecto(estado) {
  return [
    // -- auth ------------------------------------------------
    [/\/api\/auth\/me\/consents$/, 'GET', (r) => json(r, [
      { doc_type: 'terms', doc_version: '1.0', granted: true, granted_at: '2026-03-01T10:00:00' },
      { doc_type: 'data_commercial', doc_version: '1.0', granted: false, granted_at: null },
    ])],
    [/\/api\/auth\/me$/, 'GET', (r) => json(r, estado.usuario)],
    [/\/api\/auth\/me$/, 'PUT', (r) => json(r, estado.usuario)],
    [/\/api\/auth\/verify$/, 'GET', (r) => json(r, { valid: true })],
    [/\/api\/auth\/login$/, 'POST', (r) => json(r, { ...datos.SESION_TOKEN, user: estado.usuario })],
    [/\/api\/auth\/register$/, 'POST', (r) => json(r, { ...datos.SESION_TOKEN, user: estado.usuario })],

    // -- legal -----------------------------------------------
    [/\/api\/legal\/documents\/(\w+)$/, 'GET', (r, m) => json(r, datos.DOCUMENTO_COMPLETO(m[1]))],
    [/\/api\/legal\/documents$/, 'GET', (r) => json(r, datos.DOCUMENTOS_LEGALES)],

    // -- cuestionario ----------------------------------------
    [/\/api\/sessions\/\d+\/questions$/, 'GET', (r) => json(r, estado.preguntas)],
    [/\/api\/sessions\/\d+\/answers$/, 'POST', (r) => json(r, { saved: true })],
    [/\/api\/sessions\/\d+\/submit_phase$/, 'POST', (r) => json(r, estado.submitPhase())],
    [/\/api\/sessions\/?$/, 'POST', (r) => json(r, datos.SESION_CUESTIONARIO)],
    [/\/api\/sessions\/?$/, 'GET', (r) => json(r, [datos.SESION_CUESTIONARIO])],
    [/\/api\/questions\/categories\/list$/, 'GET', (r) => json(r, ['programming', 'data', 'infra'])],
    [/\/api\/questions\/?$/, 'GET', (r) => json(r, datos.PREGUNTAS_FASE1)],
    [/\/api\/psychometric\/specialization\/\d+$/, 'GET', (r) => json(r, datos.PREGUNTAS_PSICOMETRICAS)],
    [/\/api\/courses\/specialization\/\d+$/, 'GET', (r) => json(r, datos.CURSOS)],
    [/\/api\/jobs\/specialization\/\d+$/, 'GET', (r) => json(r, [])],

    // -- modelo ----------------------------------------------
    [/\/api\/predict\/user\/\d+\/history$/, 'GET', (r) => json(r, estado.historial)],
    [/\/api\/predict\/model\/importances$/, 'GET', (r) => json(r, datos.IMPORTANCIAS)],
    [/\/api\/predict\/model\/tree$/, 'GET', (r) => json(r, { nodes: [], depth: 8 })],
    [/\/api\/predict\/\d+\/feedback$/, 'POST', (r) => json(r, { ok: true })],
    [/\/api\/predict\/\d+$/, 'GET', (r) => json(r, estado.prediccion)],
    [/\/api\/predict\/?$/, 'POST', (r) => json(r, datos.PREDICCION)],

    // -- estadisticas (admin) --------------------------------
    [/\/api\/stats\/overview$/, 'GET', (r) => json(r, datos.RESUMEN_ADMIN)],
    [/\/api\/stats\/training-history$/, 'GET', (r) => json(r, datos.HISTORIAL_ENTRENAMIENTO)],
    [/\/api\/stats\/train$/, 'POST', (r) => json(r, {
      model_version: '1.5.0', accuracy: 0.92, precision: 0.9, recall: 0.9, f1: 0.91,
      baseline_accuracy: 0.61, lift_over_baseline: 0.31,
      training_samples: 5500, test_samples: 1100, tree_depth: 8, n_leaves: 24,
    })],
    [/\/api\/stats\/export-csv$/, 'GET', (r) => r.fulfill({
      status: 200,
      contentType: 'text/csv',
      body: 'aff_1,aff_2,label\n0.8,0.2,2\n',
    })],
  ]
}

/**
 * Instala el interceptor en una pagina.
 *
 * @param {import('@playwright/test').Page} page
 * @param {object} [opciones]
 * @param {object} [opciones.usuario]    usuario devuelto por /auth/me
 * @param {Array}  [opciones.historial]  respuesta de /predict/user/N/history
 * @param {Array}  [opciones.preguntas]  respuesta de /sessions/N/questions
 * @param {object} [opciones.prediccion] respuesta de /predict/N
 * @param {Array}  [opciones.reglas]     reglas con prioridad sobre las de serie
 * @param {number} [opciones.retardoMs]  retardo artificial en cada respuesta
 */
export async function instalarApiSimulada(page, opciones = {}) {
  const origenBase = new URL(
    process.env.REVO_URL_PRUEBAS || `http://localhost:${process.env.REVO_PUERTO_PRUEBAS || 5173}`,
  ).origin

  const estado = {
    usuario: opciones.usuario ?? datos.USUARIO,
    historial: opciones.historial ?? datos.HISTORIAL,
    preguntas: opciones.preguntas ?? datos.PREGUNTAS_FASE1,
    prediccion: opciones.prediccion ?? datos.PREDICCION,
    // El envio de fase devuelve algo distinto en fase 1 (pasa a fase 2) que
    // en fase 2 (ya hay prediccion). Se lleva la cuenta aqui.
    faseEnviada: 0,
    submitPhase() {
      this.faseEnviada += 1
      if (this.faseEnviada === 1) return { next_phase: 2 }
      return {
        prediction_id: datos.PREDICCION.prediction_id,
        primary_specialization: datos.PREDICCION.primary_specialization,
        primary_specialization_id: datos.PREDICCION.primary_specialization_id,
      }
    },
  }

  const registro = { llamadas: [], noReconocidas: [] }
  const tabla = [...(opciones.reglas || []), ...tablaPorDefecto(estado)]

  // Terceros: Remotive se consulta desde la pagina de resultados. Sin
  // simularlo la prueba depende de una API publica ajena.
  await page.route(/remotive\.com/, (route) => json(route, {
    jobs: [{
      id: 1,
      title: 'Data Analyst',
      company_name: 'Acme',
      url: 'https://example.org/e1',
      candidate_required_location: 'Remoto',
      publication_date: '2026-08-20',
    }],
  }))

  // Se filtra por origen y no solo por ruta. La API publica de empleos que
  // consulta la pantalla de resultado tambien vive bajo /api/ en SU dominio,
  // asi que un patron por ruta se la traga y le responde un 404 nuestro.
  const esNuestraApi = (url) => url.pathname.startsWith('/api/') && url.origin === origenBase

  await page.route((url) => esNuestraApi(url), async (route, request) => {
    const url = new URL(request.url())
    const metodo = request.method()
    registro.llamadas.push({ metodo, ruta: url.pathname })

    if (opciones.retardoMs) await new Promise((r) => setTimeout(r, opciones.retardoMs))

    for (const [patron, metodoEsperado, manejador] of tabla) {
      const coincide = patron.exec(url.pathname)
      if (coincide && metodoEsperado === metodo) return manejador(route, coincide, request)
    }

    registro.noReconocidas.push(`${metodo} ${url.pathname}`)
    return json(route, { detail: `Ruta no simulada: ${metodo} ${url.pathname}` }, 404)
  })

  return { estado, registro }
}

/** Deja la sesion iniciada antes de que arranque React. */
export async function iniciarSesion(page) {
  // `addInitScript` corre en CADA carga de documento, no solo en la primera.
  // Sin el centinela, cerrar sesion y volver a una ruta privada devolvia la
  // sesion por la puerta de atras: el guion reescribia el token antes de que
  // arrancara la aplicacion. Eso hacia imposible de cumplir la ultima
  // afirmacion de "salir borra la sesion y devuelve a la portada", que es
  // justamente la que comprueba que no se puede volver atras.
  //
  // El centinela vive en sessionStorage, que sobrevive a las navegaciones de
  // la misma pestana y muere con el contexto de cada prueba.
  await page.addInitScript((token) => {
    if (sessionStorage.getItem('revo_sesion_sembrada')) return
    sessionStorage.setItem('revo_sesion_sembrada', '1')
    sessionStorage.setItem('revo_token', token)
  }, datos.TOKEN)
}

/** Regla que responde un error HTTP concreto. */
export const reglaError = (patron, metodo, status, cuerpo = {}, headers = {}) => [
  patron,
  metodo,
  (route) => route.fulfill({
    status,
    contentType: 'application/json',
    headers,
    body: JSON.stringify(cuerpo),
  }),
]

/** Regla que corta la conexion, como si no hubiera red. */
export const reglaSinRed = (patron, metodo) => [
  patron,
  metodo,
  (route) => route.abort('connectionfailed'),
]
