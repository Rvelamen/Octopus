"""Handler registry for Desktop channel."""

import asyncio
import time
from pathlib import Path
from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.schemas import MESSAGE_TYPE_TO_SCHEMA
from pydantic import ValidationError
from backend.channels.desktop.provider_handlers import (
    ProviderHandler, ModelHandler, SettingsHandler, AgentDefaultsHandler,
    ChannelConfigHandler, ToolConfigHandler, ImageProviderConfigHandler
)
from backend.channels.desktop.wechat_handler import WechatConfigHandler
from backend.core.events.bus import MessageBus
from backend.mcp.manager import MCPManager

# Import handlers from extensions (unified extension system)
from backend.extensions.desktop_handlers import (
    ExtensionGetListHandler,
    ExtensionInstallHandler,
    ExtensionUninstallHandler,
    ExtensionRunHandler,
    ExtensionConfigHandler,
)

# Import chat handlers
from backend.channels.desktop.handlers.chat import ChatHandler

# Import config handlers
from backend.channels.desktop.handlers.config import (
    GetConfigHandler, SaveConfigHandler, PingHandler, StopAgentsHandler
)

# Import models handlers
from backend.channels.desktop.handlers.models import GetModelsHandler

# Import MCP handlers
from backend.channels.desktop.handlers.mcp import (
    MCPGetStatusHandler, TTSHandler, MCPGetServersHandler,
    MCPGetServerToolsHandler, MCPAddServerHandler, MCPDeleteServerHandler,
    MCPUpdateServerHandler, MCPUpdateToolHandler, MCPDiscoverToolsHandler,
    MCPConnectServerHandler, MCPDisconnectServerHandler, MCPReconnectServerHandler,
    MCPCallToolHandler, MCPGetConfigHandler, MCPUpdateConfigHandler
)

# Import session handlers
from backend.channels.desktop.handlers.session import (
    SessionGetChannelsHandler, SessionGetChannelSessionsHandler,
    SessionGetSessionDetailHandler, SessionGetMessagesHandler,
    SessionDeleteInstanceHandler, SessionCreateHandler,
    SessionSetActiveHandler, SessionGetInstancesHandler,
    SessionCompressContextHandler, SessionGetContextStatsHandler
)

# Import memory handlers
from backend.channels.desktop.handlers.memory import (
    MemoryListHandler, MemorySearchHandler, MemoryReadHandler,
    MemoryTimelineHandler, MemoryDeleteHandler, MemoryExtractHandler,
    MemoryPromoteHandler
)

# Import workspace handlers
from backend.channels.desktop.handlers.workspace import (
    WorkspaceGetRootHandler, WorkspaceListHandler, WorkspaceReadHandler,
    WorkspaceWriteHandler, WorkspaceWriteChunkHandler, WorkspaceDeleteHandler, WorkspaceMkdirHandler,
    WorkspaceRenameHandler
)

# Import cron handlers
from backend.channels.desktop.handlers.cron import (
    CronGetJobsHandler, CronAddJobHandler, CronDeleteJobHandler,
    CronToggleJobHandler, CronRunJobHandler
)

# Import agent handlers
from backend.channels.desktop.handlers.agent import (
    AgentGetListHandler, AgentGetSoulHandler, AgentSaveSoulHandler,
    AgentDeleteHandler, AgentGetSystemFilesHandler, AgentGetSystemFileHandler,
    AgentSaveSystemFileHandler
)

# Import subagent handlers
from backend.channels.desktop.handlers.subagent import (
    SubagentGetAvailableToolsHandler, SubagentGetAvailableExtensionsHandler,
    SubagentGetProviderModelsHandler
)

# Import token handlers
from backend.channels.desktop.handlers.token import TokenUsageHandler

# Import image handlers
from backend.channels.desktop.handlers.image import (
    ImageUploadHandler, FileUploadHandler, ImageAnalyzeHandler,
    ImageGenerateHandler, ImageGetUnderstandingProvidersHandler,
    ImageGetGenerationProvidersHandler
)

# Import knowledge handlers
from backend.channels.desktop.handlers.knowledge import (
    KnowledgeListHandler, KnowledgeReadHandler, KnowledgeWriteHandler,
    KnowledgeDeleteHandler, KnowledgeSearchHandler, KnowledgeGraphHandler,
    KnowledgeDistillHandler, KnowledgeDistillListHandler,
    KnowledgeDistillDetailHandler, KnowledgeGetTagsHandler, KnowledgeExportHandler, KnowledgeImportHandler,
    KnowledgeGetDocumentMetaHandler,
)
from backend.channels.desktop.handlers.file_preview import FilePreviewPDFHandler

from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.services.knowledge_task_queue import KnowledgeTaskQueue
from backend.services.knowledge_task_worker import KnowledgeTaskWorker


class HandlerRegistry:
    """Registry for message handlers."""

    def __init__(self, bus: MessageBus, pending_responses: dict[str, asyncio.Queue], mcp_manager: MCPManager | None = None, cron_service=None, db=None, agent_loop=None, subagent_manager=None):
        from backend.data import Database
        self.mcp_manager = mcp_manager
        self.cron_service = cron_service
        self.db = db or Database()
        self.agent_loop = agent_loop
        self.subagent_manager = subagent_manager

        from backend.data.provider_store import ProviderRepository, ModelRepository, SettingsRepository
        self.provider_handler_db = self.db
        self.model_handler_db = self.db
        self.settings_handler_db = self.db

        self.handlers: dict[MessageType, MessageHandler] = {
            MessageType.CHAT: ChatHandler(bus, pending_responses),
            MessageType.GET_CONFIG: GetConfigHandler(bus, self.db),
            MessageType.SAVE_CONFIG: SaveConfigHandler(bus),
            MessageType.PING: PingHandler(bus),
            MessageType.GET_MODELS: GetModelsHandler(bus, self.db),
            MessageType.STOP_AGENTS: StopAgentsHandler(bus, agent_loop, subagent_manager),
        }

        # Register MCP handlers if manager is available
        if mcp_manager:
            self.handlers.update({
                MessageType.MCP_GET_STATUS: MCPGetStatusHandler(bus, mcp_manager),
                MessageType.MCP_GET_SERVERS: MCPGetServersHandler(bus, mcp_manager),
                MessageType.MCP_GET_SERVER_TOOLS: MCPGetServerToolsHandler(bus, mcp_manager),
                MessageType.MCP_ADD_SERVER: MCPAddServerHandler(bus, mcp_manager),
                MessageType.MCP_DELETE_SERVER: MCPDeleteServerHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_SERVER: MCPUpdateServerHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_TOOL: MCPUpdateToolHandler(bus, mcp_manager),
                MessageType.MCP_DISCOVER_TOOLS: MCPDiscoverToolsHandler(bus, mcp_manager),
                MessageType.MCP_CONNECT_SERVER: MCPConnectServerHandler(bus, mcp_manager),
                MessageType.MCP_RECONNECT_SERVER: MCPReconnectServerHandler(bus, mcp_manager),
                MessageType.MCP_DISCONNECT_SERVER: MCPDisconnectServerHandler(bus, mcp_manager),
                MessageType.MCP_CALL_TOOL: MCPCallToolHandler(bus, mcp_manager),
                MessageType.MCP_GET_CONFIG: MCPGetConfigHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_CONFIG: MCPUpdateConfigHandler(bus, mcp_manager),
                MessageType.PROVIDER_GET_ALL: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_GET: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_ADD: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_UPDATE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_DELETE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_ENABLE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.MODEL_GET_ALL: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_ADD: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_UPDATE: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_DELETE: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_SET_DEFAULT: ModelHandler(bus, self.model_handler_db),
                MessageType.SETTINGS_GET: SettingsHandler(bus, self.settings_handler_db),
                MessageType.SETTINGS_SET: SettingsHandler(bus, self.settings_handler_db),
                MessageType.AGENT_DEFAULTS_GET: AgentDefaultsHandler(bus, self.db),
                MessageType.AGENT_DEFAULTS_UPDATE: AgentDefaultsHandler(bus, self.db),
                MessageType.GET_ENABLED_MODELS: AgentDefaultsHandler(bus, self.db),
                MessageType.CHANNEL_GET_LIST: ChannelConfigHandler(bus, self.db),
                MessageType.CHANNEL_UPDATE: ChannelConfigHandler(bus, self.db),
                MessageType.CHANNEL_DELETE: ChannelConfigHandler(bus, self.db),
                MessageType.WECHAT_GET_QRCODE: WechatConfigHandler(bus, self.db),
                MessageType.WECHAT_CHECK_STATUS: WechatConfigHandler(bus, self.db),
                MessageType.WECHAT_CLEAR_TOKEN: WechatConfigHandler(bus, self.db),
                MessageType.TOOL_GET_CONFIG: ToolConfigHandler(bus, self.db),
                MessageType.TOOL_UPDATE_CONFIG: ToolConfigHandler(bus, self.db),
                MessageType.IMAGE_GET_PROVIDERS: ImageProviderConfigHandler(bus, self.db),
                MessageType.IMAGE_SET_DEFAULT_PROVIDER: ImageProviderConfigHandler(bus, self.db),
                MessageType.TOKEN_GET_USAGE: TokenUsageHandler(bus, self.db),
            })

        # Register Extension handlers (unified)
        self.handlers.update({
            MessageType.EXTENSION_GET_LIST: ExtensionGetListHandler(bus),
            MessageType.EXTENSION_INSTALL: ExtensionInstallHandler(bus, pending_responses),
            MessageType.EXTENSION_UNINSTALL: ExtensionUninstallHandler(bus),
            MessageType.EXTENSION_RUN: ExtensionRunHandler(bus, pending_responses),
            MessageType.EXTENSION_CONFIG: ExtensionConfigHandler(bus),
        })

        # Register Session History handlers
        self.handlers.update({
            MessageType.SESSION_GET_CHANNELS: SessionGetChannelsHandler(bus),
            MessageType.SESSION_GET_CHANNEL_SESSIONS: SessionGetChannelSessionsHandler(bus),
            MessageType.SESSION_GET_SESSION_DETAIL: SessionGetSessionDetailHandler(bus),
            MessageType.SESSION_GET_MESSAGES: SessionGetMessagesHandler(bus),
            MessageType.SESSION_DELETE_INSTANCE: SessionDeleteInstanceHandler(bus),
            MessageType.SESSION_CREATE: SessionCreateHandler(bus, self.agent_loop),
            MessageType.SESSION_SET_ACTIVE: SessionSetActiveHandler(bus, self.agent_loop),
            MessageType.SESSION_GET_INSTANCES: SessionGetInstancesHandler(bus),
            MessageType.SESSION_COMPRESS_CONTEXT: SessionCompressContextHandler(bus, self.agent_loop),
            MessageType.SESSION_GET_CONTEXT_STATS: SessionGetContextStatsHandler(bus),
        })

        # Register Memory Stream handlers
        self.handlers.update({
            MessageType.MEMORY_LIST: MemoryListHandler(bus),
            MessageType.MEMORY_SEARCH: MemorySearchHandler(bus),
            MessageType.MEMORY_READ: MemoryReadHandler(bus),
            MessageType.MEMORY_TIMELINE: MemoryTimelineHandler(bus),
            MessageType.MEMORY_DELETE: MemoryDeleteHandler(bus),
            MessageType.MEMORY_EXTRACT: MemoryExtractHandler(bus, self.agent_loop),
            MessageType.MEMORY_PROMOTE: MemoryPromoteHandler(bus, self.agent_loop),
        })

        # Register Workspace File System handlers
        self.handlers.update({
            MessageType.WORKSPACE_GET_ROOT: WorkspaceGetRootHandler(bus),
            MessageType.WORKSPACE_LIST: WorkspaceListHandler(bus),
            MessageType.WORKSPACE_READ: WorkspaceReadHandler(bus),
            MessageType.WORKSPACE_WRITE: WorkspaceWriteHandler(bus),
            MessageType.WORKSPACE_WRITE_CHUNK: WorkspaceWriteChunkHandler(),
            MessageType.WORKSPACE_DELETE: WorkspaceDeleteHandler(bus),
            MessageType.WORKSPACE_MKDIR: WorkspaceMkdirHandler(bus),
            MessageType.WORKSPACE_RENAME: WorkspaceRenameHandler(bus),
        })

        # Register Cron Job handlers
        self.handlers.update({
            MessageType.CRON_GET_JOBS: CronGetJobsHandler(bus, cron_service),
            MessageType.CRON_ADD_JOB: CronAddJobHandler(bus, cron_service),
            MessageType.CRON_DELETE_JOB: CronDeleteJobHandler(bus, cron_service),
            MessageType.CRON_TOGGLE_JOB: CronToggleJobHandler(bus, cron_service),
            MessageType.CRON_RUN_JOB: CronRunJobHandler(bus, cron_service),
        })

        # Register Agent handlers
        self.handlers.update({
            MessageType.AGENT_GET_LIST: AgentGetListHandler(bus, db),
            MessageType.AGENT_GET_SOUL: AgentGetSoulHandler(bus, db),
            MessageType.AGENT_SAVE_SOUL: AgentSaveSoulHandler(bus, db),
            MessageType.AGENT_DELETE: AgentDeleteHandler(bus, db),
            MessageType.AGENT_GET_SYSTEM_FILES: AgentGetSystemFilesHandler(bus),
            MessageType.AGENT_GET_SYSTEM_FILE: AgentGetSystemFileHandler(bus),
            MessageType.AGENT_SAVE_SYSTEM_FILE: AgentSaveSystemFileHandler(bus),
        })

        # Register Subagent Options handlers
        self.handlers.update({
            MessageType.SUBAGENT_GET_AVAILABLE_TOOLS: SubagentGetAvailableToolsHandler(bus, db),
            MessageType.SUBAGENT_GET_AVAILABLE_EXTENSIONS: SubagentGetAvailableExtensionsHandler(bus, db),
            MessageType.SUBAGENT_GET_PROVIDER_MODELS: SubagentGetProviderModelsHandler(bus, db),
        })

        # Register Image handlers
        self.handlers.update({
            MessageType.IMAGE_UPLOAD: ImageUploadHandler(bus),
            MessageType.FILE_UPLOAD: FileUploadHandler(bus),
            MessageType.IMAGE_ANALYZE: ImageAnalyzeHandler(bus),
            MessageType.IMAGE_GENERATE: ImageGenerateHandler(bus),
            MessageType.IMAGE_GET_UNDERSTANDING_PROVIDERS: ImageGetUnderstandingProvidersHandler(bus),
            MessageType.IMAGE_GET_GENERATION_PROVIDERS: ImageGetGenerationProvidersHandler(bus),
        })

        # Register TTS handlers
        self.handlers.update({
            MessageType.TTS_GET_INSTANCE_CONFIG: TTSHandler(bus, self.db),
            MessageType.TTS_UPDATE_INSTANCE_CONFIG: TTSHandler(bus, self.db),
            MessageType.TTS_GET_DEFAULTS: TTSHandler(bus, self.db),
            MessageType.TTS_SET_DEFAULTS: TTSHandler(bus, self.db),
            MessageType.TTS_SYNTHESIZE: TTSHandler(bus, self.db),
            MessageType.TTS_GET_VOICES: TTSHandler(bus, self.db),
            MessageType.TTS_GET_PROVIDERS: TTSHandler(bus, self.db),
            MessageType.TTS_GET_STYLES: TTSHandler(bus, self.db),
        })

        # Register Knowledge Base handlers
        from backend.utils.helpers import get_workspace_path
        workspace_root = str(get_workspace_path())
        knowledge_engine = KnowledgeGraphEngine(workspace_root)
        task_queue_db = Path(workspace_root) / "knowledge" / ".distill_tasks.db"
        self.knowledge_task_queue = KnowledgeTaskQueue(task_queue_db)
        self.knowledge_task_worker = KnowledgeTaskWorker(
            queue=self.knowledge_task_queue,
            bus=bus,
            engine=knowledge_engine,
            workspace_root=Path(workspace_root),
            subagent_manager=self.agent_loop.subagents,
        )
        self.knowledge_task_worker.start()

        self.handlers.update({
            MessageType.KNOWLEDGE_LIST: KnowledgeListHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_READ: KnowledgeReadHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_WRITE: KnowledgeWriteHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_DELETE: KnowledgeDeleteHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_SEARCH: KnowledgeSearchHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_GRAPH: KnowledgeGraphHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_DISTILL: KnowledgeDistillHandler(bus, self.knowledge_task_queue),
            MessageType.KNOWLEDGE_DISTILL_LIST: KnowledgeDistillListHandler(bus, self.knowledge_task_queue),
            MessageType.KNOWLEDGE_DISTILL_DETAIL: KnowledgeDistillDetailHandler(bus, self.knowledge_task_queue),
            MessageType.KNOWLEDGE_GET_TAGS: KnowledgeGetTagsHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_EXPORT: KnowledgeExportHandler(bus, knowledge_engine, self.knowledge_task_queue),
            MessageType.KNOWLEDGE_IMPORT: KnowledgeImportHandler(bus, knowledge_engine),
            MessageType.KNOWLEDGE_GET_DOCUMENT_META: KnowledgeGetDocumentMetaHandler(bus, knowledge_engine),
            MessageType.FILE_PREVIEW_PDF: FilePreviewPDFHandler(bus),
        })

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Route message to appropriate handler with timing, structured logging, and Pydantic validation."""
        handler = self.handlers.get(message.type)
        msg_type_str = message.type.value if hasattr(message.type, "value") else str(message.type)
        request_id = message.request_id
        start = time.perf_counter()
        error_info: str | None = None

        if handler:
            # Try Pydantic validation + handle_validated
            schema = MESSAGE_TYPE_TO_SCHEMA.get(message.type) or MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
            validated = None
            if schema is not None:
                try:
                    validated = schema.model_validate(message.data)
                except ValidationError as ve:
                    error_info = f"Validation error: {ve}"
                    logger.warning(f"Validation error for {msg_type_str}: {ve}")
                    await websocket.send_json(WSMessage(
                        type=MessageType.ERROR,
                        request_id=request_id,
                        data={"error": "Invalid request data", "details": ve.errors()}
                    ).to_dict())
                    duration_ms = round((time.perf_counter() - start) * 1000, 2)
                    logger.bind(event="ws_handler_metric", message_type=msg_type_str, request_id=request_id,
                                duration_ms=duration_ms, success=False, error=error_info)
                    return

            try:
                if validated is not None:
                    try:
                        await handler.handle_validated(websocket, message, validated)
                    except (NotImplementedError, AttributeError):
                        await handler.handle(websocket, message)
                else:
                    await handler.handle(websocket, message)
            except Exception as e:
                error_info = str(e)
                logger.error(f"Handler error for {message.type}: {e}")
                await websocket.send_json(WSMessage(
                    type=MessageType.ERROR,
                    request_id=request_id,
                    data={"error": f"Internal error: {str(e)}"}
                ).to_dict())
        else:
            error_info = f"Unknown message type: {msg_type_str}"
            logger.warning(f"No handler for message type: {message.type}")
            await websocket.send_json(WSMessage(
                type=MessageType.ERROR,
                request_id=request_id,
                data={"error": error_info}
            ).to_dict())

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_payload = {
            "event": "ws_handler_metric",
            "message_type": msg_type_str,
            "request_id": request_id,
            "duration_ms": duration_ms,
            "success": error_info is None,
        }
        if error_info:
            log_payload["error"] = error_info
        # logger.bind(**log_payload).info("WS handler finished")

