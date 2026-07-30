import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      // ws so the Socket.IO connection upgrades through the dev proxy
      // instead of being stuck on long-polling.
      '/socket.io': { target: 'http://localhost:5000', ws: true },
    },
  },
})
