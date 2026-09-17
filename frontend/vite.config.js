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
  build: {
    // 大包拆分：把框架、UI 库、重渲染库分到独立 chunk，
    // 让首屏只加载核心代码，重库（monaco/mdxeditor/pixi 等）按需懒加载。
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          // React 核心 + 路由
          if (/node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/.test(id)) {
            return 'vendor-react';
          }
          // 代码编辑器（最重，独立 chunk）
          if (id.includes('monaco-editor') || id.includes('@monaco-editor')) {
            return 'vendor-monaco';
          }
          // Markdown 编辑器
          if (id.includes('@mdxeditor') || id.includes('mdxeditor')) {
            return 'vendor-mdxeditor';
          }
          // 图形/可视化库
          if (/(pixi|@pixi|markmap|mermaid|react-pdf|pdfjs-dist|xlsx)/.test(id)) {
            return 'vendor-viz';
          }
          // markdown 渲染栈
          if (/(react-markdown|remark|rehype|katex|micromark|mdast|hast|unist|unified|vfile)/.test(id)) {
            return 'vendor-markdown';
          }
          // 其余第三方依赖归到一个公共 vendor
          return 'vendor-misc';
        },
      },
    },
  },
  server: {
    port: 3007,
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
