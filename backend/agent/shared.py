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
