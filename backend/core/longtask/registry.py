"""Registry for long-running task plugins."""

from pathlib import Path
from typing import Any

from loguru import logger


class LongTaskRegistry:
    """Registry for managing long-running task plugins.

    This registry keeps track of all available longtask plugins and their
    worker classes. It works with the Extension system to discover and
    load plugins dynamically.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._plugins: dict[str, dict] = {}  # task_type -> plugin info
        self._initialized = True

        logger.info("[LongTaskRegistry] Initialized")

    def register(self, task_type: str, worker_class: str, plugin_name: str, extension_path: Path):
        """Register a longtask plugin.

        Args:
            task_type: Unique task type identifier (e.g., "claude_code")
            worker_class: Full Python path to worker class
            plugin_name: Plugin name
            extension_path: Path to extension directory
        """
        self._plugins[task_type] = {
            "worker_class": worker_class,
            "plugin_name": plugin_name,
            "extension_path": str(extension_path),
        }
        logger.info(f"[LongTaskRegistry] Registered plugin '{plugin_name}' for task type '{task_type}'")

    def unregister(self, task_type: str):
        """Unregister a plugin."""
        if task_type in self._plugins:
            del self._plugins[task_type]
            logger.info(f"[LongTaskRegistry] Unregistered task type '{task_type}'")

    def get(self, task_type: str) -> dict | None:
        """Get plugin info for task type."""
        return self._plugins.get(task_type)

    def list_all(self) -> list[dict]:
        """List all registered plugins."""
        return [
            {"task_type": k, **v}
            for k, v in self._plugins.items()
        ]

    def discover_from_extensions(self):
        """Discover longtask plugins from extensions."""
        from backend.extensions.registry import get_registry

        registry = get_registry()
        count = 0

        for ext in registry.list_all():
            if ext.type == "longtask":
                longtask_config = ext.manifest.get("longtask", {})
                task_type = longtask_config.get("task_type")
                worker_class = longtask_config.get("worker_class")

                if task_type and worker_class:
                    self.register(
                        task_type=task_type,
                        worker_class=worker_class,
                        plugin_name=ext.name,
                        extension_path=ext.directory,
                    )
                    count += 1

        logger.info(f"[LongTaskRegistry] Discovered {count} longtask plugins")
        return count


# Global instance
_registry: LongTaskRegistry | None = None


def get_longtask_registry() -> LongTaskRegistry:
    """Get the global LongTaskRegistry instance."""
    global _registry
    if _registry is None:
        _registry = LongTaskRegistry()
    return _registry
