import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Relative paths for Electron
  server: {
    port: 3000,
    proxy: {
      '/workspace': {
        target: 'http://localhost:18791',
        changeOrigin: true,
      },
    },
  },
})
