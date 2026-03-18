# 删除 Heartbeat 代码计划

## 概述

Agent Heartbeat 功能已被移除或从未完成实现，但配置字段和 UI 仍然存在。本计划将清理所有残留代码。

## 需要修改的文件

### 1. Backend - 配置和数据层

#### `backend/core/config/schema.py`
- 删除 `AgentDefaults` 类中的三个字段：
  - `heartbeat_enabled`
  - `heartbeat_interval`
  - `heartbeat_channel`

#### `backend/data/database.py`
- 从 `agent_defaults` 表定义中删除三个列：
  - `heartbeat_enabled BOOLEAN DEFAULT 1`
  - `heartbeat_interval INTEGER DEFAULT 1800`
  - `heartbeat_channel TEXT DEFAULT 'cli'`

#### `backend/data/provider_store.py`
- 从 `AgentDefaultsRecord` dataclass 中删除三个字段
- 从 `get_or_create_defaults()` 方法中删除相关字段
- 从 `update_agent_defaults()` 方法中删除相关参数和更新逻辑
- 从 `_row_to_agent_defaults()` 方法中删除相关字段映射

#### `backend/channels/desktop/provider_handlers.py`
- 从 `AgentDefaultsHandler._get()` 响应中删除三个字段
- 从 `AgentDefaultsHandler._update()` 方法中删除相关参数

#### `backend/core/events/types.py`
- 更新 `InboundMessage.message_type` 注释，移除 heartbeat 相关说明（保留字段以兼容旧数据）

#### `backend/agent/loop.py`
- 更新 `process_direct()` 方法的 `message_type` 参数注释

### 2. Frontend - UI 层

#### `frontend/src/components/panels/ConfigPanel.jsx`
- 删除 heartbeat 相关的 UI 组件：
  - `SwitchField` for "Heartbeat Enabled"
  - `InputField` for "Heartbeat Interval"
  - `SelectField` for "Heartbeat Channel"
- 删除保存时的 heartbeat 字段

#### `frontend/src/components/panels/HistoryPanel.jsx`
- 删除 `filterType` 的 "heartbeat" 选项
- 删除 heartbeat 消息的样式类和 badge 显示

#### `frontend/src/pixel-theme.css`
- 删除 `.heartbeat-badge` 样式
- 删除 `.heartbeat-msg` 样式

### 3. 文件删除

#### `workspace/HEARTBEAT.md`
- 删除整个文件

## 执行步骤

1. **Backend 配置层** - 修改 `schema.py`
2. **Backend 数据库层** - 修改 `database.py` 和 `provider_store.py`
3. **Backend API 层** - 修改 `provider_handlers.py`
4. **Backend 事件类型** - 修改 `types.py` 和 `loop.py` 注释
5. **Frontend 配置面板** - 修改 `ConfigPanel.jsx`
6. **Frontend 历史面板** - 修改 `HistoryPanel.jsx`
7. **Frontend 样式** - 修改 `pixel-theme.css`
8. **删除文件** - 删除 `HEARTBEAT.md`

## 注意事项

- 数据库字段删除后，现有数据库中的数据会被忽略（SQLite 不会自动删除列，但新代码不会读取这些列）
- `message_type` 字段保留在 `InboundMessage` 中，以保持向后兼容性
- MCP 连接的 heartbeat（`mcp/server/connection.py`）不受影响，这是不同用途的心跳机制
