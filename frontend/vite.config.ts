import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // All /api/* requests → FastAPI backend
      // Works both in Docker (http://backend:8000) and locally (http://localhost:8000)
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
