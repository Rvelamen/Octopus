"""Backward-compatible provider re-exports."""

from backend.core.providers.openai_provider import OpenAIProvider
from backend.core.providers.anthropic_provider import AnthropicProvider


class UnifiedProvider:
    """Deprecated dispatcher; use OpenAIProvider or AnthropicProvider directly."""

    def __new__(cls, *args, provider_type: str = "openai", **kwargs):
        if provider_type in ("anthropic", "kimi", "minimax"):
            return AnthropicProvider(*args, provider_type=provider_type, **kwargs)
        return OpenAIProvider(*args, provider_type=provider_type, **kwargs)
