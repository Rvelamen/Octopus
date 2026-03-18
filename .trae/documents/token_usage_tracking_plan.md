# Token 使用情况记录功能设计方案

## 一、需求分析

### 1.1 核心需求
- **全局 Token 统计**: 记录系统整体的 token 使用情况
- **Session Instance 级别统计**: 每个 session instance 消耗的 token 情况
- **上传/下载 Token 区分**: 区分 prompt_tokens (上传) 和 completion_tokens (下载)
- **Provider/Model 级别统计**: 按 provider 和 model 维度统计 token 使用

### 1.2 数据来源
- Provider 层 (`backend/core/providers/provider.py`) 的 `LLMResponse.usage` 已包含:
  - `prompt_tokens`: 输入 token 数
  - `completion_tokens`: 输出 token 数
  - `total_tokens`: 总 token 数

## 二、数据库设计

### 2.1 新增表结构

#### 2.1.1 `token_usage` 表 - 详细 token 使用记录
```sql
CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_instance_id INTEGER,          -- 关联的 session instance
    provider_name TEXT NOT NULL,          -- provider 名称 (如 openai, anthropic)
    model_id TEXT NOT NULL,               -- model ID (如 gpt-4, claude-3-opus)
    prompt_tokens INTEGER DEFAULT 0,      -- 输入 token 数
    completion_tokens INTEGER DEFAULT 0,  -- 输出 token 数
    total_tokens INTEGER DEFAULT 0,       -- 总 token 数
    request_type TEXT DEFAULT 'chat',     -- 请求类型 (chat, compression, etc.)
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_token_usage_instance ON token_usage(session_instance_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider_name);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at);
```

#### 2.1.2 `token_usage_summary` 表 - 汇总统计 (可选，用于快速查询)
```sql
CREATE TABLE IF NOT EXISTS token_usage_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_type TEXT NOT NULL,             -- 'global', 'session', 'instance', 'provider', 'model'
    scope_id TEXT,                        -- 对应的 ID (session_key, instance_id, provider_name, model_id)
    provider_name TEXT,                   -- provider 名称 (可选维度)
    model_id TEXT,                        -- model ID (可选维度)
    total_prompt_tokens INTEGER DEFAULT 0,
    total_completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    date_date TEXT,                       -- 日期 (YYYY-MM-DD)，用于按天统计
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    UNIQUE(scope_type, scope_id, provider_name, model_id, date_date)
);

CREATE INDEX IF NOT EXISTS idx_token_summary_scope ON token_usage_summary(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_token_summary_date ON token_usage_summary(date_date);
```

## 三、代码实现方案

### 3.1 数据层 (`backend/data/token_store.py`) - 新建文件

```python
"""Token usage tracking and storage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from loguru import logger
from backend.data.database import Database


@dataclass
class TokenUsageRecord:
    """Token usage record."""
    id: int
    session_instance_id: int | None
    provider_name: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_type: str
    created_at: datetime


@dataclass
class TokenUsageSummary:
    """Token usage summary."""
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    request_count: int


class TokenUsageRepository:
    """Repository for token usage operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def record_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_type: str = "chat"
    ) -> TokenUsageRecord:
        """Record a token usage event."""
        ...
    
    def get_global_summary(self) -> TokenUsageSummary:
        """Get global token usage summary."""
        ...
    
    def get_instance_summary(self, instance_id: int) -> TokenUsageSummary:
        """Get token usage summary for a session instance."""
        ...
    
    def get_session_summary(self, session_key: str) -> TokenUsageSummary:
        """Get token usage summary for a session (all instances)."""
        ...
    
    def get_provider_summary(self, provider_name: str) -> TokenUsageSummary:
        """Get token usage summary for a provider."""
        ...
    
    def get_daily_usage(self, days: int = 7) -> list[dict]:
        """Get daily token usage for the last N days."""
        ...
```

### 3.2 修改 Provider 层 (`backend/core/providers/provider.py`)

在 `_parse_response` 方法中，返回的 `LLMResponse` 已包含 `usage` 字段。无需修改。

### 3.3 修改 Agent Loop (`backend/agent/loop.py`)

在 `_process_message` 和 `_process_system_message` 方法中，调用 LLM 后记录 token 使用:

```python
# 在 response = await provider.chat(...) 之后
if response.usage:
    await self._record_token_usage(
        session_instance_id=session_instance_id,
        provider_name=provider_type,
        model_id=model,
        usage=response.usage
    )
```

新增方法:
```python
async def _record_token_usage(
    self,
    session_instance_id: int | None,
    provider_name: str,
    model_id: str,
    usage: dict
) -> None:
    """Record token usage to database."""
    ...
```

### 3.4 修改 Desktop Channel Handlers (`backend/channels/desktop/handlers.py`)

新增 Handler 用于查询 token 使用情况:

```python
class GetTokenUsageHandler(MessageHandler):
    """Handle token usage queries."""
    
    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return token usage statistics."""
        scope = message.data.get("scope", "global")  # global, instance, session, provider
        scope_id = message.data.get("scope_id")
        
        # Query token usage from repository
        ...
```

### 3.5 修改 Protocol (`backend/channels/desktop/protocol.py`)

新增消息类型:
```python
class MessageType(Enum):
    # ... existing types
    TOKEN_USAGE = "token_usage"
    GET_TOKEN_USAGE = "get_token_usage"
```

### 3.6 修改前端 (`frontend/src/App.jsx`)

在状态中添加 token 使用情况:
```javascript
const [tokenUsage, setTokenUsage] = useState({
    global: { prompt: 0, completion: 0, total: 0 },
    currentSession: { prompt: 0, completion: 0, total: 0 }
});
```

在 WebSocket 消息处理中添加:
```javascript
case "token_usage":
    setTokenUsage(data);
    break;
```

## 四、实现步骤

### Phase 1: 数据库层 (后端)
1. 在 `database.py` 中添加 `token_usage` 和 `token_usage_summary` 表
2. 创建 `backend/data/token_store.py` 文件，实现 `TokenUsageRepository`

### Phase 2: Agent Loop 集成
3. 修改 `backend/agent/loop.py`:
   - 添加 `TokenUsageRepository` 依赖
   - 在 LLM 调用后记录 token 使用
   - 在 context compression 调用后记录 token 使用

### Phase 3: API 层
4. 修改 `backend/channels/desktop/protocol.py` 添加新消息类型
5. 修改 `backend/channels/desktop/handlers.py` 添加查询 Handler
6. 修改 `backend/channels/desktop/channel.py` 注册新 Handler

### Phase 4: 前端集成
7. 修改 `frontend/src/App.jsx` 添加 token 状态和显示
8. 可选: 创建新的 `TokenUsagePanel` 组件显示详细统计

### Phase 5: 测试与优化
9. 测试 token 记录功能
10. 测试查询接口
11. 性能优化 (索引、汇总表)

## 五、数据流示意

```
用户消息 → Desktop Channel → MessageBus → AgentLoop
                                              ↓
                                    Provider.chat() 
                                              ↓
                                    LLMResponse (含 usage)
                                              ↓
                              TokenUsageRepository.record_usage()
                                              ↓
                                    SQLite Database
                                              ↓
                              前端查询 → GetTokenUsageHandler
                                              ↓
                              TokenUsageRepository.get_*_summary()
                                              ↓
                              WebSocket → 前端显示
```

## 六、API 设计

### 6.1 WebSocket 消息格式

#### 查询 Token 使用
```json
{
    "type": "get_token_usage",
    "request_id": "req-xxx",
    "data": {
        "scope": "global",  // global | instance | session | provider | daily
        "scope_id": null,   // instance_id, session_key, provider_name 等
        "days": 7           // 仅用于 daily scope
    }
}
```

#### 响应
```json
{
    "type": "token_usage",
    "request_id": "req-xxx",
    "data": {
        "scope": "global",
        "summary": {
            "total_prompt_tokens": 100000,
            "total_completion_tokens": 50000,
            "total_tokens": 150000,
            "request_count": 100
        },
        "details": [...]  // 可选，按天/按 model 分组
    }
}
```

### 6.2 实时推送

在每次 LLM 调用后，可选推送 token 使用更新:
```json
{
    "type": "token_usage_update",
    "data": {
        "session_instance_id": 123,
        "provider": "openai",
        "model": "gpt-4",
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500
    }
}
```

## 七、注意事项

1. **性能考虑**: 
   - 使用索引优化查询
   - 汇总表用于快速统计
   - 考虑定期清理旧数据

2. **隐私考虑**:
   - 不记录具体消息内容，只记录 token 数量
   - 可配置是否启用 token 追踪

3. **兼容性**:
   - 现有数据库升级时自动创建新表
   - 不影响现有功能

4. **扩展性**:
   - 预留字段用于未来扩展 (如 cost 计算)
   - 支持按日期范围查询
