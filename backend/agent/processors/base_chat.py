"""Shared base class for chat message processors (streaming & non-streaming).

Extracts ~85% duplicated logic from StreamingMessageProcessor and
NonStreamingMessageProcessor into a single template-method base.
"""

import json
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.agent.shared import _normalize_usage
from .base import MessageProcessor


@dataclass
class ToolCallInfo:
    """Unified tool-call representation for both streaming and non-streaming paths."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Unified LLM response returned by :meth:`BaseChatProcessor._call_llm`."""

    content: str | None
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    usage: dict | None = None
    should_stop_after_tools: bool = False


class BaseChatProcessor(MessageProcessor):
    """Template-method base for chat-oriented message processors.

    Subclasses only need to implement:

    * :meth:`can_process`
    * :meth:`_call_llm`

    Optionally override the hook methods to customise event emission and
    post-finish behaviour.
    """

    # ------------------------------------------------------------------
    # Abstract interface (subclass must implement)
    # ------------------------------------------------------------------

    @abstractmethod
    async def _call_llm(
        self,
        messages: list,
        tools: list,
        model: str,
        max_tokens: int,
        temperature: float,
        msg: InboundMessage,
        session_instance_id: int | None,
        current_session: str,
    ) -> LLMResponse:
        """Execute the provider-specific LLM call.

        Streaming subclasses emit per-chunk events inside this method;
        non-streaming subclasses simply ``await provider.chat(...)``.
        """

    # ------------------------------------------------------------------
    # Hook methods (optional overrides)
    # ------------------------------------------------------------------

    def _build_usage_dict(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
    ) -> dict[str, int]:
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
        }

    def _build_metadata(
        self,
        session_instance_id: int | None,
        extra: dict | None = None,
    ) -> dict:
        meta: dict[str, Any] = {}
        if session_instance_id:
            meta["session_instance_id"] = session_instance_id
        if extra:
            meta.update(extra)
        return meta

    def _get_tool_error_message(self, tool_name: str, error: Exception) -> str:
        return f"Error executing tool {tool_name}: {str(error)}"

    def _tool_call_id(self, tc: ToolCallInfo) -> str:
        """Normalised tool-call id used for tracking / cancellation."""
        return str(tc.id)

    async def _on_tool_execution_start(
        self,
        tc: ToolCallInfo,
        iteration: int,
        session_instance_id: int | None,
        response_content: str | None,
        msg: InboundMessage,
    ) -> None:
        """Hook: emit events *before* a tool is executed."""

    async def _on_tool_execution_success(
        self,
        tc: ToolCallInfo,
        result: str,
        iteration: int,
        session_instance_id: int | None,
        msg: InboundMessage,
    ) -> None:
        """Hook: emit events after a tool has executed successfully."""

    async def _on_tool_execution_error(
        self,
        tc: ToolCallInfo,
        error: Exception,
        iteration: int,
        session_instance_id: int | None,
        msg: InboundMessage,
    ) -> None:
        """Hook: emit events when a tool execution raises an exception."""

    def _check_tool_early_stop(
        self,
        tc: ToolCallInfo,
        tool_args: dict,
        result: str | None,
        msg: InboundMessage,
    ) -> str | None:
        """Return a ``final_content`` string to stop the loop, or ``None`` to continue."""
        return None

    async def _post_agent_finish(
        self,
        final_content: str | None,
        current_session: str,
        channel: str,
        session_instance_id: int | None,
    ) -> None:
        """Hook: run after ``agent_finish`` is published (e.g. send stream chunks)."""

    # ------------------------------------------------------------------
    # Template method
    # ------------------------------------------------------------------

    async def process(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
    ) -> OutboundMessage | None:
        ctx, early_response = await self.agent_loop._prepare_session_and_context(msg, session_key)
        if ctx is None:
            return early_response

        session = ctx.session
        messages = ctx.messages
        session_instance_id = ctx.session_instance_id
        current_session = ctx.current_session

        iteration = 0
        final_content = None
        last_prompt_tokens = 0

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cached_tokens = 0

        should_stop = False

        self.agent_loop._stop_current_task = False
        instance_id_int = int(session_instance_id) if session_instance_id else None
        if instance_id_int:
            self.agent_loop._instance_stop_flags[instance_id_int] = False

        start_time = time.time()

        last_tool_call_entries: list[tuple[str, str]] = []
        last_saved_tool_ids: set[str] = set()

        while (
            iteration < self.agent_loop.max_iterations
            and not should_stop
            and not self.agent_loop._should_stop(instance_id_int)
        ):
            iteration += 1

            await self.agent_loop._emit(
                "agent_thinking",
                {"iteration": iteration, "session": session.key, "session_instance_id": session_instance_id},
                channel=msg.channel,
            )

            provider, model, provider_type, max_tokens, temperature = (
                self.agent_loop._get_current_provider_and_model()
            )

            try:
                llm_response = await self._call_llm(
                    messages=messages,
                    tools=self.agent_loop.tools.get_definitions(),
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    msg=msg,
                    session_instance_id=session_instance_id,
                    current_session=current_session,
                )

                if llm_response.usage:
                    normalized = _normalize_usage(
                        llm_response.usage, messages, llm_response.content or "", model
                    )
                    last_prompt_tokens = normalized["prompt_tokens"] + normalized["cached_tokens"]
                    total_prompt_tokens += normalized["prompt_tokens"] + normalized["cached_tokens"]
                    total_completion_tokens += normalized["completion_tokens"]
                    total_cached_tokens += normalized["cached_tokens"]
                    self.agent_loop._record_token_usage(
                        session_instance_id=session_instance_id,
                        provider_name=provider_type,
                        model_id=model,
                        usage=normalized,
                    )

                if llm_response.tool_calls:
                    tool_calls_data = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in llm_response.tool_calls
                    ]

                    session.add_message(
                        "assistant",
                        llm_response.content or "",
                        message_type="tool_call",
                        tool_calls=tool_calls_data,
                        metadata=self._build_metadata(
                            session_instance_id,
                            {
                                "usage": self._build_usage_dict(
                                    total_prompt_tokens, total_completion_tokens, total_cached_tokens
                                )
                            },
                        ),
                    )
                    self.agent_loop.sessions.save(session)

                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in llm_response.tool_calls
                    ]
                    messages = self.agent_loop.context.add_assistant_message(
                        messages, llm_response.content, tool_call_dicts, provider_type
                    )

                    saved_tool_ids: set[str] = set()
                    last_tool_call_entries = [(tc.id, tc.name) for tc in llm_response.tool_calls]
                    last_saved_tool_ids = saved_tool_ids

                    for tc in llm_response.tool_calls:
                        if self.agent_loop._should_stop(instance_id_int):
                            logger.info("Task stopped by user request")
                            break

                        result = None
                        try:
                            await self._on_tool_execution_start(
                                tc, iteration, session_instance_id, llm_response.content, msg
                            )

                            tool_args = self._inject_tool_args(tc, msg, session)

                            try:
                                result = await self.agent_loop.tools.execute(tc.name, tool_args)
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                logger.error(f"Tool execution error: {tc.name} - {e}")
                                result = self._get_tool_error_message(tc.name, e)
                                await self._on_tool_execution_error(tc, e, iteration, session_instance_id, msg)
                            else:
                                await self._on_tool_execution_success(tc, result, iteration, session_instance_id, msg)

                            early_stop_content = self._check_tool_early_stop(tc, tool_args, result, msg)
                            if early_stop_content is not None:
                                should_stop = True
                                final_content = early_stop_content

                            if tool_call_id := self._tool_call_id(tc):
                                saved_tool_ids.add(tool_call_id)

                        except Exception as outer_e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Unexpected error in tool call processing: {tc.name} - {outer_e}")
                            result = f"Unexpected error processing tool {tc.name}: {str(outer_e)}"

                        if result is not None:
                            try:
                                session.add_message(
                                    "tool",
                                    result,
                                    message_type="tool_result",
                                    name=tc.name,
                                    tool_call_id=tc.id,
                                    metadata=self._build_metadata(session_instance_id),
                                )
                                self.agent_loop.sessions.save(session)
                            except Exception as save_err:
                                logger.error(f"Failed to save tool result to database: {save_err}")

                            try:
                                messages = self.agent_loop.context.add_tool_result(
                                    messages, tc.id, tc.name, result, provider_type
                                )
                            except Exception as add_err:
                                logger.error(f"Failed to add tool result to messages: {add_err}")

                        if should_stop:
                            break

                    if not should_stop and not self.agent_loop._should_stop(instance_id_int):
                        await self.agent_loop._emit(
                            "agent_iteration_complete",
                            {
                                "iteration": iteration,
                                "final_content": llm_response.content or "",
                                "status": "completed",
                                "session_instance_id": session_instance_id,
                                "token_usage": self._build_usage_dict(
                                    total_prompt_tokens, total_completion_tokens, total_cached_tokens
                                ),
                                "messages": session.messages[-20:],
                            },
                            channel=msg.channel,
                        )
                else:
                    final_content = llm_response.content
                    usage = self._build_usage_dict(total_prompt_tokens, total_completion_tokens, total_cached_tokens)
                    session.add_message(
                        "assistant",
                        final_content or "",
                        message_type=msg.message_type,
                        metadata=self._build_metadata(session_instance_id, {"usage": usage}),
                    )
                    self.agent_loop.sessions.save(session)
                    await self.agent_loop._emit(
                        "agent_iteration_complete",
                        {
                            "iteration": iteration,
                            "final_content": final_content or "",
                            "status": "completed",
                            "session_instance_id": session_instance_id,
                            "token_usage": usage,
                            "messages": session.messages[-20:],
                        },
                        channel=msg.channel,
                    )
                    break

            except Exception as e:
                import traceback
                logger.error(f"[{self.__class__.__name__}] Error in agent loop: {e}")
                logger.error(traceback.format_exc())
                final_content = f"Error: {str(e)}"
                break

        # ---- Stop / cancelled handling ----
        if self.agent_loop._should_stop(instance_id_int):
            self.agent_loop._save_cancelled_tool_results_and_mark_stopped(
                session,
                tool_call_entries=last_tool_call_entries,
                saved_ids=last_saved_tool_ids,
                session_instance_id=session_instance_id,
                start_time=start_time,
            )

            if final_content is None:
                final_content = "任务已被用户暂停。"
                session.add_message(
                    "assistant",
                    final_content,
                    message_type="stopped",
                    metadata=self._build_metadata(session_instance_id, {"stopped_by_user": True}),
                )
                self.agent_loop.sessions.save(session)
                await self.agent_loop._emit(
                    "agent_stopped",
                    {
                        "content": final_content,
                        "session": current_session,
                        "session_instance_id": session_instance_id,
                        "status": "stopped",
                    },
                    channel=msg.channel,
                )

        # ---- Max iterations fallback ----
        if final_content is None:
            final_content = (
                f"⚠️ 当前任务已达到最大迭代次数限制（{self.agent_loop.max_iterations} 次），未能完成所有操作。"
                f"\n\n您可以回复 **\"继续\"** 让 Agent 接着处理剩余步骤。"
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        token_usage_data = self._build_usage_dict(
            total_prompt_tokens, total_completion_tokens, total_cached_tokens
        )
        logger.info(f"[{self.__class__.__name__}] Token usage for this run: {token_usage_data}")

        # ---- TTS config ----
        tts_enabled = False
        tts_config = {}
        if session_instance_id:
            try:
                tts_result = self.agent_loop.tts_service.get_instance_tts_config(session_instance_id)
                tts_enabled = tts_result.get("enabled", False)
                tts_config = tts_result.get("config", {})
            except Exception as tts_err:
                logger.warning(f"Failed to check TTS config: {tts_err}")

        # ---- Publish agent_finish ----
        logger.info(f"[{self.__class__.__name__}] Publishing agent_finish event")
        try:
            await self.agent_loop.bus.publish_event(
                AgentEvent(
                    event_type="agent_finish",
                    data={
                        "content": final_content,
                        "session": msg.chat_id,
                        "elapsed_ms": elapsed_ms,
                        "token_usage": token_usage_data,
                        "session_instance_id": session_instance_id,
                        "messages": session.messages[-20:],
                    },
                    channel=msg.channel,
                )
            )
            logger.info(f"[{self.__class__.__name__}] agent_finish event published successfully")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Failed to publish agent_finish event: {e}")
            import traceback
            traceback.print_exc()

        # ---- Post-finish hook (e.g. send stream chunks for non-streaming) ----
        await self._post_agent_finish(final_content, current_session, msg.channel, session_instance_id)

        # ---- Cleanup: compression + memory sync ----
        model_context_window = 0
        if hasattr(self.agent_loop.compressor.sessions.db, "get_model_context_window"):
            model_context_window = self.agent_loop.compressor.sessions.db.get_model_context_window()
        await self.agent_loop.compressor.maybe_compress(
            session, prompt_tokens=last_prompt_tokens, model_context_window=model_context_window
        )

        if self.agent_loop.memory_manager:
            await self.agent_loop.memory_manager.sync_turn(
                user_msg=msg.content,
                assistant_msg=final_content or "",
                session_instance_id=session_instance_id,
            )

        # ---- Persist elapsed_ms ----
        if session_instance_id and final_content is not None:
            try:
                self.agent_loop.sessions.update_last_message_metadata(
                    session_instance_id,
                    {"elapsed_ms": elapsed_ms, "usage": token_usage_data},
                )
            except Exception as update_err:
                logger.warning(f"Failed to update message metadata with elapsed_ms: {update_err}")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={
                "session_instance_id": session_instance_id,
                "tts_enabled": tts_enabled,
                "tts_config": tts_config,
                "elapsed_ms": elapsed_ms,
            },
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _inject_tool_args(
        self,
        tc: ToolCallInfo,
        msg: InboundMessage,
        session: Any,
    ) -> dict:
        """Inject channel / session context into tool arguments."""
        tool_args = tc.arguments.copy()
        if tc.name == "action":
            tool_args["_channel"] = msg.channel
            tool_args["_chat_id"] = msg.chat_id
            tool_args["_session_instance_id"] = session.active_instance.id
        if tc.name == "spawn":
            tool_args["parent_tool_call_id"] = tc.id
        return tool_args