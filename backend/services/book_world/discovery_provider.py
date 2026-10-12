"""Resolve a model once; persist only a non-secret, comparable configuration snapshot."""

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.core.config.schema import AgentDefaults, ProviderConfig
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import MockProvider, create_provider
from backend.data.database import Database
from backend.data.provider_store import AgentDefaultsRepository, ModelRepository, ProviderRepository

from .discovery_models import DiscoveryConfig
from .source import BookWorldError


@dataclass(frozen=True)
class DiscoveryModel:
    provider: LLMProvider
    config: DiscoveryConfig
    context_window: int = 32768


def resolve_discovery_model() -> DiscoveryModel:
    db = Database()
    defaults = AgentDefaultsRepository(db).get_or_create_defaults()
    providers = ProviderRepository(db)
    models = ModelRepository(db)
    selected_id = defaults.library_extract_provider_id or defaults.default_provider_id
    provider_record = (
        providers.get_provider_by_id(selected_id)
        if selected_id
        else next((record for record in providers.get_enabled_providers() if record.api_key), None)
    )
    if not provider_record or not provider_record.enabled or not provider_record.api_key:
        raise BookWorldError(
            "blocked_config", "Configure an enabled library extraction provider in Settings"
        )
    selected_model = defaults.library_extract_model_id or defaults.default_model_id
    model_record = models.get_model_by_id(selected_model) if selected_model else None
    if selected_model and (
        not model_record
        or model_record.provider_id != provider_record.id
        or not model_record.enabled
    ):
        raise BookWorldError(
            "blocked_config", "Library extraction model must belong to its enabled provider"
        )
    if model_record is None:
        available = models.get_enabled_models_by_provider(provider_record.id)
        model_record = next((record for record in available if record.is_default), None) or next(
            iter(available), None
        )
    if not model_record:
        raise BookWorldError(
            "blocked_config", "Choose an enabled library extraction model in Settings"
        )
    max_tokens = min(model_record.max_tokens or 4096, 4096)
    # Reserve schema, known identities and response tokens; Chinese input uses a conservative budget.
    input_budget = min(4000, ((model_record.context_window or 32768) - max_tokens - 10000) // 2)
    if input_budget < 2000 or max_tokens < 512:
        raise BookWorldError("blocked_config", "Extraction model context window is too small")
    signature = hashlib.sha256(
        json.dumps(
            [provider_record.id, provider_record.provider_type, provider_record.api_host],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    endpoint = urlsplit(provider_record.api_host)
    is_kimi_anthropic = (
        provider_record.provider_type == "anthropic"
        and endpoint.hostname in ("api.kimi.com", "api.kimi.ai")
        and endpoint.path.rstrip("/") == "/coding"
    )
    model_id = model_record.model_id
    if is_kimi_anthropic and model_id.casefold() in ("k3", "k3-256k"):
        model_id = model_id.casefold()
    config = DiscoveryConfig(
        provider_id=provider_record.id,
        model=model_id,
        reasoning_effort="low" if is_kimi_anthropic else None,
        provider_signature=signature,
        unit_char_limit=input_budget,
        max_tokens=max_tokens,
    )
    provider = create_provider(
        {
            provider_record.name: ProviderConfig(
                type=provider_record.provider_type,
                api_key=provider_record.api_key,
                api_base=provider_record.api_host,
            )
        },
        AgentDefaults(
            provider=provider_record.name,
            model=model_id,
            max_tokens=max_tokens,
            temperature=0,
            llm_max_retries=0,
        ),
    )
    if isinstance(provider, MockProvider):
        raise BookWorldError("blocked_config", "A real extraction model is required")
    return DiscoveryModel(
        provider=provider, config=config, context_window=model_record.context_window or 32768
    )
