"""Plugin handler base class - similar to FeishuCapabilities."""

import os
from abc import abstractmethod
from pathlib import Path
from typing import Any

from loguru import logger

from backend.extensions.plugin_interface import PluginInterface, PluginResult
from backend.extensions.plugin_skill_parser import PluginSkill, SkillParser
from backend.utils.helpers import get_extensions_path


class PluginHandler(PluginInterface):
    """
    Plugin handler base class - similar to FeishuCapabilities.
    
    Subclasses implement specific action methods.
    SKILL.md defines what actions are available.
    """
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.skill: PluginSkill | None = None
        self.config: dict = {}
        self.missing_configs: list[dict] = []  # 缺失的必需配置
    
    async def load(self) -> bool:
        """Load plugin - parse SKILL.md and initialize."""
        # Parse SKILL.md
        skill_path = self.plugin_dir / "SKILL.md"
        self.skill = SkillParser.parse(skill_path)

        if not self.skill:
            raise ValueError(f"Cannot parse SKILL.md in {self.plugin_dir}")

        # Load configuration from manifest.yaml
        self.config = self._load_manifest_config()

        # Load plugin environment variables
        self._load_plugin_env()

        # Check required environment configuration
        self._check_required_config()

        # Call subclass initialization
        return await self.on_load()

    def _load_manifest_config(self) -> dict:
        """Load configuration from manifest.yaml.

        Returns:
            Configuration dict from manifest's config section.
        """
        manifest_path = self.plugin_dir / "manifest.yaml"
        if not manifest_path.exists():
            return {}

        try:
            import yaml
            manifest = yaml.safe_load(manifest_path.read_text()) or {}
            return manifest.get("config", {})
        except Exception as e:
            logger.warning(f"Failed to parse manifest.yaml: {e}")
            return {}
    
    def _load_plugin_env(self) -> None:
        """Load environment variables from plugin's .env file."""
        plugin_name = self.plugin_dir.name
        plugin_env_path = get_extensions_path() / plugin_name / ".env"

        logger.info(f"Loading env for plugin {plugin_name} from {plugin_env_path}")

        if not plugin_env_path.exists():
            logger.warning(f"Env file not found: {plugin_env_path}")
            return

        try:
            loaded_count = 0
            with open(plugin_env_path, "r") as f:
                content = f.read()
                logger.info(f"Env file content: {repr(content)}")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        # Strip whitespace from key and value
                        key = key.strip()
                        value = value.strip()
                        if key:  # Only set if key is not empty
                            # Set in current process with plugin prefix to avoid conflicts
                            os.environ[f"PLUGIN_{plugin_name.upper()}_{key}"] = value
                            # Also set without prefix for convenience
                            os.environ[key] = value
                            loaded_count += 1
                            logger.info(f"Set env var: {key}={value}")
            logger.info(f"Loaded {loaded_count} environment variables for plugin: {plugin_name}")
        except Exception as e:
            logger.warning(f"Failed to load env for plugin {plugin_name}: {e}")
    
    def _check_required_config(self) -> None:
        """Check if required environment variables are configured."""
        self.missing_configs = []

        # Get environment configuration schema from config.yaml
        env_config = self.config.get("environment", {})
        fields = env_config.get("fields", [])

        logger.info(f"Checking required config for plugin {self.plugin_dir.name}, fields: {[f.get('name') for f in fields]}")

        if not fields:
            return

        for field in fields:
            env_var = field.get("name")
            if not env_var:
                continue

            # Check if required and not set
            is_required = field.get("required", False)
            env_value = os.environ.get(env_var)
            logger.info(f"Checking {env_var}: required={is_required}, value={repr(env_value)}")

            if is_required and not env_value:
                self.missing_configs.append(field)

        if self.missing_configs:
            field_names = [f["name"] for f in self.missing_configs]
            logger.warning(
                f"Plugin '{self.name}' missing required config: {', '.join(field_names)}"
            )
    
    def get_config_page_params(self) -> dict | None:
        """Get parameters for creating a configuration page.
        
        Returns:
            Dict with title, description, fields, etc. or None if no config needed.
        """
        if not self.missing_configs:
            return None
        
        env_config = self.config.get("environment", {})
        config_page = env_config.get("config_page", {})
        
        return {
            "title": config_page.get("title", f"{self.name} 配置"),
            "description": config_page.get(
                "description", 
                f"请配置 {self.name} 插件所需的以下信息"
            ),
            "fields": self.missing_configs,
            "expires_in_minutes": config_page.get("expires_in_minutes", 30),
            "plugin": self.name
        }
    
    async def unload(self) -> None:
        """Unload plugin - cleanup resources."""
        await self.on_unload()
    
    @abstractmethod
    async def on_load(self) -> bool:
        """
        Subclass implements: initialization when loading.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    async def on_unload(self) -> None:
        """Subclass implements: cleanup when unloading."""
        pass
    
    @property
    def name(self) -> str:
        """Plugin name from SKILL.md."""
        return self.skill.name if self.skill else ""
    
    @property
    def actions(self) -> list[str]:
        """Actions auto-discovered from handle_* methods."""
        actions = []
        for attr_name in dir(self):
            if attr_name.startswith('handle_') and callable(getattr(self, attr_name)):
                action_name = attr_name[7:]  # Remove 'handle_' prefix
                actions.append(action_name)
        return actions
    
    @property
    def capabilities(self) -> list[str]:
        """Capabilities from SKILL.md."""
        if not self.skill:
            return []
        return self.skill.capabilities
    
    async def execute(self, action: str, **kwargs: Any) -> PluginResult:
        """
        Execute action - dispatch to handle_{action} method.
        """
        logger.info(f"Executing action '{action}' for plugin '{self.name}'")
        
        # Validate action exists
        if action not in self.actions:
            return PluginResult(
                success=False,
                error=f"Action '{action}' not supported. Available: {', '.join(self.actions)}"
            )
        
        # Note: Configuration check is done in ActionTool._execute_plugin() before calling this method
        
        # Find handler method
        method_name = f"handle_{action}"
        method = getattr(self, method_name, None)
        
        if not method:
            return PluginResult(
                success=False,
                error=f"Handler method '{method_name}' not implemented"
            )
        
        # Execute
        try:
            result = await method(**kwargs)
            if isinstance(result, PluginResult):
                return result
            return PluginResult(success=True, data=result)
        except Exception as e:
            return PluginResult(success=False, error=str(e))
    
    def get_skill_doc(self) -> str:
        """Get SKILL.md content for agent context - always read fresh from file."""
        skill_path = self.plugin_dir / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return self.skill.raw_content if self.skill else ""
    
    def get_action_info(self, action: str) -> dict[str, Any] | None:
        """Get information about a specific action."""
        if not self.skill:
            return None
        
        for a in self.skill.actions:
            if a.name == action:
                return {
                    "name": a.name,
                    "description": a.description,
                    "required_params": a.required_params,
                    "optional_params": a.optional_params,
                }
        return None
