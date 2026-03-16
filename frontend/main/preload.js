const { contextBridge } = require('electron')
const path = require('path')

// Expose a limited API to the renderer process
contextBridge.exposeInMainWorld('octopus', {
  backendUrl: 'http://127.0.0.1:18791'
})
