const { app, BrowserWindow } = require('electron')
const path = require('path')

// 强制走最快的 GPU 路径:
//  - ignore-gpu-blocklist:跳过 Chromium 的"黑名单 GPU"判定(老 AMD/Intel 集显有时被误判,
//    会让 WebGL 走 SwiftShader 软渲染,直接掉到 5~10 fps)
//  - enable-gpu-rasterization:合成层走 GPU 而不是 CPU
//  - enable-features=Vulkan,UseSkiaRenderer:把 GL 后端切到 ANGLE/Vulkan,Skia 接管 2D
// 必须在 app.whenReady() 之前调用,否则 commandLine 开关不生效
app.commandLine.appendSwitch('ignore-gpu-blocklist')
app.commandLine.appendSwitch('enable-gpu-rasterization')
app.commandLine.appendSwitch('enable-features', 'Vulkan,UseSkiaRenderer')
// WebGPU 实验性开关(目前我们不用,但加上后用户将来想切到 WebGPU 时不用再发版)
app.commandLine.appendSwitch('enable-unsafe-webgpu')

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      // 强制使用独立 GPU 进程渲染主页面(Electron 28+ 默认开启,显式写更稳)
      backgroundThrottling: false,
    }
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  if (!app.isPackaged) {
    win.webContents.openDevTools()
  }
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})