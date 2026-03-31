import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/auth':   { target: 'http://localhost:8011', rewrite: p => p.replace(/^\/api\/auth/, '') },
      '/api/survey': { target: 'http://localhost:8012', rewrite: p => p.replace(/^\/api\/survey/, '') },
      '/api/ml':     { target: 'http://localhost:8013', rewrite: p => p.replace(/^\/api\/ml/, '') },
    }
  }
})
