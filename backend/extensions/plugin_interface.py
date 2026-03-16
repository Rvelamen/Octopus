"""Plugin interface - similar to ChannelInterface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class PluginResult:
    """Result of a plugin action execution."""
    success: bool
    data: Any = None
    error: str = None


class PluginInterface(ABC):
    """
    Plugin interface - symmetric design with ChannelInterface.
    
    Each plugin implements this interface to expose its capabilities.
    """
    
    name: str = "base"
    version: str = "1.0.0"
    description: str = ""
    
    @property
    def actions(self) -> list[str]:
        """
        Return list of supported action names.
        
        These actions can be invoked via the plugin tool.
        Example: ["weather_query", "forecast_get", "city_search"]
        """
        return []
    
    @property
    def capabilities(self) -> list[str]:
        """
        Return list of high-level capabilities this plugin provides.
        
        Used for skill matching and auto-discovery.
        Example: ["weather", "forecast", "location"]
        """
        return []
    
    async def execute(self, action: str, **kwargs: Any) -> PluginResult:
        """
        Execute an action on this plugin.
        
        Args:
            action: The action name to execute
            **kwargs: Action-specific parameters
            
        Returns:
            PluginResult with success status and data/error
        """
        method_name = f"action_{action}"
        method = getattr(self, method_name, None)
        
        if not method:
            return PluginResult(
                success=False,
                error=f"Action '{action}' not supported by plugin '{self.name}'. "
                      f"Supported: {', '.join(self.actions)}"
            )
        
        try:
            result = await method(**kwargs)
            if isinstance(result, PluginResult):
                return result
            return PluginResult(success=True, data=result)
        except Exception as e:
            return PluginResult(success=False, error=str(e))
    
    async def action_help(self, **kwargs) -> PluginResult:
        """Return plugin help information."""
        return PluginResult(
            success=True,
            data={
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "actions": self.actions,
                "capabilities": self.capabilities,
            }
        )
