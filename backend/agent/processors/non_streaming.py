"""Non-streaming message processor."""
import json
import time

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.agent.shared import _normalize_usage
from .base import MessageProcessor


class NonStreamingMessageProcessor(MessageProcessor):
    """Processor for non-streaming messages (non-desktop channels)."""

    def can_process(self, msg: InboundMessage) -> bool:
        return msg.channel != "desktop"

    async def process(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """Process message without streaming (original logic)."""
        ctx, early_response = await self.agent_loop._prepare_session_and_context(msg, session_key)
        if ctx is None:
            return early_response

        session = ctx.session
        messages = ctx.messages
        session_instance_id = ctx.session_instance_id
        current_session = ctx.current_session

        # Agent loop
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

        while iteration < self.agent_loop.max_iterations and not should_stop and not self.agent_loop._should_stop(instance_id_int):
            iteration += 1

            await self.agent_loop._emit(
                "agent_thinking",
                {"iteration": iteration, "session": session.key, "session_instance_id": session_instance_id},
                channel=msg.channel
            )

            provider, model, provider_type, max_tokens, temperature = self.agent_loop._get_current_provider_and_model()
            response = await provider.chat(
                messages=messages,
                tools=self.agent_loop.tools.get_definitions(),
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info(f"LLM Response: {response}")

            normalized = _normalize_usage(response.usage, messages, response.content or "", model)
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

            if response.has_tool_calls:
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

                session.add_message(
                    "assistant",
                    response.content or "",
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
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.agent_loop.context.add_assistant_message(
                    messages, response.content, tool_call_dicts, provider_type
                )

                saved_tool_ids: set[str] = set()
                for tool_call in response.tool_calls:
                    if self.agent_loop._should_stop(instance_id_int):
                        logger.info("Task stopped by user request")
                        break

                    result = None
                    try:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                        try:
                            await self.agent_loop._emit(
                                "agent_tool_call",
                                {
                                    "tool": tool_call.name,
                                    "args": tool_call.arguments,
                                    "content": response.content if response.content else None,
                                    "iteration": iteration,
                                    "tool_call_id": tool_call.id,
                                    "session_instance_id": session_instance_id
                                },
                                channel=msg.channel
                            )
                        except Exception as emit_err:
                            logger.warning(f"Failed to emit tool call event: {emit_err}")

                        tool_args = tool_call.arguments.copy()
                        if tool_call.name == "action":
                            tool_args["_channel"] = msg.channel
                            tool_args["_chat_id"] = msg.chat_id
                            tool_args["_session_instance_id"] = session.active_instance.id

                        if tool_call.name == "spawn":
                            tool_args["parent_tool_call_id"] = tool_call.id

                        try:
                            result = await self.agent_loop.tools.execute(tool_call.name, tool_args)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tool_call.name} - {e}")
                            result = f"Error executing tool {tool_call.name}: {str(e)}"

                        is_longtask_auth = (
                            tool_call.name == "action" and
                            tool_args.get("type") == "plugin" and
                            tool_args.get("action") == "auth"
                        )

                        if is_longtask_auth and "success" in result:
                            plugin_name = tool_args.get("name", "longtask")
                            final_content = f"✅ 授权已发送，{plugin_name} 将继续执行任务。任务完成后我会通知您。"
                            messages = self.agent_loop.context.add_tool_result(
                                messages, tool_call.id, tool_call.name, result, provider_type
                            )
                            session.add_message(
                                "tool",
                                result,
                                message_type="tool_result",
                                name=tool_call.name,
                                tool_call_id=tool_call.id,
                                metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
                            )
                            self.agent_loop.sessions.save(session)
                            saved_tool_ids.add(str(tool_call.id))
                            should_stop = True
                            break

                        # 注意：subagent 的 token 不累计到主 agent 的 usage 中，
                        # 因为 subagent 的完整 react 不会出现在主上下文中
                        try:
                            result_preview = result if tool_call.name == "spawn" else (
                                result[:500] + "..." if len(result) > 500 else result
                            )
                            await self.agent_loop._emit(
                                "agent_tool_result",
                                {
                                    "tool": tool_call.name,
                                    "result": result_preview,
                                    "tool_call_id": tool_call.id,
                                    "iteration": iteration,
                                    "session_instance_id": session_instance_id
                                },
                                channel=msg.channel
                            )
                        except Exception as e:
                            logger.warning(f"Failed to emit tool result event: {e}")

                    except Exception as outer_e:
                        import traceback
                        traceback.print_exc()
                        logger.error(f"Unexpected error in tool call processing: {tool_call.name} - {outer_e}")
                        result = f"Unexpected error processing tool {tool_call.name}: {str(outer_e)}"

                    if result is not None:
                        try:
                            session.add_message(
                                "tool",
                                result,
                                message_type="tool_result",
                                name=tool_call.name,
                                tool_call_id=tool_call.id,
                                metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
                            )
                            self.agent_loop.sessions.save(session)
                        except Exception as save_err:
                            logger.error(f"Failed to save tool result to database: {save_err}")

                        try:
                            messages = self.agent_loop.context.add_tool_result(
                                messages, tool_call.id, tool_call.name, result, provider_type
                            )
                        except Exception as add_err:
                            logger.error(f"Failed to add tool result to messages: {add_err}")

                        saved_tool_ids.add(str(tool_call.id))

                if response.tool_calls and self.agent_loop._should_stop(instance_id_int):
                    entries = [(str(tc.id), tc.name) for tc in response.tool_calls]
                    self.agent_loop._save_cancelled_tool_results_and_mark_stopped(
                        session,
                        tool_call_entries=entries,
                        saved_ids=saved_tool_ids,
                        session_instance_id=session_instance_id,
                        start_time=start_time,
                    )

                if not should_stop and not self.agent_loop._should_stop(instance_id_int):
                    await self.agent_loop._emit(
                        "agent_iteration_complete",
                        {
                            "iteration": iteration,
                            "final_content": response.content or "",
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
                final_content = response.content
                session.add_message(
                    "assistant",
                    final_content or "",
                    message_type=msg.message_type,
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

        if self.agent_loop._should_stop(instance_id_int) and final_content is None:
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

        logger.info(f"[AgentLoop] Sending final response with {len(final_content)} chars")
        await self.agent_loop._send_stream_chunks(final_content, current_session, msg.channel, session_instance_id)

        elapsed_ms = int((time.time() - start_time) * 1000)

        tts_enabled = False
        tts_config = {}
        if session_instance_id:
            try:
                tts_result = self.agent_loop.tts_service.get_instance_tts_config(session_instance_id)
                tts_enabled = tts_result.get("enabled", False)
                tts_config = tts_result.get("config", {})
            except Exception as tts_err:
                logger.warning(f"Failed to check TTS config: {tts_err}")

        if session_instance_id and final_content is not None:
            try:
                self.agent_loop.sessions.update_last_message_metadata(
                    session_instance_id,
                    {
                        "elapsed_ms": elapsed_ms,
                        "usage": {
                            "prompt_tokens": total_prompt_tokens,
                            "completion_tokens": total_completion_tokens,
                            "total_tokens": total_prompt_tokens + total_completion_tokens,
                            "cached_tokens": total_cached_tokens
                        }
                    }
                )
            except Exception as update_err:
                logger.warning(f"Failed to update message metadata with elapsed_ms: {update_err}")

        logger.info("[AgentLoop] Publishing agent_finish event")
        logger.info(
            f"[AgentLoop] Token usage for this run: prompt={total_prompt_tokens}, "
            f"completion={total_completion_tokens}, cached={total_cached_tokens}"
        )
        await self.agent_loop.bus.publish_event(AgentEvent(
            event_type="agent_finish",
            data={
                "content": final_content,
                "session": msg.chat_id,
                "elapsed_ms": elapsed_ms,
                "token_usage": {
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "total_tokens": total_prompt_tokens + total_completion_tokens,
                    "cached_tokens": total_cached_tokens
                },
                "session_instance_id": session_instance_id,
                "messages": session.messages[-20:]
            },
            channel=msg.channel
        ))
        logger.info("[AgentLoop] agent_finish event published")

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
