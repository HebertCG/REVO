import { defineConfig, devices } from '@playwright/test'

/**
 * Pruebas E2E del frontend de REVO.
 *
 * Estas pruebas levantan Vite y simulan la API dentro de cada escenario.
 * Verifican recorridos completos del navegador, pero no la comunicacion real
 * entre microservicios. El E2E de sistema vive en pruebas/e2e/sistema.
 */

const PUERTO = Number(process.env.REVO_PUERTO_PRUEBAS) || 5173
const URL_BASE = process.env.REVO_URL_PRUEBAS || `http://localhost:${PUERTO}`
const TRABAJADORES = Number(process.env.REVO_TRABAJADORES_PRUEBAS) || (process.env.CI ? 2 : 4)
const SERVIDOR_EXTERNO = process.env.REVO_SERVIDOR_E2E_EXTERNO === '1'

export default defineConfig({
  testDir: './pruebas/e2e',
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
  },

  projects: [
    {
      name: 'escritorio',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'movil',
      use: { ...devices['Pixel 7'] },
    },
  ],

  ...(SERVIDOR_EXTERNO ? {} : {
    webServer: {
      command: 'node ./node_modules/vite/bin/vite.js --port ' + PUERTO,
      url: URL_BASE,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
  }),
})
