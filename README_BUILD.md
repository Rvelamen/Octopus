# Octopus Desktop 打包指南

## 项目结构

```
octopus/
├── electron/           # Electron 主进程代码
│   ├── main.js        # 主进程入口
│   └── preload.js     # 预加载脚本
├── frontend/          # React 前端
│   ├── src/          # 前端源码
│   ├── dist/         # 构建输出 (vite build 生成)
│   └── package.json  # 前端依赖
├── backend/          # Python 后端
├── python-dist/       # PyInstaller 输出目录
├── package.json       # 根目录 Electron 配置
└── build_python.py    # Python 打包脚本
```

## 打包步骤

### 1. 安装依赖

```bash
# 在项目根目录执行
npm install
```

这会同时安装 Electron 依赖和前端依赖。

### T2. 打包前端

```bash
npm run build:frontend
```

这会使用 Vite 构建前端，输出到 `frontend/dist/`。

### 3. 打包 Python 后端

```bash
npm run build:python
```

这会使用 PyInstaller 将 Python 后端打包成独立可执行文件，输出到 `python-dist/`。

**注意**: 首次运行会自动安装 PyInstaller。

### 4. 完整打包

```bash
# 打包所有平台
npm run dist

# 仅 macOS
npm run dist:mac

# 仅 Windows
npm run dist:win
```

打包输出目录: `dist-electron/`

## 预估包大小

| 组件                      | 大小               |
| ----------------------- | ---------------- |
| Electron 运行时            | \~180-250 MB     |
| 前端构建产物                  | \~5-15 MB        |
| Python 后端 (PyInstaller) | \~50-150 MB      |
| **总计**                  | **\~250-450 MB** |

## 开发模式

```bash
# 同时启动前端开发服务器和 Electron
npm run dev
```

这会:

1. 启动 Vite 开发服务器 (localhost:3000)
2. 启动 Electron 并加载开发服务器

## 常见问题

### 1. Python 打包失败

确保已安装所有 Python 依赖:

```bash
pip install -r requirements.txt
```

### 2. 前端构建失败

确保前端依赖已安装:

```bash
cd frontend && npm install
```

### 3. Electron 无法启动 Python 服务

检查日志文件:

- macOS: `~/Library/Logs/octopus-desktop/main.log`
- Windows: `%USERPROFILE%\AppData\Roaming\octopus-desktop\logs\main.log`
- Linux: `~/.config/octopus-desktop/logs/main.log`

## 配置说明

### Electron 配置 (package.json)

- `main`: Electron 主进程入口
- `build.files`: 包含在应用包中的文件
- `build.extraResources`: 额外资源文件 (Python 可执行文件)
- `build.mac/target`: macOS 打包格式 (dmg, zip)
- `build.win/target`: Windows 打包格式 (nsis, portable)

### PyInstaller 配置 (build\_python.py)

- `--onefile`: 打包成单个可执行文件
- `--hidden-import`: 隐式导入的模块
- `--add-data`: 包含的数据文件

## 发布

打包完成后，发布文件位于:

- macOS: `dist-electron/Octopus-1.0.0.dmg`, `dist-electron/Octopus-1.0.0-mac.zip`
- Windows: `dist-electron/Octopus Setup 1.0.0.exe`, `dist-electron/Octopus 1.0.0.exe`

