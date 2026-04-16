"""System message processor."""
import json

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage
from backend.tools.message import MessageTool
from backend.tools.spawn import SpawnTool
from backend.tools.cron import CronTool
from backend.agent.shared import _normalize_usage
from .base import MessageProcessor


class SystemMessageProcessor(MessageProcessor):
    """Processor for system messages (e.g., subagent announce, aggregate summary)."""

    def can_process(self, msg: InboundMessage) -> bool:
        return msg.channel == "system"

    async def process(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """Process a system message."""
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
                origin_channel = "cli"
                origin_chat_id = msg.chat_id
            session_key = f"{origin_channel}:{origin_chat_id}"

        session = self.agent_loop.sessions.get_or_create(session_key)

        # If session_instance_id is provided, ensure we're using the correct instance
        if session_instance_id and session.active_instance:
            if session.active_instance.id != session_instance_id:
                logger.warning(
                    f"Session instance mismatch: active={session.active_instance.id}, "
                    f"expected={session_instance_id}. Using provided instance_id for routing."
                )

        # Update tool contexts with session instance ID
        active_instance_id = session.active_instance.id if session.active_instance else None
        target_instance_id = session_instance_id or active_instance_id

        message_tool = self.agent_loop.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)

        spawn_tool = self.agent_loop.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id, target_instance_id)

        cron_tool = self.agent_loop.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id, target_instance_id)

        # Build messages with the announce content
        messages = self.agent_loop.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )

        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None

        # Track token usage (initialized to 0 to avoid NameError in metadata)
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cached_tokens = 0

        # Save input message immediately
        msg_role = "system" if is_aggregate_summary else "user"
        session.add_message(
            msg_role,
            f"[{msg.sender_id}] {msg.content}",
            message_type=msg_type or msg.message_type,
            metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
        )
        self.agent_loop.sessions.save(session)

        while iteration < self.agent_loop.max_iterations:
            iteration += 1

            # Call LLM - get fresh provider and model from config
            provider, model, provider_type, max_tokens, temperature = self.agent_loop._get_current_provider_and_model()
            response = await provider.chat(
                messages=messages,
                tools=self.agent_loop.tools.get_definitions(),
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Record token usage
            normalized = _normalize_usage(response.usage, messages, response.content or "", model)
            self.agent_loop._record_token_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_type,
                model_id=model,
                usage=normalized
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

                for tool_call in response.tool_calls:
                    result = None
                    try:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")

                        # Emit tool call start
                        try:
                            await self.agent_loop._emit(
                                "agent_tool_call",
                                {
                                    "tool": tool_call.name,
                                    "args": tool_call.arguments,
                                    "session_instance_id": session_instance_id
                                },
                                channel=origin_channel
                            )
                        except Exception as e:
                            logger.warning(f"Failed to emit tool call event: {e}")

                        # Execute tool with error handling
                        try:
                            result = await self.agent_loop.tools.execute(tool_call.name, tool_call.arguments)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            logger.error(f"Tool execution error: {tool_call.name} - {e}")
                            result = f"Error executing tool {tool_call.name}: {str(e)}"

                        # Emit tool call result
                        try:
                            result_preview = result[:500] + "..." if len(result) > 500 else result
                            await self.agent_loop._emit(
                                "agent_tool_result",
                                {
                                    "tool": tool_call.name,
                                    "result": result_preview,
                                    "session_instance_id": session_instance_id
                                },
                                channel=origin_channel
                            )
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

                # Emit iteration complete event for system message processing
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
                    channel=origin_channel
                )
            else:
                final_content = response.content
                # Save final assistant response immediately
                session.add_message(
                    "assistant",
                    final_content or "",
                    message_type=msg_type or msg.message_type,
                    metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
                )
                self.agent_loop.sessions.save(session)
                break

        if final_content is None:
            final_content = "Background task completed."

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content,
            metadata={"session_instance_id": session_instance_id} if session_instance_id else {}
        )
