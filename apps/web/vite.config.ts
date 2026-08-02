import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.CORPUS_API_URL ?? 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // /api/live/ws rides the same proxy — creds stay server-side
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
