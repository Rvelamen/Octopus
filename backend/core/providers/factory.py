"""Provider factory for creating LLM providers based on configuration."""

from loguru import logger

from backend.core.providers.base import LLMProvider, LLMResponse
from backend.core.providers.provider import UnifiedProvider
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
        An LLMProvider instance (UnifiedProvider or MockProvider).
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
            if provider_config.api_key:
                provider_type = provider_config.type or "openai"
                logger.info(f"Using requested provider: {requested_provider} (type: {provider_type})")
            else:
                logger.warning(f"Requested provider '{requested_provider}' has no API key configured")
                provider_config = None

    if provider_config is None:
        for name, config in providers_dict.items():
            if config.api_key:
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

    return UnifiedProvider(
        default_model=agent_defaults.model or "gpt-4",
        api_key=provider_config.api_key,
        api_base=provider_config.api_base,
        provider_type=internal_type,
    )
