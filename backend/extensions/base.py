"""Base classes for extensions."""

import shutil
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PluginResult:
    """Result of a plugin action execution."""
    success: bool
    data: Any = None
    error: str = None


@dataclass
class Extension:
    """Base class for all extensions.

    Extensions provide a unified interface for skills and plugins.
    """

    name: str
    directory: Path
    manifest: dict
    enabled: bool = True
    _metadata: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Load metadata from SKILL.md if exists."""
        self._metadata = self._load_metadata()

    @property
    def type(self) -> str:
        """Get extension type."""
        return self.manifest.get("type", "skill")

    @property
    def description(self) -> str:
        """Get extension description."""
        return self.manifest.get(
            "description",
            self._metadata.get("description", f"Extension: {self.name}")
        )

    @property
    def version(self) -> str:
        """Get extension version."""
        return self.manifest.get("version", "1.0.0")

    @property
    def author(self) -> str:
        """Get extension author."""
        return self.manifest.get("author", "unknown")

    @property
    def capabilities(self) -> list[str]:
        """Get extension capabilities."""
        return self.manifest.get("capabilities", [])

    def has_capability(self, capability: str) -> bool:
        """Check if extension has a specific capability."""
        return capability in self.capabilities

    def check_requirements(self) -> tuple[bool, list[str]]:
        """Check if extension requirements are met.

        Returns:
            Tuple of (is_available, list_of_missing_requirements)
        """
        requires = self.manifest.get("requires", {})
        missing = []

        # Check required binaries
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                missing.append(f"binary: {binary}")

        # Check required environment variables
        for env_var in requires.get("env", []):
            if not os.environ.get(env_var):
                missing.append(f"env: {env_var}")

        # Check Python packages
        for package in requires.get("python_packages", []):
            try:
                __import__(package)
            except ImportError:
                missing.append(f"python_package: {package}")

        return len(missing) == 0, missing

    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get configuration value from manifest.

        Args:
            key: Configuration key to get. If None, returns entire config dict.
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        config = self.manifest.get("config", {})
        if key is None:
            return config
        return config.get(key, default)

    @property
    def environment_config(self) -> dict:
        """Get environment configuration definition from manifest."""
        return self.manifest.get("config", {}).get("environment", {})

    @property
    def defaults_config(self) -> dict:
        """Get default configuration values from manifest."""
        return self.manifest.get("config", {}).get("defaults", {})

    def _load_metadata(self) -> dict:
        """Load metadata from SKILL.md frontmatter if exists."""
        skill_file = self.directory / "SKILL.md"
        if not skill_file.exists():
            return {}

        try:
            content = skill_file.read_text(encoding="utf-8")
            if content.startswith("---"):
                import re
                match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if match:
                    try:
                        import yaml
                        return yaml.safe_load(match.group(1)) or {}
                    except ImportError:
                        # Fallback to simple parsing
                        metadata = {}
                        for line in match.group(1).split("\n"):
                            if ":" in line and not line.strip().startswith("#"):
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip().strip('"\'')
                        return metadata
        except Exception as e:
            logger.warning(f"Failed to load metadata for {self.name}: {e}")

        return {}


class SkillExtension(Extension):
    """Extension that provides skill documentation."""

    @property
    def always_load(self) -> bool:
        """Whether to always load this skill."""
        skill_config = self.manifest.get("skill", {})
        return skill_config.get("always", False) or self._metadata.get("always", False)

    @property
    def emoji(self) -> str:
        """Get skill emoji."""
        skill_config = self.manifest.get("skill", {})
        return skill_config.get("emoji", "🔧")

    @property
    def tool(self) -> str:
        """Get tool type for this skill."""
        skill_config = self.manifest.get("skill", {})
        return skill_config.get("tool", "action")

    def load_documentation(self) -> str:
        """Load and return skill documentation.

        Returns:
            Skill documentation content
        """
        skill_file = self.directory / "SKILL.md"
        if not skill_file.exists():
            return f"# {self.name}\n\n{self.description}"

        content = skill_file.read_text(encoding="utf-8")

        # Strip frontmatter if present
        if content.startswith("---"):
            import re
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                content = content[match.end():]

        return content.strip()


class PluginExtension(Extension):
    """Extension that provides plugin functionality."""

    @property
    def handler_class(self) -> str | None:
        """Get plugin handler class path."""
        # Priority 1: Use explicit config from manifest
        explicit = self.manifest.get("plugin", {}).get("handler")
        if explicit:
            return explicit

        # Priority 2: Auto-discover from handler.py
        return self._auto_discover_handler()

    def _auto_discover_handler(self) -> str | None:
        """Auto-discover handler class from handler.py.

        Finds the first class that inherits from PluginHandler or LongTaskPlugin.
        """
        handler_file = self.directory / "handler.py"
        if not handler_file.exists():
            return None

        try:
            import ast
            source = handler_file.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        # Check for PluginHandler or LongTaskPlugin inheritance
                        base_name = None
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr

                        if base_name in ("PluginHandler", "LongTaskPlugin"):
                            # Build module path: workspace.extensions.{name}.handler
                            return f"workspace.extensions.{self.name}.handler.{node.name}"

            logger.warning(f"No PluginHandler or LongTaskPlugin subclass found in {handler_file}")
        except Exception as e:
            logger.warning(f"Failed to auto-discover handler for {self.name}: {e}")

        return None

    @property
    def hooks_file(self) -> Path | None:
        """Get hooks configuration file path."""
        hooks_path = self.manifest.get("plugin", {}).get("hooks")
        if hooks_path:
            return self.directory / hooks_path
        return None

    def create_handler(self) -> Any:
        """Create and return plugin handler instance."""
        handler_class = self.handler_class
        if not handler_class:
            raise ValueError(f"No handler found for plugin '{self.name}'. "
                           f"Either define 'plugin.handler' in manifest.yaml "
                           f"or create a handler.py with a PluginHandler subclass.")

        from backend.extensions.plugin_isolated_loader import PluginModuleLoader

        loader = PluginModuleLoader(self.name, self.directory)
        loader.setup()

        try:
            module = loader.load_handler()
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and attr.__module__ == module.__name__:
                    for base in attr.__mro__[1:]:
                        if base.__name__ in ("PluginHandler", "LongTaskPlugin"):
                            return attr(self.directory)

            raise ValueError(f"No PluginHandler subclass found in {module.__name__}")
        except Exception as e:
            loader.cleanup()
            raise e


class LongTaskExtension(PluginExtension):
    """Extension that provides long-running task functionality.

    LongTaskExtension inherits from PluginExtension so it can be used
    with the action tool just like regular plugins.
    """

    @property
    def handler_class(self) -> str | None:
        """Get longtask handler class path."""
        # Priority 1: Use explicit config from manifest
        explicit = self.manifest.get("longtask", {}).get("handler")
        if explicit:
            return explicit

        # Priority 2: Auto-discover from handler.py
        return self._auto_discover_handler()

    def _auto_discover_handler(self) -> str | None:
        """Auto-discover handler class from handler.py.

        Finds the first class that inherits from LongTaskPlugin.
        """
        handler_file = self.directory / "handler.py"
        if not handler_file.exists():
            return None

        try:
            import ast
            source = handler_file.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        # Check for LongTaskPlugin inheritance
                        base_name = None
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr

                        if base_name == "LongTaskPlugin":
                            # Build module path: workspace.extensions.{name}.handler
                            return f"workspace.extensions.{self.name}.handler.{node.name}"

            logger.warning(f"No LongTaskPlugin subclass found in {handler_file}")
        except Exception as e:
            logger.warning(f"Failed to auto-discover handler for {self.name}: {e}")

        return None

    @property
    def worker_class(self) -> str | None:
        """Get worker class path from manifest."""
        return self.manifest.get("longtask", {}).get("worker_class")

    @property
    def task_type(self) -> str | None:
        """Get task type from manifest."""
        return self.manifest.get("longtask", {}).get("task_type")

    def create_handler(self) -> Any:
        """Create and return longtask handler instance."""
        handler_class = self.handler_class
        if not handler_class:
            raise ValueError(f"No handler found for longtask plugin '{self.name}'. "
                           f"Either define 'longtask.handler' in manifest.yaml "
                           f"or create a handler.py with a LongTaskPlugin subclass.")

        # Import and instantiate handler
        module_path, class_name = handler_class.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        handler_cls = getattr(module, class_name)

        return handler_cls(self.directory)
