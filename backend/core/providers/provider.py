"""Unified LLM provider supporting OpenAI, Azure, and Anthropic."""

import json
from typing import Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from anthropic import Anthropic, AsyncAnthropic
from loguru import logger

from backend.core.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from backend.core.providers.message_adapter import MessageAdapter


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


class UnifiedProvider(LLMProvider):
    """
    Unified LLM provider supporting OpenAI, Azure OpenAI, and Anthropic.
    
    Provider selection is based on api_base or explicit type hint.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gpt-4",
        provider_type: str = "openai",  # "openai", "azure", "anthropic", "kimi"
        api_version: str = "2024-02-01",  # For Azure
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.provider_type = provider_type
        self.api_version = api_version

        if provider_type in ["anthropic", "kimi", "minimax"]:
            # Kimi uses Anthropic-compatible API
            # Use Kimi's Anthropic-compatible endpoint if using kimi type

            self._client = AsyncAnthropic(
                api_key=api_key or "",
                base_url=api_base,
            )
            logger.info(f"Anthropic client created with base URL: {api_base}")
        else:
            # OpenAI and Azure use OpenAI-compatible format
            logger.info(f"Creating OpenAI client with base URL: {api_base}")
            
            # Configure httpx with larger connection pool for concurrent requests
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=1200.0,
                    write=30.0,
                    pool=30.0,
                ),
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                ),
            )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=http_client,
            )
            logger.info(f"OpenAI client created: {self._client.base_url}")

    def _detect_provider_type(self, api_base: str | None) -> str:
        """Detect provider type from api_base URL."""
        if not api_base:
            return "openai"
        
        api_base_lower = api_base.lower()
        if "azure" in api_base_lower:
            return "azure"
        if "anthropic" in api_base_lower:
            return "anthropic"
        return "openai"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            stream: Whether to stream the response.
        
        Returns:
            LLMResponse for non-streaming, or async generator of chunks for streaming.
        """
        model = model or self.default_model
        provider = self.provider_type or self._detect_provider_type(self.api_base)
        
        logger.info(f"Calling {provider.upper()} API with model: {model}")
        logger.info(f"Tools provided: {len(tools) if tools else 0} tools")
        # logger.info(f"Messages provided: {messages} ")
        
        if provider in ("anthropic", "kimi", "minimax"):
            return await self._chat_anthropic(messages, tools, model, max_tokens, temperature, stream)
        else:
            return await self._chat_openai(messages, tools, model, max_tokens, temperature, stream, provider)

    async def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
        stream: bool,
        provider: str,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Handle OpenAI and Azure API calls."""

        actual_model = model

        # Adapt messages for OpenAI-compatible providers (DeepSeek, etc. require strict format)
        adapted_messages = MessageAdapter.adapt_messages(messages, provider)

        if stream:
            return self._stream_openai(adapted_messages, tools, actual_model, max_tokens, temperature, provider)
        
        try:
            kwargs = dict(
                model=actual_model,
                messages=adapted_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            logger.debug(f"[Provider] Sending request to {provider} with model {model}, tools count: {len(tools) if tools else 0}")
            response = await self._client.chat.completions.create(**kwargs)
            logger.info(f"[Provider] Response received from {provider}: id={response.id}, finish_reason={response.choices[0].finish_reason if response.choices else 'N/A'}")
            return self._parse_response(response)
            
        except Exception as e:
            import traceback
            logger.error(f"[Provider] {provider.upper()} API call failed: {e}")
            logger.error(f"[Provider] Traceback: {traceback.format_exc()}")
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    async def _stream_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
        provider: str,
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI/Azure completions."""
        try:
            kwargs = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            stream = await self._client.chat.completions.create(**kwargs)
            
            async for chunk in stream:
                content = self._extract_stream_content(chunk)
                if content:
                    yield content
                    
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"Error: {str(e)}"

    async def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
        stream: bool,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Handle Anthropic API calls."""
        
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                # Handle multi-modal content for Anthropic format
                content = msg["content"]
                if isinstance(content, list):
                    # Convert OpenAI format to Anthropic format
                    anthropic_content = []
                    for item in content:
                        if item["type"] == "text":
                            anthropic_content.append({"type": "text", "text": item["text"]})
                        elif item["type"] == "image_url":
                            # Convert image_url to Anthropic image format
                            image_url = item["image_url"]["url"]
                            if image_url.startswith("data:"):
                                # Extract mime type and base64 data
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
                                # URL image
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
                    # Text-only content
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
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tool.get("id"),
                            "name": tool.get("name"),
                            "input": tool.get("input", {}),
                        })
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": func.get("name"),
                            "input": args,
                        })
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content_blocks if content_blocks else [{"type": "text", "text": ""}],
                })
            elif msg["role"] == "tool":
                tool_use_id = msg.get("tool_use_id") or msg.get("tool_call_id")
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": msg.get("content", ""),
                    }],
                })

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
                # logger.info(f"[Anthropic] Tools content: {anthropic_tools}")
            
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
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            )
            
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    async def _stream_anthropic(
        self,
        messages: list[dict[str, Any]],
        system_message: str | None,
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream Anthropic completions."""
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

    def _extract_stream_content(self, chunk: ChatCompletionChunk) -> str | None:
        """Extract content delta from a streaming chunk."""
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta:
                return delta.content or ""
        return None

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    async def close(self):
        """Close the async client."""
        await self._client.aclose()
