"""Resolve the user's default chat model and seconds settings without extraction fallback."""

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.core.book_room_settings import BookRoomTimeoutSettings
from backend.core.config.schema import AgentDefaults, ProviderConfig
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import MockProvider, create_provider
from backend.data.database import Database
from backend.data.provider_store import AgentDefaultsRepository, ModelRepository, ProviderRepository

from .room_models import CharacterChatConfig
from .source import BookWorldError


@dataclass(frozen=True)
class CharacterChatModel:
    provider: LLMProvider
    config: CharacterChatConfig
    timeouts: BookRoomTimeoutSettings


def list_character_chat_models() -> list[dict]:
    db = Database()
    providers, models = ProviderRepository(db), ModelRepository(db)
    return [
        {
            "provider_id": provider.id,
            "model_record_id": model.id,
            "label": f"{provider.name} · {model.display_name or model.model_id}",
        }
        for provider in providers.get_enabled_providers()
        if provider.api_key
        for model in models.get_enabled_models_by_provider(provider.id)
        if "chat" in model.model_types
        if (model.context_window or 32768) >= 16000 and (model.max_tokens or 4096) >= 512
    ]


def resolve_character_chat_model(
    provider_id: int | None = None,
    model_record_id: int | None = None,
    *,
    original_config: CharacterChatConfig | None = None,
) -> CharacterChatModel:
    db = Database()
    defaults = AgentDefaultsRepository(db).get_or_create_defaults()
    providers, models = ProviderRepository(db), ModelRepository(db)
    provider = (
        providers.get_provider_by_id(
            provider_id if provider_id is not None else defaults.default_provider_id
        )
        if provider_id is not None or defaults.default_provider_id
        else None
    )
    selected_model = model_record_id if model_record_id is not None else defaults.default_model_id
    model = models.get_model_by_id(selected_model) if selected_model else None
    if (
        provider is None
        or not provider.enabled
        or not provider.api_key
        or model is None
        or not model.enabled
        or "chat" not in model.model_types
        or model.provider_id != provider.id
    ):
        raise BookWorldError(
            "blocked_config", "Choose an enabled default chat provider and its model in Settings"
        )
    endpoint = urlsplit(provider.api_host)
    kimi = (
        provider.provider_type == "anthropic"
        and endpoint.hostname in ("api.kimi.com", "api.kimi.ai")
        and endpoint.path.rstrip("/") == "/coding"
    )
    model_id = (
        model.model_id.casefold()
        if kimi and model.model_id.casefold() in ("k3", "k3-256k")
        else model.model_id
    )
    max_tokens = (
        original_config.max_tokens
        if original_config is not None
        else min(model.max_tokens or 4096, defaults.max_tokens or 4096, 4096)
    )
    context_window = (
        original_config.context_window
        if original_config is not None
        else model.context_window or 32768
    )
    if max_tokens < 512 or context_window < 16000:
        raise BookWorldError(
            "blocked_config", "Default chat model needs a sufficient input/output budget"
        )
    signature = hashlib.sha256(
        json.dumps(
            [provider.id, provider.provider_type, provider.api_host], ensure_ascii=False
        ).encode()
    ).hexdigest()
    config = CharacterChatConfig(
        model_record_id=model.id,
        provider_id=provider.id,
        model=model_id,
        provider_signature=signature,
        max_tokens=max_tokens,
        context_window=context_window,
        reasoning_effort="low" if kimi else None,
        expression_selection_version="expression-selection-v2",
        memory_policy_version="typed-room-memory-v1",
        memory_prompt_version="room-memory-v2",
        prompt_version=original_config.prompt_version if original_config else "character-chat-v14",
        review_prompt_version=original_config.review_prompt_version
        if original_config
        else "character-chat-review-v9",
    )
    resolved = create_provider(
        {
            provider.name: ProviderConfig(
                type=provider.provider_type, api_key=provider.api_key, api_base=provider.api_host
            )
        },
        AgentDefaults(
            provider=provider.name,
            model=model_id,
            max_tokens=max_tokens,
            temperature=0,
            llm_max_retries=0,
        ),
    )
    if isinstance(resolved, MockProvider):
        raise BookWorldError("blocked_config", "A real default chat model is required")
    timeouts = BookRoomTimeoutSettings(
        book_room_round_timeout_seconds=defaults.book_room_round_timeout_seconds,
        book_room_all_round_timeout_seconds=defaults.book_room_all_round_timeout_seconds,
    )
    return CharacterChatModel(resolved, config, timeouts)
