const { contextBridge, ipcRenderer } = require('electron');

// 暴露安全的API给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取API端口
  getApiPort: () => ipcRenderer.invoke('get-api-port'),

  // 获取应用版本
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),

  // 获取平台信息
  getPlatform: () => ipcRenderer.invoke('get-platform'),

  // 监听API端口事件
  onApiPort: (callback) => {
    ipcRenderer.on('api-port', (event, port) => callback(port));
  },

  // 移除监听器
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  },

  // 窗口控制 API
  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),
  windowIsMaximized: () => ipcRenderer.invoke('window-is-maximized'),

  // 监听窗口焦点变化
  onWindowFocusChange: (callback) => {
    ipcRenderer.on('window-focus-change', (event, isFocused) => callback(isFocused));
  },

  // 监听窗口最大化状态变化
  onWindowMaximizeChange: (callback) => {
    ipcRenderer.invoke('on-window-maximize-change').then(() => {
      ipcRenderer.on('window-maximize-change', (event, isMaximized) => callback(isMaximized));
    });
  },

  // 清除所有窗口相关监听器
  removeWindowListeners: () => {
    ipcRenderer.removeAllListeners('window-focus-change');
    ipcRenderer.removeAllListeners('window-maximize-change');
  },
});
