"""SubAgent loader for discovering and loading role-based subagents."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class SubAgentConfig:
    """Configuration for a SubAgent role."""
    name: str
    description: str
    provider: str = "openai"
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    max_iterations: int = 30
    temperature: float = 0.7
    system_prompt: str = ""
    provider_id: int | None = None
    model_id: int | None = None
    
    @property
    def display_name(self) -> str:
        """Get display name for the subagent."""
        return self.name.replace("-", " ").replace("_", " ").title()


class SubAgentLoader:
    """Loader for discovering and loading SubAgent roles from database."""

    def __init__(self, workspace: Path, db=None):
        self.workspace = workspace
        self._cache: dict[str, SubAgentConfig] = {}
        self._db = db
        self._subagent_repo = None

    def _get_db(self):
        """Get database instance."""
        if self._db is None:
            from backend.data import Database
            self._db = Database()
        return self._db

    def _get_subagent_repo(self):
        """Get subagent repository instance."""
        if self._subagent_repo is None:
            from backend.data.subagent_store import SubagentRepository
            self._subagent_repo = SubagentRepository(self._get_db())
        return self._subagent_repo

    def load_all(self) -> list[SubAgentConfig]:
        """Load all available subagent configurations from database.

        Returns:
            List of SubAgentConfig instances.
        """
        configs = []
        seen_names = set()

        try:
            db_configs = self._load_all_from_database()
            for config in db_configs:
                if config.name not in seen_names:
                    configs.append(config)
                    seen_names.add(config.name)
                    logger.debug(f"Loaded subagent from database: {config.name}")
        except Exception as e:
            logger.warning(f"Failed to load subagents from database: {e}")

        logger.info(f"Loaded {len(configs)} subagent configurations")
        return configs

    def _load_all_from_database(self) -> list[SubAgentConfig]:
        """Load all subagent configurations from database.
        
        Returns:
            List of SubAgentConfig instances.
        """
        from backend.data.provider_store import ProviderRepository, ModelRepository
        
        repo = self._get_subagent_repo()
        provider_repo = ProviderRepository(self._get_db())
        model_repo = ModelRepository(self._get_db())
        
        records = repo.get_enabled_subagents()
        configs = []
        
        for record in records:
            provider_name = "openai"
            model_name = None
            
            if record.provider_id:
                provider = provider_repo.get_provider_by_id(record.provider_id)
                if provider:
                    provider_name = provider.name
            
            if record.model_id:
                model = model_repo.get_model_by_id(record.model_id)
                if model:
                    model_name = model.model_id
            
            config = SubAgentConfig(
                name=record.name,
                description=record.description,
                provider=provider_name,
                model=model_name,
                tools=record.tools,
                extensions=record.extensions,
                max_iterations=record.max_iterations,
                temperature=record.temperature,
                system_prompt=record.system_prompt,
                provider_id=record.provider_id,
                model_id=record.model_id,
            )
            configs.append(config)
        
        return configs
    
    def get(self, name: str, reload: bool = False) -> SubAgentConfig | None:
        """Get a subagent configuration by name.

        Args:
            name: Subagent name
            reload: If True, force reload from database, bypassing cache

        Returns:
            SubAgentConfig or None if not found
        """
        if not reload and name in self._cache:
            return self._cache[name]

        if reload and name in self._cache:
            del self._cache[name]

        for config in self.load_all():
            if config.name == name:
                self._cache[name] = config
                return config

        return None
    
    def list_agents(self) -> list[dict[str, str]]:
        """List all available subagents.
        
        Returns:
            List of agent info dicts with 'name', 'description'
        """
        configs = self.load_all()
        return [
            {
                "name": config.name,
                "description": config.description,
            }
            for config in configs
        ]
    
    def build_agents_summary(self) -> str:
        """Build a summary of all subagents for system prompt.
        
        Returns:
            XML-formatted subagents summary
        """
        configs = self.load_all()
        if not configs:
            return ""
        
        lines = ["<subagents>"]
        for config in configs:
            lines.append(f'  <subagent name="{config.name}">')
            lines.append(f"    <description>{config.description}</description>")
            lines.append(f"    <tools>{', '.join(config.tools)}</tools>")
            lines.append(f"    <extensions>{', '.join(config.extensions)}</extensions>")
            lines.append("  </subagent>")
        lines.append("</subagents>")
        
        return "\n".join(lines)
    
    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()
