/**
 * 全局配置常量
 */

// 后端服务端口（Electron 生产环境通过环境变量注入，开发环境使用默认值）
export const BACKEND_PORT = Number(
  // @ts-expect-error —— 允许 window.electronAPI 不存在
  window.electronAPI?.getBackendPort?.() ??
    import.meta.env.VITE_BACKEND_PORT ??
    18791
);

/** WebSocket URL */
export const WS_URL = `ws://127.0.0.1:${BACKEND_PORT}/ws`;

/** HTTP API 基础地址 */
export const API_BASE = `http://localhost:${BACKEND_PORT}`;
