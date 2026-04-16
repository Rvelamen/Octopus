"""Provider factory for creating LLM providers based on configuration."""

from loguru import logger

from backend.core.providers.base import LLMProvider, LLMResponse
from backend.core.providers.openai_provider import OpenAIProvider
from backend.core.providers.anthropic_provider import AnthropicProvider
from backend.core.config.schema import AgentDefaults, ProviderConfig


class MockProvider(LLMProvider):
    """Mock provider that returns a helpful message when no LLM is configured."""

    def __init__(self):
        super().__init__(api_key=None, api_base=None)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(
            content="⚠️ **LLM Not Configured**\n\n"
                    "Please configure one of the following API keys to enable LLM functionality:\n\n"
                    "- `OPENROUTER_API_KEY`\n"
                    "- `ANTHROPIC_API_KEY`\n"
                    "- `OPENAI_API_KEY`\n"
                    "- `DEEPSEEK_API_KEY`\n\n"
                    "You can set these as environment variables or configure them in the settings.",
            finish_reason="stop",
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        from backend.core.providers.base import StreamChunk
        yield StreamChunk(
            content="⚠️ **LLM Not Configured**\n\n"
                    "Please configure one of the following API keys to enable LLM functionality:\n\n"
                    "- `OPENROUTER_API_KEY`\n"
                    "- `ANTHROPIC_API_KEY`\n"
                    "- `OPENAI_API_KEY`\n"
                    "- `DEEPSEEK_API_KEY`\n\n"
                    "You can set these as environment variables or configure them in the settings.",
            is_final=True,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    def get_default_model(self) -> str:
        return "none"


# 只支持图片中的8种类型
TYPE_TO_INTERNAL = {
    "openai": "openai",
    "openai-response": "openai",
    "gemini": "openai",
    "anthropic": "anthropic",
    "azure-openai": "openai",
    "new-api": "openai",
    "cherryln": "openai",
    "ollama": "openai",
}


def create_provider(
    providers_config: dict[str, ProviderConfig],
    agent_defaults: AgentDefaults,
) -> LLMProvider:
    """
    Create an LLM provider based on configuration.

    Priority:
    1. If agent_defaults.provider is set, use that specific provider
    2. Otherwise, use the first configured provider as fallback

    Args:
        providers_config: The providers configuration object.
        agent_defaults: The agent defaults configuration.

    Returns:
        An LLMProvider instance (OpenAIProvider, AnthropicProvider, or MockProvider).
    """
    provider_config: ProviderConfig | None = None
    provider_type: str = "openai"
    provider_name: str = ""

    providers_dict = providers_config or {}

    requested_provider = agent_defaults.provider

    if requested_provider:
        if requested_provider in providers_dict:
            provider_config = providers_dict[requested_provider]
            provider_name = requested_provider
            if provider_config.api_key and getattr(provider_config, "enabled", True):
                provider_type = provider_config.type or "openai"
                logger.info(f"Using requested provider: {requested_provider} (type: {provider_type})")
            else:
                if not provider_config.api_key:
                    logger.warning(f"Requested provider '{requested_provider}' has no API key configured")
                if not getattr(provider_config, "enabled", True):
                    logger.warning(f"Requested provider '{requested_provider}' is disabled")
                provider_config = None

    if provider_config is None:
        for name, config in providers_dict.items():
            if config.api_key and getattr(config, "enabled", True):
                provider_config = config
                provider_name = name
                provider_type = config.type or "openai"
                logger.info(f"Using fallback provider: {name} (type: {provider_type})")
                break

    if provider_config is None:
        logger.warning("No LLM provider configured. Please set one of the following environment variables:")
        logger.warning("  - OPENROUTER_API_KEY")
        logger.warning("  - ANTHROPIC_API_KEY")
        logger.warning("  - OPENAI_API_KEY")
        logger.warning("  - DEEPSEEK_API_KEY")
        logger.warning("Service will start with mock provider.")
        return MockProvider()

    internal_type = TYPE_TO_INTERNAL.get(provider_type, "openai")

    common_kwargs = dict(
        default_model=agent_defaults.model or "gpt-4",
        api_key=provider_config.api_key,
        api_base=provider_config.api_base,
        provider_type=internal_type,
        max_retries=agent_defaults.llm_max_retries,
        retry_base_delay=agent_defaults.llm_retry_base_delay,
        retry_max_delay=agent_defaults.llm_retry_max_delay,
    )

    if internal_type == "anthropic":
        return AnthropicProvider(**common_kwargs)
    return OpenAIProvider(**common_kwargs)
