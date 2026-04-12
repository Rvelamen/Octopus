import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Relative paths for Electron
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@contexts': path.resolve(__dirname, './src/contexts'),
      '@assets': path.resolve(__dirname, './src/assets'),
      '@services': path.resolve(__dirname, './src/services'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/workspace': {
        target: 'http://localhost:18791',
        changeOrigin: true,
        bypass: (req) => {
          // 如果是页面刷新请求（Accept 包含 text/html），不代理，让 Vite 返回 index.html
          if (req.headers.accept && req.headers.accept.includes('text/html')) {
            return req.url;
          }
        },
      },
      '/wechat_qrcodes': {
        target: 'http://localhost:18791',
        changeOrigin: true,
      },
    },
  },
})
