# Octopus 多Agent Team 系统设计文档

## 1. 设计目标

设计一套**独立于现有agent loop**的多Agent Team系统，实现：
- 多个Agent协同工作，形成团队
- 动态任务分解与分配
- Agent间直接通信
- 共享团队记忆和上下文
- 与现有系统共存，不破坏现有功能

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Agent Team System                                │
│                    (独立于现有Agent Loop的新系统)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Team Orchestrator Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │ Team Manager│  │Task Planner │  │  Scheduler  │  │  Monitor  │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │   │
│  │         └─────────────────┴─────────────────┴───────────────┘       │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│  ┌────────────────────────────────▼────────────────────────────────────┐   │
│  │                      Agent Pool Layer                               │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │ Agent 1 │ │ Agent 2 │ │ Agent 3 │ │ Agent 4 │ │ Agent N │ ...   │   │
│  │  │(Worker) │ │(Worker) │ │(Worker) │ │(Reviewer│ │(Special)│       │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │   │
│  │       └───────────┴───────────┴───────────┴───────────┘             │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│  ┌────────────────────────────────▼────────────────────────────────────┐   │
│  │                    Communication Layer                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │ Team Bus    │  │Message Router│  │Topic Pub/Sub│  │ Event Hub │  │   │
│  │  │(团队消息总线)│  │ (消息路由)   │  │ (主题订阅)  │  │(事件中心) │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Shared Context Layer                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │Team Memory  │  │ Shared State│  │Knowledge Graph│  │Context  │  │   │
│  │  │(团队记忆)   │  │ (共享状态)  │  │ (知识图谱)   │  │(上下文) │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        Existing System (现有系统)                           │
│  ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐ │
│  │  Desktop Channel│◄──────►│   Agent Loop    │◄──────►│  Subagent Mgr   │ │
│  └─────────────────┘        └─────────────────┘        └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ 集成点: Team Adapter
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Team Adapter (适配器层)                              │
│              将Agent Team系统与现有Desktop Channel集成                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件设计

### 3.1 Team Orchestrator Layer (团队编排层)

#### 3.1.1 Team Manager
```python
class TeamManager:
    """
    团队生命周期管理
    - 创建/销毁团队
    - 管理团队成员
    - 维护团队状态
    """

    async def create_team(
        self,
        team_config: TeamConfig,
        session_id: str
    ) -> Team:
        """创建新团队"""

    async def disband_team(self, team_id: str) -> None:
        """解散团队"""

    async def add_agent(self, team_id: str, agent_config: AgentConfig) -> Agent:
        """向团队添加Agent"""

    async def remove_agent(self, team_id: str, agent_id: str) -> None:
        """从团队移除Agent"""

    async def get_team_status(self, team_id: str) -> TeamStatus:
        """获取团队状态"""
```

#### 3.1.2 Task Planner (任务规划器)
```python
class TaskPlanner:
    """
    智能任务分解与规划
    - 分析任务复杂度
    - 分解为子任务
    - 确定执行顺序和依赖关系
    """

    async def plan_task(
        self,
        task: str,
        context: TaskContext,
        available_agents: List[AgentProfile]
    ) -> ExecutionPlan:
        """
        生成执行计划

        ExecutionPlan 结构:
        {
            "task_id": str,
            "subtasks": [
                {
                    "id": str,
                    "description": str,
                    "assigned_agent": str,  # agent_id or None (待分配)
                    "dependencies": [str],  # 依赖的子任务ID
                    "estimated_effort": int,
                    "required_skills": [str],
                    "status": "pending"
                }
            ],
            "parallel_groups": [[str]],  # 可并行执行的子任务组
            "strategy": "sequential" | "parallel" | "mixed"
        }
        """

    async def replan_on_failure(
        self,
        plan: ExecutionPlan,
        failed_subtask: str,
        reason: str
    ) -> ExecutionPlan:
        """失败时重新规划"""
```

#### 3.1.3 Scheduler (调度器)
```python
class TaskScheduler:
    """
    任务调度执行
    - 根据依赖关系调度任务
    - 管理任务执行顺序
    - 处理并行执行
    """

    async def schedule(self, plan: ExecutionPlan, team: Team) -> None:
        """调度执行计划"""

    async def execute_subtask(
        self,
        subtask: SubTask,
        agent: Agent,
        context: SharedContext
    ) -> SubTaskResult:
        """执行单个子任务"""

    async def handle_dependency_completion(
        self,
        completed_subtask: str,
        plan: ExecutionPlan
    ) -> List[SubTask]:
        """处理依赖完成，返回可执行的子任务"""
```

#### 3.1.4 Monitor (监控器)
```python
class TeamMonitor:
    """
    团队执行监控
    - 跟踪任务进度
    - 检测死锁/超时
    - 收集执行指标
    """

    async def watch(self, team_id: str) -> None:
        """开始监控团队"""

    async def check_health(self, team_id: str) -> HealthStatus:
        """检查团队健康状态"""

    async def handle_stuck_team(self, team_id: str) -> RecoveryAction:
        """处理卡住的团队"""
```

---

### 3.2 Agent Pool Layer (Agent池层)

#### 3.2.1 Team Agent 定义
```python
@dataclass
class TeamAgent:
    """
    团队中的Agent
    与现有Subagent的区别：
    - 支持Agent间直接通信
    - 有角色定义
    - 参与团队协作
    """
    id: str
    name: str
    role: AgentRole  # LEADER / WORKER / REVIEWER / SPECIALIST
    profile: AgentProfile
    state: AgentState  # IDLE / BUSY / WAITING / OFFLINE
    capabilities: List[Capability]
    config: AgentConfig

    # 运行时状态
    current_task: Optional[str]
    message_inbox: Queue[AgentMessage]
    collaboration_sessions: List[str]

class AgentRole(Enum):
    LEADER = "leader"           # 领导者：协调团队，做决策
    WORKER = "worker"           # 工作者：执行具体任务
    REVIEWER = "reviewer"       # 审查者：检查质量
    SPECIALIST = "specialist"   # 专家：特定领域深度处理
    COORDINATOR = "coordinator" # 协调者：专门协调沟通

@dataclass
class AgentProfile:
    """Agent画像"""
    skills: List[Skill]
    personality: Personality  # 影响协作风格
    communication_style: CommunicationStyle
    expertise_domains: List[str]
    performance_history: PerformanceMetrics
```

#### 3.2.2 Agent Runner
```python
class TeamAgentRunner:
    """
    Team Agent的执行引擎
    独立实现，不依赖现有loop.py
    """

    def __init__(
        self,
        agent: TeamAgent,
        team_bus: TeamBus,
        shared_context: SharedContext,
        llm_provider: LLMProvider
    ):
        self.agent = agent
        self.bus = team_bus
        self.context = shared_context
        self.llm = llm_provider

    async def run_task(
        self,
        task: SubTask,
        callbacks: TaskCallbacks
    ) -> TaskResult:
        """
        执行任务

        与现有loop的区别：
        1. 支持任务执行中的协作请求
        2. 可以主动发起与其他Agent的通信
        3. 可以访问共享上下文
        """

    async def handle_collaboration_request(
        self,
        request: CollaborationRequest
    ) -> CollaborationResponse:
        """处理来自其他Agent的协作请求"""

    async def request_help(
        self,
        help_type: HelpType,
        description: str,
        target_agents: Optional[List[str]]
    ) -> List[HelpResponse]:
        """向其他Agent请求帮助"""
```

---

### 3.3 Communication Layer (通信层)

#### 3.3.1 Team Bus (团队消息总线)
```python
class TeamBus:
    """
    团队内部消息总线
    与现有MessageBus的区别：
    - 支持Agent间直接通信
    - 支持topic订阅
    - 消息路由更灵活
    """

    def __init__(self, team_id: str):
        self.team_id = team_id
        self.message_queue: Queue[TeamMessage]
        self.subscribers: Dict[str, Set[Callable]]  # topic -> handlers
        self.direct_routes: Dict[str, Queue]  # agent_id -> inbox

    async def publish(
        self,
        message: TeamMessage,
        target: TargetType = TargetType.BROADCAST
    ) -> None:
        """
        发布消息

        TargetType:
        - BROADCAST: 广播给所有Agent
        - DIRECT: 直接发给特定Agent
        - TOPIC: 发给订阅了topic的Agent
        - ROLE: 发给特定角色的所有Agent
        """

    async def subscribe(
        self,
        subscriber_id: str,
        topic: str,
        handler: Callable[[TeamMessage], Awaitable[None]]
    ) -> None:
        """订阅topic"""

    async def send_direct(
        self,
        from_agent: str,
        to_agent: str,
        message: TeamMessage
    ) -> None:
        """发送直接消息"""

    async def create_channel(
        self,
        channel_id: str,
        participants: List[str]
    ) -> TeamChannel:
        """创建临时协作频道"""
```

#### 3.3.2 消息类型定义
```python
@dataclass
class TeamMessage:
    """团队消息基类"""
    id: str
    timestamp: datetime
    message_type: MessageType
    sender: str  # agent_id
    payload: Dict[str, Any]

class MessageType(Enum):
    # 任务相关
    TASK_ASSIGN = "task_assign"
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"

    # 协作相关
    COLLABORATION_REQUEST = "collaboration_request"
    COLLABORATION_RESPONSE = "collaboration_response"
    HELP_REQUEST = "help_request"
    HELP_RESPONSE = "help_response"

    # 知识共享
    KNOWLEDGE_SHARE = "knowledge_share"
    CONTEXT_UPDATE = "context_update"

    # 团队管理
    AGENT_JOIN = "agent_join"
    AGENT_LEAVE = "agent_leave"
    HEARTBEAT = "heartbeat"

    # 自定义
    CUSTOM = "custom"

@dataclass
class CollaborationRequest(TeamMessage):
    """协作请求"""
    request_type: CollaborationType
    description: str
    deadline: Optional[datetime]
    priority: Priority

class CollaborationType(Enum):
    CODE_REVIEW = "code_review"
    QUESTION_ANSWER = "question_answer"
    VALIDATION = "validation"
    BRAINSTORM = "brainstorm"
    DELEGATION = "delegation"
```

---

### 3.4 Shared Context Layer (共享上下文层)

#### 3.4.1 Team Memory (团队记忆)
```python
class TeamMemory:
    """
    团队级长期记忆
    与个人记忆的区别：
    - 所有Agent共享
    - 结构化为知识图谱
    - 支持语义检索
    """

    def __init__(self, team_id: str, vector_store: VectorStore):
        self.team_id = team_id
        self.vector_store = vector_store
        self.knowledge_graph = KnowledgeGraph()

    async def remember(
        self,
        content: str,
        metadata: MemoryMetadata,
        agent_id: Optional[str] = None
    ) -> MemoryEntry:
        """存储记忆"""

    async def recall(
        self,
        query: str,
        context_filter: Optional[Dict] = None,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """检索记忆"""

    async def consolidate(self) -> None:
        """
        记忆整合
        - 去重
        - 总结
        - 提取关键洞察
        """
```

#### 3.4.2 Shared State (共享状态)
```python
class SharedState:
    """
    团队共享状态
    用于实时同步Agent间的工作进展
    """

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._subscribers: Dict[str, Set[Callable]] = {}

    async def get(self, key: str) -> Any:
        """获取状态值"""

    async def set(
        self,
        key: str,
        value: Any,
        agent_id: str,
        broadcast: bool = True
    ) -> None:
        """设置状态值，可选择广播给其他Agent"""

    async def update(
        self,
        key: str,
        update_fn: Callable[[Any], Any],
        agent_id: str
    ) -> Any:
        """原子更新状态"""

    async def subscribe(
        self,
        key: str,
        handler: Callable[[StateChangeEvent], Awaitable[None]]
    ) -> None:
        """订阅状态变化"""
```

#### 3.4.3 Knowledge Graph (知识图谱)
```python
class TeamKnowledgeGraph:
    """
    团队知识图谱
    以图的形式组织团队积累的知识
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_concept(
        self,
        concept: Concept,
        relations: List[Relation]
    ) -> None:
        """添加概念和关系"""

    def query(
        self,
        start_concept: str,
        relation_type: Optional[str] = None,
        depth: int = 2
    ) -> List[ConceptPath]:
        """查询知识图谱"""

    def find_connections(
        self,
        concept_a: str,
        concept_b: str
    ) -> List[List[str]]:
        """找到两个概念之间的连接路径"""
```

---

## 4. 工作流模式

### 4.1 主从模式 (Leader-Workers)
```
┌─────────┐     1.分解任务      ┌─────────┐
│ Leader  │ ──────────────────► │ Worker 1│
│ (协调)  │ ──────────────────► │ Worker 2│
│         │ ──────────────────► │ Worker 3│
└────┬────┘                     └────┬────┘
     │                               │
     │ 4.汇总结果                    │ 2.执行任务
     │ ◄─────────────────────────────┤
     │                               │
     ▼                               │
┌─────────┐                          │
│ 整合输出 │ ◄────────────────────────┘
└─────────┘         3.返回结果
```

**适用场景**: 复杂任务分解，需要统一协调

### 4.2 流水线模式 (Pipeline)
```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Stage 1 │───►│ Stage 2 │───►│ Stage 3 │───►│ Stage 4 │
│ (分析)  │    │ (设计)  │    │ (实现)  │    │ (测试)  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     ▲                                              │
     └────────────── 反馈循环 ◄─────────────────────┘
```

**适用场景**: 软件开发、文档编写等阶段性任务

### 4.3 辩论模式 (Debate)
```
┌─────────┐         ┌─────────┐
│ Proposer│◄───────►│Opponent │
│ (正方)  │ 辩论    │ (反方)  │
└────┬────┘         └────┬────┘
     │                   │
     └─────────┬─────────┘
               ▼
         ┌─────────┐
         │ Judge   │
         │ (裁决)  │
         └────┬────┘
              ▼
         最终结论
```

**适用场景**: 方案评估、风险分析、决策制定

### 4.4 专家会诊模式 (Expert Panel)
```
┌─────────┐
│  Patient│
│ (问题)  │
└────┬────┘
     │ 分发给多个专家
     ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Expert 1│ │ Expert 2│ │ Expert 3│ │ Expert 4│
│(技术)   │ │(业务)   │ │(安全)   │ │(运维)   │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │           │           │           │
     └───────────┴───────────┴───────────┘
                 ▼
           ┌─────────┐
           │ Synthesizer│
           │(综合建议)│
           └────┬────┘
                ▼
           综合报告
```

**适用场景**: 复杂问题需要多领域专业知识

### 4.5 蜂群模式 (Swarm)
```
所有Agent平等协作，没有中心协调者
通过局部通信达成全局目标

┌─────┐ ◄──► ┌─────┐
│ A1  │      │ A2  │
└──┬──┘      └──┬──┘
   │            │
   ▼            ▼
┌─────┐ ◄──► ┌─────┐
│ A3  │      │ A4  │
└──┬──┘      └──┬──┘
   │            │
   ▼            ▼
┌─────┐ ◄──► ┌─────┐
│ A5  │      │ A6  │
└─────┘      └─────┘
```

**适用场景**: 大规模并行处理、搜索、优化问题

---

## 5. 与现有系统集成

### 5.1 集成架构

```
┌─────────────────────────────────────────────────────────┐
│                   Desktop Channel                       │
│              (backend/channels/desktop/)                │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Team Adapter   │  ← 新增：适配器层
              │  (集成点)       │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  Agent Team  │ │ Existing │ │   Legacy     │
│   System     │ │  Agent   │ │  Subagent    │
│  (新系统)     │ │  Loop    │ │  System      │
└──────────────┘ └──────────┘ └──────────────┘
```

### 5.2 Team Adapter 实现
```python
class TeamAdapter:
    """
    将Agent Team系统适配到现有的Desktop Channel
    """

    def __init__(
        self,
        desktop_handler: DesktopHandler,
        team_manager: TeamManager
    ):
        self.desktop = desktop_handler
        self.teams = team_manager

    async def handle_chat_message(
        self,
        message: ChatMessage
    ) -> None:
        """
        处理聊天消息

        策略:
        1. 检测是否需要启用Agent Team
           - 消息包含 @team 标记
           - 任务复杂度超过阈值
           - 用户显式选择Team模式

        2. 如果需要，创建Team并启动

        3. 将Team输出转发到Desktop Channel
        """

    async def forward_team_output(
        self,
        team_id: str,
        output: TeamOutput
    ) -> None:
        """
        将Team输出转换为Desktop Channel消息格式
        """

    async def handle_team_event(
        self,
        event: TeamEvent
    ) -> None:
        """
        处理Team事件，转换为前端可展示的格式
        """
```

### 5.3 WebSocket 消息扩展
```python
# 新增消息类型 (与现有系统兼容)

class TeamWebSocketMessages:
    # 客户端 -> 服务器
    TEAM_CREATE = "team_create"           # 创建团队
    TEAM_DISBAND = "team_disband"         # 解散团队
    TEAM_CHAT = "team_chat"               # 向团队发送消息
    TEAM_GET_STATUS = "team_get_status"   # 获取团队状态

    # 服务器 -> 客户端
    TEAM_CREATED = "team_created"         # 团队创建成功
    TEAM_AGENT_JOIN = "team_agent_join"   # Agent加入团队
    TEAM_AGENT_LEAVE = "team_agent_leave" # Agent离开团队
    TEAM_PROGRESS = "team_progress"       # 进度更新
    TEAM_MESSAGE = "team_message"         # 团队消息
    TEAM_COMPLETE = "team_complete"       # 任务完成
```

---

## 6. 数据模型

### 6.1 数据库表设计

```sql
-- 团队表
CREATE TABLE teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    workflow_mode TEXT NOT NULL, -- leader_worker, pipeline, debate, panel, swarm
    status TEXT NOT NULL, -- creating, active, paused, completed, error
    session_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSON
);

-- 团队成员表
CREATE TABLE team_agents (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL, -- leader, worker, reviewer, specialist, coordinator
    provider_id INTEGER,
    model_id INTEGER,
    config JSON, -- Agent配置
    status TEXT NOT NULL, -- idle, busy, waiting, offline
    current_task_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务表
CREATE TABLE team_tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    parent_task_id TEXT REFERENCES team_tasks(id),
    title TEXT NOT NULL,
    description TEXT,
    assigned_agent_id TEXT REFERENCES team_agents(id),
    status TEXT NOT NULL, -- pending, in_progress, completed, failed, cancelled
    dependencies JSON, -- [task_id, ...]
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSON,
    error_message TEXT
);

-- 团队消息表
CREATE TABLE team_messages (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    message_type TEXT NOT NULL,
    sender_agent_id TEXT REFERENCES team_agents(id),
    target_agent_id TEXT REFERENCES team_agents(id), -- NULL表示广播
    content JSON NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 团队记忆表
CREATE TABLE team_memories (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES team_agents(id), -- NULL表示集体记忆
    content TEXT NOT NULL,
    embedding BLOB, -- 向量嵌入
    metadata JSON,
    importance_score REAL,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP
);

-- 执行计划表
CREATE TABLE execution_plans (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    original_task TEXT NOT NULL,
    strategy TEXT NOT NULL,
    plan_data JSON NOT NULL, -- 完整的执行计划
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. 实现路线图

### Phase 1: 基础设施 (2-3周)
- [ ] 创建 `backend/team/` 目录结构
- [ ] 实现 TeamBus 消息总线
- [ ] 实现 SharedState 共享状态
- [ ] 实现基础的 TeamMemory
- [ ] 数据库表创建

### Phase 2: Core Team (2-3周)
- [ ] 实现 TeamManager
- [ ] 实现 TeamAgent 和 TeamAgentRunner
- [ ] 实现基础的工作流模式（主从模式）
- [ ] 与 Desktop Channel 集成（TeamAdapter）
- [ ] 前端基础UI（团队创建、状态展示）

### Phase 3: 智能规划 (2周)
- [ ] 实现 TaskPlanner
- [ ] 实现 TaskScheduler
- [ ] 支持更多工作流模式（流水线、辩论）
- [ ] 任务依赖管理

### Phase 4: 高级功能 (2-3周)
- [ ] TeamKnowledgeGraph 实现
- [ ] Agent间直接协作
- [ ] 动态Agent增删
- [ ] 完整的监控和诊断

### Phase 5: 优化与扩展 (持续)
- [ ] 性能优化
- [ ] 更多工作流模式
- [ ] 可视化编排工具
- [ ] 模板市场

---

## 8. 目录结构

```
backend/
├── team/                          # 新Agent Team系统
│   ├── __init__.py
│   ├── adapter.py                 # TeamAdapter - 与现有系统集成
│   │
│   ├── orchestrator/              # 编排层
│   │   ├── __init__.py
│   │   ├── manager.py             # TeamManager
│   │   ├── planner.py             # TaskPlanner
│   │   ├── scheduler.py           # TaskScheduler
│   │   └── monitor.py             # TeamMonitor
│   │
│   ├── agent/                     # Agent层
│   │   ├── __init__.py
│   │   ├── models.py              # TeamAgent, AgentRole等数据模型
│   │   ├── runner.py              # TeamAgentRunner
│   │   ├── pool.py                # AgentPool 管理Agent生命周期
│   │   └── roles/                 # 不同角色的特殊实现
│   │       ├── __init__.py
│   │       ├── leader.py
│   │       ├── worker.py
│   │       └── reviewer.py
│   │
│   ├── communication/             # 通信层
│   │   ├── __init__.py
│   │   ├── bus.py                 # TeamBus
│   │   ├── router.py              # MessageRouter
│   │   ├── channels.py            # TeamChannel
│   │   └── messages.py            # 消息类型定义
│   │
│   ├── context/                   # 共享上下文层
│   │   ├── __init__.py
│   │   ├── memory.py              # TeamMemory
│   │   ├── state.py               # SharedState
│   │   ├── knowledge_graph.py     # TeamKnowledgeGraph
│   │   └── builder.py             # TeamContextBuilder
│   │
│   ├── workflow/                  # 工作流模式
│   │   ├── __init__.py
│   │   ├── base.py                # 工作流基类
│   │   ├── leader_worker.py       # 主从模式
│   │   ├── pipeline.py            # 流水线模式
│   │   ├── debate.py              # 辩论模式
│   │   ├── expert_panel.py        # 专家会诊模式
│   │   └── swarm.py               # 蜂群模式
│   │
│   └── storage/                   # 数据存储
│       ├── __init__.py
│       ├── team_store.py          # 团队数据访问
│       ├── task_store.py          # 任务数据访问
│       └── memory_store.py        # 记忆数据访问
│
├── agent/                         # 现有系统 (保持不变)
│   ├── loop.py
│   ├── subagent.py
│   └── ...
│
└── channels/
    └── desktop/
        └── handlers/
            └── team.py            # Team消息处理器
```

---

## 9. 关键设计决策

### 9.1 为什么独立于现有Agent Loop？

| 方面 | 现有Agent Loop | 新Team System |
|------|---------------|---------------|
| 设计目标 | 单Agent交互 | 多Agent协作 |
| 通信模式 | 主从式 | 网状P2P |
| 状态管理 | 会话隔离 | 团队共享 |
| 扩展性 | 子Agent单向 | Agent间双向 |
| 复杂度 | 单一任务流 | 多任务并行 |

**独立设计的优势：**
1. **不破坏现有功能** - 现有用户不受影响
2. **专注解决新问题** - 协作需要不同的抽象
3. **并行迭代** - 两个系统可以独立演进
4. **可选使用** - 用户按需选择使用方式

### 9.2 与现有Subagent的关系

```
Existing Subagent          New Team Agent
─────────────────          ──────────────
后台执行                    前台+后台执行
单向结果返回                 双向通信
无角色概念                   角色驱动
单一任务                    多任务协作
生命周期由parent控制         自主+协调
```

**关系定位：**
- Team Agent可以spawn现有的Subagent（复用）
- Subagent可以通过Adapter调用Team（扩展）
- 两者可以嵌套使用

### 9.3 扩展性设计

1. **工作流可扩展** - 通过继承BaseWorkflow添加新模式
2. **角色可扩展** - 通过继承BaseRole添加新角色
3. **通信可扩展** - 通过Bus的topic机制添加新消息类型
4. **存储可扩展** - 通过抽象接口支持不同存储后端

---

## 10. 使用示例

### 10.1 创建一个Code Review团队

```python
# 通过API创建团队
from backend.team.orchestrator.manager import TeamManager
from backend.team.agent.models import AgentConfig, AgentRole

manager = TeamManager()

# 创建团队
team = await manager.create_team(
    team_config=TeamConfig(
        name="Code Review Team",
        workflow_mode="expert_panel",
        session_id="session_123"
    )
)

# 添加成员
code_reviewer = await manager.add_agent(
    team_id=team.id,
    agent_config=AgentConfig(
        name="CodeReviewer",
        role=AgentRole.SPECIALIST,
        expertise_domains=["python", "best_practices"],
        provider="openai",
        model="gpt-4"
    )
)

security_expert = await manager.add_agent(
    team_id=team.id,
    agent_config=AgentConfig(
        name="SecurityExpert",
        role=AgentRole.SPECIALIST,
        expertise_domains=["security", "vulnerabilities"],
        provider="openai",
        model="gpt-4"
    )
)

synthesizer = await manager.add_agent(
    team_id=team.id,
    agent_config=AgentConfig(
        name="Synthesizer",
        role=AgentRole.COORDINATOR,
        provider="openai",
        model="gpt-4"
    )
)

# 分配任务
plan = await team.planner.plan_task(
    task="Review this Python code for issues",
    context=TaskContext(code=code_snippet),
    available_agents=team.get_agent_profiles()
)

# 执行
await team.scheduler.schedule(plan, team)
```

### 10.2 前端调用

```javascript
// 创建团队
sendWSMessage("team_create", {
    name: "Architecture Design Team",
    workflow_mode: "debate",
    agents: [
        { name: "ArchitectA", role: "proposer", model: "gpt-4" },
        { name: "ArchitectB", role: "opponent", model: "gpt-4" },
        { name: "Judge", role: "reviewer", model: "claude-3" }
    ]
});

// 监听团队进度
useEffect(() => {
    const handleTeamProgress = (data) => {
        console.log(`Agent ${data.agent_name}: ${data.status}`);
        updateTeamProgress(data);
    };

    subscribeEvent("team_progress", handleTeamProgress);
    return () => unsubscribeEvent("team_progress", handleTeamProgress);
}, []);
```

---

## 11. 风险评估与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|---------|
| 架构过于复杂 | 高 | 中 | 分阶段实现，保持核心简洁 |
| 与现有系统冲突 | 高 | 低 | 清晰的Adapter层，独立命名空间 |
| 性能问题 | 中 | 中 | 异步设计，可配置并发度，监控告警 |
| LLM成本过高 | 中 | 高 | 智能缓存，token预算控制，使用量追踪 |
| 调试困难 | 中 | 高 | 完善的日志，可视化监控，重放能力 |

---

## 12. 结论

这套Agent Team系统设计：

1. **独立性** - 完全独立于现有Agent Loop，不影响现有功能
2. **协作性** - 支持Agent间直接通信和共享上下文
3. **灵活性** - 多种工作流模式适应不同场景
4. **可扩展** - 模块化设计，易于扩展新功能
5. **可集成** - 通过Adapter层与现有系统无缝集成

建议先从**Phase 1**开始，实现基础架构并验证核心概念，然后逐步迭代添加更多功能。
