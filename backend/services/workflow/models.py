"""Workflow data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkflowStatus(Enum):
    """Workflow status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class NodeType(Enum):
    """Workflow node types."""
    # System nodes
    WORKFLOW_START = "workflowStart"
    ANSWER = "answerNode"

    # AI nodes
    CHAT = "chatNode"
    CLASSIFY_QUESTION = "classifyQuestion"
    CONTENT_EXTRACT = "contentExtract"

    # Tool nodes
    HTTP_REQUEST = "httpRequest468"
    CODE = "code"
    READ_FILES = "readFiles"
    JSON_SERIALIZE = "jsonSerialize"
    JSON_DESERIALIZE = "jsonDeserialize"

    # Logic nodes
    IF_ELSE = "ifElseNode"
    VARIABLE_UPDATE = "variableUpdate"
    LOOP = "loop"
    PARALLEL_RUN = "parallelRun"

    # Interactive nodes
    USER_SELECT = "userSelect"
    FORM_INPUT = "formInput"

    # Plugin nodes
    PLUGIN_INPUT = "pluginInput"
    PLUGIN_OUTPUT = "pluginOutput"

    # Agent nodes
    AGENT = "agentNode"
    SUB_WORKFLOW = "subWorkflowNode"
    TOOL_CALL = "toolCall"

    # Other
    WORKFLOW_END = "workflowEnd"
    COMMENT = "comment"
    EMPTY = "emptyNode"

    # Legacy aliases (old DB data / frontend shorthand)
    START = "start"
    LLM = "llm"
    END = "end"


class VariableType(Enum):
    """Workflow variable types."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY_STRING = "arrayString"
    ARRAY_NUMBER = "arrayNumber"
    ARRAY_BOOLEAN = "arrayBoolean"
    ARRAY_OBJECT = "arrayObject"
    CHAT_HISTORY = "chatHistory"
    DATASET_QUOTE = "datasetQuote"


class TriggerType(Enum):
    """Workflow trigger types."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    API = "api"


@dataclass
class WorkflowRecord:
    """Workflow record."""
    id: str
    name: str
    description: str = ""
    category: str = "general"
    status: WorkflowStatus = WorkflowStatus.DRAFT
    current_version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class WorkflowVersionRecord:
    """Workflow version record."""
    id: str
    workflow_id: str
    version: int
    name: str
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.DRAFT
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class WorkflowNodeRecord:
    """Workflow node record."""
    id: str
    version_id: str
    type: NodeType
    label: str
    position_x: float = 0
    position_y: float = 0
    width: float = 240
    height: float = 120
    config: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60
    max_retries: int = 0
    created_at: Optional[datetime] = None


@dataclass
class WorkflowEdgeRecord:
    """Workflow edge record."""
    id: str
    version_id: str
    source_node_id: str
    target_node_id: str
    label: Optional[str] = None
    condition: Optional[str] = None
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class WorkflowVariableRecord:
    """Workflow variable record."""
    id: str
    version_id: str
    name: str
    type: VariableType
    default_value: Optional[Any] = None
    description: str = ""
    required: bool = False
    is_input: bool = True
    created_at: Optional[datetime] = None


@dataclass
class WorkflowTriggerRecord:
    """Workflow trigger record."""
    id: str
    workflow_id: str
    trigger_type: TriggerType
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: Optional[datetime] = None


@dataclass
class WorkflowRunRecord:
    """Workflow run record."""
    id: str
    workflow_id: str
    version_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    trigger_type: str = "manual"
    input_variables: dict[str, Any] = field(default_factory=dict)
    output_result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    current_node_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class WorkflowRunNodeRecord:
    """Workflow run node record."""
    id: str
    run_id: str
    node_id: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    created_at: Optional[datetime] = None
