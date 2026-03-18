"""SubAgent loader for discovering and loading role-based subagents."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
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
    
    @property
    def display_name(self) -> str:
        """Get display name for the subagent."""
        return self.name.replace("-", " ").replace("_", " ").title()


class SubAgentLoader:
    """Loader for discovering and loading SubAgent roles from SOUL.md files.

    Similar to SkillsLoader, but for SubAgent configurations.
    SubAgents are defined in workspace/agents/<name>/SOUL.md files.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.agents_dir = workspace / "agents"
        self._cache: dict[str, SubAgentConfig] = {}

    def load_all(self) -> list[SubAgentConfig]:
        """Load all available subagent configurations.

        Returns:
            List of SubAgentConfig instances.
        """
        configs = []
        seen_names = set()

        if self.agents_dir.exists():
            for agent_dir in sorted(self.agents_dir.iterdir()):
                if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                    config = self._load_from_directory(agent_dir)
                    if config and config.name not in seen_names:
                        configs.append(config)
                        seen_names.add(config.name)
                        logger.debug(f"Loaded subagent config: {config.name}")

        logger.info(f"Loaded {len(configs)} subagent configurations")
        return configs
    
    def _load_from_directory(self, directory: Path) -> SubAgentConfig | None:
        """Load subagent configuration from a directory.
        
        Args:
            directory: Agent directory containing SOUL.md
            
        Returns:
            SubAgentConfig or None if invalid
        """
        soul_file = directory / "SOUL.md"
        if not soul_file.exists():
            logger.debug(f"No SOUL.md found in {directory}")
            return None
        
        try:
            content = soul_file.read_text(encoding="utf-8")
            return self._parse_soul_md(directory.name, content)
        except Exception as e:
            logger.error(f"Failed to load SOUL.md from {directory}: {e}")
            return None
    
    def _parse_soul_md(self, name: str, content: str) -> SubAgentConfig | None:
        """Parse SOUL.md content into SubAgentConfig.
        
        Args:
            name: Subagent name (directory name)
            content: SOUL.md file content
            
        Returns:
            SubAgentConfig or None if parsing fails
        """
        # Extract YAML frontmatter
        metadata: dict[str, Any] = {}
        system_prompt = content
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
            if match:
                yaml_content = match.group(1)
                system_prompt = match.group(2).strip()
                try:
                    metadata = yaml.safe_load(yaml_content) or {}
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse YAML frontmatter: {e}")
        
        # Build config from metadata
        return SubAgentConfig(
            name=metadata.get("name", name),
            description=metadata.get("description", f"SubAgent: {name}"),
            provider=metadata.get("provider", "openai"),
            model=metadata.get("model"),
            tools=self._parse_list_field(metadata.get("tools", [])),
            extensions=self._parse_list_field(metadata.get("extensions", [])),
            max_iterations=metadata.get("max_iterations", 30),
            temperature=metadata.get("temperature", 0.7),
            system_prompt=system_prompt,
        )
    
    def _parse_list_field(self, value: Any) -> list[str]:
        """Parse a field that can be string or list into list of strings.
        
        Args:
            value: Field value (string, list, or None)
            
        Returns:
            List of strings
        """
        if not value:
            return []
        if isinstance(value, str):
            # Handle comma-separated string
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if item]
        return []
    
    def get(self, name: str, reload: bool = False) -> SubAgentConfig | None:
        """Get a subagent configuration by name.

        Args:
            name: Subagent name (matches the 'name' field in SOUL.md)
            reload: If True, force reload from disk, bypassing cache

        Returns:
            SubAgentConfig or None if not found
        """
        # Check cache first (unless reload is requested)
        if not reload and name in self._cache:
            return self._cache[name]

        # If reload is requested, clear cache for this agent
        if reload and name in self._cache:
            del self._cache[name]

        # Load all and find by name field
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
