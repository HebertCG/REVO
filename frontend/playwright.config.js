import { defineConfig, devices } from '@playwright/test'

/**
 * Configuracion de las pruebas de interfaz de REVO.
 *
 * Las pruebas levantan el servidor de Vite y hablan con una API simulada
 * (ver pruebas/utiles/apiSimulada.js). No hace falta tener los tres
 * microservicios corriendo: lo que se prueba aqui es el frontend, y una
 * bateria que solo pasa cuando el backend esta arriba no detecta fallos,
 * detecta el estado del laboratorio.
 *
 * Los proyectos separan cuatro intenciones:
 *   - `escritorio` y `movil` ejecutan las pruebas funcionales en los dos
 *     tamanos donde el diseno cambia de verdad.
 *   - `responsivo` ejecuta una sola vez la bateria que ya recorre por dentro
 *     todos los anchos; duplicarla por proyecto seria trabajo repetido.
 *   - `carga` lanza seis clientes en paralelo sobre las vistas mas pesadas.
 *   - `capturas` no afirma nada: guarda imagenes de las pantallas y vuelca el
 *     contraste real de cada elemento que incumple. Se queda fuera de la
 *     bateria porque un fichero que siempre pasa falsea el recuento.
 */

const PUERTO = Number(process.env.REVO_PUERTO_PRUEBAS) || 5173
const URL_BASE = process.env.REVO_URL_PRUEBAS || `http://localhost:${PUERTO}`
const TRABAJADORES = Number(process.env.REVO_TRABAJADORES_PRUEBAS) || (process.env.CI ? 2 : 4)

// Solo las pruebas que dependen del tamano de pantalla se repiten en movil.
const FUNCIONALES_EN_MOVIL = [
  'navegacion.spec.js',
  'autenticacion.spec.js',
  'panel.spec.js',
  'cuestionario.spec.js',
]

export default defineConfig({
  testDir: './pruebas',
  outputDir: './pruebas/.resultados',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: TRABAJADORES,
  timeout: 45_000,
  expect: { timeout: 7_000 },

  reporter: [
    ['list'],
    ['html', { outputFolder: './pruebas/.informe', open: 'never' }],
    ['json', { outputFile: './pruebas/.resultados/resultados.json' }],
  ],

  use: {
    baseURL: URL_BASE,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'es-PE',
    timezoneId: 'America/Lima',
    // La preferencia de movimiento reducido NO se declara aqui: en esta
    // version de Playwright la opcion no llega al navegador. Se emula en el
    // fixture `movimientoReducido` de pruebas/utiles/fixtures.js, que si
    // funciona y ademas se puede comprobar.
  },

  projects: [
    {
      name: 'escritorio',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
      testIgnore: ['responsividad.spec.js', 'carga.spec.js', 'capturas.spec.js', 'contraste.diagnostico.spec.js'],
    },
    {
      name: 'movil',
      use: { ...devices['Pixel 7'] },
      testMatch: FUNCIONALES_EN_MOVIL,
    },
    {
      name: 'responsivo',
      use: { ...devices['Desktop Chrome'] },
      testMatch: ['responsividad.spec.js'],
    },
    {
      name: 'carga',
      use: { ...devices['Desktop Chrome'] },
      testMatch: ['carga.spec.js'],
    },
    {
      name: 'capturas',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
      testMatch: ['capturas.spec.js', 'contraste.diagnostico.spec.js'],
    },
  ],

  webServer: {
    command: 'node ./node_modules/vite/bin/vite.js --port ' + PUERTO,
    url: URL_BASE,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
