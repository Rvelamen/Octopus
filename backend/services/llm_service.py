"""LLM Service wrapper for workflow execution."""

from __future__ import annotations

from typing import Any

from backend.core.config.schema import AgentDefaults, ProviderConfig
from backend.core.providers.factory import create_provider
from backend.data.provider_store import ProviderRepository, ModelRepository
from backend.data.database import Database


class LLMService:
    """Service for LLM chat completions."""

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a chat completion.

        Args:
            model: The model ID to use.
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            provider_id: Optional provider ID to use specific provider.

        Returns:
            Dict with 'content' and 'reasoning' keys.
        """
        db = Database()
        provider_repo = ProviderRepository(db)
        model_repo = ModelRepository(db)

        provider_record = None
        model_record = None

        if provider_id:
            provider_record = provider_repo.get_provider_by_name(provider_id)
            if provider_record:
                model_record = model_repo.get_model_by_provider_and_model_id(
                    provider_record.id, model
                )

        if provider_record and model_record:
            provider_config = ProviderConfig(
                type=provider_record.provider_type,
                api_key=provider_record.api_key,
                api_base=provider_record.api_host,
            )
            providers_dict = {provider_record.name: provider_config}
            agent_defaults = AgentDefaults(
                model=model_record.model_id,
                provider=provider_record.name,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            # Fallback: use default from config
            from backend.core.config.loader import load_config
            config = load_config()
            providers_dict = config.providers
            agent_defaults = AgentDefaults(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        provider = create_provider(providers_dict, agent_defaults)

        response = await provider.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return {
            "content": response.content,
            "reasoning": getattr(response, "reasoning", "") or "",
        }
