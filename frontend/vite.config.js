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
