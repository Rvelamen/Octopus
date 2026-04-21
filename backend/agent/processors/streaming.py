"""Streaming message processor."""
import json
import time

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.agent.shared import _normalize_usage
from .base import MessageProcessor


class StreamingMessageProcessor(MessageProcessor):
    """Processor for streaming messages (desktop channel)."""

    def can_process(self, msg: InboundMessage) -> bool:
        return msg.channel == "desktop"

    async def process(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """Process message with streaming for desktop channel."""
        ctx, early_response = await self.agent_loop._prepare_session_and_context(msg, session_key)
        if ctx is None:
            return early_response

        session = ctx.session
        messages = ctx.messages
        session_instance_id = ctx.session_instance_id
        current_session = ctx.current_session

        # Agent loop with streaming
        iteration = 0
        final_content = None
        last_prompt_tokens = 0

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cached_tokens = 0

        should_stop = False

        # Reset stop flags for new task
        self.agent_loop._stop_current_task = False
        instance_id_int = int(session_instance_id) if session_instance_id else None
        if instance_id_int:
            self.agent_loop._instance_stop_flags[instance_id_int] = False

        start_time = time.time()

        # Track the last iteration's tool state so we can mark the thought fold
        # as stopped even when the final iteration had no tool calls.
        last_tool_calls_buffer = {}
        last_saved_tool_ids: set[str] = set()

        while iteration < self.agent_loop.max_iterations and not should_stop and not self.agent_loop._should_stop(instance_id_int):
            iteration += 1

            await self.agent_loop._emit(
                "agent_thinking",
                {"iteration": iteration, "session": session.key, "session_instance_id": session_instance_id},
                channel=msg.channel
            )

            provider, model, provider_type, max_tokens, temperature = self.agent_loop._get_current_provider_and_model()

            full_content = ""
            tool_calls_buffer = {}

            try:
                async for chunk in provider.chat_stream(
                    messages=messages,
                    tools=self.agent_loop.tools.get_definitions(),
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ):
                    if chunk.content:
                        full_content += chunk.content
                        await self.agent_loop._emit(
                            "agent_token",
                            {
                                "content": chunk.content,
                                "session": current_session,
                                "session_instance_id": session_instance_id
                            },
                            channel=msg.channel
                        )

                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            if tc.id not in tool_calls_buffer:
                                tool_calls_buffer[tc.id] = {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "arguments": tc.arguments
                                }
                                await self.agent_loop._emit(
                                    "agent_tool_call_start",
                                    {
                                        "tool_call_id": tc.id,
                                        "tool": tc.name,
                                        "args": tc.arguments,
                                        "partial_args": tc.arguments,
                                        "content": full_content if full_content else None,
                                        "iteration": iteration,
                                        "status": "pending",
                                        "session_instance_id": session_instance_id
                                    },
                                    channel=msg.channel
                                )
                            else:
                                tool_calls_buffer[tc.id]["arguments"].update(tc.arguments)
                                await self.agent_loop._emit(
                                    "agent_tool_call_streaming",
                                    {
                                        "tool_call_id": tc.id,
                                        "tool": tc.name,
                                        "partial_args": tool_calls_buffer[tc.id]["arguments"],
                                        "status": "streaming",
                                        "session_instance_id": session_instance_id
                                    },
                                    channel=msg.channel
                                )

                    if chunk.is_final:
                        normalized = _normalize_usage(chunk.usage, messages, full_content or "", model)
                        last_prompt_tokens = normalized["prompt_tokens"] + normalized["cached_tokens"]
                        total_prompt_tokens += normalized["prompt_tokens"] + normalized["cached_tokens"]
                        total_completion_tokens += normalized["completion_tokens"]
                        total_cached_tokens += normalized["cached_tokens"]
                        self.agent_loop._record_token_usage(
                            session_instance_id=session_instance_id,
                            provider_name=provider_type,
                            model_id=model,
                            usage=normalized
                        )

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

                    session.add_message(
                        "assistant",
                        full_content or "",
                        message_type="tool_call",
                        tool_calls=tool_calls_data,
                        metadata={
                            "session_instance_id": session_instance_id,
                            "usage": {
                                "prompt_tokens": total_prompt_tokens,
                                "completion_tokens": total_completion_tokens,
                                "total_tokens": total_prompt_tokens + total_completion_tokens,
                                "cached_tokens": total_cached_tokens
                            }
                        } if session_instance_id else {
                            "usage": {
                                "prompt_tokens": total_prompt_tokens,
                                "completion_tokens": total_completion_tokens,
                                "total_tokens": total_prompt_tokens + total_completion_tokens,
                                "cached_tokens": total_cached_tokens
                            }
                        }
                    )
                    self.agent_loop.sessions.save(session)

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
                    messages = self.agent_loop.context.add_assistant_message(
                        messages, full_content, tool_call_dicts, provider_type
                    )

                    saved_stream_tool_ids: set[str] = set()
                    last_tool_calls_buffer = tool_calls_buffer
                    last_saved_tool_ids = saved_stream_tool_ids
                    for tc_id, tc_data in tool_calls_buffer.items():
                        if self.agent_loop._should_stop(instance_id_int):
                            logger.info("Task stopped by user request")
                            break

                        await self.agent_loop._emit(
                            "agent_tool_call_invoking",
                            {
                                "tool_call_id": tc_id,
                                "tool": tc_data["name"],
                                "status": "invoking",
                                "session_instance_id": session_instance_id
                            },
                            channel=msg.channel
                        )

                        result = None
                        try:
                            tool_args = tc_data["arguments"].copy()
                            if tc_data["name"] == "action":
                                tool_args["_channel"] = msg.channel
                                tool_args["_chat_id"] = msg.chat_id
                                tool_args["_session_instance_id"] = session.active_instance.id

                            if tc_data["name"] == "spawn":
                                tool_args["parent_tool_call_id"] = tc_id

                            result = await self.agent_loop.tools.execute(tc_data["name"], tool_args)

                            # 注意：subagent 的 token 不累计到主 agent 的 usage 中，
                            # 因为 subagent 的完整 react 不会出现在主上下文中
                            await self.agent_loop._emit(
                                "agent_tool_call_complete",
                                {
                                    "tool_call_id": tc_id,
                                    "tool": tc_data["name"],
                                    "args": tc_data["arguments"],
                                    "result": result if tc_data["name"] == "spawn" else (
                                        result[:500] + "..." if len(result) > 500 else result
                                    ),
                                    "status": "completed",
                                    "session_instance_id": session_instance_id
                                },
                                channel=msg.channel
                            )

                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tc_data['name']} - {e}")
                            result = f"Error executing tool {tc_data['name']}: {str(e)}"

                            await self.agent_loop._emit(
                                "agent_tool_call_error",
                                {
                                    "tool_call_id": tc_id,
                                    "tool": tc_data["name"],
                                    "args": tc_data["arguments"],
                                    "error": str(e),
                                    "status": "error",
                                    "session_instance_id": session_instance_id
                                },
                                channel=msg.channel
                            )

                        if result is not None:
                            session.add_message(
                                "tool",
                                result,
                                message_type="tool_result",
                                name=tc_data["name"],
                                tool_call_id=tc_id,
                                metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
                            )
                            self.agent_loop.sessions.save(session)

                            messages = self.agent_loop.context.add_tool_result(
                                messages, tc_id, tc_data["name"], result, provider_type
                            )

                        saved_stream_tool_ids.add(str(tc_id))

                    if not self.agent_loop._should_stop(instance_id_int):
                        await self.agent_loop._emit(
                            "agent_iteration_complete",
                            {
                                "iteration": iteration,
                                "final_content": full_content or "",
                                "status": "completed",
                                "session_instance_id": session_instance_id,
                                "token_usage": {
                                    "prompt_tokens": total_prompt_tokens,
                                    "completion_tokens": total_completion_tokens,
                                    "total_tokens": total_prompt_tokens + total_completion_tokens,
                                    "cached_tokens": total_cached_tokens
                                },
                                "messages": session.messages[-20:]
                            },
                            channel=msg.channel
                        )
                else:
                    final_content = full_content
                    current_usage = {
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                        "cached_tokens": total_cached_tokens
                    }
                    session.add_message(
                        "assistant",
                        final_content or "",
                        message_type=msg.message_type,
                        metadata={
                            "session_instance_id": session_instance_id,
                            "usage": current_usage
                        } if session_instance_id else {"usage": current_usage}
                    )
                    self.agent_loop.sessions.save(session)
                    await self.agent_loop._emit(
                        "agent_iteration_complete",
                        {
                            "iteration": iteration,
                            "final_content": final_content or "",
                            "status": "completed",
                            "session_instance_id": session_instance_id,
                            "token_usage": {
                                "prompt_tokens": total_prompt_tokens,
                                "completion_tokens": total_completion_tokens,
                                "total_tokens": total_prompt_tokens + total_completion_tokens,
                                "cached_tokens": total_cached_tokens
                            },
                            "messages": session.messages[-20:]
                        },
                        channel=msg.channel
                    )
                    break

            except Exception as e:
                import traceback
                logger.error(f"[Stream] Error in streaming: {e}")
                logger.error(traceback.format_exc())
                final_content = f"Error: {str(e)}"
                break

        if self.agent_loop._should_stop(instance_id_int):
            # Persist cancelled placeholders and mark the last assistant message
            # with tool_calls as stopped, regardless of whether the final
            # iteration had tool calls.
            entries = [(str(tid), tc_data["name"]) for tid, tc_data in last_tool_calls_buffer.items()]
            self.agent_loop._save_cancelled_tool_results_and_mark_stopped(
                session,
                tool_call_entries=entries,
                saved_ids=last_saved_tool_ids,
                session_instance_id=session_instance_id,
                start_time=start_time,
            )

            if final_content is None:
                final_content = "任务已被用户暂停。"
                # 保存暂停状态到数据库
                session.add_message(
                    "assistant",
                    final_content,
                    message_type="stopped",
                    metadata={
                        "session_instance_id": session_instance_id,
                        "stopped_by_user": True,
                    } if session_instance_id else {"stopped_by_user": True}
                )
                self.agent_loop.sessions.save(session)
                # 向前端 emit 明确的暂停事件
                await self.agent_loop._emit(
                    "agent_stopped",
                    {
                        "content": final_content,
                        "session": current_session,
                        "session_instance_id": session_instance_id,
                        "status": "stopped"
                    },
                    channel=msg.channel
                )

        if final_content is None:
            final_content = (
                f"⚠️ 当前任务已达到最大迭代次数限制（{self.agent_loop.max_iterations} 次），未能完成所有操作。"
                f"\n\n您可以回复 **\"继续\"** 让 Agent 接着处理剩余步骤。"
            )

        # Get model context window for smart compression trigger
        model_context_window = 0
        if hasattr(self.agent_loop.compressor.sessions.db, 'get_model_context_window'):
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

        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.info(f"[Stream] Sending final response with {len(final_content)} chars")

        token_usage_data = {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "cached_tokens": total_cached_tokens
        }
        logger.info(f"[Stream] Token usage for this run: {token_usage_data}")

        tts_enabled = False
        tts_config = {}
        if session_instance_id:
            try:
                tts_result = self.agent_loop.tts_service.get_instance_tts_config(session_instance_id)
                tts_enabled = tts_result.get("enabled", False)
                tts_config = tts_result.get("config", {})
            except Exception as tts_err:
                logger.warning(f"Failed to check TTS config: {tts_err}")

        # Persist elapsed_ms BEFORE agent_finish so immediate refetch includes it (stop/complete race)
        if session_instance_id and final_content is not None:
            try:
                self.agent_loop.sessions.update_last_message_metadata(
                    session_instance_id,
                    {
                        "elapsed_ms": elapsed_ms,
                        "usage": token_usage_data
                    }
                )
            except Exception as update_err:
                logger.warning(f"Failed to update message metadata with elapsed_ms: {update_err}")

        try:
            await self.agent_loop.bus.publish_event(AgentEvent(
                event_type="agent_finish",
                data={
                    "content": final_content,
                    "session": msg.chat_id,
                    "elapsed_ms": elapsed_ms,
                    "token_usage": token_usage_data,
                    "session_instance_id": session_instance_id,
                    "messages": session.messages[-20:]
                },
                channel=msg.channel
            ))
            logger.info("[Stream] agent_finish event published successfully")
        except Exception as e:
            logger.error(f"[Stream] Failed to publish agent_finish event: {e}")
            import traceback
            traceback.print_exc()

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={
                "session_instance_id": session_instance_id,
                "tts_enabled": tts_enabled,
                "tts_config": tts_config,
                "elapsed_ms": elapsed_ms
            }
        )
