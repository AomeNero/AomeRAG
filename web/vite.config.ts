import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend API base (the FastAPI app). In dev, Vite proxies these prefixes so the browser
// stays same-origin (no CORS); in prod, `npm run build` output is served by FastAPI.
const BACKEND = 'http://localhost:8000'
const API_PREFIXES = ['/chat', '/sessions', '/ingest', '/health', '/readyz', '/stats', '/clean', '/admin', '/feedback', '/images']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [p, { target: BACKEND, changeOrigin: true }]),
    ),
  },
})
