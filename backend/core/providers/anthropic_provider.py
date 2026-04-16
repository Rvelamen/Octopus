"""Anthropic-compatible provider (Anthropic, Kimi, MiniMax, etc.)."""

import json
from typing import Any, AsyncGenerator

from anthropic import AsyncAnthropic
from loguru import logger

from backend.core.providers.base import LLMResponse, ToolCallRequest, StreamChunk
from backend.core.providers.base_client import RetryableProvider


def convert_tools_to_anthropic_format(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI function format tools to Anthropic format.

    OpenAI format:
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}

    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {...}}
    """
    anthropic_tools = []
    for tool in tools:
        if isinstance(tool, dict):
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                anthropic_tools.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            else:
                anthropic_tools.append(tool)
    return anthropic_tools


class AnthropicProvider(RetryableProvider):
    """Provider for Anthropic-compatible APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"Anthropic client created with base URL: {self.api_base}")
        self._client = AsyncAnthropic(
            api_key=self.api_key or "",
            base_url=self.api_base,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        model = model or self.default_model
        logger.info(f"Calling ANTHROPIC API with model: {model}")
        logger.info(f"Tools provided: {len(tools) if tools else 0} tools")
        system_message, anthropic_messages = self._adapt_messages(messages)

        try:
            if stream:
                return self._stream_anthropic(
                    anthropic_messages, system_message, tools, model, max_tokens, temperature
                )

            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message,
                messages=anthropic_messages,
            )
            if tools:
                anthropic_tools = convert_tools_to_anthropic_format(tools)
                kwargs["tools"] = anthropic_tools
                logger.info(f"[Anthropic] Tools converted and passed to API: {len(anthropic_tools)} tools")

            async def _call_anthropic():
                response = await self._client.messages.create(**kwargs)
                tool_calls = []
                content = None
                if response.content:
                    for block in response.content:
                        if block.type == "text":
                            content = block.text
                        elif block.type == "tool_use":
                            tool_calls.append(ToolCallRequest(
                                id=block.id,
                                name=block.name,
                                arguments=block.input,
                            ))

                usage = {}
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                    }
                    if hasattr(response.usage, "cache_read_input_tokens"):
                        usage["cache_read_input_tokens"] = response.usage.cache_read_input_tokens
                    if hasattr(response.usage, "cache_creation_input_tokens"):
                        usage["cache_creation_input_tokens"] = response.usage.cache_creation_input_tokens

                has_real_usage = bool(
                    usage and (usage.get("prompt_tokens", 0) > 0 or usage.get("completion_tokens", 0) > 0)
                )
                if not has_real_usage:
                    from backend.agent.shared import _estimate_token_usage
                    usage = _estimate_token_usage(anthropic_messages, content or "", model)
                    logger.warning(f"[Anthropic] Non-streaming response missing valid usage; estimated: {usage}")

                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason=response.stop_reason or "stop",
                    usage=usage,
                )

            return await self._execute_with_retry(_call_anthropic, "Anthropic chat")
        except Exception as e:
            logger.error(f"Anthropic API call failed after retries: {e}")
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        model = model or self.default_model
        logger.info(f"[Stream] Calling ANTHROPIC API with model: {model}")
        system_message, anthropic_messages = self._adapt_messages(messages)

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=anthropic_messages,
        )
        if tools:
            anthropic_tools = convert_tools_to_anthropic_format(tools)
            kwargs["tools"] = anthropic_tools

        try:
            accumulated_content = ""
            tool_calls: list[ToolCallRequest] = []
            current_tool_call: ToolCallRequest | None = None

            final_usage = {}
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            accumulated_content += event.delta.text
                            yield StreamChunk(content=event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            if current_tool_call:
                                partial = getattr(event.delta, "partial_json", "")
                                if partial:
                                    if not hasattr(current_tool_call, "_raw_args"):
                                        current_tool_call._raw_args = ""
                                    current_tool_call._raw_args += partial

                    elif event.type == "content_block_start":
                        if event.content_block and event.content_block.type == "tool_use":
                            current_tool_call = ToolCallRequest(
                                id=event.content_block.id,
                                name=event.content_block.name,
                                arguments={},
                            )
                            current_tool_call._raw_args = ""

                    elif event.type == "content_block_stop":
                        if current_tool_call:
                            raw = getattr(current_tool_call, "_raw_args", "{}")
                            try:
                                current_tool_call.arguments = json.loads(raw) if raw else {}
                            except json.JSONDecodeError:
                                current_tool_call.arguments = {"raw": raw}
                            tool_calls.append(current_tool_call)
                            current_tool_call = None

                try:
                    final_message = await stream.get_final_message()
                    if final_message and final_message.usage:
                        final_usage = {
                            "prompt_tokens": final_message.usage.input_tokens,
                            "completion_tokens": final_message.usage.output_tokens,
                            "total_tokens": final_message.usage.input_tokens + final_message.usage.output_tokens,
                        }
                        if hasattr(final_message.usage, "cache_read_input_tokens"):
                            final_usage["cache_read_input_tokens"] = final_message.usage.cache_read_input_tokens
                        if hasattr(final_message.usage, "cache_creation_input_tokens"):
                            final_usage["cache_creation_input_tokens"] = final_message.usage.cache_creation_input_tokens
                except Exception as usage_err:
                    logger.warning(f"Failed to get anthropic stream usage: {usage_err}")

            has_real_usage = bool(
                final_usage
                and (final_usage.get("prompt_tokens", 0) > 0 or final_usage.get("completion_tokens", 0) > 0)
            )
            if not has_real_usage:
                from backend.agent.shared import _estimate_token_usage
                final_usage = _estimate_token_usage(anthropic_messages, accumulated_content, model)
                logger.warning(f"[Anthropic] API did not return valid streaming usage; estimated: {final_usage}")

            yield StreamChunk(
                content="",
                tool_calls=tool_calls if tool_calls else None,
                is_final=True,
                usage=final_usage,
            )
        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}")
            yield StreamChunk(content=f"Error: {str(e)}", is_final=True)

    async def _stream_anthropic(
        self,
        messages: list[dict[str, Any]],
        system_message: str | None,
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream Anthropic completions (legacy string generator)."""
        try:
            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message,
                messages=messages,
            )
            if tools:
                anthropic_tools = convert_tools_to_anthropic_format(tools)
                kwargs["tools"] = anthropic_tools

            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}")
            yield f"Error: {str(e)}"

    def _adapt_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert generic messages to Anthropic format."""
        system_message = None
        anthropic_messages = []
        added_tool_use_ids: set[str] = set()

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    anthropic_content = []
                    for item in content:
                        if item["type"] == "text":
                            anthropic_content.append({"type": "text", "text": item["text"]})
                        elif item["type"] == "image_url":
                            image_url = item["image_url"]["url"]
                            if image_url.startswith("data:"):
                                mime_type = image_url.split(";")[0].split(":")[1]
                                base64_data = image_url.split(",")[1]
                                anthropic_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": base64_data,
                                    }
                                })
                            else:
                                anthropic_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": image_url,
                                    }
                                })
                    anthropic_messages.append({
                        "role": "user",
                        "content": anthropic_content,
                    })
                else:
                    anthropic_messages.append({
                        "role": "user",
                        "content": content,
                    })
            elif msg["role"] == "assistant":
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_use"):
                    for tool in msg["tool_use"]:
                        tool_id = tool.get("id")
                        if not tool_id:
                            tool_id = f"fallback_{hash(str(tool))}_{len(added_tool_use_ids)}"
                            logger.warning(f"[Anthropic] Tool use missing id, generated fallback: {tool_id}")
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool.get("name", "unknown"),
                            "input": tool.get("input", {}),
                        })
                        added_tool_use_ids.add(tool_id)
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        tc_id = tc.get("id")
                        if not tc_id:
                            tc_id = f"fallback_{hash(str(tc))}_{len(added_tool_use_ids)}"
                            logger.warning(f"[Anthropic] Tool call missing id, generated fallback: {tc_id}")
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc_id,
                            "name": func.get("name", "unknown"),
                            "input": args,
                        })
                        added_tool_use_ids.add(tc_id)

                if content_blocks:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content_blocks,
                    })
                else:
                    logger.warning(f"[Anthropic] Skipping empty assistant message: {msg}")
                    continue
            elif msg["role"] == "tool":
                tool_use_id = msg.get("tool_use_id") or msg.get("tool_call_id")
                if not tool_use_id:
                    logger.warning(f"[Anthropic] Tool message missing tool_use_id, skipping: {msg}")
                    continue
                if tool_use_id not in added_tool_use_ids:
                    logger.warning(f"[Anthropic] Tool result references non-existent tool_use_id: {tool_use_id}, skipping")
                    continue
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": msg.get("content", ""),
                    }],
                })

        return system_message, anthropic_messages
