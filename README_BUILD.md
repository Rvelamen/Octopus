# Octopus Desktop 构建指南

## 项目结构

```
octopus/
├── electron/           # Electron 主进程代码
│   ├── main.js         # 主进程入口（Python 生命周期管理、窗口管理）
│   └── preload.js      # 预加载脚本（IPC 安全桥接）
├── frontend/           # React 前端
│   ├── src/            # 前端源码
│   ├── dist/           # 构建输出（vite build 生成）
│   └── package.json    # 前端依赖
├── backend/            # Python 后端
│   ├── api/            # FastAPI 服务
│   ├── agent/          # Agent 核心逻辑
│   ├── channels/       # 多通道支持（9 个通道）
│   ├── core/           # 核心模块
│   ├── data/           # 数据存储（SQLite + 11 个迁移）
│   ├── extensions/     # 插件系统
│   ├── mcp/            # MCP 协议集成
│   ├── services/       # 服务层（cron/tts/workflow/knowledge/image/llm）
│   ├── tools/          # 内置工具集（12 个工具模块）
│   └── requirements.txt
├── build/              # 构建资源（图标等）
├── python-dist/        # PyInstaller 输出目录
├── build_python.py     # Python 打包脚本
└── package.json        # 根目录 Electron 配置
```

## 环境要求

| 依赖       | 版本要求     | 说明             |
| :------- | :------- | :------------- |
| Node.js  | >= 18    | 前端构建和 Electron |
| Python   | >= 3.10  | 后端运行和打包        |
| pip      | 最新       | Python 包管理     |
| npm      | >= 9     | Node 包管理       |

## 打包步骤

### 1. 安装依赖

```bash
# 在项目根目录执行
npm install
```

这会同时安装 Electron 依赖和前端依赖（通过 `postinstall` 脚本自动执行 `cd frontend && npm install`）。

### 2. 打包前端

```bash
npm run build:frontend
```

这会使用 Vite 构建前端，输出到 `frontend/dist/`。

### 3. 打包 Python 后端

```bash
npm run build:python
```

这会使用 PyInstaller 将 Python 后端打包成独立可执行文件，输出到 `python-dist/`。

**注意**：首次运行会自动安装 PyInstaller。

### 4. 完整打包

```bash
# 打包所有平台
npm run dist

# 仅 macOS
npm run dist:mac

# 仅 Windows
npm run dist:win
```

打包输出目录：`dist-electron/`

## 开发模式

```bash
# 同时启动前端开发服务器和 Electron
npm run dev
```

这会：

1. 启动 Vite 开发服务器（localhost:3000）
2. 等待前端就绪后启动 Electron
3. Electron 自动启动 Python 子进程（`python -m backend.api.server`）
4. Python 后端从端口 18791 开始自动寻找可用端口

### 开发模式架构

```
npm run dev
├── dev:frontend → Vite Dev Server (localhost:3000)
│                   └── 代理 /workspace → localhost:18791
└── dev:electron → wait-on → Electron 加载 localhost:3000
                    └── 自动启动 Python 子进程
                        └── Uvicorn + FastAPI (localhost:PORT)
```

### 单独启动

```bash
# 仅前端开发服务器
npm run dev:frontend

# 仅 Electron（需前端已启动）
npm run dev:electron
```

## NPM Scripts 完整列表

| 脚本               | 命令                                                | 说明                |
| :--------------- | :------------------------------------------------ | :---------------- |
| `dev`            | `concurrently "npm run dev:frontend" "npm run dev:electron"` | 并行启动前端和 Electron  |
| `dev:frontend`   | `cd frontend && npx vite`                          | 启动 Vite 开发服务器     |
| `dev:electron`   | `wait-on http://localhost:3000 && electron .`      | 等待前端就绪后启动 Electron |
| `build`          | `npm run build:frontend && npm run build:electron` | 构建前端 + Electron   |
| `build:frontend` | `cd frontend && npm run build`                     | 构建前端              |
| `build:python`   | `python build_python.py`                           | 打包 Python 后端      |
| `build:electron` | `electron-builder`                                 | Electron 打包       |
| `dist`           | `npm run build:frontend && npm run build:python && electron-builder` | 完整分发构建      |
| `dist:mac`       | `... && electron-builder --mac`                    | macOS 分发构建        |
| `dist:win`       | `... && electron-builder --win`                    | Windows 分发构建      |
| `postinstall`    | `cd frontend && npm install`                       | 安装后自动安装前端依赖       |

## Electron 配置详情

### 主进程（electron/main.js）

| 功能         | 说明                                      |
| :--------- | :-------------------------------------- |
| 单实例锁      | `app.requestSingleInstanceLock()` 确保唯一实例 |
| Python 生命周期 | 自动启动/停止 Python 子进程                    |
| 端口分配      | 从 18791 开始自动寻找可用端口                    |
| 启动检测      | 监听 stdout 中的 `Uvicorn running` 或 `Application startup complete` |
| 超时处理      | 10 秒超时后假定启动成功                         |

### 窗口配置

```javascript
{
  width: 1400,
  height: 900,
  minWidth: 1000,
  minHeight: 700,
  transparent: true,
  vibrancy: 'under-window',    // macOS 毛玻璃效果
  frame: false,                 // 自定义窗口框架
  titleBarStyle: 'hidden',
  webPreferences: {
    nodeIntegration: false,
    contextIsolation: true,
    preload: path.join(__dirname, 'preload.js'),
    webSecurity: false,         // 允许本地 API 跨域
    webviewTag: true            // 允许 webview 内嵌网页
  }
}
```

### IPC 通信接口

| 通道                      | 方向     | 说明        |
| :---------------------- | :----- | :-------- |
| `get-api-port`          | 渲染→主  | 获取 Python 端口 |
| `get-app-version`       | 渲染→主  | 获取应用版本    |
| `get-platform`          | 渲染→主  | 获取平台信息    |
| `window-minimize`       | 渲染→主  | 最小化窗口     |
| `window-maximize`       | 渲染→主  | 最大化/还原窗口  |
| `window-close`          | 渲染→主  | 关闭窗口      |
| `window-is-maximized`   | 渲染→主  | 查询最大化状态   |
| `backend-ready`         | 主→渲染  | Python 后端就绪 |
| `backend-error`         | 主→渲染  | Python 后端错误 |
| `window-focus-change`   | 主→渲染  | 窗口焦点变化    |
| `window-maximize-change` | 主→渲染  | 最大化状态变化   |

## electron-builder 配置

### 基本信息

| 配置项        | 值                     |
| :--------- | :-------------------- |
| appId      | `com.oopus.desktop`   |
| productName | `Octopus`           |
| 输出目录       | `dist-electron`       |
| 构建资源目录     | `build`               |

### 打包文件包含

- `frontend/dist/**/*` — 前端构建产物
- `electron/**/*` — Electron 主进程代码
- `python-dist/**/*` — Python 后端打包产物
- `node_modules/**/*` — Node 依赖

### macOS 配置

| 配置项              | 值                          |
| :--------------- | :------------------------- |
| 目标格式            | `dmg` + `zip`              |
| 架构              | `x64` + `arm64`（通用二进制）     |
| 类别              | `public.app-category.productivity` |
| hardenedRuntime  | 启用                         |
| gatekeeperAssess | 关闭                         |

### Windows 配置

| 配置项        | 值                   |
| :--------- | :------------------ |
| 目标格式      | `nsis` + `portable` |
| 架构        | `x64`               |
| NSIS 一键安装 | 关闭（允许自定义安装目录）       |

### Linux 配置

| 配置项   | 值                      |
| :---- | :--------------------- |
| 目标格式 | `AppImage` + `deb`     |
| 架构   | `x64`                  |
| 类别   | `Office`               |

## PyInstaller 配置（build_python.py）

| 配置项          | 值               |
| :------------ | :-------------- |
| 入口文件         | `backend/__main__.py` |
| 输出文件名        | `octopus-server` |
| 打包模式         | `--onefile`（单文件） |
| 控制台模式        | `--console`     |
| 输出目录         | `python-dist/`  |
| Hidden Imports | 28 个隐式导入模块      |

### Hidden Imports 列表

覆盖了 uvicorn 全套协议、fastapi、starlette、pydantic、httpx、aiohttp、requests、websockets、openai、anthropic、apscheduler、sqlalchemy、playwright、bs4、lark_oapi、yaml、loguru 等关键依赖。

## 预估包大小

| 组件                      | 大小               |
| ----------------------- | ---------------- |
| Electron 运行时            | \~180-250 MB     |
| 前端构建产物                  | \~5-15 MB        |
| Python 后端 (PyInstaller) | \~50-150 MB      |
| **总计**                  | **\~250-450 MB** |

## 常见问题

### 1. Python 打包失败

确保已安装所有 Python 依赖：

```bash
pip install -r requirements.txt
```

### 2. 前端构建失败

确保前端依赖已安装：

```bash
cd frontend && npm install
```

### 3. Electron 无法启动 Python 服务

检查日志文件：

- macOS: `~/Library/Logs/octopus-desktop/main.log`
- Windows: `%USERPROFILE%\AppData\Roaming\octopus-desktop\logs\main.log`
- Linux: `~/.config/octopus-desktop/logs/main.log`

### 4. 开发模式端口冲突

Python 后端从 18791 开始自动寻找可用端口，但 Vite 代理硬编码为 18791。如果 18791 被占用，需要先释放该端口或修改 `frontend/vite.config.js` 中的代理配置。

### 5. macOS 打包签名问题

如果没有 Apple Developer 证书，需要在 `package.json` 的 `build.mac` 中添加 `"identity": null` 以跳过签名。

## 发布

打包完成后，发布文件位于：

- macOS: `dist-electron/Octopus-1.0.0.dmg`, `dist-electron/Octopus-1.0.0-mac.zip`
- Windows: `dist-electron/Octopus Setup 1.0.0.exe`, `dist-electron/Octopus 1.0.0.exe`
- Linux: `dist-electron/Octopus-1.0.0.AppImage`, `dist-electron/octopus-desktop_1.0.0_amd64.deb`
