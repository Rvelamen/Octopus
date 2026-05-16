"""Streaming message processor for the desktop channel."""

from backend.core.events.types import InboundMessage
from .base_chat import BaseChatProcessor, ToolCallInfo, LLMResponse


class StreamingMessageProcessor(BaseChatProcessor):
    """Processor for streaming messages (desktop channel).

    Extends :class:`BaseChatProcessor` and only implements the LLM call
    and streaming-specific event hooks.
    """

    def can_process(self, msg: InboundMessage) -> bool:
        return msg.channel == "desktop"

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

        full_content = ""
        tool_calls_buffer: dict[str, dict] = {}
        usage = None

        async for chunk in provider.chat_stream(
            messages=messages,
            tools=tools,
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
                        "session_instance_id": session_instance_id,
                    },
                    channel=msg.channel,
                )

            if chunk.tool_calls:
                for tc in chunk.tool_calls:
                    if tc.id not in tool_calls_buffer:
                        tool_calls_buffer[tc.id] = {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                        await self.agent_loop._emit(
                            "agent_tool_call_start",
                            {
                                "tool_call_id": tc.id,
                                "tool": tc.name,
                                "args": tc.arguments,
                                "partial_args": tc.arguments,
                                "content": full_content if full_content else None,
                                "iteration": None,
                                "status": "pending",
                                "session_instance_id": session_instance_id,
                            },
                            channel=msg.channel,
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
                                "session_instance_id": session_instance_id,
                            },
                            channel=msg.channel,
                        )

            if chunk.is_final:
                usage = chunk.usage

        tool_calls = [
            ToolCallInfo(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in tool_calls_buffer.values()
        ]

        return LLMResponse(content=full_content, tool_calls=tool_calls, usage=usage)

    # ------------------------------------------------------------------
    # Streaming-specific tool event hooks
    # ------------------------------------------------------------------

    async def _on_tool_execution_start(
        self,
        tc: ToolCallInfo,
        iteration: int,
        session_instance_id: int | None,
        response_content: str | None,
        msg: InboundMessage,
    ) -> None:
        await self.agent_loop._emit(
            "agent_tool_call_invoking",
            {
                "tool_call_id": tc.id,
                "tool": tc.name,
                "status": "invoking",
                "session_instance_id": session_instance_id,
            },
            channel=msg.channel,
        )

    async def _on_tool_execution_success(
        self,
        tc: ToolCallInfo,
        result: str,
        iteration: int,
        session_instance_id: int | None,
        msg: InboundMessage,
    ) -> None:
        await self.agent_loop._emit(
            "agent_tool_call_complete",
            {
                "tool_call_id": tc.id,
                "tool": tc.name,
                "args": tc.arguments,
                "result": result if tc.name == "spawn" else (
                    result[:500] + "..." if len(result) > 500 else result
                ),
                "status": "completed",
                "session_instance_id": session_instance_id,
            },
            channel=msg.channel,
        )

    async def _on_tool_execution_error(
        self,
        tc: ToolCallInfo,
        error: Exception,
        iteration: int,
        session_instance_id: int | None,
        msg: InboundMessage,
    ) -> None:
        await self.agent_loop._emit(
            "agent_tool_call_error",
            {
                "tool_call_id": tc.id,
                "tool": tc.name,
                "args": tc.arguments,
                "error": str(error),
                "status": "error",
                "session_instance_id": session_instance_id,
            },
            channel=msg.channel,
        )