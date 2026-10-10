"""Shared utilities for agent processing."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PreparedContext:
    """Shared context prepared before LLM call (used by both streaming and non-streaming paths)."""

    session: Any
    messages: list
    session_instance_id: int | None
    current_session: str
    session_key: str


def _extract_cached_tokens(usage: dict) -> int:
    """Extract cache hit tokens from provider-specific usage fields."""
    if not usage:
        return 0
    # DeepSeek style
    if "prompt_cache_hit_tokens" in usage:
        return usage.get("prompt_cache_hit_tokens", 0)
    # OpenAI style
    details = usage.get("prompt_tokens_details")
    if details and isinstance(details, dict):
        return details.get("cached_tokens", 0)
    # Generic fallback
    return usage.get("cached_tokens", 0) or usage.get("cache_read_input_tokens", 0)


def _extract_prompt_tokens_with_cache(usage: dict) -> int:
    """Get real prompt/input tokens including cache hits.

    Provider behavior:
    - DeepSeek: prompt_tokens does NOT include prompt_cache_hit_tokens, so we add them.
    - OpenAI/Anthropic: prompt_tokens / input_tokens already include cached tokens.
    """
    if not usage:
        return 0
    # DeepSeek style: need to add cache hits
    if "prompt_cache_hit_tokens" in usage:
        return usage.get("prompt_tokens", 0) + usage.get("prompt_cache_hit_tokens", 0)
    # Anthropic style
    if "input_tokens" in usage:
        return usage.get("input_tokens", 0)
    # OpenAI / generic style
    return usage.get("prompt_tokens", 0)


def _tool_calls_to_text(tool_calls) -> str:
    """Serialize assistant tool_calls for token estimation.

    Each call becomes "name(json_input)" — the same shape the model sees on
    the wire, so the estimate tracks what the API would bill.
    """
    if not tool_calls:
        return ""
    import json

    parts: list[str] = []
    for tc in tool_calls:
        # Support both pydantic objects (.name/.arguments) and dicts.
        if isinstance(tc, dict):
            name = tc.get("name") or tc.get("function", {}).get("name", "")
            args = tc.get("arguments")
            if args is None:
                args = tc.get("input") or tc.get("function", {}).get("arguments", "")
        else:
            name = getattr(tc, "name", "")
            args = getattr(tc, "arguments", None)
            if args is None:
                args = getattr(tc, "input", "")
        if isinstance(args, (dict, list)):
            try:
                args_repr = json.dumps(args, ensure_ascii=False)
            except (TypeError, ValueError):
                args_repr = str(args)
        else:
            args_repr = str(args or "")
        parts.append(f"[tool_use:{name}]{args_repr}")
    return "\n".join(parts)


def _estimate_token_usage(
    messages: list[dict],
    content: str | None,
    model: str | None = None,
    tool_calls=None,
) -> dict[str, int]:
    """Estimate token usage when API does not return it (or returns zeros).

    Tries tiktoken first, falls back to a simple character-based heuristic
    (~1.5 chars per token for CJK, ~4 chars per token for ASCII) if tiktoken
    is unavailable or the model is unknown.
    """

    def _extract_text(msg_content) -> str:
        """Serialize any Anthropic-style content block to text for token estimation.

        Handles every block type the model can see in its prompt, so the
        fallback estimate stays accurate when a proxy returns usage=0.
        """
        if msg_content is None:
            return ""
        if isinstance(msg_content, str):
            return msg_content
        if not isinstance(msg_content, list):
            return str(msg_content)

        import json

        parts: list[str] = []
        for item in msg_content:
            if not isinstance(item, dict):
                continue
            block_type = item.get("type")
            if block_type == "text":
                parts.append(item.get("text", "") or "")
            elif block_type == "thinking":
                # Extended-thinking block — its text counts toward prompt tokens.
                parts.append(item.get("thinking", "") or "")
            elif block_type == "tool_use":
                # Model sees: tool_name + JSON(input). Serialize that exact shape.
                name = item.get("name", "")
                try:
                    args_repr = json.dumps(item.get("input", {}), ensure_ascii=False)
                except (TypeError, ValueError):
                    args_repr = str(item.get("input", ""))
                parts.append(f"[tool_use:{name}]{args_repr}")
            elif block_type == "tool_result":
                # tool_result.content can be a string OR a list of blocks (text/image).
                inner = item.get("content", "")
                if isinstance(inner, list):
                    parts.append(_extract_text(inner))
                else:
                    parts.append(str(inner or ""))
            elif block_type == "image" or block_type == "image_url":
                # Approximate image token cost. Anthropic bills by tile (~1.6k
                # tokens for a typical 1024px image); we don't have exact dims
                # in estimation context, so use the standard flat estimate.
                parts.append("[image]" * 1600)
            # Unknown block types: skip rather than guess.
        return "\n".join(p for p in parts if p)

    prompt_text = "\n".join(_extract_text(m.get("content", "")) for m in messages)
    completion_text_parts = [content or ""]
    completion_text_parts.append(_tool_calls_to_text(tool_calls))
    completion_text = "\n".join(p for p in completion_text_parts if p)

    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model or "gpt-4")
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        prompt_tokens = len(enc.encode(prompt_text))
        completion_tokens = len(enc.encode(completion_text))
    except Exception:
        # Fallback heuristic that works better across languages:
        # CJK ~ 1.5 chars/token, ASCII ~ 4 chars/token
        def _approx(chars: str) -> int:
            import unicodedata

            total = 0.0
            for ch in chars:
                cat = unicodedata.category(ch)
                if cat in ("Cc", "Cf", "Cn", "Co", "Cs"):
                    continue
                if "\u4e00" <= ch <= "\u9fff":
                    total += 0.67  # ~1.5 chars per token
                elif ch.isalpha():
                    total += 0.25  # ~4 chars per token
                elif ch.isdigit():
                    total += 0.33
                else:
                    total += 0.5
            return max(1, int(total))

        prompt_tokens = _approx(prompt_text)
        completion_tokens = _approx(completion_text)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _normalize_usage(
    usage: dict | None,
    messages: list[dict],
    content: str | None,
    model: str | None = None,
    tool_calls=None,
) -> dict[str, int]:
    """Cross-check API usage with a local estimate and return the best guess.

    Some compatible proxies / model endpoints return prompt_tokens that are
    far too low (e.g., they strip the system prompt or only count the last
    turn).  We always estimate locally and take the larger of the two values
    so the user never sees an implausibly small token count.
    """
    usage = usage or {}
    estimated = _estimate_token_usage(messages, content or "", model, tool_calls)

    api_prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
    api_completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
    cached = _extract_cached_tokens(usage)

    # Some Anthropic-compatible proxies report 0 input_tokens but non-zero
    # cache_read_input_tokens. Treat cached tokens as part of the prompt.
    if not api_prompt:
        api_prompt = cached + (usage.get("cache_creation_input_tokens", 0) or 0)

    # Use the larger value so under-counting proxies are corrected.
    prompt_tokens = max(api_prompt, estimated["prompt_tokens"])
    completion_tokens = max(api_completion, estimated["completion_tokens"])

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cached_tokens": cached,
    }
