<div align="center">
  <img src="./backend/templates/workspace/avatars/octopus.png" alt="Octopus Logo" width="200" />

  <h1>
    <img src="https://img.shields.io/badge/🐙Octopus-FF6B35?style=for-the-badge&labelColor=1a1a2e" alt="Octopus" />
  </h1>

  <p>
    <strong style="font-size: 1.2em; color: #FF6B35;">Desktop AI Agent Framework · Multi-tentacle Collaboration</strong>
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

---

<div align="center">
  <h3>🌟 Like an octopus, handle multiple things at once 🌟</h3>
</div>

## ✨ Core Features

<table align="center">
<tr>
<td align="center" width="260px">

**🚀 One-Click Deploy**
*No server, no YAML*

⚡ Double-click to install
🐍 Embedded Python env
💾 Portable USB mode
🔒 Data stays local

</td>
<td align="center" width="260px">

**💰 Cost Transparency**
*Know what you spend*

📊 Real-time token counter
📈 Visual cost charts
⚠️ Budget alerts
🔄 Model cost compare

</td>
<td align="center" width="260px">

**🧩 Markdown Skills**
*Extend without coding*

📝 Write `SKILL.md`
🔗 MCP protocol support
📦 Git install extensions
♻️ Hot-reload enabled

</td>
</tr>
<tr>
<td align="center" width="260px">

**🤖 Visual SubAgent**
*Create AI workers*

🎨 GUI agent creator
📁 Isolated workspaces
🎯 Auto task dispatch
🧠 Own config & memory

</td>
<td align="center" width="260px">

**⏰ Smart Tasks**
*Actually run tasks*

▶️ SubAgent execution
📅 Cron/interval/once
💪 Survive restarts
💬 Access context

</td>
<td align="center" width="260px">

**🗂️ Project Isolation**
*Separate workspaces*

⚙️ Per-project config
🔄 Switch instantly
👥 Export for team
💬 Never lose history

</td>
</tr>
</table>

---

## 🔌 Extension Ecosystem

### Skill Extensions (Just Markdown)

Write a `SKILL.md` file to teach AI new capabilities:

```markdown
---
name: "Code Review"
emoji: "🔍"
---

When reviewing code, check for:
1. Security issues (SQL injection, XSS)
2. Performance bottlenecks
3. Naming conventions
```

Drop it into `workspace/extensions/my-skill/SKILL.md` and restart to activate.

### MCP Protocol Support

- Connect to any MCP server (stdio / WebSocket / SSE)
- Auto-discover tools, no manual configuration needed
- Visual permission management

---

## ⚙️ Visual Configuration

All configuration has a graphical interface, no YAML required:

| Config Item | Description |
|:--|:--|
| **Model Providers** | Add OpenAI/Anthropic/DeepSeek, support multi-provider switching |
| **Tool Toggles** | Enable/disable tools with one click, set timeout |
| **Workspace** | Isolated workspaces with separate config and memory |
| **Budget Limit** | Set monthly token limit with over-budget alerts |

---

## 💰 Token Usage Visualization

Monitor the cost of every conversation in real-time:

- 📊 **Real-time Stats**: Input/output tokens, cost breakdown
- 📈 **Historical Trends**: View consumption by day/week/month
- ⚠️ **Budget Alerts**: Set limits with automatic warnings
- 🔄 **Model Comparison**: Cost efficiency across models at a glance

---

## ⏰ Smart Scheduled Tasks

Not just notifications, but actual work:

- **SubAgent Execution**: Tasks run in isolated agents, performing real operations
- **Flexible Scheduling**: Support ISO time, interval seconds, Cron expressions
- **Context Inheritance**: Tasks can access session memory from creation time
- **Persistent Storage**: Tasks saved in SQLite, survive restarts

---

## 🗂️ Workspace Management

Each project has its own isolated workspace:

```
workspace/
├── project-a/          # Project A
│   ├── extensions/     # Exclusive extensions
│   ├── memory/         # Long-term memory
│   └── history/        # Chat history
├── project-b/          # Project B
│   └── ...
```

- Switch workspace = switch complete config and memory
- Export/import workspaces supported
- Team sharing: export workspace, colleagues import to use

---

## 💬 Chat History

- All conversations saved in local SQLite
- Organized by session with search support
- Return to any historical session anytime
- Support parallel multi-sessions

---

## 🤖 Visual SubAgent

Create and manage specialized agents through the UI:

- **Visual Editing**: Modify `SOUL.md` to configure role, tools, model
- **One-click Creation**: Fill in name to auto-generate template config
- **Isolated Workspace**: Each SubAgent has its own config and memory
- **Master-Slave Dispatch**: Main agent automatically calls appropriate SubAgent

---

## 🛠️ Built-in Tools

| Category | Tools | Description |
|:--|:--|:--|
| 📁 Filesystem | `read`, `write`, `edit`, `list` | File read/write operations |
| 🖥️ System | `shell`, `spawn` | Command execution |
| 🌐 Network | `web_fetch` | Web content fetching |
| 🖼️ Image | `image_understand`, `image_generate` | AI image processing |
| ⏰ Schedule | `cron_add`, `cron_list`, `cron_remove` | Task scheduling |
| 💬 Message | `send_message` | Multi-channel messaging |
| ⚡ Action | `action` | Execute extension actions |

---

## 🚀 Quick Start

### Requirements
- **Node.js** >= 18
- **Python** >= 3.10

### Install & Run

```bash
# 1. Clone repository
git clone <repository-url>
cd octopus

# 2. Install dependencies
npm install

# 3. Setup Python environment
python setup_portable_python.py

# 4. Start development mode
npm run dev
```

> 💡 `npm run dev` starts both:
> - Frontend dev server (http://localhost:3000)
> - Electron desktop window

---

## 📦 Build & Release

### Development Commands

| Command | Description |
|:--|:--|
| `npm run dev` | Dev mode (frontend + Electron) |
| `npm run dev:frontend` | Frontend dev server only |
| `npm run dev:electron` | Electron only |

### Build Commands

| Command | Description |
|:--|:--|
| `npm run build:frontend` | Build React frontend |
| `npm run build:python` | Package Python backend |
| `npm run build` | Full build (frontend + Electron) |

### Package & Release

| Command | Description | Output |
|:--|:--|:--|
| `npm run dist` | Package current platform | Auto-select by platform |
| `npm run dist:mac` | macOS package | DMG + ZIP (x64/arm64) |
| `npm run dist:win` | Windows package | NSIS installer + portable |

> 📂 Output: `dist-electron/`
> 📖 Detailed guide: [README_BUILD.md](./README_BUILD.md)

---

## 🏗️ Project Architecture

```
octopus/
├── agents/                 🧠 AI Agent workspace
│   ├── code-reviewer/      Code review agent
│   ├── common/             Common agent templates
│   └── system/             System agent config
│       └── avatars/        Agent avatar assets
├── backend/                ⚡ Python backend
│   ├── agent/              Agent core logic
│   ├── api/                FastAPI service interface
│   ├── channels/           Multi-channel support (desktop/feishu)
│   ├── core/               Core modules (config/events/models)
│   ├── data/               Data storage (SQLite)
│   ├── extensions/         Plugin system
│   ├── mcp/                MCP protocol integration
│   ├── services/           Service layer (cron/image)
│   ├── tools/              Built-in tools
│   │   ├── filesystem.py   Filesystem tools
│   │   ├── shell.py        Shell tools
│   │   ├── web_fetch.py    Web fetch tools
│   │   ├── image.py        Image processing tools
│   │   ├── cron.py         Cron task tools
│   │   └── message.py      Message tools
│   └── utils/              Utility functions
├── electron/               🖥️ Electron main process
│   ├── main.js             Main entry
│   └── preload.js          Preload script
├── frontend/               🎨 React frontend
│   ├── src/
│   │   ├── components/     UI components
│   │   │   ├── config/     Config components
│   │   │   ├── forms/      Form components
│   │   │   ├── modals/     Modal components
│   │   │   └── panels/     Feature panels
│   │   ├── utils/          Utilities
│   │   ├── App.jsx         App entry
│   │   └── pixel-theme.css Pixel theme styles
│   └── package.json
├── workspace/              📂 Workspace data
│   └── memory/             Agent memory storage
├── package.json            Project config & scripts
├── setup_portable_python.py Python environment setup
└── README.md               Project documentation
```

### Tech Stack

| Layer | Technology | Description |
|:--|:--|:--|
| **Frontend** | React 18 + Vite | Modern UI framework |
| | Ant Design | Component library |
| | Monaco Editor | Code editor |
| | ECharts | Data visualization |
| **Backend** | Python 3.10+ + FastAPI | High-performance async web service |
| | SQLite | Local lightweight database |
| **Desktop** | Electron 28 | Cross-platform desktop framework |
| | electron-builder | App packaging tool |

---

## 🔧 Model Configuration

Add API keys in the app settings panel:

### Supported Providers

| Provider | Representative Models |
|:--|:--|
| OpenAI | GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo |
| Anthropic | Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku |
| Google | Gemini Pro, Gemini Ultra |
| DeepSeek | DeepSeek Chat, DeepSeek Coder |
| Alibaba | Tongyi Qianwen series |
| Baidu | Wenxin Yiyan series |

### Configuration Steps

1. Open app → Settings → Model Providers
2. Add provider (select or custom)
3. Enter API Key
4. Select model to use
5. Save and start

---

## 🔌 MCP Protocol

Octopus fully supports **Model Context Protocol (MCP)**:

- 🔗 Connect to any MCP server
- 🛠️ Use tools provided by MCP
- 🔐 Secure permission management
- 🔄 Real-time connection monitoring

### Supported Transports

- **stdio**: Local process communication
- **WebSocket**: Remote real-time connection
- **SSE**: Server-Sent Events

---

## 🤖 Agent Workspace

Agent system supports continuous memory and personalization:

### Configuration Files

| File | Purpose |
|:--|:--|
| `SOUL.md` | Agent soul - core principles and personality |
| `IDENTITY.md` | Agent identity - self-introduction |
| `AGENTS.md` | Workspace guide - usage instructions |
| `MEMORY.md` | Long-term memory - important info persistence |
| `memory/YYYY-MM-DD.md` | Daily notes - daily event records |

### Creating Custom Agents

Create new folder in `agents/` directory, add config files to create custom agent.

---

## 📖 Documentation

- 📘 [Build Guide](./README_BUILD.md) - Packaging & release details
- 📗 [Agent Guide](./agents/system/AGENTS.md) - Agent workspace usage
- 📕 [Identity](./agents/system/IDENTITY.md) - Learn who Octopus is
- 🧠 [Soul Core](./agents/system/SOUL.md) - Agent core principles
- 🔌 [MCP Docs](./backend/mcp/README.md) - MCP protocol integration

---

## 🤝 Contributing

Issues and Pull Requests welcome:

- 🐛 Bug reports
- ✨ New features
- 📝 Documentation improvements
- 🎨 UI/UX optimizations

---

<div align="center">

### 🐙 Octopus makes your work more efficient 🐙

<img src="./backend/templates/workspace/avatars/octopus.png" width="80" style="border-radius: 10px;" />

<sub>Built with ❤️ and 🐙 tentacles</sub>

</div>
