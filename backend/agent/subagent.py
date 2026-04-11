"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage, AgentEvent
from backend.core.events.bus import MessageBus
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import create_provider
from backend.agent.config_service import AgentConfigService
from backend.tools.registry import ToolRegistry
from backend.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool, EditFileTool
from backend.tools.shell import ExecTool

from backend.tools.action import ActionTool
from backend.tools.message import MessageTool
from backend.extensions.loader import SkillsLoader
from backend.agent.loader import SubAgentLoader, SubAgentConfig
from backend.agent.aggregator import SubagentAggregator
from backend.agent.compressor import compress_messages
from backend.data import Database, TokenUsageRepository


class SubagentManager:
    """
    Manages background subagent execution with role-based configuration.
    
    Subagents are lightweight agent instances that run in the background
    to handle specific tasks. Each subagent can have its own:
    - Provider and model (from SOUL.md config)
    - Tools (configured in SOUL.md)
    - Extensions/skills (configured in SOUL.md)
    - System prompt (from SOUL.md content)
    """
    
    def __init__(
        self,
        workspace: Path,
        bus: MessageBus,
        exec_config: "ExecToolConfig | None" = None,
        aggregator: SubagentAggregator | None = None,
    ):
        from backend.core.config.schema import ExecToolConfig
        self.workspace = workspace
        self.bus = bus
        self.exec_config = exec_config or ExecToolConfig()
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._stop_flags: dict[str, bool] = {}
        # Track which instance each subagent belongs to: { task_id: session_instance_id }
        self._task_instance_map: dict[str, int | None] = {}
        self._subagent_compression_enabled: bool = False
        self._subagent_compression_turns: int = 10
        self._subagent_compression_token_threshold: int = 200000
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace)
        self._aggregator = aggregator
        self._token_usage = TokenUsageRepository(Database())
        
        # 同步任务追踪
        self._sync_tasks: dict[str, asyncio.Future] = {}  # task_id -> future
        self._task_token_usage: dict[str, dict] = {}  # task_id -> token_usage
        
        # 任务上下文追踪：用于事件路由
        self._task_contexts: dict[str, dict] = {}  # task_id -> {channel, chat_id, session_instance_id}

        if self._aggregator:
            self._aggregator.set_bus(bus)
    
    def _get_provider_for_config(self, config: SubAgentConfig) -> tuple[LLMProvider, str, str, int, float]:
        """Get provider, model, provider_type, max_tokens, and temperature for a subagent configuration."""
        config_service = AgentConfigService()
        defaults = config_service._get_agent_defaults_repo().get_or_create_defaults()
        max_tokens = getattr(defaults, 'max_tokens', 8192) or 8192
        temperature = getattr(defaults, 'temperature', 0.7) or 0.7

        if config.provider_id and config.model_id:
            from backend.data.provider_store import ProviderRepository, ModelRepository
            from backend.data import Database
            from backend.core.config.schema import AgentDefaults, ProviderConfig
            from backend.core.providers.factory import create_provider

            db = Database()
            provider_repo = ProviderRepository(db)
            model_repo = ModelRepository(db)

            provider_record = provider_repo.get_provider_by_id(config.provider_id)
            model_record = model_repo.get_model_by_id(config.model_id)

            if provider_record and model_record:
                provider_config = ProviderConfig(
                    type=provider_record.provider_type,
                    api_key=provider_record.api_key,
                    api_base=provider_record.api_host
                )

                agent_defaults = AgentDefaults(
                    provider=provider_record.name,
                    model=model_record.model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    llm_max_retries=getattr(defaults, 'llm_max_retries', 3) or 3,
                    llm_retry_base_delay=getattr(defaults, 'llm_retry_base_delay', 1.0) or 1.0,
                    llm_retry_max_delay=getattr(defaults, 'llm_retry_max_delay', 30.0) or 30.0,
                )

                providers_dict = {provider_record.name: provider_config}
                provider = create_provider(providers_dict, agent_defaults)

                self._subagent_compression_enabled = config_service.get_context_compression_enabled()
                self._subagent_compression_turns = config_service.get_context_compression_turns()
                self._subagent_compression_token_threshold = config_service.get_context_compression_token_threshold()

                return provider, model_record.model_id, provider_record.provider_type, max_tokens, temperature

        provider, model = config_service.get_provider_for_subagent(
            provider_name=config.provider,
            model_name=config.model
        )

        provider_record = config_service.get_provider_by_name(config.provider)
        provider_type = provider_record.provider_type if provider_record else "openai"

        self._subagent_compression_enabled = config_service.get_context_compression_enabled()
        self._subagent_compression_turns = config_service.get_context_compression_turns()
        self._subagent_compression_token_threshold = config_service.get_context_compression_token_threshold()

        return provider, model, provider_type, max_tokens, temperature
    
    def _get_default_provider_and_model(self) -> tuple[LLMProvider, str, str, int, float]:
        """Get default provider, model, provider_type, max_tokens, and temperature from database."""
        config_service = AgentConfigService()

        provider, model, provider_type, max_tokens, temperature = config_service.get_default_provider_and_model()

        self._subagent_compression_enabled = config_service.get_context_compression_enabled()
        self._subagent_compression_turns = config_service.get_context_compression_turns()
        self._subagent_compression_token_threshold = config_service.get_context_compression_token_threshold()
        
        return provider, model, provider_type
    
    async def _emit(
        self,
        event_type: str,
        data: dict,
        task_id: str,
    ) -> None:
        """发送事件到前端，用于显示 subagent 的执行状态"""
        context = self._task_contexts.get(task_id, {})
        channel = context.get("channel", "cli")
        parent_tool_call_id = context.get("parent_tool_call_id")
        
        # 添加 parent_tool_call_id 到事件数据
        if parent_tool_call_id:
            data["parent_tool_call_id"] = parent_tool_call_id
        
        # 调试日志 - 打印完整数据
        logger.info(f"[Subagent:{task_id}] Emitting event: {event_type}")
        logger.info(f"[Subagent:{task_id}]   channel={channel}, parent_tool_call_id={parent_tool_call_id}")
        logger.info(f"[Subagent:{task_id}]   data: tool={data.get('tool')}, tool_call_id={data.get('tool_call_id')}, args={str(data.get('args', {}))[:200]}")
        
        if hasattr(self.bus, 'publish_event'):
            try:
                await self.bus.publish_event(AgentEvent(
                    event_type=event_type,
                    data=data,
                    channel=channel
                ))
                logger.debug(f"[Subagent:{task_id}] Event {event_type} published successfully to channel={channel}")
            except Exception as e:
                logger.warning(f"[Subagent:{task_id}] Failed to emit event {event_type}: {e}")
    
    def _build_tools_for_config(self, config: SubAgentConfig, origin: dict[str, str]) -> ToolRegistry:
        """Build tool registry based on subagent configuration."""
        tools = ToolRegistry()
        
        # Map tool names to tool classes
        tool_mapping = {
            "read": ReadFileTool,
            "write": WriteFileTool,
            "edit": EditFileTool,
            "list": ListDirTool,
            "glob": ReadFileTool,
            "grep": ReadFileTool,
            "exec": lambda: ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
            ),
            "action": ActionTool,
            "message": lambda: MessageTool(send_callback=self.bus.publish_outbound),
        }
        
        # Register requested tools
        for tool_name in config.tools:
            tool_name_lower = tool_name.lower()
            if tool_name_lower in tool_mapping:
                try:
                    tool = tool_mapping[tool_name_lower]()
                    if isinstance(tool, MessageTool):
                        tool.set_context(origin.get("channel", ""), origin.get("chat_id", ""))
                    tools.register(tool)
                    logger.debug(f"Registered tool '{tool_name}' for subagent '{config.name}'")
                except Exception as e:
                    logger.warning(f"Failed to register tool '{tool_name}': {e}")
            else:
                logger.warning(f"Unknown tool '{tool_name}' requested by subagent '{config.name}'")
        
        # Always include message tool if not already added
        if "message" not in [t.lower() for t in config.tools]:
            message_tool = MessageTool(send_callback=self.bus.publish_outbound)
            message_tool.set_context(origin.get("channel", ""), origin.get("chat_id", ""))
            tools.register(message_tool)
        
        return tools
    
    def _build_default_tools(self, origin: dict[str, str]) -> ToolRegistry:
        """Build default tool registry for legacy subagents."""
        tools = ToolRegistry()
        tools.register(ReadFileTool())
        tools.register(WriteFileTool())
        tools.register(EditFileTool())
        tools.register(ListDirTool())
        tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
        ))
        tools.register(ActionTool())
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        message_tool.set_context(origin.get("channel", ""), origin.get("chat_id", ""))
        tools.register(message_tool)
        
        return tools
    
    def _load_bootstrap_files(self) -> str:
        """Load bootstrap files from system directory."""
        parts = []
        system_dir = self.workspace / "system"
        bootstrap_files = ["AGENTS.md", "SOUL.md", "USER.md"]
        
        for filename in bootstrap_files:
            file_path = system_dir / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _build_subagent_prompt(self, config: SubAgentConfig, task: str) -> str:
        """Build system prompt for a configured subagent."""
        # Build skills summary for configured extensions (skills)
        skills_section = ""
        if config.extensions:
            skills_summary = self._skills.build_skills_summary(exclude_types=["longtask"])
            if skills_summary:
                skills_section = f"""

## Available Skills

{skills_summary}"""

        return f"""# {config.display_name}

{config.system_prompt}

## Current Task
{task}

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## Workspace
Your workspace is at: {self.workspace}
{skills_section}

When you have completed the task, provide a clear summary of your findings or actions."""
    
    def _build_default_subagent_prompt(self, task: str) -> str:
        """Build default system prompt for subagents without role configuration."""
        skills_summary = self._skills.build_skills_summary(exclude_types=["longtask"])
        skills_section = ""
        if skills_summary:
            skills_section = f"""

## Available Skills

{skills_summary}"""

        return f"""# Subagent

You are a subagent spawned by the main agent to complete a specific task.

## Your Task
{task}

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## Workspace
Your workspace is at: {self.workspace}
{skills_section}

When you have completed the task, provide a clear summary of your findings or actions."""
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        agent_role: str | None = None,
        group_id: str | None = None,
        session_instance_id: int | None = None,
        parent_tool_call_id: str | None = None,
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.
        
        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
            agent_role: Optional subagent role name (e.g., "common-worker", "code-reviewer").
                       If not specified, uses default behavior.
            group_id: Optional task group ID for aggregation. If provided, result will be
                     aggregated with other subagents in the same group.
            session_instance_id: Session instance ID for precise routing.
            parent_tool_call_id: Parent tool call ID (injected by AgentLoop) for event routing.
        
        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        self._stop_flags[task_id] = False
        self._task_instance_map[task_id] = session_instance_id
        
        # 保存任务上下文用于事件路由
        self._task_contexts[task_id] = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
            "session_instance_id": session_instance_id,
            "parent_tool_call_id": parent_tool_call_id,
        }
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
            "session_instance_id": session_instance_id,
        }
        
        # Register with aggregator if group_id provided
        if group_id and self._aggregator:
            await self._aggregator.join_group(group_id, task_id)
            logger.info(f"[Subagent:{task_id}] Joined aggregation group {group_id}")
        
        # Load agent configuration if role specified
        # Always reload from disk to pick up any changes to SOUL.md
        agent_config = None
        if agent_role:
            agent_config = self._agent_loader.get(agent_role, reload=True)
            if not agent_config:
                logger.warning(f"Subagent role '{agent_role}' not found, using default configuration")
        
        # Create background task
        loop = asyncio.get_event_loop()
        bg_future = loop.run_in_executor(
            None,
            lambda: asyncio.run(self._run_subagent(task_id, task, display_label, origin, agent_config, group_id))
        )
        bg_task = asyncio.ensure_future(bg_future)
        
        def cleanup_callback(_):
            self._running_tasks.pop(task_id, None)
            self._stop_flags.pop(task_id, None)
            self._task_instance_map.pop(task_id, None)
            self._task_contexts.pop(task_id, None)
        
        bg_task.add_done_callback(cleanup_callback)
        
        role_info = f" [{agent_role}]" if agent_role else ""
        group_info = f" [group:{group_id}]" if group_id else ""
        logger.info(f"[Subagent:{task_id}] Spawned{role_info}{group_info}: {display_label}")
        return f"[Async] Subagent [{display_label}]{role_info}{group_info} started (id: {task_id}). This is a long-running task - do NOT wait or sleep for it. You may continue with other parallelizable tasks. I'll initiate a new conversation when it completes."

    async def spawn_sync_task(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        agent_role: str | None = None,
        session_instance_id: int | None = None,
        parent_tool_call_id: str | None = None,
    ) -> tuple[str, asyncio.Future]:
        """
        创建一个同步子代理任务，返回 (task_id, future)。
        
        调用方可以用 asyncio.wait_for(future, timeout) 等待结果。
        子代理完成后会自动设置 future 结果。

        Args:
            task: 任务描述
            label: 可选标签
            origin_channel: 来源通道
            origin_chat_id: 来源聊天 ID
            agent_role: 可选子代理角色
            session_instance_id: 会话实例 ID
            parent_tool_call_id: 父工具调用 ID（主 agent 的 tool call ID）

        Returns:
            (task_id, future) - future 的结果包含 summary, token_usage, duration
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        self._sync_tasks[task_id] = future
        self._task_instance_map[task_id] = session_instance_id
        
        # 保存任务上下文用于事件路由
        self._task_contexts[task_id] = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
            "session_instance_id": session_instance_id,
            "parent_tool_call_id": parent_tool_call_id,
        }
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
            "session_instance_id": session_instance_id,
            "parent_tool_call_id": parent_tool_call_id,
        }
        
        # 加载角色配置
        agent_config = None
        if agent_role:
            agent_config = self._agent_loader.get(agent_role, reload=True)
            if not agent_config:
                logger.warning(f"Subagent role '{agent_role}' not found, using default configuration")
        
        # 在线程池中运行
        bg_future = loop.run_in_executor(
            None,
            lambda: asyncio.run(self._run_subagent_and_set_future(
                task_id, task, display_label, origin, agent_config, future
            ))
        )
        
        logger.info(f"[Subagent:sync:{task_id}] Created sync task: {display_label}")
        return task_id, future

    async def _run_subagent_and_set_future(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        agent_config: SubAgentConfig | None,
        future: asyncio.Future,
    ) -> None:
        """执行子代理，完成后设置 future 结果"""
        import time
        start_time = time.time()
        
        role_name = agent_config.name if agent_config else "default"
        session_instance_id = origin.get("session_instance_id")
        logger.info(f"[Subagent:sync:{task_id}] Starting sync task: {label} (role: {role_name})")
        
        try:
            # 获取配置
            if agent_config:
                provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(agent_config)
                tools = self._build_tools_for_config(agent_config, origin)
                system_prompt = self._build_subagent_prompt(agent_config, task)
                max_iterations = agent_config.max_iterations
                temperature = agent_config.temperature
            else:
                provider, model, provider_type, max_tokens, temperature = self._get_default_provider_and_model()
                tools = self._build_default_tools(origin)
                system_prompt = self._build_default_subagent_prompt(task)
                max_iterations = 50

            # 构建消息
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            # 执行 Agent Loop
            iteration = 0
            final_result: str | None = None
            total_prompt_tokens = 0
            total_completion_tokens = 0
            iterations: list[dict[str, Any]] = []

            while iteration < max_iterations:
                iteration += 1
                
                iter_record: dict[str, Any] = {"iteration": iteration, "tools": []}
                
                try:
                    response = await provider.chat_streaming_complete(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

                    if response.usage:
                        total_prompt_tokens += response.usage.get("prompt_tokens", 0)
                        total_completion_tokens += response.usage.get("completion_tokens", 0)
                        self._record_token_usage(
                            session_instance_id=session_instance_id,
                            provider_name=provider_type,
                            model_id=model,
                            usage=response.usage,
                            request_type="subagent"
                        )

                except Exception as e:
                    logger.error(f"[Subagent:sync:{task_id}] LLM call failed: {e}")
                    raise

                if response.content:
                    iter_record["reasoning"] = response.content

                if response.has_tool_calls:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })

                    for tool_call in response.tool_calls:
                        try:
                            await self._emit("subagent_tool_call", {
                                "tool": tool_call.name,
                                "args": tool_call.arguments,
                                "content": response.content if response.content else None,
                                "iteration": iteration,
                                "tool_call_id": tool_call.id,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                            }, task_id)
                            
                            result = await tools.execute(tool_call.name, tool_call.arguments)
                            
                            iter_record["tools"].append({
                                "toolCallId": tool_call.id,
                                "toolName": tool_call.name,
                                "args": tool_call.arguments,
                                "result": result[:2000] if len(result) > 2000 else result,
                                "status": "completed",
                            })
                            
                            result_preview = result[:500] + "..." if len(result) > 500 else result
                            await self._emit("subagent_tool_result", {
                                "tool": tool_call.name,
                                "result": result_preview,
                                "tool_call_id": tool_call.id,
                                "iteration": iteration,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                            }, task_id)
                        except Exception as e:
                            result = f"Error: {str(e)}"
                            iter_record["tools"].append({
                                "toolCallId": tool_call.id,
                                "toolName": tool_call.name,
                                "args": tool_call.arguments,
                                "result": f"Error: {str(e)}",
                                "status": "error",
                            })
                            await self._emit("subagent_tool_result", {
                                "tool": tool_call.name,
                                "result": f"Error: {str(e)}",
                                "tool_call_id": tool_call.id,
                                "iteration": iteration,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                                "error": True,
                            }, task_id)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    iterations.append(iter_record)
                    break

                iterations.append(iter_record)

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            duration = time.time() - start_time
            
            # 记录 token 消耗
            token_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
            }
            self._task_token_usage[task_id] = token_usage
            
            # 设置 future 结果
            if not future.done():
                future.set_result({
                    "summary": final_result,
                    "token_usage": token_usage,
                    "duration": duration,
                    "iterations": iterations,
                })
            
            logger.info(f"[Subagent:sync:{task_id}] Completed in {duration:.1f}s, "
                       f"tokens: {total_prompt_tokens}+{total_completion_tokens}")

        except Exception as e:
            import traceback
            duration = time.time() - start_time
            error_msg = f"Error: {str(e)}"
            logger.error(f"[Subagent:sync:{task_id}] Failed: {e}")
            logger.error(f"[Subagent:sync:{task_id}] Traceback: {traceback.format_exc()}")
            
            if not future.done():
                future.set_result({
                    "summary": error_msg,
                    "token_usage": {},
                    "duration": duration,
                    "iterations": iterations,
                })
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        agent_config: SubAgentConfig | None,
        group_id: str | None = None,
    ) -> None:
        """Execute the subagent task and announce the result."""
        role_name = agent_config.name if agent_config else "default"
        logger.info(f"[Subagent:{task_id}] Starting task: {label} (role: {role_name})")
        logger.info(f"[Subagent:{task_id}] Task content: {task[:200]}...")
        
        try:
            # Get configuration
            if agent_config:
                provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(agent_config)
                tools = self._build_tools_for_config(agent_config, origin)
                system_prompt = self._build_subagent_prompt(agent_config, task)
                max_iterations = agent_config.max_iterations
                temperature = agent_config.temperature
            else:
                # Fallback to default behavior
                provider, model, provider_type, max_tokens, temperature = self._get_default_provider_and_model()
                tools = self._build_default_tools(origin)
                system_prompt = self._build_default_subagent_prompt(task)
                max_iterations = 50
                temperature = temperature
            
            session_instance_id = origin.get("session_instance_id")
            
            logger.info(f"[Subagent:{task_id}] Using role={role_name}, model={model}, provider_type={provider_type}")
            logger.info(f"[Subagent:{task_id}] Tools: {list(tools._tools.keys())}")
            
            # Build messages
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # Run agent loop
            iteration = 0
            final_result: str | None = None
            
            # Subagent context compression state
            subagent_compressed_context = ""
            subagent_message_count = 0
            last_prompt_tokens = 0
            
            while iteration < max_iterations:
                # Check if task should stop
                if self._stop_flags.get(task_id, False):
                    logger.info(f"[Subagent:{task_id}] Task stopped by user request")
                    final_result = "任务已被用户暂停。"
                    break
                
                iteration += 1
                logger.info(f"[Subagent:{task_id}] Iteration {iteration}/{max_iterations} - calling LLM...")
                
                # Check if context compression is needed (hybrid trigger)
                if self._subagent_compression_enabled:
                    should_compress = False
                    trigger_reason = ""
                    
                    # Strategy 1: Token threshold (primary)
                    if last_prompt_tokens >= self._subagent_compression_token_threshold:
                        should_compress = True
                        trigger_reason = f"token threshold ({last_prompt_tokens} >= {self._subagent_compression_token_threshold})"
                    
                    # Strategy 2: Turn threshold (fallback)
                    if not should_compress and subagent_message_count >= self._subagent_compression_turns:
                        should_compress = True
                        trigger_reason = f"turn threshold (turn {subagent_message_count})"
                    
                    if should_compress:
                        logger.info(f"[Subagent:{task_id}] Compressing context triggered by {trigger_reason}")
                        keep_count = 6
                        non_system_messages = [m for m in messages if m.get("role") not in ("system",)]
                        to_compress = non_system_messages[:-keep_count] if len(non_system_messages) > keep_count else non_system_messages
                        
                        if len(to_compress) >= 4:
                            summary = await compress_messages(
                                messages=to_compress,
                                provider=provider,
                                model=model,
                                provider_type=provider_type,
                                record_token_usage=self._record_token_usage,
                                request_type="subagent_compression"
                            )
                            if summary:
                                subagent_compressed_context = summary
                                system_messages = [m for m in messages if m.get("role") == "system"]
                                remaining_non_system = non_system_messages[-keep_count:] if len(non_system_messages) > keep_count else non_system_messages
                                messages = system_messages + [
                                    {"role": "system", "content": f"# Previous Context Summary\n\n{summary}"},
                                ] + remaining_non_system
                                subagent_message_count = 0
                                logger.info(f"[Subagent:{task_id}] Context compressed")
                
                try:
                    response = await provider.chat_streaming_complete(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    logger.info(f"[Subagent:{task_id}] LLM response received, has_tool_calls={response.has_tool_calls}")
                    
                    if response.usage:
                        last_prompt_tokens = response.usage.get("prompt_tokens", 0)
                        self._record_token_usage(
                            session_instance_id=session_instance_id,
                            provider_name=provider_type,
                            model_id=model,
                            usage=response.usage,
                            request_type="subagent"
                        )
                except Exception as e:
                    logger.error(f"[Subagent:{task_id}] LLM call failed: {e}")
                    raise
                
                if response.has_tool_calls:
                    logger.info(f"[Subagent:{task_id}] Processing {len(response.tool_calls)} tool calls...")
                    
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })
                    
                    for i, tool_call in enumerate(response.tool_calls):
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.info(f"[Subagent:{task_id}] Executing tool {i+1}/{len(response.tool_calls)}: {tool_call.name}")
                        logger.info(f"[Subagent:{task_id}] Tool args: {args_str[:500]}")
                        
                        try:
                            await self._emit("subagent_tool_call", {
                                "tool": tool_call.name,
                                "args": tool_call.arguments,
                                "content": response.content if response.content else None,
                                "iteration": iteration,
                                "tool_call_id": tool_call.id,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                            }, task_id)
                            
                            result = await tools.execute(tool_call.name, tool_call.arguments)
                            logger.info(f"[Subagent:{task_id}] Tool result: {result[:200] if result else 'None'}...")
                            
                            result_preview = result[:500] + "..." if len(result) > 500 else result
                            await self._emit("subagent_tool_result", {
                                "tool": tool_call.name,
                                "result": result_preview,
                                "tool_call_id": tool_call.id,
                                "iteration": iteration,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                            }, task_id)
                        except Exception as e:
                            logger.error(f"[Subagent:{task_id}] Tool execution failed: {e}")
                            result = f"Error: {str(e)}"
                            
                            await self._emit("subagent_tool_result", {
                                "tool": tool_call.name,
                                "result": f"Error: {str(e)}",
                                "tool_call_id": tool_call.id,
                                "iteration": iteration,
                                "session_instance_id": session_instance_id,
                                "subagent_id": task_id,
                                "error": True,
                            }, task_id)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                    
                    subagent_message_count += 1
                else:
                    final_result = response.content
                    logger.info(f"[Subagent:{task_id}] No tool calls, final result: {final_result[:100] if final_result else 'None'}...")
                    break
            
            if final_result is None:
                final_result = "Task completed but no final response was generated."
                logger.warning(f"[Subagent:{task_id}] No final result after {max_iterations} iterations")
            
            logger.info(f"[Subagent:{task_id}] Task completed successfully")
            await self._announce_result(task_id, label, task, final_result, origin, "ok", group_id)
            
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            logger.error(f"[Subagent:{task_id}] Failed: {e}")
            logger.error(f"[Subagent:{task_id}] Traceback: {traceback.format_exc()}")
            await self._announce_result(task_id, label, task, error_msg, origin, "error", group_id)
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
        group_id: str | None = None,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        logger.info(f"[Subagent:{task_id}] Announcing result to {origin['channel']}:{origin['chat_id']}")
        
        # Check if this subagent is part of an aggregation group
        if group_id and self._aggregator:
            is_grouped, is_complete = await self._aggregator.submit_result(
                task_id, label, task, result, status
            )
            
            if is_grouped:
                if is_complete:
                    logger.info(f"[Subagent:{task_id}] Group {group_id} complete, summary triggered")
                else:
                    logger.info(f"[Subagent:{task_id}] Result added to group {group_id}, waiting for others")
                return
            # If not grouped (shouldn't happen), fall through to individual announcement
        
        # Individual announcement (no aggregation or not part of a group)
        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
        
        # Inject as system message to trigger main agent
        session_instance_id = origin.get("session_instance_id")
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
            metadata={
                "session_instance_id": session_instance_id,
                "subagent_id": task_id,
            }
        )
        
        try:
            await self.bus.publish_inbound(msg)
            logger.info(f"[Subagent:{task_id}] Result announced successfully")
        except Exception as e:
            logger.error(f"[Subagent:{task_id}] Failed to announce result: {e}")

    def _record_token_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        usage: dict,
        request_type: str = "subagent"
    ) -> None:
        """Record token usage to database.
        
        Args:
            session_instance_id: The session instance ID
            provider_name: Provider name (e.g., openai, anthropic)
            model_id: Model ID (e.g., gpt-4, claude-3-opus)
            usage: Usage dict with prompt_tokens, completion_tokens, total_tokens
            request_type: Type of request (subagent, compression, etc.)
        """
        try:
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            self._token_usage.record_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_name,
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                request_type=request_type
            )
            
            logger.debug(f"[Subagent] Token usage recorded: {provider_name}/{model_id} - "
                        f"prompt={prompt_tokens}, completion={completion_tokens}")
        except Exception as e:
            logger.error(f"[Subagent] Failed to record token usage: {e}")
    
    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
    
    def list_available_roles(self) -> list[dict[str, str]]:
        """List all available subagent roles."""
        return self._agent_loader.list_agents()
    
    def get_role_config(self, role_name: str) -> SubAgentConfig | None:
        """Get configuration for a specific role."""
        return self._agent_loader.get(role_name)
    
    def stop_all(self) -> int:
        """Stop all running subagents.
        
        Returns:
            Number of subagents that were stopped.
        """
        count = len(self._running_tasks)
        
        # Set stop flags for all running tasks
        for task_id in list(self._running_tasks.keys()):
            self._stop_flags[task_id] = True
            logger.info(f"[Subagent:{task_id}] Stop flag set")
        
        # Cancel all running tasks
        for task_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                logger.info(f"[Subagent:{task_id}] Task cancelled")
        
        logger.info(f"[SubagentManager] Stopped {count} subagents")
        return count
    
    def stop_by_instance(self, instance_id: int) -> int:
        """Stop all running subagents for a specific session instance.
        
        Args:
            instance_id: The session instance ID to stop subagents for.
        
        Returns:
            Number of subagents that were stopped.
        """
        instance_id_int = int(instance_id) if instance_id else None
        if not instance_id_int:
            logger.warning("[SubagentManager] stop_by_instance called with invalid instance_id")
            return 0
        
        # Find all subagents belonging to this instance
        tasks_to_stop = [
            task_id for task_id, inst_id in self._task_instance_map.items()
            if inst_id == instance_id_int and task_id in self._running_tasks
        ]
        
        count = len(tasks_to_stop)
        
        # Set stop flags and cancel tasks
        for task_id in tasks_to_stop:
            self._stop_flags[task_id] = True
            logger.info(f"[Subagent:{task_id}] Stop flag set for instance {instance_id_int}")
            
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"[Subagent:{task_id}] Task cancelled for instance {instance_id_int}")
        
        logger.info(f"[SubagentManager] Stopped {count} subagents for instance {instance_id_int}")
        return count
