"""OpenAI-compatible provider (OpenAI, Azure, Ollama, etc.)."""

import json
from typing import Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from loguru import logger

from backend.core.providers.base import LLMResponse, ToolCallRequest, StreamChunk
from backend.core.providers.base_client import RetryableProvider
from backend.core.providers.message_adapter import MessageAdapter


class OpenAIProvider(RetryableProvider):
    """Provider for OpenAI-compatible APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"Creating OpenAI client with base URL: {self.api_base}")
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
            api_key=self.api_key,
            base_url=self.api_base,
            http_client=http_client,
        )
        logger.info(f"OpenAI client created: {self._client.base_url}")

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
        logger.info(f"Calling OPENAI API with model: {model}")
        logger.info(f"Tools provided: {len(tools) if tools else 0} tools")
        adapted_messages = MessageAdapter.adapt_messages(messages, "openai")
        if stream:
            return self._stream_openai(adapted_messages, tools, model, max_tokens, temperature)

        kwargs = dict(
            model=model,
            messages=adapted_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        async def _call_api():
            logger.debug(f"[Provider] Sending request to openai with model {model}, tools count: {len(tools) if tools else 0}")
            response = await self._client.chat.completions.create(**kwargs)
            logger.info(f"[Provider] Response received from openai: id={response.id}, finish_reason={response.choices[0].finish_reason if response.choices else 'N/A'}")
            return self._parse_response(response, adapted_messages=adapted_messages, model=model)

        try:
            return await self._execute_with_retry(_call_api, "openai chat")
        except Exception as e:
            import traceback
            logger.error(f"[Provider] OPENAI API call failed after retries: {e}")
            logger.error(f"[Provider] Traceback: {traceback.format_exc()}")
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
        logger.info(f"[Stream] Calling OPENAI API with model: {model}")
        adapted_messages = MessageAdapter.adapt_messages(messages, "openai")
        accumulated_content = ""
        tool_calls: list[ToolCallRequest] = []

        kwargs = dict(
            model=model,
            messages=adapted_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        final_usage = {}
        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                # Capture usage from ANY chunk that carries it (some proxies attach
                # usage to the last content chunk instead of a dedicated usage chunk)
                if chunk.usage:
                    final_usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                    if hasattr(chunk.usage, "prompt_tokens_details") and chunk.usage.prompt_tokens_details:
                        final_usage["prompt_tokens_details"] = {
                            "cached_tokens": chunk.usage.prompt_tokens_details.cached_tokens
                        }

                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    accumulated_content += delta.content
                    yield StreamChunk(content=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        while len(tool_calls) <= idx:
                            tool_calls.append(ToolCallRequest(id="", name="", arguments={}))
                        existing = tool_calls[idx]
                        if tc.id:
                            existing.id = tc.id
                        if tc.function and tc.function.name:
                            existing.name = tc.function.name
                        if tc.function and tc.function.arguments:
                            raw_args = tc.function.arguments
                            if isinstance(raw_args, str):
                                try:
                                    parsed = json.loads(raw_args)
                                except json.JSONDecodeError:
                                    parsed = {"raw": raw_args}
                                existing.arguments = parsed
                            else:
                                existing.arguments = raw_args

            # Some compatible APIs return a usage dict with all zeros; treat that as missing too.
            has_real_usage = bool(
                final_usage
                and (final_usage.get("prompt_tokens", 0) > 0 or final_usage.get("completion_tokens", 0) > 0)
            )
            if not has_real_usage:
                from backend.agent.shared import _estimate_token_usage
                final_usage = _estimate_token_usage(adapted_messages or messages, accumulated_content, model)
                logger.warning(f"[OpenAI] API did not return valid streaming usage; estimated: {final_usage}")

            yield StreamChunk(
                content="",
                tool_calls=tool_calls if tool_calls else None,
                is_final=True,
                usage=final_usage,
            )
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield StreamChunk(content=f"Error: {str(e)}", is_final=True)

    async def _stream_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI/Azure completions (legacy string generator)."""
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

    def _extract_stream_content(self, chunk: ChatCompletionChunk) -> str | None:
        """Extract content delta from a streaming chunk."""
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta:
                return delta.content or ""
        return None

    def _parse_response(self, response: Any, adapted_messages: list | None = None, model: str | None = None) -> LLMResponse:
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
            if hasattr(response.usage, "prompt_tokens_details") and response.usage.prompt_tokens_details:
                usage["prompt_tokens_details"] = {
                    "cached_tokens": getattr(response.usage.prompt_tokens_details, "cached_tokens", 0),
                }

        has_real_usage = bool(
            usage and (usage.get("prompt_tokens", 0) > 0 or usage.get("completion_tokens", 0) > 0)
        )
        if not has_real_usage:
            from backend.agent.shared import _estimate_token_usage
            usage = _estimate_token_usage(adapted_messages or messages, message.content or "", self.default_model)
            logger.warning(f"[OpenAI] Non-streaming response missing valid usage; estimated: {usage}")

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
