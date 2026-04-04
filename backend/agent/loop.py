"""Agent loop: the core processing engine."""

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent, MessageContentItem
from backend.core.events.bus import MessageBus
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import create_provider
from backend.agent.config_service import AgentConfigService
from backend.agent.context import ContextBuilder, set_agent_loop
from backend.agent.compressor import ContextCompressor
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
from backend.data.token_store import TokenUsageRepository
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
        self.token_usage = TokenUsageRepository(self.db)

        self.compressor = ContextCompressor(
            db=self.db,
            sessions=self.sessions,
            token_usage=self.token_usage,
            get_provider_and_model=self._get_current_provider_and_model,
            record_token_usage=self._record_token_usage,
        )

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
        self._stop_current_task = False
        self._register_default_tools()
        self._tts_service = None

    @property
    def tts_service(self):
        """Lazy load TTS service using SessionManager's database."""
        if self._tts_service is None:
            from backend.services.tts_service import TTSService
            from backend.data.provider_store import ProviderRepository, SettingsRepository
            
            provider_repo = ProviderRepository(self.db)
            settings_repo = SettingsRepository(self.db)
            self._tts_service = TTSService(
                self.sessions.db, 
                provider_repo, 
                settings_repo
            )
        return self._tts_service

    @property
    def max_iterations(self) -> int:
        """Get max_iterations from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_max_iterations()
        except Exception:
            return self._default_max_iterations

    def _get_current_provider_and_model(self) -> tuple[LLMProvider, str, str]:
        """Get current provider, model, and provider_type from database."""
        config_service = AgentConfigService(self.db)
        return config_service.get_default_provider_and_model()

    async def _emit(self, event_type: str, data: dict, channel: str = ""):
        """Helper to emit events to the bus."""
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
    
    def stop_current_task(self) -> None:
        """Stop the current running task."""
        self._stop_current_task = True
        logger.info("Agent current task stopping")
    
    def reset_stop_flag(self) -> None:
        """Reset the stop flag for new task."""
        self._stop_current_task = False
    
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
        
        # Determine if streaming should be enabled (only for desktop channel)
        enable_streaming = msg.channel == "desktop"
        
        if enable_streaming:
            return await self._process_streaming_message(msg, session_key)
        else:
            # Keep original non-streaming logic
            return await self._process_non_streaming_message(msg, session_key)
    
    async def _process_non_streaming_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None
    ) -> OutboundMessage | None:
        """
        Process message without streaming (original logic).
        
        This method preserves the original non-streaming behavior for non-desktop channels.
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

        # Use fixed session key for desktop channel
        session_key = msg.session_key
        if msg.channel == "desktop":
            session_key = "desktop:desktop_session"
        
        # Get instance_id from metadata if provided (frontend selected instance)
        metadata_instance_id = msg.metadata.get("instance_id") if msg.metadata else None
        
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

        # === 1. Check for session management commands (after instance switch) ===
        command_result = await handle_session_command(
            msg.content,
            session_key,
            self.sessions
        )

        if command_result:
            # Command was handled, return response
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=command_result.message
            )
        
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
            user_content = self._build_multimodal_content(msg.content)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=user_content,
                media=None,
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            images = msg.get_images()
            logger.info(f"[AgentLoop] get_images returned: {images}")
            for img in images:
                logger.info(f"[AgentLoop] Image item: type={img.type}, image_path={img.image_path}")
            image_list = [{"path": img.image_path, "name": img.image_path.split('/').pop()} for img in images] if images else []
            
            files = msg.get_files()
            logger.info(f"[AgentLoop] get_files returned: {files}")
            file_list = []
            for f in files:
                file_list.append({
                    "path": f.file_path,
                    "name": f.file_name or f.file_path.split('/').pop(),
                    "originalName": f.file_name,
                    "mimeType": f.mime_type,
                    "size": f.file_size
                })
            
            metadata = {}
            if image_list:
                metadata["images"] = image_list
            if file_list:
                metadata["files"] = file_list
            
            metadata = metadata if metadata else None
            logger.info(f"[AgentLoop] Saving multimodal message with {len(images)} images, {len(files)} files, metadata: {metadata}")
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
        last_prompt_tokens = 0  # Track prompt tokens for compression trigger

        should_stop = False  # Flag to stop the outer loop

        # Reset stop flag for new task
        self._stop_current_task = False

        while iteration < self.max_iterations and not should_stop and not self._stop_current_task:
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
            
            # Record token usage and track prompt_tokens for compression
            if response.usage:
                last_prompt_tokens = response.usage.get("prompt_tokens", 0)
                self._record_token_usage(
                    session_instance_id=session_instance_id,
                    provider_name=provider_type,
                    model_id=model,
                    usage=response.usage
                )
            
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

                # Execute tools with error handling
                for tool_call in response.tool_calls:
                    # Check if task should stop
                    if self._stop_current_task:
                        logger.info("Task stopped by user request")
                        break
                    
                    result = None
                    try:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                        # Emit tool call start (include assistant content if any)
                        try:
                            await self._emit("agent_tool_call", {
                                "tool": tool_call.name,
                                "args": tool_call.arguments,
                                "content": response.content if response.content else None,
                                "iteration": iteration,
                                "tool_call_id": tool_call.id
                            }, channel=msg.channel)
                        except Exception as emit_err:
                            logger.warning(f"Failed to emit tool call event: {emit_err}")

                        # Inject channel, chat_id, and session_instance_id for action tools
                        tool_args = tool_call.arguments.copy()
                        if tool_call.name == "action":
                            tool_args["_channel"] = msg.channel
                            tool_args["_chat_id"] = msg.chat_id
                            tool_args["_session_instance_id"] = session.active_instance.id

                        # Execute tool with error handling
                        try:
                            result = await self.tools.execute(tool_call.name, tool_args)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tool_call.name} - {e}")
                            result = f"Error executing tool {tool_call.name}: {str(e)}"

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
                        try:
                            result_preview = result[:500] + "..." if len(result) > 500 else result
                            await self._emit("agent_tool_result", {
                                "tool": tool_call.name,
                                "result": result_preview,
                                "tool_call_id": tool_call.id,
                                "iteration": iteration
                            }, channel=msg.channel)
                        except Exception as e:
                            logger.warning(f"Failed to emit tool result event: {e}")

                    except Exception as outer_e:
                        import traceback
                        traceback.print_exc()
                        logger.error(f"Unexpected error in tool call processing: {tool_call.name} - {outer_e}")
                        result = f"Unexpected error processing tool {tool_call.name}: {str(outer_e)}"

                    # Always save tool result to database, even if errors occurred
                    if result is not None:
                        try:
                            session.add_message("tool", result,
                                              message_type="tool_result",
                                              name=tool_call.name,
                                              tool_call_id=tool_call.id,
                                              metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                            self.sessions.save(session)
                        except Exception as save_err:
                            logger.error(f"Failed to save tool result to database: {save_err}")

                        try:
                            messages = self.context.add_tool_result(
                                messages, tool_call.id, tool_call.name, result, provider_type
                            )
                        except Exception as add_err:
                            logger.error(f"Failed to add tool result to messages: {add_err}")
            else:
                # No tool calls, we're done
                final_content = response.content
                # Save final assistant response immediately
                session.add_message("assistant", final_content or "",
                                  message_type=msg.message_type,
                                  metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                self.sessions.save(session)
                break

        # Check if stopped by user request
        if self._stop_current_task and final_content is None:
            final_content = "任务已被用户暂停。"

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        await self.compressor.maybe_compress(session, prompt_tokens=last_prompt_tokens)

        logger.info(f"[AgentLoop] Sending final response with {len(final_content)} chars")
        await self._send_stream_chunks(final_content, current_session, msg.channel)

        logger.info(f"[AgentLoop] Publishing agent_finish event")
        await self.bus.publish_event(AgentEvent(
            event_type="agent_finish",
            data={"content": final_content, "session": msg.chat_id},
            channel=msg.channel
        ))
        logger.info(f"[AgentLoop] agent_finish event published")

        # Get TTS config for metadata (channel will handle TTS)
        tts_enabled = False
        tts_config = {}
        if session_instance_id:
            try:
                tts_result = self.tts_service.get_instance_tts_config(session_instance_id)
                tts_enabled = tts_result.get("enabled", False)
                tts_config = tts_result.get("config", {})
            except Exception as tts_err:
                logger.warning(f"Failed to check TTS config: {tts_err}")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={
                "session_instance_id": session_instance_id,
                "tts_enabled": tts_enabled,
                "tts_config": tts_config
            }
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

            # Record token usage
            if response.usage:
                self._record_token_usage(
                    session_instance_id=session_instance_id,
                    provider_name=provider_type,
                    model_id=model,
                    usage=response.usage
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
                    result = None
                    try:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                        # Emit tool call start
                        try:
                            await self._emit("agent_tool_call", {
                                "tool": tool_call.name,
                                "args": tool_call.arguments
                            }, channel=origin_channel)
                        except Exception as e:
                            logger.warning(f"Failed to emit tool call event: {e}")

                        # Execute tool with error handling
                        try:
                            result = await self.tools.execute(tool_call.name, tool_call.arguments)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tool_call.name} - {e}")
                            result = f"Error executing tool {tool_call.name}: {str(e)}"

                        # Emit tool call result
                        try:
                            result_preview = result[:500] + "..." if len(result) > 500 else result
                            await self._emit("agent_tool_result", {
                                "tool": tool_call.name,
                                "result": result_preview
                            }, channel=origin_channel)
                        except Exception as e:
                            logger.warning(f"Failed to emit tool result event: {e}")

                    except Exception as outer_e:
                        import traceback
                        traceback.print_exc()
                        logger.error(f"Unexpected error in tool call processing: {tool_call.name} - {outer_e}")
                        result = f"Unexpected error processing tool {tool_call.name}: {str(outer_e)}"

                    # Always save tool result to database, even if errors occurred
                    if result is not None:
                        try:
                            session.add_message("tool", result,
                                              message_type="tool_result",
                                              name=tool_call.name,
                                              tool_call_id=tool_call.id,
                                              metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                            self.sessions.save(session)
                        except Exception as save_err:
                            logger.error(f"Failed to save tool result to database: {save_err}")

                        try:
                            messages = self.context.add_tool_result(
                                messages, tool_call.id, tool_call.name, result, provider_type
                            )
                        except Exception as add_err:
                            logger.error(f"Failed to add tool result to messages: {add_err}")
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
            message_type: Message type for routing/filtering.

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
            elif item.type == "file" and item.file_path:
                file_info = f"\n[用户上传了文件]\n- 文件名: {item.file_name or '未知'}\n- 路径: {item.file_path}\n- 类型: {item.mime_type or '未知'}\n- 大小: {item.file_size or 0} 字节\n"
                if result and result[0].get("type") == "text":
                    result[0]["text"] += file_info
                else:
                    result.append({"type": "text", "text": file_info})
                logger.info(f"[_build_multimodal_content] Added file info: {item.file_name}")

        logger.info(f"[_build_multimodal_content] Built {len(result)} content items")
        return result

    async def _process_streaming_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None
    ) -> OutboundMessage | None:
        """
        Process message with streaming for desktop channel.
        
        This method implements real-time streaming of tokens and tool call status updates.
        """
        # Handle longtask messages (auth requests, completions)
        if msg.message_type in ("longtask_auth", "longtask_complete"):
            await self._process_longtask_message(msg)
            if msg.message_type == "longtask_auth":
                return None

        if msg.channel == "system":
            return await self._process_system_message(msg, session_key=session_key)

        logger.info(f"[Stream] Processing message from {msg.channel}:{msg.sender_id}")

        current_session = session_key or msg.session_key

        # Convert content to JSON-safe format for events
        event_content = msg.text_content if msg.is_multimodal else msg.content

        await self.bus.publish_event(AgentEvent(
            event_type="agent_start",
            data={"content": event_content, "session": current_session},
            channel=msg.channel
        ))

        # Use fixed session key for desktop channel
        session_key = msg.session_key
        if msg.channel == "desktop":
            session_key = "desktop:desktop_session"
        
        # Get instance_id from metadata if provided (frontend selected instance)
        metadata_instance_id = msg.metadata.get("instance_id") if msg.metadata else None
        
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

        # === 1. Check for session management commands (after instance switch) ===
        command_result = await handle_session_command(
            msg.content,
            session_key,
            self.sessions
        )

        if command_result:
            # Command was handled, return response
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=command_result.message
            )
        
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
        
        # Build initial messages
        if msg.is_multimodal:
            user_content = self._build_multimodal_content(msg.content)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=user_content,
                media=None,
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            images = msg.get_images()
            image_list = [{"path": img.image_path, "name": img.image_path.split('/').pop()} for img in images] if images else []
            
            files = msg.get_files()
            file_list = []
            for f in files:
                file_list.append({
                    "path": f.file_path,
                    "name": f.file_name or f.file_path.split('/').pop(),
                    "originalName": f.file_name,
                    "mimeType": f.mime_type,
                    "size": f.file_size
                })
            
            metadata = {}
            if image_list:
                metadata["images"] = image_list
            if file_list:
                metadata["files"] = file_list
            
            metadata = metadata if metadata else None
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
        
        # Agent loop with streaming
        iteration = 0
        final_content = None
        last_prompt_tokens = 0

        should_stop = False

        # Reset stop flag for new task
        self._stop_current_task = False

        while iteration < self.max_iterations and not should_stop and not self._stop_current_task:
            iteration += 1

            # Emit "thinking" event
            await self._emit("agent_thinking", {"iteration": iteration, "session": session.key}, channel=msg.channel)

            # Call LLM with streaming
            provider, model, provider_type = self._get_current_provider_and_model()
            
            full_content = ""
            tool_calls_buffer = {}
            
            try:
                # Use streaming API
                async for chunk in provider.chat_stream(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=model
                ):
                    # Send content token
                    if chunk.content:
                        full_content += chunk.content
                        await self._emit("agent_token", {
                            "content": chunk.content,
                            "session": current_session
                        }, channel=msg.channel)
                    
                    # Handle tool calls (streaming)
                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            # Cache tool call
                            if tc.id not in tool_calls_buffer:
                                tool_calls_buffer[tc.id] = {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "arguments": tc.arguments
                                }
                                # Send tool call start event
                                await self._emit("agent_tool_call_start", {
                                    "tool_call_id": tc.id,
                                    "tool": tc.name,
                                    "iteration": iteration,
                                    "status": "pending"
                                }, channel=msg.channel)
                            else:
                                # Update arguments (streaming)
                                tool_calls_buffer[tc.id]["arguments"].update(tc.arguments)
                                await self._emit("agent_tool_call_streaming", {
                                    "tool_call_id": tc.id,
                                    "tool": tc.name,
                                    "partial_args": tool_calls_buffer[tc.id]["arguments"],
                                    "status": "streaming"
                                }, channel=msg.channel)
                    
                    # Final chunk
                    if chunk.is_final:
                        # Record token usage
                        if chunk.usage:
                            last_prompt_tokens = chunk.usage.get("prompt_tokens", 0)
                            self._record_token_usage(
                                session_instance_id=session_instance_id,
                                provider_name=provider_type,
                                model_id=model,
                                usage=chunk.usage
                            )
                
                # Save assistant message with tool calls
                if tool_calls_buffer:
                    tool_calls_data = [
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": json.dumps(tc_data["arguments"], ensure_ascii=False)
                            }
                        }
                        for tc_data in tool_calls_buffer.values()
                    ]
                    
                    session.add_message("assistant", full_content or "",
                                      message_type="tool_call",
                                      tool_calls=tool_calls_data,
                                      metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                    self.sessions.save(session)
                    
                    # Add assistant message to messages
                    tool_call_dicts = [
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": json.dumps(tc_data["arguments"], ensure_ascii=False)
                            }
                        }
                        for tc_data in tool_calls_buffer.values()
                    ]
                    messages = self.context.add_assistant_message(
                        messages, full_content, tool_call_dicts, provider_type
                    )
                    
                    # Execute tools
                    for tc_id, tc_data in tool_calls_buffer.items():
                        if self._stop_current_task:
                            logger.info("Task stopped by user request")
                            break
                        
                        # Update status to invoking
                        await self._emit("agent_tool_call_invoking", {
                            "tool_call_id": tc_id,
                            "tool": tc_data["name"],
                            "status": "invoking"
                        }, channel=msg.channel)
                        
                        result = None
                        try:
                            # Inject channel, chat_id, and session_instance_id for action tools
                            tool_args = tc_data["arguments"].copy()
                            if tc_data["name"] == "action":
                                tool_args["_channel"] = msg.channel
                                tool_args["_chat_id"] = msg.chat_id
                                tool_args["_session_instance_id"] = session.active_instance.id
                            
                            # Execute tool
                            result = await self.tools.execute(tc_data["name"], tool_args)
                            
                            # Send completion event
                            await self._emit("agent_tool_call_complete", {
                                "tool_call_id": tc_id,
                                "tool": tc_data["name"],
                                "result": result[:500] + "..." if len(result) > 500 else result,
                                "status": "completed"
                            }, channel=msg.channel)
                            
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tc_data['name']} - {e}")
                            result = f"Error executing tool {tc_data['name']}: {str(e)}"
                            
                            # Send error event
                            await self._emit("agent_tool_call_error", {
                                "tool_call_id": tc_id,
                                "tool": tc_data["name"],
                                "error": str(e),
                                "status": "error"
                            }, channel=msg.channel)
                        
                        # Save tool result
                        if result is not None:
                            session.add_message("tool", result,
                                              message_type="tool_result",
                                              name=tc_data["name"],
                                              tool_call_id=tc_id,
                                              metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                            self.sessions.save(session)
                            
                            messages = self.context.add_tool_result(
                                messages, tc_id, tc_data["name"], result, provider_type
                            )
                else:
                    # No tool calls, we're done
                    final_content = full_content
                    # Save final assistant response
                    session.add_message("assistant", final_content or "",
                                      message_type=msg.message_type,
                                      metadata={"session_instance_id": session_instance_id} if session_instance_id else {})
                    self.sessions.save(session)
                    break
                    
            except Exception as e:
                import traceback
                logger.error(f"[Stream] Error in streaming: {e}")
                logger.error(traceback.format_exc())
                final_content = f"Error: {str(e)}"
                break

        # Check if stopped by user request
        if self._stop_current_task and final_content is None:
            final_content = "任务已被用户暂停。"

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        await self.compressor.maybe_compress(session, prompt_tokens=last_prompt_tokens)

        logger.info(f"[Stream] Sending final response with {len(final_content)} chars")

        await self.bus.publish_event(AgentEvent(
            event_type="agent_finish",
            data={"content": final_content, "session": msg.chat_id},
            channel=msg.channel
        ))

        # Get TTS config for metadata
        tts_enabled = False
        tts_config = {}
        if session_instance_id:
            try:
                tts_result = self.tts_service.get_instance_tts_config(session_instance_id)
                tts_enabled = tts_result.get("enabled", False)
                tts_config = tts_result.get("config", {})
            except Exception as tts_err:
                logger.warning(f"Failed to check TTS config: {tts_err}")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={
                "session_instance_id": session_instance_id,
                "tts_enabled": tts_enabled,
                "tts_config": tts_config
            }
        )

    def _record_token_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        usage: dict,
        request_type: str = "chat"
    ) -> None:
        """Record token usage to database.
        
        Args:
            session_instance_id: The session instance ID
            provider_name: Provider name (e.g., openai, anthropic)
            model_id: Model ID (e.g., gpt-4, claude-3-opus)
            usage: Usage dict with prompt_tokens, completion_tokens, total_tokens
            request_type: Type of request (chat, compression, etc.)
        """
        try:
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            self.token_usage.record_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_name,
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                request_type=request_type
            )
            
            logger.debug(f"Token usage recorded: {provider_name}/{model_id} - "
                        f"prompt={prompt_tokens}, completion={completion_tokens}")
        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")


