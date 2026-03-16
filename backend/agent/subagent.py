"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage
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
        self._subagent_compression_enabled: bool = False
        self._subagent_compression_turns: int = 10
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace)
        self._aggregator = aggregator
        
        # Set bus on aggregator if provided
        if self._aggregator:
            self._aggregator.set_bus(bus)
    
    def _get_provider_for_config(self, config: SubAgentConfig) -> tuple[LLMProvider, str]:
        """Get provider and model for a subagent configuration."""
        # Use AgentConfigService to get provider from database
        config_service = AgentConfigService()
        
        # Get provider and model for this subagent
        provider, model = config_service.get_provider_for_subagent(
            provider_name=config.provider,
            model_name=config.model
        )
        
        # Load compression settings from database
        self._subagent_compression_enabled = config_service.get_context_compression_enabled()
        self._subagent_compression_turns = config_service.get_context_compression_turns()
        
        return provider, model
    
    def _get_default_provider_and_model(self) -> tuple[LLMProvider, str]:
        """Get default provider and model from database."""
        config_service = AgentConfigService()
        
        # Get default provider and model from database
        provider, model, _ = config_service.get_default_provider_and_model()
        
        # Load compression settings from database
        self._subagent_compression_enabled = config_service.get_context_compression_enabled()
        self._subagent_compression_turns = config_service.get_context_compression_turns()
        
        return provider, model
    
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
        
        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
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
        
        # Cleanup when done
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
        
        role_info = f" [{agent_role}]" if agent_role else ""
        group_info = f" [group:{group_id}]" if group_id else ""
        logger.info(f"[Subagent:{task_id}] Spawned{role_info}{group_info}: {display_label}")
        return f"Subagent [{display_label}]{role_info}{group_info} started (id: {task_id}). I'll notify you when it completes."
    
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
                provider, model = self._get_provider_for_config(agent_config)
                tools = self._build_tools_for_config(agent_config, origin)
                system_prompt = self._build_subagent_prompt(agent_config, task)
                max_iterations = agent_config.max_iterations
                temperature = agent_config.temperature
            else:
                # Fallback to default behavior
                provider, model = self._get_default_provider_and_model()
                tools = self._build_default_tools(origin)
                system_prompt = self._build_default_subagent_prompt(task)
                max_iterations = 50
                temperature = 0.7
            
            logger.info(f"[Subagent:{task_id}] Using role={role_name}, model={model}")
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
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"[Subagent:{task_id}] Iteration {iteration}/{max_iterations} - calling LLM...")
                
                # Check if context compression is needed
                if self._subagent_compression_enabled and subagent_message_count >= self._subagent_compression_turns:
                    logger.info(f"[Subagent:{task_id}] Compressing context at iteration {iteration}")
                    summary = await self._compress_subagent_context(messages)
                    if summary:
                        subagent_compressed_context = summary
                        messages = [
                            {"role": "system", "content": f"# Previous Context Summary\n\n{summary}"},
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": task},
                        ]
                        subagent_message_count = 0
                        logger.info(f"[Subagent:{task_id}] Context compressed")
                
                try:
                    response = await provider.chat(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=model,
                        temperature=temperature,
                    )
                    logger.info(f"[Subagent:{task_id}] LLM response received, has_tool_calls={response.has_tool_calls}")
                except Exception as e:
                    logger.error(f"[Subagent:{task_id}] LLM call failed: {e}")
                    raise
                
                if response.has_tool_calls:
                    logger.info(f"[Subagent:{task_id}] Processing {len(response.tool_calls)} tool calls...")
                    
                    # Add assistant message with tool calls
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
                    
                    # Execute tools
                    for i, tool_call in enumerate(response.tool_calls):
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.info(f"[Subagent:{task_id}] Executing tool {i+1}/{len(response.tool_calls)}: {tool_call.name}")
                        logger.info(f"[Subagent:{task_id}] Tool args: {args_str[:500]}")
                        
                        try:
                            result = await tools.execute(tool_call.name, tool_call.arguments)
                            logger.info(f"[Subagent:{task_id}] Tool result: {result[:200] if result else 'None'}...")
                        except Exception as e:
                            logger.error(f"[Subagent:{task_id}] Tool execution failed: {e}")
                            result = f"Error: {str(e)}"
                        
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

    async def _compress_subagent_context(
        self,
        messages: list[dict[str, Any]],
    ) -> str:
        """
        Compress subagent conversation history using LLM.
        
        Args:
            messages: Current message list.
        
        Returns:
            Compressed context summary.
        """
        # Get non-system messages to compress
        to_compress = [m for m in messages if m.get("role") not in ("system",)]
        
        if len(to_compress) < 4:
            return ""
        
        conversation_text = "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
            for m in to_compress
        ])
        
        compression_prompt = f"""请总结以下对话的要点，保留关键信息、用户请求和重要的上下文：

{conversation_text}

请用简洁的中文总结（不超过 300 字），包括：
1. 用户的主要请求
2. 已经完成的工作
3. 重要的上下文信息"""

        provider, model = self._get_default_provider_and_model()
        compression_messages = [
            {"role": "system", "content": "你是一个对话摘要助手。请简洁地总结对话要点。"},
            {"role": "user", "content": compression_prompt}
        ]
        
        try:
            response = await provider.chat(
                messages=compression_messages,
                tools=[],
                model=model
            )
            summary = response.content or ""
            return summary
        except Exception as e:
            logger.error(f"[Subagent] Context compression failed: {e}")
            return ""
    
    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
    
    def list_available_roles(self) -> list[dict[str, str]]:
        """List all available subagent roles."""
        return self._agent_loader.list_agents()
    
    def get_role_config(self, role_name: str) -> SubAgentConfig | None:
        """Get configuration for a specific role."""
        return self._agent_loader.get(role_name)
