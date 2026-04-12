const { app, BrowserWindow, ipcMain, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const log = require('electron-log');

const isDev = !app.isPackaged;

function getIconPath(size) {
  const sizeMap = {
    16: 'icon_16x16.png',
    32: 'icon_32x32.png',
    64: 'icon_64x64.png',
    128: 'icon_128x128.png',
    256: 'icon_256x256.png',
    512: 'icon_512x512.png',
    1024: 'icon_1024x1024.png',
  };
  
  const filename = sizeMap[size] || 'icon.png';
  return isDev
    ? path.join(__dirname, '..', 'build', filename)
    : path.join(process.resourcesPath, 'build', filename);
}

function createAppIcon() {
  const icon = nativeImage.createEmpty();
  
  const sizes = [16, 32, 64, 128, 256, 512, 1024];
  
  sizes.forEach(size => {
    const iconPath = getIconPath(size);
    if (fs.existsSync(iconPath)) {
      const sizeIcon = nativeImage.createFromPath(iconPath);
      if (process.platform === 'darwin') {
        icon.addRepresentation({
          scaleFactor: size / 128,
          width: size,
          height: size,
          buffer: sizeIcon.toBitmap()
        });
      }
    }
  });
  
  if (process.platform === 'darwin') {
    return icon;
  } else {
    return nativeImage.createFromPath(getIconPath(256));
  }
}

if (isDev && fs.existsSync(getIconPath(512))) {
  app.setAboutPanelOptions({
    applicationName: 'Octopus',
    applicationIconPath: getIconPath(512),
  });
}

// 配置日志
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

let mainWindow = null;
let pythonProcess = null;
let pythonPort = null;

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  log.info('Another instance is already running, quitting...');
  app.quit();
} else {
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// 获取Python可执行文件路径
function getPythonExecutablePath() {
  const isDev = !app.isPackaged;
  
  if (isDev) {
    // 开发模式：使用系统Python
    return 'python';
  } else {
    // 生产模式：使用打包后的Python
    const platform = process.platform;
    let pythonPath;
    
    if (platform === 'darwin') {
      // macOS
      pythonPath = path.join(process.resourcesPath, 'python-dist', 'octopus-server');
    } else if (platform === 'win32') {
      // Windows
      pythonPath = path.join(process.resourcesPath, 'python-dist', 'octopus-server.exe');
    } else {
      // Linux
      pythonPath = path.join(process.resourcesPath, 'python-dist', 'octopus-server');
    }
    
    log.info('Python executable path:', pythonPath);
    return pythonPath;
  }
}

// 查找可用端口
async function findAvailablePort(startPort = 18791) {
  const net = require('net');
  
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(startPort, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => {
        resolve(port);
      });
    });
    server.on('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        findAvailablePort(startPort + 1).then(resolve).catch(reject);
      } else {
        reject(err);
      }
    });
  });
}

// 启动Python后端服务
async function startPythonService() {
  return new Promise(async (resolve, reject) => {
    try {
      pythonPort = await findAvailablePort();
      log.info(`Starting Python service on port ${pythonPort}...`);
      
      const pythonExecutable = getPythonExecutablePath();
      const isDev = !app.isPackaged;
      
      let spawnArgs = [];
      let spawnOptions = {
        env: {
          ...process.env,
          OCTOPUS_PORT: pythonPort.toString(),
        },
        stdio: ['pipe', 'pipe', 'pipe'],
      };
      
      if (isDev) {
        // 开发模式：直接运行Python模块
        spawnArgs = ['-m', 'backend.api.server'];
        spawnOptions.cwd = path.join(__dirname, '..');
        spawnOptions.env.PYTHONPATH = path.join(__dirname, '..');
      }
      
      log.info('Spawning Python process:', pythonExecutable, spawnArgs);
      pythonProcess = spawn(pythonExecutable, spawnArgs, spawnOptions);
      
      let stdout = '';
      let stderr = '';
      
      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
        log.info('[Python stdout]:', data.toString());
        
        // 检查服务是否启动成功
        if (data.toString().includes('Uvicorn running') || 
            data.toString().includes('Application startup complete')) {
          log.info('Python service started successfully');
          resolve(pythonPort);
        }
      });
      
      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
        log.error('[Python stderr]:', data.toString());
      });
      
      pythonProcess.on('error', (error) => {
        log.error('Failed to start Python process:', error);
        reject(error);
      });
      
      pythonProcess.on('exit', (code) => {
        log.info(`Python process exited with code ${code}`);
        if (code !== 0 && code !== null) {
          reject(new Error(`Python process exited with code ${code}. stderr: ${stderr}`));
        }
      });
      
      // 超时处理
      setTimeout(() => {
        if (pythonProcess && !pythonProcess.killed) {
          log.info('Python service startup timeout check - assuming started');
          resolve(pythonPort);
        }
      }, 10000);
      
    } catch (error) {
      log.error('Error starting Python service:', error);
      reject(error);
    }
  });
}

// 停止Python服务
function stopPythonService() {
  return new Promise((resolve) => {
    if (pythonProcess && !pythonProcess.killed) {
      log.info('Stopping Python service...');
      
      // 尝试优雅关闭
      if (process.platform === 'win32') {
        pythonProcess.kill('SIGTERM');
      } else {
        pythonProcess.kill('SIGTERM');
      }
      
      // 强制关闭超时处理
      setTimeout(() => {
        if (pythonProcess && !pythonProcess.killed) {
          log.warn('Force killing Python process');
          pythonProcess.kill('SIGKILL');
        }
        resolve();
      }, 5000);
    } else {
      resolve();
    }
  });
}

// 创建主窗口
async function createWindow() {
  try {
    // 设置 macOS Dock 图标 (1024x1024 - App Store、Finder 详情)
    if (process.platform === 'darwin') {
      const dockIconPath = getIconPath(1024);
      log.info('Setting dock icon from:', dockIconPath);
      log.info('Icon exists:', fs.existsSync(dockIconPath));
      if (fs.existsSync(dockIconPath)) {
        app.dock.setIcon(dockIconPath);
        log.info('Dock icon set successfully');
      }
    }

    // 创建应用图标
    const appIcon = createAppIcon();

    mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1000,
      minHeight: 700,
      icon: appIcon,
      transparent: true,
      vibrancy: 'under-window',
      visualEffectState: 'active',
      frame: false, // 使用自定义窗口框架以支持失焦时保持交通灯可见
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js'),
        webSecurity: false, // 允许跨域请求到本地API
      },
      titleBarStyle: 'hidden', // 隐藏原生标题栏
      show: false, // 先不显示，等加载完成
    });

    // 监听窗口焦点状态变化，通知渲染进程
    mainWindow.on('focus', () => {
      mainWindow.webContents.send('window-focus-change', true);
    });

    mainWindow.on('blur', () => {
      mainWindow.webContents.send('window-focus-change', false);
    });
    
    const isDev = !app.isPackaged;
    
    if (isDev) {
      // 开发模式：加载Vite开发服务器
      mainWindow.loadURL('http://localhost:3000');
    } else {
      // 生产模式：加载打包后的文件
      const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
      log.info('Loading production build from:', indexPath);
      
      if (!fs.existsSync(indexPath)) {
        log.error('Production build not found at:', indexPath);
        throw new Error('Production build not found. Please run npm run build:frontend first.');
      }
      
      mainWindow.loadFile(indexPath);
    }
    
    // 窗口加载完成后显示
    mainWindow.once('ready-to-show', () => {
      mainWindow.show();
      
      if (isDev) {
        mainWindow.webContents.openDevTools();
      }
    });
    
    mainWindow.on('closed', () => {
      mainWindow = null;
    });
    
    // 异步启动Python服务（不阻塞窗口显示）
    startPythonService().then((port) => {
      log.info(`Python service running on port ${port}`);
      // 通知前端服务已启动
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-ready', port);
      }
    }).catch((error) => {
      log.error('Failed to start Python service:', error);
      // 通知前端服务启动失败
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-error', error.message);
      }
    });
    
  } catch (error) {
    log.error('Failed to create window:', error);
    
    // 显示错误对话框
    const { dialog } = require('electron');
    dialog.showErrorBox('启动错误', `无法启动Octopus:\n${error.message}`);
    
    app.quit();
  }
}

// IPC通信处理
ipcMain.handle('get-api-port', () => {
  return pythonPort;
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-platform', () => {
  return process.platform;
});

// 窗口控制 IPC 处理
ipcMain.handle('window-minimize', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('window-close', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.handle('window-is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

// 监听窗口最大化状态变化
ipcMain.handle('on-window-maximize-change', (event) => {
  if (mainWindow) {
    mainWindow.on('maximize', () => {
      event.sender.send('window-maximize-change', true);
    });
    mainWindow.on('unmaximize', () => {
      event.sender.send('window-maximize-change', false);
    });
  }
});

// 应用生命周期
app.whenReady().then(createWindow);

app.on('window-all-closed', async () => {
  await stopPythonService();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', async (event) => {
  event.preventDefault();
  await stopPythonService();
  app.exit(0);
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
  log.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled rejection at:', promise, 'reason:', reason);
});
