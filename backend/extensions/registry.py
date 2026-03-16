"""Extension registry for managing loaded extensions."""

from loguru import logger

from .base import Extension, SkillExtension, PluginExtension


class ExtensionRegistry:
    """Central registry for all extensions.

    This registry maintains references to all loaded extensions
    and provides convenient lookup methods.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure single registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._extensions: dict[str, Extension] = {}
        self._skills: dict[str, SkillExtension] = {}
        self._plugins: dict[str, PluginExtension] = {}
        self._capability_index: dict[str, list[str]] = {}
        self._initialized = True

        logger.info("[ExtensionRegistry] Initialized")

    def register(self, ext: Extension) -> None:
        """Register an extension.

        Args:
            ext: Extension instance to register
        """
        self._extensions[ext.name] = ext

        # Index by type
        if isinstance(ext, SkillExtension):
            self._skills[ext.name] = ext
            logger.info(f"[ExtensionRegistry] Registered skill: {ext.name}")

        if isinstance(ext, PluginExtension):
            self._plugins[ext.name] = ext
            logger.info(f"[ExtensionRegistry] Registered plugin: {ext.name}")

        # Index by capability
        for cap in ext.capabilities:
            if cap not in self._capability_index:
                self._capability_index[cap] = []
            if ext.name not in self._capability_index[cap]:
                self._capability_index[cap].append(ext.name)

    def unregister(self, name: str) -> None:
        """Unregister an extension.

        Args:
            name: Extension name
        """
        ext = self._extensions.pop(name, None)
        if not ext:
            return

        # Remove from type indexes
        if isinstance(ext, SkillExtension):
            self._skills.pop(name, None)

        if isinstance(ext, PluginExtension):
            self._plugins.pop(name, None)

        # Remove from capability index
        for cap in ext.capabilities:
            if cap in self._capability_index:
                if name in self._capability_index[cap]:
                    self._capability_index[cap].remove(name)

        logger.info(f"[ExtensionRegistry] Unregistered extension: {name}")

    def get(self, name: str) -> Extension | None:
        """Get extension by name.

        Args:
            name: Extension name

        Returns:
            Extension instance or None
        """
        return self._extensions.get(name)

    def get_skill(self, name: str) -> SkillExtension | None:
        """Get skill extension by name.

        Args:
            name: Skill name

        Returns:
            Skill extension or None
        """
        return self._skills.get(name)

    def get_plugin(self, name: str) -> PluginExtension | None:
        """Get plugin extension by name.

        Args:
            name: Plugin name

        Returns:
            Plugin extension or None
        """
        return self._plugins.get(name)

    def list_all(self) -> list[Extension]:
        """List all registered extensions.

        Returns:
            List of all extensions
        """
        return list(self._extensions.values())

    def list_skills(self, filter_available: bool = False) -> list[Extension]:
        """List all skill-like extensions (skills and plugins).

        All extension types are included because they all have SKILL.md
        documentation that the agent needs to read.

        Args:
            filter_available: If True, only return skills with met requirements

        Returns:
            List of all skill-like extensions
        """
        # Include skills and plugins - all have SKILL.md
        all_skills = list(self._skills.values()) + list(self._plugins.values())
        if filter_available:
            all_skills = [s for s in all_skills if s.check_requirements()[0]]
        return all_skills

    def list_plugins(self) -> list[PluginExtension]:
        """List all plugin extensions.

        Returns:
            List of plugin extensions
        """
        return list(self._plugins.values())

    def list_by_capability(self, capability: str) -> list[Extension]:
        """List extensions by capability.

        Args:
            capability: Capability name

        Returns:
            List of extensions with the capability
        """
        names = self._capability_index.get(capability, [])
        return [self._extensions[n] for n in names if n in self._extensions]

    def list_capabilities(self) -> list[str]:
        """List all registered capabilities.

        Returns:
            List of capability names
        """
        return list(self._capability_index.keys())

    def get_all_skill_docs(self) -> dict[str, str]:
        """Get all skill documentation.

        Returns:
            Dict of skill name -> documentation
        """
        docs = {}
        for name, skill in self._skills.items():
            docs[name] = skill.load_documentation()
        return docs

    def build_skills_summary(self, exclude_types: list[str] | None = None) -> str:
        """Build XML summary of all skills.

        Includes skills and plugins - all have SKILL.md documentation.

        Args:
            exclude_types: List of extension types to exclude (e.g., ["longtask"])

        Returns:
            XML-formatted skills summary
        """
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]

        # Include skills and plugins - all have SKILL.md
        all_extensions = list(self._skills.values()) + list(self._plugins.values())

        # Filter out excluded types
        if exclude_types:
            all_extensions = [ext for ext in all_extensions if ext.type not in exclude_types]

        for ext in all_extensions:
            lines.append('  <skill>')
            lines.append(f'    <name>{escape_xml(ext.name)}</name>')
            lines.append(f'    <description>{escape_xml(ext.description)}</description>')
            lines.append(f'    <location>{escape_xml(str(ext.directory))}</location>')
            lines.append('  </skill>')

        lines.append("</skills>")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all registered extensions."""
        self._extensions.clear()
        self._skills.clear()
        self._plugins.clear()
        self._capability_index.clear()
        logger.info("[ExtensionRegistry] Cleared all extensions")


# Global registry instance
_registry: ExtensionRegistry | None = None


def get_registry() -> ExtensionRegistry:
    """Get global extension registry instance.

    Returns:
        ExtensionRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = ExtensionRegistry()
    return _registry


def set_registry(registry: ExtensionRegistry) -> None:
    """Set global extension registry instance.

    Args:
        registry: Registry instance to set
    """
    global _registry
    _registry = registry
