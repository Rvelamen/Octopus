"""Agent configuration service for accessing config from database.

This module provides a service layer for accessing agent configuration
from the database, replacing the previous config.json-based approach.
"""

from pathlib import Path
from typing import Any

from backend.data.database import Database
from backend.core.providers.base import LLMProvider


class AgentConfigService:
    """Service for accessing agent configuration from database.
    
    This service replaces the previous load_config() approach by reading
    configuration directly from the database tables.
    """
    
    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self._agent_defaults_repo = None
        self._provider_repo = None
        self._model_repo = None
    
    def _get_agent_defaults_repo(self):
        """Get or create AgentDefaultsRepository instance."""
        if self._agent_defaults_repo is None:
            from backend.data.provider_store import AgentDefaultsRepository
            self._agent_defaults_repo = AgentDefaultsRepository(self.db)
        return self._agent_defaults_repo
    
    def _get_provider_repo(self):
        """Get or create ProviderRepository instance."""
        if self._provider_repo is None:
            from backend.data.provider_store import ProviderRepository
            self._provider_repo = ProviderRepository(self.db)
        return self._provider_repo
    
    def _get_model_repo(self):
        """Get or create ModelRepository instance."""
        if self._model_repo is None:
            from backend.data.provider_store import ModelRepository
            self._model_repo = ModelRepository(self.db)
        return self._model_repo
    
    # ========== Agent Defaults ==========
    
    def get_max_iterations(self) -> int:
        """Get max iterations from database."""
        try:
            defaults = self._get_agent_defaults_repo().get_or_create_defaults()
            return defaults.max_iterations
        except Exception:
            return 20  # Default fallback
    
    def get_context_compression_enabled(self) -> bool:
        """Get context compression enabled from database."""
        try:
            defaults = self._get_agent_defaults_repo().get_or_create_defaults()
            return defaults.context_compression_enabled
        except Exception:
            return False  # Default fallback
    
    def get_context_compression_turns(self) -> int:
        """Get context compression turns from database."""
        try:
            defaults = self._get_agent_defaults_repo().get_or_create_defaults()
            return defaults.context_compression_turns
        except Exception:
            return 10  # Default fallback
    
    def get_context_compression_token_threshold(self) -> int:
        """Get context compression token threshold from database."""
        try:
            defaults = self._get_agent_defaults_repo().get_or_create_defaults()
            return getattr(defaults, 'context_compression_token_threshold', 8000) or 8000
        except Exception:
            return 8000  # Default fallback
    
    def get_workspace_path(self) -> str:
        """Get workspace path from database."""
        try:
            defaults = self._get_agent_defaults_repo().get_or_create_defaults()
            return defaults.workspace_path or ""
        except Exception:
            return ""
    
    # ========== Provider and Model ==========
    
    def get_default_provider_and_model(self) -> tuple[LLMProvider, str, str]:
        """Get default provider, model, and provider_type from database.
        
        Returns:
            Tuple of (provider, model_id, provider_type)
        """
        from backend.core.providers.factory import create_provider
        from backend.core.config.schema import AgentDefaults, ProviderConfig
        
        defaults = self._get_agent_defaults_repo().get_or_create_defaults()
        
        # Get provider details
        provider_record = None
        if defaults.default_provider_id:
            provider_record = self._get_provider_repo().get_provider_by_id(defaults.default_provider_id)
        
        # If no provider configured, use first available enabled provider
        if not provider_record:
            providers = self._get_provider_repo().get_enabled_providers()
            if providers:
                provider_record = providers[0]
        
        if not provider_record:
            raise ValueError("No provider configured in database")
        
        # Get model
        model_id = None
        if defaults.default_model_id:
            model_record = self._get_model_repo().get_model_by_id(defaults.default_model_id)
            if model_record:
                model_id = model_record.model_id
        
        if not model_id:
            # Use provider's default model (find model with is_default=True)
            default_model = self._get_model_repo().get_default_model(provider_record.id)
            if default_model:
                model_id = default_model.model_id
            else:
                # Fallback: use first enabled model for this provider
                enabled_models = self._get_model_repo().get_enabled_models_by_provider(provider_record.id)
                if enabled_models:
                    model_id = enabled_models[0].model_id
                else:
                    model_id = "gpt-4o"  # Ultimate fallback
        
        # Create ProviderConfig for factory
        provider_config = ProviderConfig(
            type=provider_record.provider_type,
            api_key=provider_record.api_key,
            api_base=provider_record.api_host
        )
        
        # Create AgentDefaults for factory
        agent_defaults = AgentDefaults(
            provider=provider_record.name,
            model=model_id,
            llm_max_retries=getattr(defaults, 'llm_max_retries', 3) or 3,
            llm_retry_base_delay=getattr(defaults, 'llm_retry_base_delay', 1.0) or 1.0,
            llm_retry_max_delay=getattr(defaults, 'llm_retry_max_delay', 30.0) or 30.0,
        )
        
        # Create provider using factory
        providers_dict = {provider_record.name: provider_config}
        provider = create_provider(providers_dict, agent_defaults)
        
        return provider, model_id, provider_record.provider_type
    
    def get_provider_by_name(self, name: str) -> Any | None:
        """Get provider record by name.
        
        Args:
            name: Provider name
            
        Returns:
            Provider record or None if not found
        """
        return self._get_provider_repo().get_provider_by_name(name)
    
    def get_provider_for_subagent(self, provider_name: str, model_name: str | None = None) -> tuple[LLMProvider, str]:
        """Get provider and model for a subagent configuration.
        
        Args:
            provider_name: Provider name
            model_name: Optional model name
            
        Returns:
            Tuple of (provider, model_id)
        """
        from backend.core.providers.factory import create_provider
        from backend.core.config.schema import AgentDefaults, ProviderConfig
        
        # Get agent defaults for retry config
        defaults = self._get_agent_defaults_repo().get_or_create_defaults()
        
        # Get provider from database
        provider_record = self._get_provider_repo().get_provider_by_name(provider_name)
        
        # If not found, use first available
        if not provider_record:
            providers = self._get_provider_repo().get_enabled_providers()
            if providers:
                provider_record = providers[0]
        
        if not provider_record:
            raise ValueError(f"Provider '{provider_name}' not found")
        
        # Get model
        if model_name:
            # Try to find the model in this provider
            models = self._get_model_repo().get_models_by_provider(provider_record.id)
            model_id = None
            for model in models:
                if model.model_id == model_name or model_name in model.model_id:
                    model_id = model.model_id
                    break
            if not model_id:
                model_id = model_name  # Use as-is if not found
        else:
            # Use provider's default model (find model with is_default=True)
            default_model = self._get_model_repo().get_default_model(provider_record.id)
            if default_model:
                model_id = default_model.model_id
            else:
                # Fallback: use first enabled model for this provider
                enabled_models = self._get_model_repo().get_enabled_models_by_provider(provider_record.id)
                if enabled_models:
                    model_id = enabled_models[0].model_id
                else:
                    model_id = "gpt-4o"  # Ultimate fallback
        
        # Create ProviderConfig for factory
        provider_config = ProviderConfig(
            type=provider_record.provider_type,
            api_key=provider_record.api_key,
            api_base=provider_record.api_host
        )
        
        # Create AgentDefaults for factory
        agent_defaults = AgentDefaults(
            provider=provider_record.name,
            model=model_id,
            llm_max_retries=getattr(defaults, 'llm_max_retries', 3) if defaults else 3,
            llm_retry_base_delay=getattr(defaults, 'llm_retry_base_delay', 1.0) if defaults else 1.0,
            llm_retry_max_delay=getattr(defaults, 'llm_retry_max_delay', 30.0) if defaults else 30.0,
        )
        
        # Create provider using factory
        providers_dict = {provider_record.name: provider_config}
        provider = create_provider(providers_dict, agent_defaults)
        
        return provider, model_id
    
    def get_all_providers(self) -> list[Any]:
        """Get all enabled providers.
        
        Returns:
            List of provider records
        """
        return self._get_provider_repo().get_enabled_providers()
