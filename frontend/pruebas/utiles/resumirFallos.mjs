import fs from 'node:fs'

/**
 * Resume el JSON de resultados en una lista legible de fallos.
 *
 * El informe HTML de Playwright es comodo para investigar UNO, pero para ver
 * de un vistazo que se ha roto hay que abrir el navegador y pinchar. Esto
 * saca lo mismo por consola, que es lo que se pega en un ticket.
 *
 *   npm run prueba -- --reporter=json
 *   node pruebas/utiles/resumirFallos.mjs pruebas/.resultados/resultados.json
 */

const RUTA = process.argv[2] || 'pruebas/.resultados/resultados.json'

if (!fs.existsSync(RUTA)) {
  console.error(`No existe ${RUTA}. Ejecuta las pruebas con el informe JSON primero.`)
  process.exit(1)
}

const limpio = (texto) => texto.replace(/\x1b\[[0-9;]*m/g, '')
const fallos = []

const recorrer = (suites, ruta = []) => {
  for (const suite of suites) {
    const camino = [...ruta, suite.title].filter(Boolean)
    for (const spec of suite.specs || []) {
      for (const prueba of spec.tests || []) {
        for (const resultado of prueba.results || []) {
          if (resultado.status === 'passed' || resultado.status === 'skipped') continue
          const mensaje = (resultado.errors || []).map((e) => limpio(e.message || '')).join('\n')
          const cabeza = mensaje.split('\n').filter((l) => l.trim()).slice(0, 5).join('\n      ')
          fallos.push(`### ${camino.join(' > ')} > ${spec.title}\n      ${cabeza}`)
        }
      }
    }
    recorrer(suite.suites || [], camino)
  }
}

recorrer(JSON.parse(fs.readFileSync(RUTA, 'utf8')).suites)

console.log(fallos.join('\n\n'))
console.log(`\n--- ${fallos.length} fallos ---`)
