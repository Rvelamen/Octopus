<div align="center">
  <img src="./backend/templates/workspace/avatars/octopus.png" alt="Octopus Logo" width="200" />

  <h1>
    <img src="https://img.shields.io/badge/🐙Octopus·章鱼哥-FF6B35?style=for-the-badge&labelColor=1a1a2e" alt="Octopus·章鱼哥" />
  </h1>

  <p>
    <strong style="font-size: 1.2em; color: #FF6B35;">AI Agent 桌面框架 · 多触手高效协作</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/version-1.0.0-FF6B35?style=flat-square&logo=github" alt="Version" />
    <img src="https://img.shields.io/badge/license-MIT-4ECDC4?style=flat-square" alt="License" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-45B7D1?style=flat-square" alt="Platform" />
  </p>

  <p>
    <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Electron-28-47848F?style=flat-square&logo=electron&logoColor=white" alt="Electron" />
    <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  </p>
</div>

***

<div align="center">
  <h3>🌟 像章鱼一样，同时处理多件事 🌟</h3>
</div>

## 🎬 演示视频

<div align="center">

### 文本转语音演示
https://github.com/user-attachments/assets/ef0af274-e988-436f-a7da-a007e1a814ee

### 微信通道演示
https://github.com/user-attachments/assets/1de4e3d3-3397-46f8-a6b5-8f9dfef2b580

</div>

***

## ✨ 核心特性

<table align="center">
<tr>
<td align="center" width="260px">

**🚀 一键部署**
*无需服务器、无需 YAML*

⚡ 双击安装运行
🐍 内置 Python 环境
💾 U 盘便携模式
🔒 数据本地保存

</td>
<td align="center" width="260px">

**💰 成本透明**
*每一分花费都心中有数*

📊 实时 Token 计数
📈 可视化费用图表
⚠️ 超支自动预警
🔄 模型成本对比

</td>
<td align="center" width="260px">

**🧩 Markdown 扩展**
*不写代码也能扩展*

📝 写 `SKILL.md`
🔗 MCP 协议支持
📦 Git 直接安装
♻️ 热更新支持

</td>
</tr>
<tr>
<td align="center" width="260px">

**🤖 可视化 SubAgent**
*创建专属 AI 助手*

🎨 图形界面创建
📁 工作区隔离
🎯 自动任务分发
🧠 独立配置记忆

</td>
<td align="center" width="260px">

**⏰ 智能定时任务**
*任务真正被执行*

▶️ SubAgent 真干活
📅 多种调度方式
💪 重启任务不丢
💬 访问上下文

</td>
<td align="center" width="260px">

**🗂️ 项目隔离**
*每个项目独立空间*

⚙️ 独立配置记忆
🔄 一键切换项目
👥 导出团队共享
💬 历史永不丢失

</td>
</tr>
<tr>
<td align="center" width="260px">

**🔊 文本转语音**
*让 AI 开口说话*

🗣️ 多种 TTS 引擎
🎵 自然语音输出
⚙️ 可自定义设置
📱 实时播放支持

</td>
<td align="center" width="260px">

**💬 微信通道**
*在微信上聊天*

📱 扫码登录
📨 收发消息
🔄 状态管理
🤖 自动回复支持

</td>
<td align="center" width="260px">

**📄 多格式文件**
*读取任意文档*

📑 PDF 支持
📝 DOCX 解析
📊 Excel 读取
🔍 智能提取

</td>
</tr>
</table>

***

## 🔌 扩展生态

### 技能扩展（Markdown 即可）

写一个 `SKILL.md` 就能让 AI 学会新能力：

```markdown
---
name: "代码审查"
emoji: "🔍"
---

审查代码时检查：
1. 安全问题（SQL 注入、XSS）
2. 性能瓶颈
3. 命名规范
```

放入 `workspace/extensions/my-skill/SKILL.md`，重启即生效。

### MCP 协议支持

- 连接任意 MCP 服务器（stdio / WebSocket / SSE）
- 自动发现工具，无需手动配置
- 可视化权限管理

***

## ⚙️ 可视化配置

所有配置都有图形界面，不用写 YAML：

| 配置项       | 说明                                      |
| :-------- | :-------------------------------------- |
| **模型提供商** | 添加 OpenAI/Anthropic/DeepSeek 等，支持多提供商切换 |
| **工具开关**  | 一键启用/禁用工具，设置超时时间                        |
| **工作目录**  | 独立工作区，配置和记忆完全隔离                         |
| **预算上限**  | 设置月度 Token 上限，超支提醒                      |

***

## 💰 Token 消耗可视化

实时监控每一次对话的成本：

- 📊 **实时统计**：输入/输出 Token、费用明细
- 📈 **历史趋势**：按天/周/月查看消耗走势
- ⚠️ **预算告警**：设置上限，超支自动提醒
- 🔄 **模型对比**：不同模型的成本效率一目了然

***

## ⏰ 智能定时任务

不只是定时发通知，而是真干活：

- **SubAgent 执行**：任务在独立 Agent 中运行，真正执行操作
- **灵活调度**：支持 ISO 时间、间隔秒数、Cron 表达式
- **上下文继承**：任务可以访问创建时的会话记忆
- **持久化存储**：任务保存在 SQLite，重启不丢失

***

## 🗂️ 工作目录管理

每个项目一个工作区，互不干扰：

```
workspace/
├── project-a/          # 项目 A
│   ├── extensions/     # 专属扩展
│   ├── memory/         # 长期记忆
│   └── history/        # 聊天记录
├── project-b/          # 项目 B
│   └── ...
```

- 切换工作区 = 切换完整的配置和记忆
- 支持导出/导入工作区
- 团队共享：导出工作区，同事导入即用

***

## 💬 聊天历史记录

- 所有对话保存在本地 SQLite
- 按会话组织，支持搜索
- 可随时回到任意历史会话
- 支持多会话并行

***

## 🤖 可视化 SubAgent

通过界面创建和管理专用 Agent：

- **可视化编辑**：修改 `SOUL.md` 配置角色、工具、模型
- **一键创建**：填写名称自动生成模板配置
- **独立工作区**：每个 SubAgent 有自己的配置和记忆
- **主从调度**：主 Agent 自动调用合适的 SubAgent 处理任务

***

## 🛠️ 内置工具

| 类别      | 工具                                     | 说明      |
| :------ | :------------------------------------- | :------ |
| 📁 文件系统 | `read`, `write`, `edit`, `list`        | 文件读写操作  |
| 🖥️ 系统  | `shell`, `spawn`                       | 命令行执行   |
| 🌐 网络   | `web_fetch`                            | 网页内容抓取  |
| 🖼️ 图像  | `image_understand`, `image_generate`   | AI 图像处理 |
| ⏰ 定时    | `cron_add`, `cron_list`, `cron_remove` | 定时任务管理  |
| 💬 消息   | `send_message`                         | 多通道消息发送 |
| ⚡ 动作    | `action`                               | 执行扩展动作  |

***

## 🚀 快速开始

### 环境要求

- **Node.js** >= 18
- **Python** >= 3.10

### 安装启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd octopus

# 2. 安装依赖
npm install

# 3. 启动开发模式
npm run dev
```

> 💡 `npm run dev` 会同时启动：
>
> - 前端开发服务器 (<http://localhost:3000>)
> - Electron 桌面应用窗口

***

## 📦 构建发布

### 开发命令

| 命令                     | 说明                  |
| :--------------------- | :------------------ |
| `npm run dev`          | 开发模式（前端 + Electron） |
| `npm run dev:frontend` | 仅启动前端开发服务器          |
| `npm run dev:electron` | 仅启动 Electron        |

### 构建命令

| 命令                       | 说明                  |
| :----------------------- | :------------------ |
| `npm run build:frontend` | 构建 React 前端         |
| `npm run build:python`   | 打包 Python 后端        |
| `npm run build`          | 完整构建（前端 + Electron） |

### 打包发布

| 命令                 | 说明         | 输出格式                  |
| :----------------- | :--------- | :-------------------- |
| `npm run dist`     | 当前平台打包     | 根据平台自动选择              |
| `npm run dist:mac` | macOS 打包   | DMG + ZIP (x64/arm64) |
| `npm run dist:win` | Windows 打包 | NSIS 安装包 + 便携版        |

> 📂 输出目录：`dist-electron/`
> 📖 详细构建指南：[README\_BUILD.md](./README_BUILD.md)

***

## 🏗️ 项目架构

```
octopus/
├── agents/                 🧠 AI Agent 工作区
│   ├── code-reviewer/      代码审查 Agent
│   ├── common/             通用 Agent 模板
│   └── system/             系统 Agent 配置
│       └── avatars/        Agent 头像资源
├── backend/                ⚡ Python 后端
│   ├── agent/              Agent 核心逻辑
│   ├── api/                FastAPI 服务接口
│   ├── channels/           多通道支持（桌面/飞书）
│   ├── core/               核心模块（配置/事件/模型）
│   ├── data/               数据存储（SQLite）
│   ├── extensions/         插件系统
│   ├── mcp/                MCP 协议集成
│   ├── services/           服务层（定时任务/图像）
│   ├── tools/              内置工具集
│   │   ├── filesystem.py   文件系统工具
│   │   ├── shell.py        命令行工具
│   │   ├── web_fetch.py    网络抓取工具
│   │   ├── image.py        图像处理工具
│   │   ├── cron.py         定时任务工具
│   │   └── message.py      消息发送工具
│   └── utils/              工具函数
├── electron/               🖥️ Electron 主进程
│   ├── main.js             主进程入口
│   └── preload.js          预加载脚本
├── frontend/               🎨 React 前端
│   ├── src/
│   │   ├── components/     UI 组件
│   │   │   ├── config/     配置组件
│   │   │   ├── forms/      表单组件
│   │   │   ├── modals/     弹窗组件
│   │   │   └── panels/     功能面板
│   │   ├── utils/          工具函数
│   │   ├── App.jsx         应用入口
│   │   └── pixel-theme.css 像素主题样式
│   └── package.json
├── workspace/              📂 工作区数据
│   └── memory/             Agent 记忆存储
├── package.json            项目配置和脚本
└── README.md               项目说明
```

### 技术栈

| 层级     | 技术                     | 说明           |
| :----- | :--------------------- | :----------- |
| **前端** | React 18 + Vite        | 现代化 UI 框架    |
| <br /> | Ant Design             | 组件库          |
| <br /> | Monaco Editor          | 代码编辑器        |
| <br /> | ECharts                | 数据可视化        |
| **后端** | Python 3.10+ + FastAPI | 高性能异步 Web 服务 |
| <br /> | SQLite                 | 本地轻量数据库      |
| **桌面** | Electron 28            | 跨平台桌面应用框架    |
| <br /> | electron-builder       | 应用打包工具       |

***

## 🔧 模型配置

在应用设置面板中添加 API 密钥即可使用：

### 支持的提供商

| 提供商       | 代表模型                                           |
| :-------- | :--------------------------------------------- |
| OpenAI    | GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo             |
| Anthropic | Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku |
| Google    | Gemini Pro, Gemini Ultra                       |
| DeepSeek  | DeepSeek Chat, DeepSeek Coder                  |
| 阿里云       | 通义千问系列                                         |
| 百度        | 文心一言系列                                         |

### 配置步骤

1. 打开应用 → 设置 → 模型提供商
2. 添加提供商（选择或自定义）
3. 输入 API Key
4. 选择要使用的模型
5. 保存并开始使用

***

## 🔌 MCP 协议

Octopus 完整支持 **Model Context Protocol (MCP)**：

- 🔗 连接任意 MCP 服务器
- 🛠️ 使用 MCP 提供的工具
- 🔐 安全的权限管理
- 🔄 实时连接状态监控

### 支持的传输协议

- **stdio**：本地进程通信
- **WebSocket**：远程实时连接
- **SSE**：Server-Sent Events

***

## 🤖 Agent 工作区

Agent 系统支持持续记忆和个性化配置：

### 配置文件

| 文件                     | 用途                   |
| :--------------------- | :------------------- |
| `SOUL.md`              | Agent 灵魂 - 核心准则和性格定义 |
| `IDENTITY.md`          | Agent 身份 - 自我介绍      |
| `AGENTS.md`            | 工作区指南 - 使用说明         |
| `MEMORY.md`            | 长期记忆 - 重要信息持久化       |
| `memory/YYYY-MM-DD.md` | 每日笔记 - 当天事件记录        |

### 创建自定义 Agent

在 `agents/` 目录下创建新文件夹，添加配置文件即可创建专属 Agent。

***

## 📖 文档导航

- 📘 [构建指南](./README_BUILD.md) - 打包发布详细说明
- 📗 [Agent 指南](./agents/system/AGENTS.md) - Agent 工作区使用
- 📕 [身份设定](./agents/system/IDENTITY.md) - 了解章鱼哥是谁
- 🧠 [灵魂内核](./agents/system/SOUL.md) - Agent 核心准则
- 🔌 [MCP 文档](./backend/mcp/README.md) - MCP 协议集成详解

***

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request：

- 🐛 报告 Bug
- ✨ 提交新功能
- 📝 改进文档
- 🎨 优化 UI/UX

***

## 📋 更新日志

### 2026-03

| 日期         | 版本     | 更新内容                        |
| :--------- | :----- | :-------------------------- |
| 2026-03-29 | v1.0.0 | 🔊 新增：文本转语音 (TTS) 功能支持      |
| 2026-03-29 | v1.0.0 | 🤖 新增：子代理管理功能及 UI 改进        |
| 2026-03-28 | v1.0.0 | 🗜️ 新增：对话上下文压缩及 LLM 重试优化    |
| 2026-03-25 | v1.0.0 | 📄 新增：PDF、DOCX 和 Excel 文件支持 |
| 2026-03-24 | v1.0.0 | 💬 新增：微信通道，支持扫码登录和消息收发      |
| 2026-03-22 | v1.0.0 | 🖼️ 新增：无边框窗口支持              |
| 2026-03-20 | v1.0.0 | 🎉 发布：项目更名为 Octopus         |

***

<div align="center">

### 🐙 章鱼哥，让你的工作更高效 🐙

<img src="./backend/templates/workspace/avatars/octopus.png" width="80" style="border-radius: 10px;" />

<sub>Built with ❤️ and 🐙 tentacles</sub>

</div>
