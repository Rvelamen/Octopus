<div align="center">
  <img src="./agents/system/avatars/octopus.png" alt="Octopus Logo" width="200" " />
  
  <h1>
    <img src="https://img.shields.io/badge/🐙Octopus·章鱼哥-FF6B35?style=for-the-badge&labelColor=1a1a2e" alt="Octopus·章鱼哥" />
  </h1>
  
  <p>
    <strong style="font-size: 1.2em; color: #FF6B35;">你的智能助手 · 多触手高效协作</strong>
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
  </p>
</div>

---

<div align="center">
  <h3>🌟 像章鱼一样，同时处理多件事 🌟</h3>
</div>

## ✨ 为什么选择章鱼哥？

<table>
<tr>
<td width="50%">

### 🤖 **多模型大脑**
- OpenAI GPT 系列
- Claude 系列
- Gemini / DeepSeek
- 通义千问 / 文心一言
- **50+ 模型随心切换**

</td>
<td width="50%">

### 🔌 **无限扩展触手**
- MCP 协议支持
- 插件系统
- 自定义工具
- 外部服务接入

</td>
</tr>
<tr>
<td width="50%">

### 💻 **桌面级体验**
- React + Vite 极速 UI
- Monaco 代码编辑器
- ECharts 数据可视化
- 本地数据优先

</td>
<td width="50%">

### 🔄 **多通道协作**
- 桌面客户端
- 飞书集成
- 定时任务 (Cron)
- 智能会话管理

</td>
</tr>
</table>

---

## 🚀 快速开始

### 环境准备

```bash
# 你需要
Node.js >= 18
Python >= 3.10
```

### 一键启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd octopus

# 2. 安装依赖
npm install

# 3. 配置 Python
python setup_portable_python.py

# 4. 启动开发模式
npm run dev
```

> 💡 `npm run dev` 会同时启动前端开发服务器和 Electron 桌面应用

---

## 📦 构建发布

```bash
# 🔨 构建前端
npm run build:frontend

# 🐍 构建 Python 后端
npm run build:python

# 📀 完整打包
npm run dist        # 所有平台
npm run dist:mac    # 仅 macOS
npm run dist:win    # 仅 Windows
```

输出目录：`dist-electron/`

---

## 🏗️ 项目架构

```
🐙 octopus/
├── 🧠 agents/          # AI Agent 配置
├── ⚡ backend/         # Python 后端服务
├── 🖥️  electron/        # Electron 主进程
├── 🎨 frontend/        # React 前端应用
└── 📂 workspace/       # 工作区数据
```

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| 前端 | React 18 + Vite + Ant Design | 现代化响应式界面 |
| 后端 | Python + FastAPI + SQLite | 高性能本地服务 |
| 桌面 | Electron 28 | 跨平台桌面应用 |

---

## 🔧 模型配置

章鱼哥支持 **50+** 种 AI 模型，在设置中添加你的 API 密钥即可：

<div align="center">

| 提供商 | 状态 |
|--------|------|
| OpenAI | ✅ GPT-4 / GPT-3.5 |
| Anthropic | ✅ Claude 系列 |
| Google | ✅ Gemini |
| DeepSeek | ✅ 全系列 |
| 阿里云 | ✅ 通义千问 |
| 百度 | ✅ 文心一言 |
| ... | ✅ 更多 |

</div>

---

## 📖 文档导航

- 📘 [构建指南](./README_BUILD.md) - 打包发布详细说明
- 📗 [Agent 指南](./agents/system/AGENTS.md) - Agent 工作区使用
- 📕 [身份设定](./agents/system/IDENTITY.md) - 了解章鱼哥是谁

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

---

<div align="center">

### 🐙 章鱼哥，让你的工作更高效 🐙

<img src="./agents/system/avatars/octopus.png" width="80" style="border-radius: 10px;" />

<sub>Built with ❤️ and 🐙 tentacles</sub>

</div>
