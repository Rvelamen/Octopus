"""Unified action tool for plugin and channel operations."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from backend.tools.base import Tool
from backend.extensions.registry import get_registry
from backend.channels.registry import ChannelRegistry


class ActionTool(Tool):
    """
    Unified action tool for plugin operations.

    This single tool replaces multiple plugin-specific tools,
    avoiding tool explosion while providing access to all capabilities.

    Usage:
        action(type="plugin", action="weather_query", name="weather", city="北京")
    """

    def __init__(self):
        self._extension_registry = get_registry()
        self._channel_registry = ChannelRegistry

    @property
    def name(self) -> str:
        return "action"

    @property
    def description(self) -> str:
        return """Unified action tool for plugin operations.

## [Critical] IMPORTANT: Must Read Skill Documentation Before Calling

**[Critical] You MUST read the SKILL.md documentation for the corresponding plugin before calling this tool**, otherwise the call will fail.

### How to Get Skill Documentation

1. Use `read_file` tool to read `workspace/extensions/<name>/SKILL.md`
2. Example: Read `workspace/extensions/weather/SKILL.md` to understand available actions and parameters for the weather plugin

### Why Reading Skill Documentation is [Critical]

- Understand the specific actions supported by the plugin
- Master the parameters required for each action and their types
- Understand the correct format and value range of parameters
- Avoid call failures due to errors

## Parameters

- **type** (required): Must be "plugin"
- **action** (required): The action to execute (e.g., "search", "query") - **[Critical] MUST obtain from SKILL.md first**
- **name** (required): The plugin name (e.g., "search_aggregator", "weather")

## [Critical] Correct Calling Process

1. **[Critical] Step 1**: Use `read_file` to read `workspace/extensions/<name>/SKILL.md`
2. **[Critical] Step 2**: Understand the available actions and parameters described in the documentation
3. **[Critical] Step 3**: Call this tool according to the documentation

## Example

**[Critical] Read documentation first:**
```
read_file: workspace/extensions/search_aggregator/SKILL.md
```

**Then call according to documentation:**
```json
{
  "type": "plugin",
  "action": "search",
  "name": "search_aggregator",
  "query": "AI safety",
  "engines": "bing,baidu"
}
```

## [Critical] Warning

**[Critical] Calling this tool directly without reading SKILL.md will result in call failure or parameter errors!**

"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["plugin"],
                    "description": "Must be 'plugin'"
                },
                "action": {
                    "type": "string",
                    "description": "The action to execute. Read SKILL.md for available actions"
                },
                "name": {
                    "type": "string",
                    "description": "The plugin name (e.g., 'search_aggregator', 'weather', 'pdf_plugin')"
                }
            },
            "required": ["type", "action", "name"],
            "additionalProperties": True
        }

    async def execute(
        self,
        type: str,
        action: str,
        name: str | None = None,
        **kwargs
    ) -> str:
        """Execute unified action based on type."""

        if type == "plugin":
            return await self._execute_plugin(action, name, **kwargs)
        else:
            available = ", ".join(["plugin", "channel"])
            return f"Error: Unknown type '{type}'. Available: {available}"

    async def _execute_plugin(self, action: str, name: str | None, **kwargs) -> str:
        """Execute plugin action."""
        if not name:
            available = ", ".join([p.name for p in self._extension_registry.list_plugins()])
            return f"Error: plugin name is required. Available plugins: {available or 'none'}"

        # Extract channel, chat_id, and session_instance_id from injected parameters
        channel = kwargs.pop("_channel", "desktop")
        chat_id = kwargs.pop("_chat_id", "default")
        session_instance_id = kwargs.pop("_session_instance_id", None)

        # Try to get plugin from extension registry
        ext = self._extension_registry.get_plugin(name)
        handler = None

        # If not found, try to find by normalized name (replace hyphens with underscores and vice versa)
        if not ext:
            normalized_name = name.replace("-", "_")
            if normalized_name != name:
                ext = self._extension_registry.get_plugin(normalized_name)
            if not ext:
                normalized_name = name.replace("_", "-")
                if normalized_name != name:
                    ext = self._extension_registry.get_plugin(normalized_name)

        if ext and hasattr(ext, 'create_handler'):
            try:
                handler = ext.create_handler()
                if handler and hasattr(handler, 'load'):
                    await handler.load()
            except Exception as e:
                logger.warning(f"Failed to create handler for plugin {name}: {e}")

        # Fallback: Check legacy plugin loader
        if not handler:
            handler = self._get_plugin_handler(name)

        if not handler:
            available = ", ".join([p.name for p in self._extension_registry.list_plugins()])
            return f"Error: Plugin '{name}' not found. Available: {available or 'none'}"

        # Note: _load_plugin_env() and _check_required_config() are already called in handler.load()

        if hasattr(handler, 'missing_configs') and handler.missing_configs:
            field_names = [f["name"] for f in handler.missing_configs]

            return (
                f"Plugin '{name}' requires configuration before use.\n\n"
                f"Missing required fields: {', '.join(field_names)}\n\n"
                f"Please configure these environment variables manually."
            )

        if action not in handler.actions:
            return f"Error: Action '{action}' not supported. Available: {', '.join(handler.actions)}"

        try:
            from backend.extensions.base import PluginResult
            # Pass channel, chat_id, and session_instance_id to handler
            result = await handler.execute(action, channel=channel, chat_id=chat_id, session_instance_id=session_instance_id, **kwargs)

            if result.success:
                if result.data:
                    return json.dumps(result.data, ensure_ascii=False, indent=2)
                return "Success"
            return f"Error: {result.error}"

        except Exception as e:
            return f"Error executing {action} on plugin {name}: {str(e)}"

    def _get_plugin_handler(self, name: str):
        """Get plugin handler from extension registry."""
        from backend.extensions.plugin_handler import PluginHandler
        try:
            ext = self._extension_registry.get_plugin(name)
            if ext and hasattr(ext, 'create_handler'):
                handler = ext.create_handler()
                if handler and hasattr(handler, 'load'):
                    import asyncio
                    asyncio.get_event_loop().run_until_complete(handler.load())
                return handler
        except Exception:
            pass
        return None

    async def _execute_channel(self, action: str, name: str | None, **kwargs) -> str:
        """Execute channel action."""
        if not name:
            available = ", ".join(self._channel_registry.list_available())
            return f"Error: channel name is required. Available: {available or 'none'}"

        channel = self._channel_registry.get(name)
        if not channel:
            available = ", ".join(self._channel_registry.list_available())
            return f"Error: Channel '{name}' not found. Available: {available or 'none'}"

        if action not in channel.actions:
            return f"Error: Action '{action}' not supported. Available: {', '.join(channel.actions)}"

        try:
            result = await channel.execute(action, **kwargs)

            if result.success:
                if result.data:
                    return json.dumps(result.data, ensure_ascii=False, indent=2)
                return "Success"
            return f"Error: {result.error}"

        except Exception as e:
            return f"Error executing {action} on channel {name}: {str(e)}"
