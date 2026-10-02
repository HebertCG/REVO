/**
 * Ejecuta Playwright con Vite dentro del mismo proceso coordinador.
 *
 * En Windows, el `webServer.command` de Playwright queda detras de cmd.exe y
 * algunas versiones no consiguen cerrar el proceso hijo de Vite al terminar.
 * Arrancarlo mediante la API de Vite permite cerrarlo siempre en `finally`.
 */
import { spawn } from 'node:child_process'
import process from 'node:process'

import { createServer } from 'vite'


const puerto = Number(process.env.REVO_PUERTO_PRUEBAS) || 5173
const urlBase = process.env.REVO_URL_PRUEBAS || `http://localhost:${puerto}`
const argumentos = process.argv.slice(2)

const servidor = await createServer({
  server: { host: '127.0.0.1', port: puerto, strictPort: true },
  logLevel: 'warn',
})

let codigo = 1

try {
  await servidor.listen()

  codigo = await new Promise((resolve, reject) => {
    const playwright = spawn(
      process.execPath,
      ['./node_modules/@playwright/test/cli.js', 'test', ...argumentos],
      {
        cwd: process.cwd(),
        env: {
          ...process.env,
          REVO_SERVIDOR_E2E_EXTERNO: '1',
          REVO_URL_PRUEBAS: urlBase,
        },
        shell: false,
        stdio: 'inherit',
      },
    )

    playwright.once('error', reject)
    playwright.once('exit', (resultado) => resolve(resultado ?? 1))
  })
} finally {
  await servidor.close()
}

process.exitCode = codigo
