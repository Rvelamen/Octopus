"""Agent loop: the core processing engine."""

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent, MessageContentItem
from backend.core.events.bus import MessageBus
from backend.agent.context import set_agent_loop
from backend.agent.shared import PreparedContext
from backend.data.commands import handle_session_command
from backend.tools.message import MessageTool
from backend.tools.spawn import SpawnTool
from backend.tools.cron import CronTool

from backend.agent.processors import (
    LongtaskMessageProcessor,
    SystemMessageProcessor,
    NonStreamingMessageProcessor,
    StreamingMessageProcessor,
)

from backend.agent.container import AgentContainer


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

    def __init__(self, container: AgentContainer):
        self._container = container

        set_agent_loop(self)

        self._running = False
        self._stop_current_task = False
        self._instance_stop_flags: dict[int, bool] = {}

        self._processors = [
            LongtaskMessageProcessor(self),
            SystemMessageProcessor(self),
            StreamingMessageProcessor(self),
            NonStreamingMessageProcessor(self),
        ]

    @property
    def bus(self) -> MessageBus:
        return self._container.bus

    @property
    def workspace(self) -> Path:
        return self._container.workspace

    @property
    def db(self) -> Any:
        return self._container.db

    @property
    def exec_config(self) -> Any:
        return self._container.exec_config

    @property
    def cron_service(self) -> Any:
        return self._container.cron_service

    @property
    def context(self) -> Any:
        return self._container.context

    @property
    def memory_manager(self) -> Any:
        return self._container.memory_manager

    @property
    def sessions(self) -> Any:
        return self._container.sessions

    @property
    def tools(self) -> Any:
        return self._container.tools

    @property
    def token_usage(self) -> Any:
        return self._container.token_usage

    @property
    def compressor(self) -> Any:
        return self._container.compressor

    @property
    def aggregator(self) -> Any:
        return self._container.aggregator

    @property
    def subagents(self) -> Any:
        return self._container.subagents

    @property
    def extension_loader(self) -> Any:
        return self._container.extension_loader

    @property
    def tts_service(self) -> Any:
        return self._container.tts_service

    @property
    def max_iterations(self) -> int:
        """Get max iterations from config or default."""
        from backend.agent.config_service import AgentConfigService
        try:
            config_service = AgentConfigService(self.db)
            defaults = config_service._get_agent_defaults_repo().get_or_create_defaults()
            if defaults and defaults.max_iterations is not None:
                return defaults.max_iterations
        except Exception as e:
            logger.warning(f"Failed to get max_iterations from config: {e}")
        return self._container.max_iterations

    def _get_current_provider_and_model(self) -> tuple[Any, str, str, int, float]:
        return self._container._get_current_provider_and_model()

    def _record_token_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        usage: dict,
        request_type: str = "chat"
    ) -> None:
        self._container._record_token_usage(
            session_instance_id, provider_name, model_id, usage, request_type
        )

    async def _emit(self, event_type: str, data: dict, channel: str = ""):
        """Emit an agent event to the bus."""
        await self.bus.publish_event(AgentEvent(
            event_type=event_type,
            data=data,
            channel=channel
        ))

    async def _send_stream_chunks(self, content: str, session: str, channel: str, session_instance_id: int | None = None, chunk_size: int = 10):
        """Send content as a series of stream chunks to simulate streaming for non-desktop channels."""
        if not content:
            return

        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            await self._emit("agent_chunk", {
                "content": chunk,
                "session": session,
                "session_instance_id": session_instance_id
            }, channel=channel)

    async def load_extensions(self) -> dict[str, bool]:
        """Load all extensions from workspace/extensions."""
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
        """Stop the current running task (all instances)."""
        self._stop_current_task = True
        for instance_id in list(self._instance_stop_flags.keys()):
            self._instance_stop_flags[instance_id] = True
        logger.info("Agent current task stopping (all instances)")

    def stop_instance_task(self, instance_id) -> None:
        """Stop the running task for a specific instance."""
        instance_id_int = int(instance_id) if instance_id else None
        if instance_id_int:
            self._instance_stop_flags[instance_id_int] = True
            logger.info(f"Agent task stop signal sent for instance: {instance_id_int}")
        else:
            self._stop_current_task = True
            logger.info("Agent task stop signal sent (no instance_id, using global stop)")

    def reset_stop_flag(self, instance_id=None) -> None:
        """Reset the stop flag for new task."""
        if instance_id:
            instance_id_int = int(instance_id) if instance_id else None
            if instance_id_int and instance_id_int in self._instance_stop_flags:
                self._instance_stop_flags[instance_id_int] = False
        else:
            self._stop_current_task = False

    def _should_stop(self, instance_id=None) -> bool:
        """Check if task should stop for a specific instance or globally."""
        if self._stop_current_task:
            return True
        if instance_id:
            instance_id_int = int(instance_id) if instance_id else None
            if instance_id_int and self._instance_stop_flags.get(instance_id_int, False):
                return True
        return False

    def _save_cancelled_tool_results_and_mark_stopped(
        self,
        session: Any,
        *,
        tool_call_entries: list[tuple[str, str]],
        saved_ids: set[str],
        session_instance_id: int | None,
        start_time: float,
    ) -> None:
        """Persist placeholder tool results for calls not executed after user stop; tag last assistant message."""
        cancel = "已取消（用户暂停）"
        for tc_id, tool_name in tool_call_entries:
            tid = str(tc_id)
            if tid in saved_ids:
                continue
            meta: dict[str, Any] = {"cancelled_by_user": True}
            if session_instance_id:
                meta["session_instance_id"] = session_instance_id
            session.add_message(
                "tool",
                cancel,
                message_type="tool_result",
                name=tool_name,
                tool_call_id=tid,
                metadata=meta,
            )
        try:
            self.sessions.save(session)
        except Exception as e:
            logger.error(f"Failed to save session after cancelled tool placeholders: {e}")

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Always mark the in-memory assistant message with tool_calls so that
        # historical rendering can detect the paused state even when
        # session_instance_id is None or update_last_message_metadata hits the
        # wrong message.
        for msg in reversed(session.messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                msg.setdefault("metadata", {})
                msg["metadata"]["stopped_by_user"] = True
                msg["metadata"]["elapsed_ms"] = elapsed_ms
                break

        if session_instance_id:
            try:
                self.sessions.update_last_message_metadata(
                    int(session_instance_id),
                    {"stopped_by_user": True, "elapsed_ms": elapsed_ms},
                )
            except Exception as e:
                logger.warning(f"Failed to update stopped_by_user metadata: {e}")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None
    ) -> OutboundMessage | None:
        """Process a single inbound message by delegating to the appropriate processor."""
        for processor in self._processors:
            if processor.can_process(msg):
                return await processor.process(msg, session_key)
        logger.warning(f"No processor found for message type {msg.message_type} on channel {msg.channel}")
        return None

    async def _prepare_session_and_context(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
    ) -> tuple[PreparedContext | None, OutboundMessage | None]:
        """
        Common preparation logic shared by streaming and non-streaming paths.

        Returns:
            (PreparedContext, None) when ready for LLM call
            (None, OutboundMessage) for early returns
            (None, None) for longtask_auth
        """
        if msg.message_type == "longtask_complete":
            await self._process_longtask_message(msg)

        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        current_session = session_key or msg.session_key
        event_content = msg.text_content if msg.is_multimodal else msg.content

        session_key = msg.session_key
        if msg.channel == "desktop":
            session_key = "desktop:desktop_session"

        metadata_instance_id = msg.metadata.get("instance_id") if msg.metadata else None

        if metadata_instance_id:
            success, switch_msg = self.sessions.switch_instance(session_key, int(metadata_instance_id))
            if success:
                self.sessions._cache.pop(session_key, None)
                session = self.sessions.get_or_create(session_key)
                logger.info(f"Switched to instance {metadata_instance_id} for session {session_key}")
            else:
                logger.warning(f"Failed to switch to instance {metadata_instance_id}: {switch_msg}")
                session = self.sessions.get_or_create(session_key)
        else:
            session = self.sessions.get_or_create(session_key)

        command_result = await handle_session_command(
            msg.content,
            session_key,
            self.sessions
        )

        if command_result:
            return None, OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=command_result.message
            )

        session_instance_id = session.active_instance.id if session.active_instance else None

        await self.bus.publish_event(AgentEvent(
            event_type="agent_start",
            data={"content": event_content, "session": current_session, "session_instance_id": session_instance_id},
            channel=msg.channel
        ))

        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id, session_instance_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id, session_instance_id)

        if msg.is_multimodal:
            user_content = self._build_multimodal_content(msg.content)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=user_content,
                media=None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                session_instance_id=session_instance_id,
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
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=msg.content,
                media=msg.media if msg.media else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                session_instance_id=session_instance_id,
            )
            session.add_message("user", msg.content, message_type=msg.message_type)
        self.sessions.save(session)

        return PreparedContext(
            session=session,
            messages=messages,
            session_instance_id=session_instance_id,
            current_session=current_session,
            session_key=session_key,
        ), None

    async def _process_longtask_message(self, msg: InboundMessage) -> OutboundMessage | None:
        processor = LongtaskMessageProcessor(self)
        return await processor.process(msg)

    async def _process_system_message(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        processor = SystemMessageProcessor(self)
        return await processor.process(msg, session_key)

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
    ) -> str:
        """Process a message directly without going through the bus."""
        from backend.core.events.types import InboundMessage

        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            content=content,
            session_key=session_key,
        )
        response = await self._process_message(msg)
        return response.content if response else ""

    def _build_multimodal_content(self, content_items: list[MessageContentItem]) -> str:
        """Build a multimodal message content string from content items."""
        parts = []
        for item in content_items:
            if item.type == "text":
                parts.append(item.text)
            elif item.type == "image":
                try:
                    image_path = Path(item.image_path)
                    if image_path.exists():
                        with open(image_path, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode("utf-8")
                        parts.append(f"<image>{image_data}</image>")
                    else:
                        parts.append(f"[Image not found: {item.image_path}]")
                except Exception as e:
                    parts.append(f"[Error reading image: {e}]")
            elif item.type == "file":
                parts.append(f"[File: {item.file_path}]")

        return "\n".join(parts)
