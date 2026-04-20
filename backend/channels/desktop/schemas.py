"""Pydantic request/response schemas for Desktop WebSocket protocol."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class BaseRequest(BaseModel):
    """Base class for all inbound request payloads."""
    model_config = ConfigDict(extra="ignore")


# ============================================================================
# Chat
# ============================================================================
class ChatRequest(BaseRequest):
    content: str = ""
    images: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    instance_id: int | None = None


# ============================================================================
# Config / System
# ============================================================================
class GetConfigRequest(BaseRequest):
    pass


class SaveConfigRequest(BaseRequest):
    config: dict[str, Any] = {}


class PingRequest(BaseRequest):
    timestamp: int | None = None


class StopAgentsRequest(BaseRequest):
    instance_id: int | None = None


class RestartServiceRequest(BaseRequest):
    pass


# ============================================================================
# Models
# ============================================================================
class GetModelsRequest(BaseRequest):
    provider: str = ""


# ============================================================================
# MCP
# ============================================================================
class MCPGetStatusRequest(BaseRequest):
    pass


class MCPGetServersRequest(BaseRequest):
    pass


class MCPGetServerToolsRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPAddServerRequest(BaseRequest):
    name: str = ""
    url: str = ""
    protocol: str = "stdio"
    enabled: bool = True
    auto_connect: bool = True
    config: dict[str, Any] = {}


class MCPDeleteServerRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPUpdateServerRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None
    url: str | None = None
    protocol: str | None = None
    enabled: bool | None = None
    auto_connect: bool | None = None
    config: dict[str, Any] | None = None


class MCPUpdateToolRequest(BaseRequest):
    tool_id: int | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class MCPDiscoverToolsRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPConnectServerRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPDisconnectServerRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPReconnectServerRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None


class MCPCallToolRequest(BaseRequest):
    server_id: int | None = None
    server_name: str | None = None
    tool_name: str = ""
    arguments: dict[str, Any] = {}


class MCPGetConfigRequest(BaseRequest):
    pass


class MCPUpdateConfigRequest(BaseRequest):
    config: dict[str, Any] = {}


# ============================================================================
# Session History
# ============================================================================
class SessionGetChannelsRequest(BaseRequest):
    pass


class SessionGetChannelSessionsRequest(BaseRequest):
    channel: str = ""


class SessionGetSessionDetailRequest(BaseRequest):
    channel: str = ""
    chat_id: str = ""


class SessionGetMessagesRequest(BaseRequest):
    instance_id: int | None = None
    limit: int = 50
    offset: int = 0


class SessionDeleteInstanceRequest(BaseRequest):
    instance_id: int | None = None


class SessionCreateRequest(BaseRequest):
    channel: str = ""
    chat_id: str = ""
    instance_name: str | None = None


class SessionSetActiveRequest(BaseRequest):
    session_key: str = ""
    instance_id: int | None = None


class SessionGetInstancesRequest(BaseRequest):
    session_key: str = ""
    limit: int = 50
    offset: int = 0


class SessionCompressContextRequest(BaseRequest):
    instance_id: int


class SessionGetContextStatsRequest(BaseRequest):
    instance_id: int


# ============================================================================
# Knowledge Base
# ============================================================================
class KnowledgeListRequest(BaseRequest):
    path: str = "knowledge/notes"
    vault: str | None = None


class KnowledgeReadRequest(BaseRequest):
    path: str = ""


class KnowledgeWriteRequest(BaseRequest):
    path: str = ""
    content: str = ""


class KnowledgeDeleteRequest(BaseRequest):
    path: str = ""


class KnowledgeSearchRequest(BaseRequest):
    query: str = ""
    vault: str | None = None


class KnowledgeGraphRequest(BaseRequest):
    center: str | None = None
    depth: int = 1
    limit: int = 200
    tag: str | None = None
    vault: str | None = None


class KnowledgeDistillRequest(BaseRequest):
    source_path: str = ""
    target_path: str | None = None
    vault: str | None = None
    options: dict[str, Any] = {}


class KnowledgeDistillPreviewRequest(BaseRequest):
    source_path: str = ""
    options: dict[str, Any] = {}


class KnowledgeDistillListRequest(BaseRequest):
    limit: int = 20
    offset: int = 0


class KnowledgeDistillDetailRequest(BaseRequest):
    task_id: int | None = None


class KnowledgeGetTagsRequest(BaseRequest):
    vault: str | None = None


class KnowledgeExportRequest(BaseRequest):
    pass


class KnowledgeImportRequest(BaseRequest):
    zip_data: str = ""
    vault: str | None = None  # optional vault name override for obsidian imports


class KnowledgeListVaultsRequest(BaseRequest):
    pass


class KnowledgeGetDocumentMetaRequest(BaseRequest):
    sha256s: list[str] = []


# ============================================================================
# Memory Stream
# ============================================================================
class MemoryListRequest(BaseRequest):
    instance_id: int | None = None
    limit: int = 50
    offset: int = 0


class MemorySearchRequest(BaseRequest):
    query: str = ""
    limit: int = 20
    type_filter: str | None = None
    instance_id: int | None = None


class MemoryReadRequest(BaseRequest):
    observation_id: int | None = None


class MemoryTimelineRequest(BaseRequest):
    observation_id: int | None = None
    depth_before: int = 2
    depth_after: int = 2


class MemoryDeleteRequest(BaseRequest):
    observation_id: int | None = None


# ============================================================================
# Workspace File System
# ============================================================================
class WorkspaceGetRootRequest(BaseRequest):
    pass


class WorkspaceListRequest(BaseRequest):
    path: str = "."


class WorkspaceReadRequest(BaseRequest):
    path: str = ""


class WorkspaceWriteRequest(BaseRequest):
    path: str = ""
    content: str = ""
    encoding: str = "utf-8"


class WorkspaceWriteChunkRequest(BaseRequest):
    upload_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    content: str = ""
    path: str = ""
    mime_type: str = "application/octet-stream"


class WorkspaceDeleteRequest(BaseRequest):
    path: str = ""


class WorkspaceMkdirRequest(BaseRequest):
    path: str = ""


class WorkspaceRenameRequest(BaseRequest):
    old_path: str = ""
    new_path: str = ""


# ============================================================================
# Cron
# ============================================================================
class CronSchedulePayload(BaseRequest):
    kind: str = "every"
    expr: str | None = None
    every_ms: int | None = None
    at_ms: int | None = None


class CronGetJobsRequest(BaseRequest):
    include_disabled: bool = False


class CronAddJobRequest(BaseRequest):
    name: str = ""
    schedule: dict[str, Any] = {}
    message: str = ""
    deliver: bool = False
    channel: str | None = None
    to: str | None = None


class CronDeleteJobRequest(BaseRequest):
    job_id: str = ""


class CronToggleJobRequest(BaseRequest):
    job_id: str = ""
    enabled: bool = True


class CronRunJobRequest(BaseRequest):
    job_id: str = ""


# ============================================================================
# Agent
# ============================================================================
class AgentGetListRequest(BaseRequest):
    pass


class AgentGetSoulRequest(BaseRequest):
    id: int | None = None
    name: str | None = None


class AgentSaveSoulRequest(BaseRequest):
    id: int | None = None
    name: str = ""
    description: str = ""
    providerId: int | None = None
    modelId: int | None = None
    tools: list[str] = []
    extensions: list[str] = []
    maxIterations: int = 30
    temperature: float = 0.7
    systemPrompt: str = ""
    enabled: bool = True


class AgentDeleteRequest(BaseRequest):
    agent_id: int | None = None


class AgentGetSystemFilesRequest(BaseRequest):
    pass


class AgentGetSystemFileRequest(BaseRequest):
    filename: str = ""


class AgentSaveSystemFileRequest(BaseRequest):
    filename: str = ""
    content: str = ""


# ============================================================================
# Subagent Options
# ============================================================================
class SubagentGetAvailableToolsRequest(BaseRequest):
    pass


class SubagentGetAvailableExtensionsRequest(BaseRequest):
    pass


class SubagentGetProviderModelsRequest(BaseRequest):
    pass


# ============================================================================
# Image
# ============================================================================
class ImageUploadRequest(BaseRequest):
    image_data: str = ""
    file_name: str = "uploaded_image.png"
    mime_type: str = "image/png"
    session_instance_id: int | None = None


class FileUploadRequest(BaseRequest):
    file_data: str = ""
    file_name: str = "uploaded_file"
    mime_type: str = "application/octet-stream"
    session_instance_id: int | None = None


class ImageAnalyzeRequest(BaseRequest):
    image_path: str = ""
    question: str = ""
    provider_name: str | None = None


class ImageGenerateRequest(BaseRequest):
    prompt: str = ""
    provider_name: str | None = None
    size: str = "1024x1024"
    quality: str = "standard"
    n: int = 1


class ImageGetUnderstandingProvidersRequest(BaseRequest):
    pass


class ImageGetGenerationProvidersRequest(BaseRequest):
    pass


class ImageAddUnderstandingProviderRequest(BaseRequest):
    provider_id: int | None = None


class ImageUpdateUnderstandingProviderRequest(BaseRequest):
    provider_id: int | None = None
    config: dict[str, Any] = {}


class ImageDeleteUnderstandingProviderRequest(BaseRequest):
    provider_id: int | None = None


class ImageAddGenerationProviderRequest(BaseRequest):
    provider_id: int | None = None


class ImageUpdateGenerationProviderRequest(BaseRequest):
    provider_id: int | None = None
    config: dict[str, Any] = {}


class ImageDeleteGenerationProviderRequest(BaseRequest):
    provider_id: int | None = None


# ============================================================================
# Provider / Model / Settings / Agent Defaults / Channel / Tool / Image Provider
# ============================================================================
class ProviderGetAllRequest(BaseRequest):
    pass


class ProviderGetRequest(BaseRequest):
    id: int | None = None


class ProviderAddRequest(BaseRequest):
    name: str = ""
    displayName: str = ""
    providerType: str = ""
    apiKey: str = ""
    apiHost: str = ""
    apiVersion: str = ""
    enabled: bool = True


class ProviderUpdateRequest(BaseRequest):
    id: int | None = None
    apiKey: str | None = None
    apiHost: str | None = None
    apiVersion: str | None = None
    enabled: bool | None = None
    sortOrder: int | None = None
    config: dict[str, Any] | None = None


class ProviderDeleteRequest(BaseRequest):
    id: int | None = None


class ProviderEnableRequest(BaseRequest):
    id: int | None = None
    enabled: bool = True


class ModelGetAllRequest(BaseRequest):
    provider_id: int | None = Field(default=None, alias="providerId")


class ModelGetRequest(BaseRequest):
    id: int | None = None


class ModelAddRequest(BaseRequest):
    provider_id: int | None = Field(default=None, alias="providerId")
    model_id: str = Field(default="", alias="modelId")
    displayName: str = ""
    modelType: str = "chat"
    groupName: str = "Chat Models"
    maxTokens: int = 4096
    contextWindow: int = 128000
    supportsVision: bool = False
    supportsFunctionCalling: bool = True
    supportsStreaming: bool = True
    enabled: bool = True


class ModelUpdateRequest(BaseRequest):
    id: int | None = None
    model_id: str | None = Field(default=None, alias="modelId")
    displayName: str | None = None
    modelType: str | None = None
    groupName: str | None = None
    maxTokens: int | None = None
    contextWindow: int | None = None
    supportsVision: bool | None = None
    supportsFunctionCalling: bool | None = None
    supportsStreaming: bool | None = None
    enabled: bool | None = None


class ModelDeleteRequest(BaseRequest):
    id: int | None = None


class ModelSetDefaultRequest(BaseRequest):
    id: int | None = None


class SettingsGetRequest(BaseRequest):
    pass


class SettingsSetRequest(BaseRequest):
    settings: dict[str, Any] = {}


class AgentDefaultsGetRequest(BaseRequest):
    pass


class AgentDefaultsUpdateRequest(BaseRequest):
    default_provider_id: int | None = Field(default=None, alias="defaultProviderId")
    default_model_id: int | None = Field(default=None, alias="defaultModelId")
    workspace_path: str | None = Field(default=None, alias="workspacePath")
    max_tokens: int | None = Field(default=None, alias="maxTokens")
    temperature: float | None = None
    max_iterations: int | None = Field(default=None, alias="maxIterations")
    context_compression_enabled: bool | None = Field(default=None, alias="contextCompressionEnabled")
    context_compression_turns: int | None = Field(default=None, alias="contextCompressionTurns")
    context_compression_token_threshold: int | None = Field(default=None, alias="contextCompressionTokenThreshold")
    llm_max_retries: int | None = Field(default=None, alias="llmMaxRetries")
    llm_retry_base_delay: float | None = Field(default=None, alias="llmRetryBaseDelay")
    llm_retry_max_delay: float | None = Field(default=None, alias="llmRetryMaxDelay")
    tools: list[str] | None = None


class GetEnabledModelsRequest(BaseRequest):
    pass


class ChannelGetListRequest(BaseRequest):
    pass


class ChannelUpdateRequest(BaseRequest):
    channelName: str = ""
    channelType: str = ""
    enabled: bool = False
    appId: str = ""
    appSecret: str = ""
    encryptKey: str = ""
    verificationToken: str = ""
    allowFrom: list[str] = []
    configJson: dict[str, Any] = {}


class ChannelDeleteRequest(BaseRequest):
    channelName: str = ""


class ToolGetConfigRequest(BaseRequest):
    pass


class ToolUpdateConfigRequest(BaseRequest):
    tool_name: str = ""
    config: dict[str, Any] = {}


class ImageGetProvidersRequest(BaseRequest):
    pass


class ImageSetDefaultProviderRequest(BaseRequest):
    provider_type: str = ""
    provider_id: int | None = None


# ============================================================================
# WeChat
# ============================================================================
class WechatGetQrcodeRequest(BaseRequest):
    pass


class WechatCheckStatusRequest(BaseRequest):
    token: str = ""


class WechatClearTokenRequest(BaseRequest):
    pass


# ============================================================================
# Token Usage
# ============================================================================
class TokenGetUsageRequest(BaseRequest):
    scope: str = "global"
    scope_id: str | None = None
    instance_id: int | None = None
    session_instance_id: int | None = None
    days: int = 7


# ============================================================================
# TTS
# ============================================================================
class TTSGetInstanceConfigRequest(BaseRequest):
    instance_id: int | None = None


class TTSUpdateInstanceConfigRequest(BaseRequest):
    instance_id: int | None = None
    enabled: bool | None = None
    config: dict[str, Any] = {}


class TTSGetDefaultsRequest(BaseRequest):
    pass


class TTSSetDefaultsRequest(BaseRequest):
    config: dict[str, Any] = {}


class TTSGetVoicesRequest(BaseRequest):
    provider: str | None = None


class TTSSynthesizeRequest(BaseRequest):
    text: str = ""
    provider: str | None = None
    voice: str | None = None
    model: str | None = None


class TTSGetProvidersRequest(BaseRequest):
    pass


class TTSGetStylesRequest(BaseRequest):
    provider: str | None = None


# ============================================================================
# Extensions
# ============================================================================
class ExtensionGetListRequest(BaseRequest):
    source: str = "installed"


class ExtensionInstallRequest(BaseRequest):
    skill_id: str | None = None
    extension_id: str | None = None
    name: str | None = None


class ExtensionUninstallRequest(BaseRequest):
    extension_name: str = ""


class ExtensionRunRequest(BaseRequest):
    extension_name: str = ""
    action: str = ""
    params: dict[str, Any] = {}


class ExtensionConfigRequest(BaseRequest):
    extension_name: str = ""
    env: dict[str, str] = {}


class FilePreviewPDFRequest(BaseRequest):
    path: str = ""


# ============================================================================
# Mapping from MessageType to schema
# ============================================================================
from backend.channels.desktop.protocol import MessageType

MESSAGE_TYPE_TO_SCHEMA: dict[MessageType | str, type[BaseRequest]] = {
    MessageType.CHAT: ChatRequest,
    MessageType.GET_CONFIG: GetConfigRequest,
    MessageType.SAVE_CONFIG: SaveConfigRequest,
    MessageType.PING: PingRequest,
    MessageType.GET_MODELS: GetModelsRequest,
    MessageType.STOP_AGENTS: StopAgentsRequest,
    MessageType.RESTART_SERVICE: RestartServiceRequest,

    MessageType.MCP_GET_STATUS: MCPGetStatusRequest,
    MessageType.MCP_GET_SERVERS: MCPGetServersRequest,
    MessageType.MCP_GET_SERVER_TOOLS: MCPGetServerToolsRequest,
    MessageType.MCP_ADD_SERVER: MCPAddServerRequest,
    MessageType.MCP_DELETE_SERVER: MCPDeleteServerRequest,
    MessageType.MCP_UPDATE_SERVER: MCPUpdateServerRequest,
    MessageType.MCP_UPDATE_TOOL: MCPUpdateToolRequest,
    MessageType.MCP_DISCOVER_TOOLS: MCPDiscoverToolsRequest,
    MessageType.MCP_CONNECT_SERVER: MCPConnectServerRequest,
    MessageType.MCP_RECONNECT_SERVER: MCPReconnectServerRequest,
    MessageType.MCP_DISCONNECT_SERVER: MCPDisconnectServerRequest,
    MessageType.MCP_CALL_TOOL: MCPCallToolRequest,
    MessageType.MCP_GET_CONFIG: MCPGetConfigRequest,
    MessageType.MCP_UPDATE_CONFIG: MCPUpdateConfigRequest,

    MessageType.SESSION_GET_CHANNELS: SessionGetChannelsRequest,
    MessageType.SESSION_GET_CHANNEL_SESSIONS: SessionGetChannelSessionsRequest,
    MessageType.SESSION_GET_SESSION_DETAIL: SessionGetSessionDetailRequest,
    MessageType.SESSION_GET_MESSAGES: SessionGetMessagesRequest,
    MessageType.SESSION_DELETE_INSTANCE: SessionDeleteInstanceRequest,
    MessageType.SESSION_CREATE: SessionCreateRequest,
    MessageType.SESSION_SET_ACTIVE: SessionSetActiveRequest,
    MessageType.SESSION_GET_INSTANCES: SessionGetInstancesRequest,
    MessageType.SESSION_COMPRESS_CONTEXT: SessionCompressContextRequest,
    MessageType.SESSION_GET_CONTEXT_STATS: SessionGetContextStatsRequest,

    MessageType.KNOWLEDGE_LIST: KnowledgeListRequest,
    MessageType.KNOWLEDGE_READ: KnowledgeReadRequest,
    MessageType.KNOWLEDGE_WRITE: KnowledgeWriteRequest,
    MessageType.KNOWLEDGE_DELETE: KnowledgeDeleteRequest,
    MessageType.KNOWLEDGE_SEARCH: KnowledgeSearchRequest,
    MessageType.KNOWLEDGE_GRAPH: KnowledgeGraphRequest,
    MessageType.KNOWLEDGE_DISTILL: KnowledgeDistillRequest,
    MessageType.KNOWLEDGE_DISTILL_PREVIEW: KnowledgeDistillPreviewRequest,
    MessageType.KNOWLEDGE_DISTILL_LIST: KnowledgeDistillListRequest,
    MessageType.KNOWLEDGE_DISTILL_DETAIL: KnowledgeDistillDetailRequest,
    MessageType.KNOWLEDGE_GET_TAGS: KnowledgeGetTagsRequest,
    MessageType.KNOWLEDGE_EXPORT: KnowledgeExportRequest,
    MessageType.KNOWLEDGE_IMPORT: KnowledgeImportRequest,
    MessageType.KNOWLEDGE_GET_DOCUMENT_META: KnowledgeGetDocumentMetaRequest,
    MessageType.FILE_PREVIEW_PDF: FilePreviewPDFRequest,

    MessageType.MEMORY_LIST: MemoryListRequest,
    MessageType.MEMORY_SEARCH: MemorySearchRequest,
    MessageType.MEMORY_READ: MemoryReadRequest,
    MessageType.MEMORY_TIMELINE: MemoryTimelineRequest,
    MessageType.MEMORY_DELETE: MemoryDeleteRequest,

    MessageType.WORKSPACE_GET_ROOT: WorkspaceGetRootRequest,
    MessageType.WORKSPACE_LIST: WorkspaceListRequest,
    MessageType.WORKSPACE_READ: WorkspaceReadRequest,
    MessageType.WORKSPACE_WRITE: WorkspaceWriteRequest,
    MessageType.WORKSPACE_WRITE_CHUNK: WorkspaceWriteChunkRequest,
    MessageType.WORKSPACE_DELETE: WorkspaceDeleteRequest,
    MessageType.WORKSPACE_MKDIR: WorkspaceMkdirRequest,
    MessageType.WORKSPACE_RENAME: WorkspaceRenameRequest,

    MessageType.CRON_GET_JOBS: CronGetJobsRequest,
    MessageType.CRON_ADD_JOB: CronAddJobRequest,
    MessageType.CRON_DELETE_JOB: CronDeleteJobRequest,
    MessageType.CRON_TOGGLE_JOB: CronToggleJobRequest,
    MessageType.CRON_RUN_JOB: CronRunJobRequest,

    MessageType.AGENT_GET_LIST: AgentGetListRequest,
    MessageType.AGENT_GET_SOUL: AgentGetSoulRequest,
    MessageType.AGENT_SAVE_SOUL: AgentSaveSoulRequest,
    MessageType.AGENT_DELETE: AgentDeleteRequest,
    MessageType.AGENT_GET_SYSTEM_FILES: AgentGetSystemFilesRequest,
    MessageType.AGENT_GET_SYSTEM_FILE: AgentGetSystemFileRequest,
    MessageType.AGENT_SAVE_SYSTEM_FILE: AgentSaveSystemFileRequest,

    MessageType.SUBAGENT_GET_AVAILABLE_TOOLS: SubagentGetAvailableToolsRequest,
    MessageType.SUBAGENT_GET_AVAILABLE_EXTENSIONS: SubagentGetAvailableExtensionsRequest,
    MessageType.SUBAGENT_GET_PROVIDER_MODELS: SubagentGetProviderModelsRequest,

    MessageType.IMAGE_UPLOAD: ImageUploadRequest,
    MessageType.FILE_UPLOAD: FileUploadRequest,
    MessageType.IMAGE_ANALYZE: ImageAnalyzeRequest,
    MessageType.IMAGE_GENERATE: ImageGenerateRequest,
    MessageType.IMAGE_GET_UNDERSTANDING_PROVIDERS: ImageGetUnderstandingProvidersRequest,
    MessageType.IMAGE_GET_GENERATION_PROVIDERS: ImageGetGenerationProvidersRequest,
    MessageType.IMAGE_ADD_UNDERSTANDING_PROVIDER: ImageAddUnderstandingProviderRequest,
    MessageType.IMAGE_UPDATE_UNDERSTANDING_PROVIDER: ImageUpdateUnderstandingProviderRequest,
    MessageType.IMAGE_DELETE_UNDERSTANDING_PROVIDER: ImageDeleteUnderstandingProviderRequest,
    MessageType.IMAGE_ADD_GENERATION_PROVIDER: ImageAddGenerationProviderRequest,
    MessageType.IMAGE_UPDATE_GENERATION_PROVIDER: ImageUpdateGenerationProviderRequest,
    MessageType.IMAGE_DELETE_GENERATION_PROVIDER: ImageDeleteGenerationProviderRequest,

    MessageType.PROVIDER_GET_ALL: ProviderGetAllRequest,
    MessageType.PROVIDER_GET: ProviderGetRequest,
    MessageType.PROVIDER_ADD: ProviderAddRequest,
    MessageType.PROVIDER_UPDATE: ProviderUpdateRequest,
    MessageType.PROVIDER_DELETE: ProviderDeleteRequest,
    MessageType.PROVIDER_ENABLE: ProviderEnableRequest,

    MessageType.MODEL_GET_ALL: ModelGetAllRequest,
    MessageType.MODEL_GET: ModelGetRequest,
    MessageType.MODEL_ADD: ModelAddRequest,
    MessageType.MODEL_UPDATE: ModelUpdateRequest,
    MessageType.MODEL_DELETE: ModelDeleteRequest,
    MessageType.MODEL_SET_DEFAULT: ModelSetDefaultRequest,

    MessageType.SETTINGS_GET: SettingsGetRequest,
    MessageType.SETTINGS_SET: SettingsSetRequest,

    MessageType.AGENT_DEFAULTS_GET: AgentDefaultsGetRequest,
    MessageType.AGENT_DEFAULTS_UPDATE: AgentDefaultsUpdateRequest,
    MessageType.GET_ENABLED_MODELS: GetEnabledModelsRequest,

    MessageType.CHANNEL_GET_LIST: ChannelGetListRequest,
    MessageType.CHANNEL_UPDATE: ChannelUpdateRequest,
    MessageType.CHANNEL_DELETE: ChannelDeleteRequest,

    MessageType.WECHAT_GET_QRCODE: WechatGetQrcodeRequest,
    MessageType.WECHAT_CHECK_STATUS: WechatCheckStatusRequest,
    MessageType.WECHAT_CLEAR_TOKEN: WechatClearTokenRequest,

    MessageType.TOOL_GET_CONFIG: ToolGetConfigRequest,
    MessageType.TOOL_UPDATE_CONFIG: ToolUpdateConfigRequest,

    MessageType.IMAGE_GET_PROVIDERS: ImageGetProvidersRequest,
    MessageType.IMAGE_SET_DEFAULT_PROVIDER: ImageSetDefaultProviderRequest,

    MessageType.TOKEN_GET_USAGE: TokenGetUsageRequest,

    MessageType.TTS_GET_INSTANCE_CONFIG: TTSGetInstanceConfigRequest,
    MessageType.TTS_UPDATE_INSTANCE_CONFIG: TTSUpdateInstanceConfigRequest,
    MessageType.TTS_GET_DEFAULTS: TTSGetDefaultsRequest,
    MessageType.TTS_SET_DEFAULTS: TTSSetDefaultsRequest,
    MessageType.TTS_GET_VOICES: TTSGetVoicesRequest,
    MessageType.TTS_SYNTHESIZE: TTSSynthesizeRequest,
    MessageType.TTS_GET_PROVIDERS: TTSGetProvidersRequest,
    MessageType.TTS_GET_STYLES: TTSGetStylesRequest,

    MessageType.EXTENSION_GET_LIST: ExtensionGetListRequest,
    MessageType.EXTENSION_INSTALL: ExtensionInstallRequest,
    MessageType.EXTENSION_UNINSTALL: ExtensionUninstallRequest,
    MessageType.EXTENSION_RUN: ExtensionRunRequest,
    MessageType.EXTENSION_CONFIG: ExtensionConfigRequest,
}

# Also index by string value for fast lookup
_string_map = {mt.value: schema for mt, schema in MESSAGE_TYPE_TO_SCHEMA.items() if hasattr(mt, "value")}
MESSAGE_TYPE_TO_SCHEMA.update(_string_map)
