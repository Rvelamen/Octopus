const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const log = require('electron-log');

// 配置日志
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

let mainWindow = null;
let pythonProcess = null;
let pythonPort = null;

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
    // 先启动Python服务
    const port = await startPythonService();
    log.info(`Python service running on port ${port}`);
    
    mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1000,
      minHeight: 700,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js'),
        webSecurity: false, // 允许跨域请求到本地API
      },
      titleBarStyle: 'hiddenInset', // macOS风格
      show: false, // 先不显示，等加载完成
    });
    
    // 设置API端口
    mainWindow.webContents.on('dom-ready', () => {
      mainWindow.webContents.send('api-port', port);
    });
    
    const isDev = !app.isPackaged;
    
    if (isDev) {
      // 开发模式：加载Vite开发服务器
      mainWindow.loadURL('http://localhost:3000');
      mainWindow.webContents.openDevTools();
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
    
  } catch (error) {
    log.error('Failed to create window:', error);
    
    // 显示错误对话框
    const { dialog } = require('electron');
    dialog.showErrorBox('启动错误', `无法启动Octopus服务:\n${error.message}`);
    
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
