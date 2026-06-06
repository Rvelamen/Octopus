"""Desktop channel message handlers."""

# Base classes
# Agent handlers
from backend.channels.desktop.handlers.agent import (
    AgentDeleteHandler,
    AgentGetListHandler,
    AgentGetSoulHandler,
    AgentGetSystemFileHandler,
    AgentGetSystemFilesHandler,
    AgentSaveSoulHandler,
    AgentSaveSystemFileHandler,
)
from backend.channels.desktop.handlers.base import MessageHandler

# Chat handlers
from backend.channels.desktop.handlers.chat import ChatHandler

# Config handlers
from backend.channels.desktop.handlers.config import (
    GetConfigHandler,
    PingHandler,
    SaveConfigHandler,
    StopAgentsHandler,
)

# Cron handlers
from backend.channels.desktop.handlers.cron import (
    CronAddJobHandler,
    CronDeleteJobHandler,
    CronGetJobsHandler,
    CronRunJobHandler,
    CronToggleJobHandler,
)

# Image handlers
from backend.channels.desktop.handlers.image import (
    FileUploadHandler,
    ImageAnalyzeHandler,
    ImageGenerateHandler,
    ImageGetGenerationProvidersHandler,
    ImageGetUnderstandingProvidersHandler,
    ImageUploadHandler,
)
from backend.channels.desktop.handlers.library import LibraryHandler

# MCP handlers
from backend.channels.desktop.handlers.mcp import (
    MCPAddServerHandler,
    MCPCallToolHandler,
    MCPConnectServerHandler,
    MCPDeleteServerHandler,
    MCPDisconnectServerHandler,
    MCPDiscoverToolsHandler,
    MCPGetConfigHandler,
    MCPGetServersHandler,
    MCPGetServerToolsHandler,
    MCPGetStatusHandler,
    MCPReconnectServerHandler,
    MCPUpdateConfigHandler,
    MCPUpdateServerHandler,
    MCPUpdateToolHandler,
    TTSHandler,
)

# Models handlers
from backend.channels.desktop.handlers.models import GetModelsHandler
from backend.channels.desktop.handlers.registry import HandlerRegistry

# Session handlers
from backend.channels.desktop.handlers.session import (
    SessionCreateHandler,
    SessionDeleteInstanceHandler,
    SessionGetChannelSessionsHandler,
    SessionGetChannelsHandler,
    SessionGetInstancesHandler,
    SessionGetMessagesHandler,
    SessionGetSessionDetailHandler,
    SessionSetActiveHandler,
)

# Subagent handlers
from backend.channels.desktop.handlers.subagent import (
    SubagentGetAvailableExtensionsHandler,
    SubagentGetAvailableToolsHandler,
    SubagentGetProviderModelsHandler,
)

# Token handlers
from backend.channels.desktop.handlers.token import TokenUsageHandler

# Workspace handlers
from backend.channels.desktop.handlers.workspace import (
    WorkspaceDeleteHandler,
    WorkspaceGetRootHandler,
    WorkspaceListHandler,
    WorkspaceMkdirHandler,
    WorkspaceReadHandler,
    WorkspaceRenameHandler,
    WorkspaceWriteHandler,
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
    # Library
    "LibraryHandler",
]
