import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api -> the FastAPI backend so the browser only ever
// talks to a single origin (no CORS round-trips, credentials stay simple).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
