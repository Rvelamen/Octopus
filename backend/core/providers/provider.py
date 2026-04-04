"""Unified LLM provider supporting OpenAI, Azure, and Anthropic."""

import asyncio
import json
from typing import Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from anthropic import Anthropic, AsyncAnthropic
from loguru import logger

from backend.core.providers.base import LLMProvider, LLMResponse, ToolCallRequest, StreamChunk
from backend.core.providers.message_adapter import MessageAdapter

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    ConnectionError,
    TimeoutError,
)


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
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.provider_type = provider_type
        self.api_version = api_version
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay

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

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        if isinstance(error, RETRYABLE_EXCEPTIONS):
            return True
        
        error_str = str(error).lower()
        retryable_keywords = [
            "timeout", "timed out", "connection", "network",
            "502", "503", "504", "429", "rate limit",
            "gateway", "service unavailable", "bad gateway"
        ]
        return any(kw in error_str for kw in retryable_keywords)

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry with exponential backoff and jitter."""
        import random
        delay = min(
            self.retry_base_delay * (2 ** attempt),
            self.retry_max_delay
        )
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

    async def _execute_with_retry(
        self,
        func,
        operation_name: str = "LLM call",
    ) -> Any:
        """Execute a function with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func()
            except Exception as e:
                last_error = e
                
                if not self._is_retryable_error(e):
                    logger.error(f"[Provider] {operation_name} failed with non-retryable error: {e}")
                    raise
                
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"[Provider] {operation_name} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[Provider] {operation_name} failed after {self.max_retries + 1} attempts: {e}"
                    )
                    raise
        
        raise last_error

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
    
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream chat completion with structured chunks.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Yields:
            StreamChunk with content, tool_calls, is_final, and usage.
        """
        model = model or self.default_model
        provider = self.provider_type or self._detect_provider_type(self.api_base)
        
        logger.info(f"[Stream] Calling {provider.upper()} API with model: {model}")
        
        if provider in ("anthropic", "kimi", "minimax"):
            async for chunk in self._chat_stream_anthropic(messages, tools, model, max_tokens, temperature):
                yield chunk
        else:
            async for chunk in self._chat_stream_openai(messages, tools, model, max_tokens, temperature, provider):
                yield chunk

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

        adapted_messages = MessageAdapter.adapt_messages(messages, provider)

        if stream:
            return self._stream_openai(adapted_messages, tools, actual_model, max_tokens, temperature, provider)
        
        kwargs = dict(
            model=actual_model,
            messages=adapted_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        async def _call_api():
            logger.debug(f"[Provider] Sending request to {provider} with model {model}, tools count: {len(tools) if tools else 0}")
            response = await self._client.chat.completions.create(**kwargs)
            logger.info(f"[Provider] Response received from {provider}: id={response.id}, finish_reason={response.choices[0].finish_reason if response.choices else 'N/A'}")
            return self._parse_response(response)
        
        try:
            return await self._execute_with_retry(_call_api, f"{provider} chat")
        except Exception as e:
            import traceback
            logger.error(f"[Provider] {provider.upper()} API call failed after retries: {e}")
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
        added_tool_use_ids = set()  # Track all tool_use IDs we've added
        
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
                        tool_id = tool.get("id")
                        if not tool_id:
                            # Generate a fallback ID instead of skipping
                            tool_id = f"fallback_{hash(str(tool))}_{len(added_tool_use_ids)}"
                            logger.warning(f"[Anthropic] Tool use missing id, generated fallback: {tool_id}")
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool.get("name", "unknown"),
                            "input": tool.get("input", {}),
                        })
                        added_tool_use_ids.add(tool_id)  # Track this ID
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
                            # Generate a fallback ID instead of skipping
                            tc_id = f"fallback_{hash(str(tc))}_{len(added_tool_use_ids)}"
                            logger.warning(f"[Anthropic] Tool call missing id, generated fallback: {tc_id}")
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc_id,
                            "name": func.get("name", "unknown"),
                            "input": args,
                        })
                        added_tool_use_ids.add(tc_id)  # Track this ID
                
                # Only add assistant message if it has content
                if content_blocks:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content_blocks,
                    })
                else:
                    # Skip empty assistant messages
                    logger.warning(f"[Anthropic] Skipping empty assistant message: {msg}")
                    continue
            elif msg["role"] == "tool":
                tool_use_id = msg.get("tool_use_id") or msg.get("tool_call_id")
                if not tool_use_id:
                    logger.warning(f"[Anthropic] Tool message missing tool_use_id, skipping: {msg}")
                    continue
                # Verify that this tool_use_id exists in previous messages
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
            
            return await self._execute_with_retry(_call_anthropic, "Anthropic chat")
            
        except Exception as e:
            logger.error(f"Anthropic API call failed after retries: {e}")
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
    
    async def _chat_stream_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
        provider: str,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream OpenAI/Azure completions with structured chunks."""
        try:
            adapted_messages = MessageAdapter.adapt_messages(messages, provider)
            
            kwargs = dict(
                model=model,
                messages=adapted_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            stream = await self._client.chat.completions.create(**kwargs)
            
            tool_calls_accumulator = {}  # Accumulate tool call chunks by ID
            
            async for chunk in stream:
                if not chunk.choices or len(chunk.choices) == 0:
                    continue
                
                choice = chunk.choices[0]
                delta = choice.delta
                
                # Handle content
                if delta.content:
                    yield StreamChunk(content=delta.content)
                
                # Handle tool calls (streaming)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_id = tc.id
                        
                        # Initialize tool call accumulator if new
                        if tc_id and tc_id not in tool_calls_accumulator:
                            tool_calls_accumulator[tc_id] = {
                                "id": tc_id,
                                "name": "",
                                "arguments": ""
                            }
                        
                        # Update tool call data
                        if tc.function:
                            if tc.function.name:
                                tool_calls_accumulator[tc_id]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_accumulator[tc_id]["arguments"] += tc.function.arguments
                
                # Handle finish reason
                if choice.finish_reason:
                    # Parse accumulated tool calls
                    tool_calls = []
                    for tc_id, tc_data in tool_calls_accumulator.items():
                        try:
                            args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {"raw": tc_data["arguments"]}
                        
                        tool_calls.append(ToolCallRequest(
                            id=tc_data["id"],
                            name=tc_data["name"],
                            arguments=args,
                        ))
                    
                    # Yield final chunk with usage if available
                    usage = {}
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }
                    
                    yield StreamChunk(
                        tool_calls=tool_calls if tool_calls else None,
                        is_final=True,
                        usage=usage
                    )
                    
        except Exception as e:
            logger.error(f"[Stream] OpenAI streaming failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield StreamChunk(
                content=f"Error: {str(e)}",
                is_final=True
            )
    
    async def _chat_stream_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream Anthropic completions with structured chunks."""
        try:
            # Prepare messages (same as _chat_anthropic)
            system_message = None
            anthropic_messages = []
            added_tool_use_ids = set()  # Track all tool_use IDs we've added
            
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
                    # Handle tool_use (Anthropic format)
                    if msg.get("tool_use"):
                        for tool in msg["tool_use"]:
                            tool_id = tool.get("id")
                            if not tool_id:
                                # Generate a fallback ID instead of skipping
                                tool_id = f"fallback_{hash(str(tool))}_{len(added_tool_use_ids)}"
                                logger.warning(f"[Stream] Tool use missing id, generated fallback: {tool_id}")
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tool_id,
                                "name": tool.get("name", "unknown"),
                                "input": tool.get("input", {}),
                            })
                            added_tool_use_ids.add(tool_id)  # Track this ID
                    # Handle tool_calls (OpenAI format)
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
                                # Generate a fallback ID instead of skipping
                                tc_id = f"fallback_{hash(str(tc))}_{len(added_tool_use_ids)}"
                                logger.warning(f"[Stream] Tool call missing id, generated fallback: {tc_id}")
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tc_id,
                                "name": func.get("name", "unknown"),
                                "input": args,
                            })
                            added_tool_use_ids.add(tc_id)  # Track this ID
                    
                    # Only add assistant message if it has content
                    if content_blocks:
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": content_blocks,
                        })
                    else:
                        # Skip empty assistant messages
                        logger.warning(f"[Stream] Skipping empty assistant message: {msg}")
                        continue
                elif msg["role"] == "tool":
                    tool_use_id = msg.get("tool_use_id") or msg.get("tool_call_id")
                    if not tool_use_id:
                        logger.warning(f"[Stream] Tool message missing tool_use_id, skipping: {msg}")
                        continue
                    # Verify that this tool_use_id exists in previous messages
                    if tool_use_id not in added_tool_use_ids:
                        logger.warning(f"[Stream] Tool result references non-existent tool_use_id: {tool_use_id}, skipping")
                        continue
                    anthropic_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": msg.get("content", ""),
                        }],
                    })
            
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
            
            tool_calls_accumulator = {}  # Accumulate tool use blocks by ID
            
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    # Handle text content
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield StreamChunk(content=event.delta.text)
                    
                    # Handle tool use (streaming)
                    elif event.type == "content_block_start":
                        if hasattr(event, 'content_block') and event.content_block.type == "tool_use":
                            tc_id = event.content_block.id
                            tool_calls_accumulator[tc_id] = {
                                "id": tc_id,
                                "name": event.content_block.name,
                                "arguments": ""
                            }
                    
                    elif event.type == "content_block_delta":
                        if hasattr(event, 'delta') and event.delta.type == "input_json_delta":
                            # Get the tool use ID from the index
                            if hasattr(event, 'index'):
                                # Find the tool call by index
                                for tc_id, tc_data in tool_calls_accumulator.items():
                                    if list(tool_calls_accumulator.keys()).index(tc_id) == event.index:
                                        tc_data["arguments"] += event.delta.partial_json
                                        break
                    
                    # Handle message stop (final)
                    elif event.type == "message_stop":
                        # Parse accumulated tool calls
                        tool_calls = []
                        for tc_id, tc_data in tool_calls_accumulator.items():
                            try:
                                args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            except json.JSONDecodeError:
                                args = {"raw": tc_data["arguments"]}
                            
                            tool_calls.append(ToolCallRequest(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=args,
                            ))
                        
                        # Get final message for usage
                        final_message = await stream.get_final_message()
                        usage = {
                            "prompt_tokens": final_message.usage.input_tokens,
                            "completion_tokens": final_message.usage.output_tokens,
                            "total_tokens": final_message.usage.input_tokens + final_message.usage.output_tokens,
                        }
                        
                        yield StreamChunk(
                            tool_calls=tool_calls if tool_calls else None,
                            is_final=True,
                            usage=usage
                        )
                        
        except Exception as e:
            logger.error(f"[Stream] Anthropic streaming failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield StreamChunk(
                content=f"Error: {str(e)}",
                is_final=True
            )
