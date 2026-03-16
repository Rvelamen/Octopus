"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent, MessageContentItem
from backend.core.events.bus import MessageBus
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import create_provider
from backend.agent.config_service import AgentConfigService
from backend.agent.context import ContextBuilder, set_agent_loop
from backend.tools.registry import ToolRegistry
from backend.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from backend.tools.shell import ExecTool

from backend.tools.message import MessageTool
from backend.tools.spawn import SpawnTool
from backend.tools.cron import CronTool
from backend.tools.action import ActionTool
from backend.tools.image import ImageUnderstandTool, ImageGenerateTool
from backend.tools.web_fetch import WebFetchTool
from backend.agent.subagent import SubagentManager
from backend.agent.aggregator import SubagentAggregator
from backend.data.session_manager import SessionManager
from backend.data.commands import handle_session_command
from backend.extensions.loader import ExtensionLoader


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        workspace: Path,
        max_iterations: int = 20,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        db: "Database | None" = None,
        subagent_manager: "SubagentManager | None" = None,
        mcp_bridge=None,
    ):
        from backend.core.config.schema import ExecToolConfig
        from backend.data import Database

        self.bus = bus
        self.workspace = workspace
        self._default_max_iterations = max_iterations
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.db = db or Database()

        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace, db=self.db)
        self.tools = ToolRegistry(mcp_bridge=mcp_bridge)

        # Initialize aggregator for multi-subagent support
        self.aggregator = SubagentAggregator(bus)
        
        # Create subagent manager with aggregator
        if subagent_manager:
            self.subagents = subagent_manager
        else:
            self.subagents = SubagentManager(
                workspace=workspace,
                bus=bus,
                exec_config=self.exec_config,
                aggregator=self.aggregator
            )

        set_agent_loop(self)

        self.extension_loader = ExtensionLoader(workspace=workspace)

        self._running = False
        self._register_default_tools()

    @property
    def max_iterations(self) -> int:
        """Get max_iterations from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_max_iterations()
        except Exception:
            return self._default_max_iterations

    @property
    def context_compression_enabled(self) -> bool:
        """Get context_compression_enabled from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_context_compression_enabled()
        except Exception:
            return False

    @property
    def context_compression_turns(self) -> int:
        """Get context_compression_turns from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_context_compression_turns()
        except Exception:
            return 10

    def _get_current_provider_and_model(self) -> tuple[LLMProvider, str, str]:
        """Get current provider, model, and provider_type from database."""
        config_service = AgentConfigService(self.db)
        return config_service.get_default_provider_and_model()

    async def _emit(self, event_type: str, data: dict, channel: str = ""):
        """Helper to emit events to the bus."""
        print(f"[EMIT] {event_type} channel={channel} {data}")
        if hasattr(self.bus, 'publish_event'):
            session = data.get("session", "unknown")
            await self.bus.publish_event(AgentEvent(
                event_type=event_type,
                data=data,
                channel=channel
            ))
    
    async def _send_stream_chunks(self, content: str, session: str, channel: str, chunk_size: int = 10):
        """Send content in chunks for streaming effect."""
        if not content:
            return
        
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            await self.bus.publish_event(AgentEvent(
                event_type="agent_chunk",
                data={"content": chunk, "session": session},
                channel=channel
            ))
            await asyncio.sleep(0.05)

    async def _compress_context(
        self,
        session,
        messages: list[dict[str, Any]],
    ) -> str:
        """
        Compress conversation history using LLM.
        
        Args:
            session: The current session.
            messages: Current message list.
        
        Returns:
            Compressed context summary.
        """
        # Get messages to compress (excluding compressed ones if any)
        to_compress = session.messages[:-6] if len(session.messages) > 6 else session.messages
        
        if len(to_compress) < 4:
            return ""
        
        # Build prompt for summarization
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

        # Call LLM to compress
        provider, model, provider_type = self._get_current_provider_and_model()
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
            logger.info(f"Context compressed to {len(summary)} characters")
            return summary
        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            return ""

    async def _maybe_compress_context(self, session) -> None:
        """
        Check if context compression is needed and perform it.
        
        Args:
            session: The current session.
        """
        if not self.context_compression_enabled:
            return
        
        current_turns = session.get_turn_count()
        threshold = self.context_compression_turns
        
        # Check if we need to compress
        if current_turns >= threshold and session.last_compressed_turn < threshold:
            logger.info(f"Compressing context at turn {current_turns}")
            
            # Compress older messages
            summary = await self._compress_context(session, None)
            if summary:
                session.set_compressed_context(summary)
                # Keep only recent messages in session
                keep_count = 6
                if len(session.messages) > keep_count:
                    session.messages = session.messages[-keep_count:]
                self.sessions.save(session)
                logger.info(f"Context compressed, kept last {keep_count} messages")
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(EditFileTool())
        self.tools.register(ListDirTool())
        
        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
        ))
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents, aggregator=self.aggregator)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
        
        # Unified Action tool (plugin + channel + page)
        self.tools.register(ActionTool())

        # Image tools
        self.tools.register(ImageUnderstandTool())
        self.tools.register(ImageGenerateTool())

        # Web fetch tool
        self.tools.register(WebFetchTool())

    async def load_extensions(self) -> dict[str, bool]:
        """Load all discovered extensions (plugins, skills, workers)."""
        logger.info("Loading extensions...")
        extensions = self.extension_loader.load_all()
        loaded = len(extensions)
        logger.info(f"Loaded {loaded} extensions")
        return {ext.name: True for ext in extensions}


    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        await self.load_extensions()
        
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    logger.error(f"Error processing message: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None
    ) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.
            session_key: Optional session key override. If provided, uses this instead of msg.session_key.

        Returns:
            The response message, or None if no response needed.
        """

        # Handle longtask messages (auth requests, completions)
        if msg.message_type in ("longtask_auth", "longtask_complete"):
            await self._process_longtask_message(msg)
            if msg.message_type == "longtask_auth":
                return None

        if msg.channel == "system":
            return await self._process_system_message(msg, session_key=session_key)

        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        current_session = session_key or msg.session_key

        # Convert content to JSON-safe format for events
        event_content = msg.text_content if msg.is_multimodal else msg.content

        await self.bus.publish_event(AgentEvent(
            event_type="agent_start",
            data={"content": event_content, "session": current_session},
            channel=msg.channel
        ))

        # === 1. Check for session management commands ===
        command_result = await handle_session_command(
            msg.content,
            msg.session_key,
            self.sessions
        )

        if command_result:
            # Command was handled, return response
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=command_result.message
            )

        # Get instance_id from metadata if provided (frontend selected instance)
        metadata_instance_id = msg.metadata.get("instance_id") if msg.metadata else None
        
        # Use fixed session key for desktop channel
        session_key = msg.session_key
        if msg.channel == "desktop":
            session_key = "desktop:desktop_session"
        
        if metadata_instance_id:
            # Switch to the specified instance in the desktop session
            success, switch_msg = self.sessions.switch_instance(session_key, int(metadata_instance_id))
            if success:
                # Reload session to get the switched instance
                self.sessions._cache.pop(session_key, None)
                session = self.sessions.get_or_create(session_key)
                logger.info(f"Switched to instance {metadata_instance_id} for session {session_key}")
            else:
                logger.warning(f"Failed to switch to instance {metadata_instance_id}: {switch_msg}")
                session = self.sessions.get_or_create(session_key)
        else:
            # No instance_id provided, use default session
            session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts with session instance ID
        session_instance_id = session.active_instance.id if session.active_instance else None
        
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id, session_instance_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id, session_instance_id)
        
        # Build initial messages (use get_history for LLM-formatted messages)
        # Handle multi-modal content
        if msg.is_multimodal:
            # Multi-modal message: convert to LLM format
            user_content = self._build_multimodal_content(msg.content)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=user_content,  # Pass the formatted content
                media=None,  # Images are already in content
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            # Store text representation for session history, with image metadata
            images = msg.get_images()
            logger.info(f"[AgentLoop] get_images returned: {images}")
            for img in images:
                logger.info(f"[AgentLoop] Image item: type={img.type}, image_path={img.image_path}")
            image_list = [{"path": img.image_path, "name": img.image_path.split('/').pop()} for img in images] if images else []
            metadata = {"images": image_list} if image_list else None
            logger.info(f"[AgentLoop] Saving multimodal message with {len(images)} images, metadata: {metadata}")
            session.add_message("user", msg.text_content, message_type=msg.message_type, metadata=metadata)
        else:
            # Text-only message
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=msg.content,
                media=msg.media if msg.media else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            session.add_message("user", msg.content, message_type=msg.message_type)
        self.sessions.save(session)
        
        # Agent loop
        iteration = 0
        final_content = None

        should_stop = False  # Flag to stop the outer loop

        while iteration < self.max_iterations and not should_stop:
            iteration += 1

            # Emit "thinking" event
            await self._emit("agent_thinking", {"iteration": iteration, "session": session.key}, channel=msg.channel)

            # Call LLM - get fresh provider and model from config
            provider, model, provider_type = self._get_current_provider_and_model()
            # logger.info(f"Message: {messages}")
            response = await provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model
            )
            logger.info(f"LLM Response: {response}")
            # Handle tool calls
            if response.has_tool_calls:
                # Build tool_calls data
                tool_calls_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]

                # Save assistant message with tool calls immediately
                session.add_message("assistant", response.content or "",
                                  message_type="tool_call",
                                  tool_calls=tool_calls_data,
                                  metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                self.sessions.save(session)

                # Add assistant message with tool calls to messages
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts, provider_type
                )

                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                    # Emit tool call start (include assistant content if any)
                    await self._emit("agent_tool_call", {
                        "tool": tool_call.name,
                        "args": tool_call.arguments,
                        "content": response.content if response.content else None
                    }, channel=msg.channel)

                    # Inject channel, chat_id, and session_instance_id for action tools
                    tool_args = tool_call.arguments.copy()
                    if tool_call.name == "action":
                        tool_args["_channel"] = msg.channel
                        tool_args["_chat_id"] = msg.chat_id
                        tool_args["_session_instance_id"] = session.active_instance.id

                    # Execute tool
                    result = await self.tools.execute(tool_call.name, tool_args)

                    # Check if this is a longtask auth action - if so, return simple confirmation
                    is_longtask_auth = (
                        tool_call.name == "action" and
                        tool_args.get("type") == "plugin" and
                        tool_args.get("action") == "auth"
                    )

                    if is_longtask_auth and "success" in result:
                        # For longtask auth actions, return simple confirmation without LLM processing
                        plugin_name = tool_args.get("name", "longtask")
                        final_content = f"✅ 授权已发送，{plugin_name} 将继续执行任务。任务完成后我会通知您。"
                        # Add tool result to messages
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result, provider_type
                        )

                        # Save tool result immediately
                        session.add_message("tool", result,
                                          message_type="tool_result",
                                          name=tool_call.name,
                                          tool_call_id=tool_call.id,
                                          metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                        self.sessions.save(session)

                        should_stop = True  # Stop the outer loop
                        break  # Exit tool execution loop

                    # Emit tool call result (truncated for log)
                    result_preview = result[:500] + "..." if len(result) > 500 else result
                    await self._emit("agent_tool_result", {
                        "tool": tool_call.name,
                        "result": result_preview
                    }, channel=msg.channel)

                    # Save tool result immediately
                    session.add_message("tool", result,
                                      message_type="tool_result",
                                      name=tool_call.name,
                                      tool_call_id=tool_call.id,
                                      metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                    self.sessions.save(session)

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result, provider_type
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                # Save final assistant response immediately
                session.add_message("assistant", final_content or "",
                                  message_type=msg.message_type,
                                  metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                self.sessions.save(session)
                break

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        await self._maybe_compress_context(session)

        logger.info(f"[AgentLoop] Sending final response with {len(final_content)} chars")
        await self._send_stream_chunks(final_content, current_session, msg.channel)

        logger.info(f"[AgentLoop] Publishing agent_finish event")
        await self.bus.publish_event(AgentEvent(
            event_type="agent_finish",
            data={"content": final_content, "session": msg.chat_id},
            channel=msg.channel
        ))
        logger.info(f"[AgentLoop] agent_finish event published")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )

    async def _process_system_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None
    ) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        
        Args:
            msg: The inbound message to process.
            session_key: Optional session key override. If provided, uses this instead of parsing from msg.chat_id.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Check for aggregate summary message type
        msg_type = msg.metadata.get("type") if msg.metadata else None
        is_aggregate_summary = msg_type == "aggregate_summary"
        
        # Get session_instance_id from metadata if available
        session_instance_id = msg.metadata.get("session_instance_id") if msg.metadata else None
        
        if session_key:
            parts = session_key.split(":", 1)
            origin_channel = parts[0] if len(parts) > 0 else "cli"
            origin_chat_id = parts[1] if len(parts) > 1 else msg.chat_id
        else:
            # Parse origin from chat_id (format: "channel:chat_id")
            if ":" in msg.chat_id:
                parts = msg.chat_id.split(":", 1)
                origin_channel = parts[0]
                origin_chat_id = parts[1]
            else:
                # Fallback
                origin_channel = "cli"
                origin_chat_id = msg.chat_id
            session_key = f"{origin_channel}:{origin_chat_id}"
        
        session = self.sessions.get_or_create(session_key)
        
        # If session_instance_id is provided, ensure we're using the correct instance
        if session_instance_id and session.active_instance:
            if session.active_instance.id != session_instance_id:
                logger.warning(f"Session instance mismatch: active={session.active_instance.id}, "
                              f"expected={session_instance_id}. Using provided instance_id for routing.")
        
        # Update tool contexts with session instance ID
        active_instance_id = session.active_instance.id if session.active_instance else None
        # Use provided session_instance_id if available, otherwise use active instance
        target_instance_id = session_instance_id or active_instance_id
        
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id, target_instance_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id, target_instance_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None

        # Save input message immediately
        msg_role = "system" if is_aggregate_summary else "user"
        session.add_message(msg_role, f"[{msg.sender_id}] {msg.content}",
                          message_type=msg_type or msg.message_type,
                          metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
        self.sessions.save(session)

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM - get fresh provider and model from config
            provider, model, provider_type = self._get_current_provider_and_model()
            response = await provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model
            )

            if response.has_tool_calls:
                # Build tool_calls data
                tool_calls_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]

                # Save assistant message with tool calls immediately
                session.add_message("assistant", response.content or "",
                                  message_type="tool_call",
                                  tool_calls=tool_calls_data,
                                  metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                self.sessions.save(session)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts, provider_type
                )

                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                    # Emit tool call start
                    await self._emit("agent_tool_call", {
                        "tool": tool_call.name,
                        "args": tool_call.arguments
                    }, channel=origin_channel)

                    result = await self.tools.execute(tool_call.name, tool_call.arguments)

                    # Emit tool call result
                    result_preview = result[:500] + "..." if len(result) > 500 else result
                    await self._emit("agent_tool_result", {
                        "tool": tool_call.name,
                        "result": result_preview
                    }, channel=origin_channel)

                    # Save tool result immediately
                    session.add_message("tool", result,
                                      message_type="tool_result",
                                      name=tool_call.name,
                                      tool_call_id=tool_call.id,
                                      metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                    self.sessions.save(session)

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result, provider_type
                    )
            else:
                final_content = response.content
                # Save final assistant response immediately
                session.add_message("assistant", final_content or "",
                                  message_type=msg_type or msg.message_type,
                                  metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                self.sessions.save(session)
                break

        if final_content is None:
            final_content = "Background task completed."

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    async def _process_longtask_message(
        self,
        msg: InboundMessage,
    ) -> OutboundMessage | None:
        """
        Process a longtask message (auth request or completion notification).

        These messages are created by hooks from CLI tools and need to be
        handled by the Agent to notify the user or request authorization.

        Args:
            msg: The inbound message with message_type "longtask_auth" or "longtask_complete"

        Returns:
            The response message to send to the user.
        """
        logger.info(f"Processing longtask message: {msg.message_type}")

        # Get session and save the message for context
        session = self.sessions.get_or_create(msg.session_key)

        # For auth requests, we need to ask the user for authorization
        if msg.message_type == "longtask_auth":
            # The message content already contains the instructions
            # Just forward it to the user
            content = f"🔔 {msg.content}"
            # Save to session for context
            session.add_message("assistant", content, message_type="longtask_auth")
            self.sessions.save(session)
            logger.info(f"[_process_longtask_message] Saved longtask_auth message to session {session.key}")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )

        # For completion notifications, just notify the user
        elif msg.message_type == "longtask_complete":
            content = f"✅ {msg.content}"
            # Save to session for context
            session.add_message("assistant", content, message_type="longtask_complete")
            self.sessions.save(session)
            logger.info(f"[_process_longtask_message] Saved longtask_complete message to session {session.key}")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )

        return None

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        message_type: str = "normal",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
            message_type: "normal" or "heartbeat" - marks if this is a heartbeat-triggered message.

        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            message_type=message_type,
        )

        response = await self._process_message(msg, session_key=session_key)
        return response.content if response else ""

    def _build_multimodal_content(
        self,
        content_items: list[MessageContentItem]
    ) -> list[dict[str, Any]]:
        """Build multi-modal content for LLM from MessageContentItem list.

        Args:
            content_items: List of message content items.

        Returns:
            List of content dicts in OpenAI format.
        """
        from pathlib import Path
        import base64
        import mimetypes
        from backend.utils.helpers import get_workspace_path

        logger.info(f"[_build_multimodal_content] Building content for {len(content_items)} items")
        result = []
        workspace = get_workspace_path()
        logger.info(f"[_build_multimodal_content] Workspace: {workspace}")

        for item in content_items:
            if item.type == "text" and item.text:
                logger.info(f"[_build_multimodal_content] Adding text: {item.text[:50]}...")
                result.append({"type": "text", "text": item.text})
            elif item.type == "image" and item.image_path:
                # Read and encode image
                path = Path(item.image_path)
                logger.info(f"[_build_multimodal_content] Processing image path: {item.image_path}")
                if not path.is_absolute():
                    path = workspace / item.image_path

                logger.info(f"[_build_multimodal_content] Full image path: {path}, exists: {path.exists()}")
                if path.exists():
                    mime, _ = mimetypes.guess_type(str(path))
                    logger.info(f"[_build_multimodal_content] MIME type: {mime}")
                    if mime and mime.startswith("image/"):
                        b64 = base64.b64encode(path.read_bytes()).decode()
                        result.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        })
                else:
                    logger.error(f"[_build_multimodal_content] Image file not found: {path}")
            elif item.type == "image_url" and item.image_url:
                logger.info(f"[_build_multimodal_content] Adding image_url: {item.image_url}")
                result.append({
                    "type": "image_url",
                    "image_url": {"url": item.image_url}
                })

        logger.info(f"[_build_multimodal_content] Built {len(result)} content items")
        return result


