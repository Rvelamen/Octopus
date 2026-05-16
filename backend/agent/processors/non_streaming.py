"""Non-streaming message processor for non-desktop channels."""

from loguru import logger

from backend.core.events.types import InboundMessage
from .base_chat import BaseChatProcessor, ToolCallInfo, LLMResponse


class NonStreamingMessageProcessor(BaseChatProcessor):
    """Processor for non-streaming messages (non-desktop channels).

    Extends :class:`BaseChatProcessor` and only implements the LLM call,
    non-streaming event hooks, and longtask-auth early-stop logic.
    """

    def can_process(self, msg: InboundMessage) -> bool:
        return msg.channel != "desktop"

    async def _call_llm(
        self,
        messages,
        tools,
        model,
        max_tokens,
        temperature,
        msg,
        session_instance_id,
        current_session,
    ) -> LLMResponse:
        provider, _, provider_type, _, _ = self.agent_loop._get_current_provider_and_model()
        response = await provider.chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        logger.info(f"LLM Response: {response}")

        tool_calls = [
            ToolCallInfo(id=tc.id, name=tc.name, arguments=tc.arguments)
            for tc in (response.tool_calls or [])
        ]

        return LLMResponse(
            content=response.content,
            tool_calls=tool_calls,
            usage=response.usage,
        )

    # ------------------------------------------------------------------
    # Non-streaming-specific tool event hooks
    # ------------------------------------------------------------------

    async def _on_tool_execution_start(
        self,
        tc: ToolCallInfo,
        iteration: int,
        session_instance_id: int | None,
        response_content: str | None,
        msg: InboundMessage,
    ) -> None:
        try:
            await self.agent_loop._emit(
                "agent_tool_call",
                {
                    "tool": tc.name,
                    "args": tc.arguments,
                    "content": response_content if response_content else None,
                    "iteration": iteration,
                    "tool_call_id": tc.id,
                    "session_instance_id": session_instance_id,
                },
                channel=msg.channel,
            )
        except Exception as emit_err:
            logger.warning(f"Failed to emit tool call event: {emit_err}")

    async def _on_tool_execution_success(
        self,
        tc: ToolCallInfo,
        result: str,
        iteration: int,
        session_instance_id: int | None,
        msg: InboundMessage,
    ) -> None:
        result_preview = result if tc.name == "spawn" else (
            result[:500] + "..." if len(result) > 500 else result
        )
        try:
            await self.agent_loop._emit(
                "agent_tool_result",
                {
                    "tool": tc.name,
                    "result": result_preview,
                    "tool_call_id": tc.id,
                    "iteration": iteration,
                    "session_instance_id": session_instance_id,
                },
                channel=msg.channel,
            )
        except Exception as e:
            logger.warning(f"Failed to emit tool result event: {e}")

    def _check_tool_early_stop(
        self,
        tc: ToolCallInfo,
        tool_args: dict,
        result: str | None,
        msg: InboundMessage,
    ) -> str | None:
        is_longtask_auth = (
            tc.name == "action"
            and tool_args.get("type") == "plugin"
            and tool_args.get("action") == "auth"
        )
        if is_longtask_auth and result and "success" in result:
            plugin_name = tool_args.get("name", "longtask")
            return f"✅ 授权已发送，{plugin_name} 将继续执行任务。任务完成后我会通知您。"
        return None

    async def _post_agent_finish(
        self,
        final_content: str | None,
        current_session: str,
        channel: str,
        session_instance_id: int | None,
    ) -> None:
        if final_content:
            await self.agent_loop._send_stream_chunks(
                final_content, current_session, channel, session_instance_id
            )