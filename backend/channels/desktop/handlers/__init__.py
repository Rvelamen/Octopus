"""Desktop channel message handlers."""

# Base classes
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.handlers.registry import HandlerRegistry

# Chat handlers
from backend.channels.desktop.handlers.chat import ChatHandler

# Config handlers
from backend.channels.desktop.handlers.config import (
    GetConfigHandler,
    SaveConfigHandler,
    PingHandler,
    StopAgentsHandler,
)

# Models handlers
from backend.channels.desktop.handlers.models import GetModelsHandler

# MCP handlers
from backend.channels.desktop.handlers.mcp import (
    MCPGetStatusHandler,
    TTSHandler,
    MCPGetServersHandler,
    MCPGetServerToolsHandler,
    MCPAddServerHandler,
    MCPDeleteServerHandler,
    MCPUpdateServerHandler,
    MCPUpdateToolHandler,
    MCPDiscoverToolsHandler,
    MCPConnectServerHandler,
    MCPDisconnectServerHandler,
    MCPReconnectServerHandler,
    MCPCallToolHandler,
    MCPGetConfigHandler,
    MCPUpdateConfigHandler,
)

# Session handlers
from backend.channels.desktop.handlers.session import (
    SessionGetChannelsHandler,
    SessionGetChannelSessionsHandler,
    SessionGetSessionDetailHandler,
    SessionGetMessagesHandler,
    SessionDeleteInstanceHandler,
    SessionCreateHandler,
    SessionSetActiveHandler,
    SessionGetInstancesHandler,
)

# Workspace handlers
from backend.channels.desktop.handlers.workspace import (
    WorkspaceGetRootHandler,
    WorkspaceListHandler,
    WorkspaceReadHandler,
    WorkspaceWriteHandler,
    WorkspaceDeleteHandler,
    WorkspaceMkdirHandler,
    WorkspaceRenameHandler,
)

# Cron handlers
from backend.channels.desktop.handlers.cron import (
    CronGetJobsHandler,
    CronAddJobHandler,
    CronDeleteJobHandler,
    CronToggleJobHandler,
    CronRunJobHandler,
)

# Agent handlers
from backend.channels.desktop.handlers.agent import (
    AgentGetListHandler,
    AgentGetSoulHandler,
    AgentSaveSoulHandler,
    AgentDeleteHandler,
    AgentGetSystemFilesHandler,
    AgentGetSystemFileHandler,
    AgentSaveSystemFileHandler,
)

# Subagent handlers
from backend.channels.desktop.handlers.subagent import (
    SubagentGetAvailableToolsHandler,
    SubagentGetAvailableExtensionsHandler,
    SubagentGetProviderModelsHandler,
)

# Token handlers
from backend.channels.desktop.handlers.token import TokenUsageHandler

# Image handlers
from backend.channels.desktop.handlers.image import (
    ImageUploadHandler,
    FileUploadHandler,
    ImageAnalyzeHandler,
    ImageGenerateHandler,
    ImageGetUnderstandingProvidersHandler,
    ImageGetGenerationProvidersHandler,
)

__all__ = [
    # Base
    "MessageHandler",
    "HandlerRegistry",
    # Chat
    "ChatHandler",
    # Config
    "GetConfigHandler",
    "SaveConfigHandler",
    "PingHandler",
    "StopAgentsHandler",
    # Models
    "GetModelsHandler",
    # MCP
    "MCPGetStatusHandler",
    "TTSHandler",
    "MCPGetServersHandler",
    "MCPGetServerToolsHandler",
    "MCPAddServerHandler",
    "MCPDeleteServerHandler",
    "MCPUpdateServerHandler",
    "MCPUpdateToolHandler",
    "MCPDiscoverToolsHandler",
    "MCPConnectServerHandler",
    "MCPDisconnectServerHandler",
    "MCPReconnectServerHandler",
    "MCPCallToolHandler",
    "MCPGetConfigHandler",
    "MCPUpdateConfigHandler",
    # Session
    "SessionGetChannelsHandler",
    "SessionGetChannelSessionsHandler",
    "SessionGetSessionDetailHandler",
    "SessionGetMessagesHandler",
    "SessionDeleteInstanceHandler",
    "SessionCreateHandler",
    "SessionSetActiveHandler",
    "SessionGetInstancesHandler",
    # Workspace
    "WorkspaceGetRootHandler",
    "WorkspaceListHandler",
    "WorkspaceReadHandler",
    "WorkspaceWriteHandler",
    "WorkspaceDeleteHandler",
    "WorkspaceMkdirHandler",
    "WorkspaceRenameHandler",
    # Cron
    "CronGetJobsHandler",
    "CronAddJobHandler",
    "CronDeleteJobHandler",
    "CronToggleJobHandler",
    "CronRunJobHandler",
    # Agent
    "AgentGetListHandler",
    "AgentGetSoulHandler",
    "AgentSaveSoulHandler",
    "AgentDeleteHandler",
    "AgentGetSystemFilesHandler",
    "AgentGetSystemFileHandler",
    "AgentSaveSystemFileHandler",
    # Subagent
    "SubagentGetAvailableToolsHandler",
    "SubagentGetAvailableExtensionsHandler",
    "SubagentGetProviderModelsHandler",
    # Token
    "TokenUsageHandler",
    # Image
    "ImageUploadHandler",
    "FileUploadHandler",
    "ImageAnalyzeHandler",
    "ImageGenerateHandler",
    "ImageGetUnderstandingProvidersHandler",
    "ImageGetGenerationProvidersHandler",
]
