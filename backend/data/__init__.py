"""Data layer module for backend.

This module provides unified database access and session management.
"""

from backend.data.database import Database
from backend.data.session_store import SessionRepository, SessionRecord, SessionInstance, MessageRecord
from backend.data.mcp_store import MCPRepository, MCPServerRecord, MCPToolRecord, MCPToolStats
from backend.data.session_manager import SessionManager, Session
from backend.data.session_db import SessionDatabase
from backend.data.commands import SessionCommandHandler, CommandResult, handle_session_command
from backend.data.provider_store import ProviderRepository, ModelRepository, SettingsRepository, ProviderRecord, ModelRecord
from backend.data.system_providers import SYSTEM_PROVIDERS, SYSTEM_MODELS, get_default_models
from backend.data.token_store import TokenUsageRepository, TokenUsageRecord, TokenUsageSummary
from backend.data.subagent_store import (
    SubagentRepository, SubagentRecord,
    AvailableToolRepository, AvailableToolRecord,
    AvailableExtensionRepository, AvailableExtensionRecord
)

def init_system_providers(db: Database):
    """Initialize system providers if not exist."""
    provider_repo = ProviderRepository(db)
    model_repo = ModelRepository(db)

    for provider_data in SYSTEM_PROVIDERS:
        name = provider_data["name"]
        if not provider_repo.get_provider_by_name(name):
            provider = provider_repo.add_provider(
                name=name,
                display_name=provider_data["display_name"],
                provider_type=provider_data["provider_type"],
                api_host=provider_data.get("api_host", ""),
                is_system=True,
            )

            models = get_default_models(name)
            if models:
                for i, model_data in enumerate(models):
                    model_types = model_data.get("model_types")
                    model_repo.add_model(
                        provider_id=provider.id,
                        model_id=model_data["model_id"],
                        display_name=model_data["display_name"],
                        model_types=model_types,
                        group_name=model_data.get("group_name", "Chat Models"),
                        context_window=model_data.get("context_window", 128000),
                        supports_vision=model_data.get("supports_vision", False),
                        enabled=model_data.get("enabled", False),
                        is_default=(i == 0),
                    )

    from loguru import logger
    logger.info(f"Initialized {len(SYSTEM_PROVIDERS)} system providers")

__all__ = [
    # Core database
    "Database",
    # Session repository
    "SessionRepository",
    "SessionRecord",
    "SessionInstance",
    "MessageRecord",
    # MCP repository
    "MCPRepository",
    "MCPServerRecord",
    "MCPToolRecord",
    "MCPToolStats",
    # Session management
    "SessionManager",
    "Session",
    "SessionDatabase",
    # Commands
    "SessionCommandHandler",
    "CommandResult",
    "handle_session_command",
    # Provider & Model
    "ProviderRepository",
    "ModelRepository",
    "SettingsRepository",
    "ProviderRecord",
    "ModelRecord",
    # System providers
    "SYSTEM_PROVIDERS",
    "SYSTEM_MODELS",
    "get_default_models",
    "init_system_providers",
    # Token Usage
    "TokenUsageRepository",
    "TokenUsageRecord",
    "TokenUsageSummary",
    # Subagent
    "SubagentRepository",
    "SubagentRecord",
    "AvailableToolRepository",
    "AvailableToolRecord",
    "AvailableExtensionRepository",
    "AvailableExtensionRecord",
]
