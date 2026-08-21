import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * En desarrollo, /api se reenvia a la pasarela, igual que en produccion.
 *
 * Antes habia tres reglas de proxy apuntando a tres puertos distintos
 * (8011/8012/8013), asi que el frontend hablaba directamente con cada
 * microservicio y el codigo de desarrollo no se parecia al de produccion.
 * Los fallos de enrutado solo aparecian al desplegar.
 *
 * El destino se puede cambiar con REVO_PASARELA en el .env del frontend.
 * Se lee con loadEnv y no con process.env para no depender de un global de
 * Node dentro de un fichero que tambien analiza el linter del navegador.
 */
export default defineConfig(({ mode }) => {
  const entorno = loadEnv(mode, import.meta.dirname, '')

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: entorno.REVO_PASARELA || 'http://localhost:8080',
          changeOrigin: true,
        },
      },
    },
  }
})
