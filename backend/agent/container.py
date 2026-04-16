"""Agent dependency injection container."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.config.schema import ExecToolConfig
from backend.core.providers.base import LLMProvider
from backend.data import Database
from backend.agent.config_service import AgentConfigService
from backend.agent.context import ContextBuilder
from backend.agent.compressor import ContextCompressor
from backend.agent.memory_manager import MemoryManager
from backend.agent.observation_manager import ObservationManager
from backend.agent.shared import _extract_cached_tokens, _extract_prompt_tokens_with_cache
from backend.agent.subagent import SubagentManager
from backend.agent.aggregator import SubagentAggregator
from backend.data.session_manager import SessionManager
from backend.data.token_store import TokenUsageRepository
from backend.extensions.loader import ExtensionLoader
from backend.tools.registry import ToolRegistry
from backend.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from backend.tools.shell import ExecTool
from backend.tools.message import MessageTool
from backend.tools.spawn import SpawnTool
from backend.tools.cron import CronTool
from backend.tools.action import ActionTool
from backend.tools.image import ImageUnderstandTool, ImageGenerateTool
from backend.tools.web_fetch import WebFetchTool
from backend.tools.knowledge import KBSearchTool, KBReadNoteTool, KBListLinksTool, KBTimelineTool
from backend.tools.memory import MemorySearchTool, MemoryReadTool, MemoryTimelineTool
from backend.tools.browser.registration import register_browser_tools


@dataclass
class AgentContainer:
    """Holds all runtime dependencies for the agent loop."""

    bus: Any
    workspace: Path
    max_iterations: int = 20
    exec_config: ExecToolConfig | None = None
    cron_service: Any | None = None
    db: Database | None = None
    subagent_manager: SubagentManager | None = None
    mcp_bridge: Any | None = None

    context: ContextBuilder = field(init=False)
    sessions: SessionManager = field(init=False)
    tools: ToolRegistry = field(init=False)
    token_usage: TokenUsageRepository = field(init=False)
    compressor: ContextCompressor = field(init=False)
    aggregator: SubagentAggregator = field(init=False)
    subagents: SubagentManager = field(init=False)
    extension_loader: ExtensionLoader = field(init=False)
    memory_manager: MemoryManager = field(init=False)
    observation_manager: ObservationManager = field(init=False)

    def __post_init__(self):
        self.exec_config = self.exec_config or ExecToolConfig()
        self.db = self.db or Database()

        self.observation_manager = ObservationManager(
            db=self.db,
            get_provider_and_model=self._get_current_provider_and_model,
            record_token_usage=self._record_token_usage,
        )
        self.memory_manager = MemoryManager(
            workspace=self.workspace,
            observation_manager=self.observation_manager,
        )
        self.context = ContextBuilder(self.workspace, memory_manager=self.memory_manager)
        self.sessions = SessionManager(self.workspace, db=self.db)
        self.tools = ToolRegistry(mcp_bridge=self.mcp_bridge)
        self.token_usage = TokenUsageRepository(self.db)
        self.aggregator = SubagentAggregator(self.bus)

        if self.subagent_manager:
            self.subagents = self.subagent_manager
        else:
            self.subagents = SubagentManager(
                workspace=self.workspace,
                bus=self.bus,
                exec_config=self.exec_config,
                aggregator=self.aggregator,
            )

        self.extension_loader = ExtensionLoader(workspace=self.workspace)
        self.compressor = ContextCompressor(
            db=self.db,
            sessions=self.sessions,
            token_usage=self.token_usage,
            get_provider_and_model=self._get_current_provider_and_model,
            record_token_usage=self._record_token_usage,
            observation_manager=self.observation_manager,
        )

        self._register_default_tools()

    @property
    def tts_service(self):
        """Lazy-load TTS service to avoid circular imports."""
        from backend.services.tts_service import TTSServiceFactory
        if not hasattr(self, '_tts_service'):
            self._tts_service = TTSServiceFactory.create_service(self.db)
        return self._tts_service

    def _get_current_provider_and_model(self) -> tuple[LLMProvider, str, str, int, float]:
        """Get current provider, model, provider_type, max_tokens, and temperature from database."""
        config_service = AgentConfigService(self.db)
        return config_service.get_default_provider_and_model()

    def _record_token_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        usage: dict,
        request_type: str = "chat"
    ) -> None:
        """Record token usage to database."""
        try:
            prompt_tokens = _extract_prompt_tokens_with_cache(usage)
            completion_tokens = usage.get("completion_tokens", 0)
            cached_tokens = _extract_cached_tokens(usage)

            self.token_usage.record_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_name,
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                request_type=request_type
            )

            logger.debug(f"Token usage recorded: {provider_name}/{model_id} - "
                        f"prompt={prompt_tokens}, completion={completion_tokens}, cached={cached_tokens}")
        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")

    def _register_default_tools(self) -> None:
        """Register the built-in tool set, respecting agent defaults configuration."""
        enabled_tools = set()
        try:
            from backend.data.provider_store import AgentDefaultsRepository
            repo = AgentDefaultsRepository(self.db)
            defaults = repo.get_agent_defaults()
            if defaults and defaults.tools:
                enabled_tools = set(defaults.tools)
        except Exception as e:
            logger.warning(f"Failed to load agent default tools: {e}")

        use_all = not enabled_tools

        def should_register(name: str) -> bool:
            return use_all or name in enabled_tools

        if should_register("read"):
            self.tools.register(ReadFileTool())
        if should_register("write"):
            self.tools.register(WriteFileTool())
        if should_register("edit"):
            self.tools.register(EditFileTool())
        if should_register("list"):
            self.tools.register(ListDirTool())
        if should_register("exec"):
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
            ))
        if should_register("message"):
            self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        if should_register("spawn"):
            self.tools.register(SpawnTool(manager=self.subagents, aggregator=self.aggregator))
        if should_register("web_fetch"):
            self.tools.register(WebFetchTool())
        if should_register("kb_search"):
            self.tools.register(KBSearchTool())
        if should_register("kb_read_note"):
            self.tools.register(KBReadNoteTool())
        if should_register("kb_list_links"):
            self.tools.register(KBListLinksTool())
        if should_register("kb_timeline"):
            self.tools.register(KBTimelineTool())
        if should_register("image_understand"):
            self.tools.register(ImageUnderstandTool())
        if should_register("image_generate"):
            self.tools.register(ImageGenerateTool())
        if should_register("cron"):
            self.tools.register(CronTool(cron_service=self.cron_service))
        if should_register("action"):
            self.tools.register(ActionTool())
        if should_register("memory_search"):
            self.tools.register(MemorySearchTool())
        if should_register("memory_read"):
            self.tools.register(MemoryReadTool())
        if should_register("memory_timeline"):
            self.tools.register(MemoryTimelineTool())
        if should_register("memory_write"):
            from backend.tools.memory_write import MemoryWriteTool
            self.tools.register(MemoryWriteTool(store=self.memory_manager.builtin))
        if use_all or any(t in enabled_tools for t in ["browser_snapshot", "browser_click", "browser_type", "browser_navigate"]):
            register_browser_tools(self.tools)
        logger.info(f"Default tools registered (enabled: {len(self.tools)} tools)")
