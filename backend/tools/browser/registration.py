"""
Browser tool registration module.

Registers browser tools to the ToolRegistry.
"""

from typing import Any
from pathlib import Path

from loguru import logger

from backend.tools.browser.tool import BrowserTool
from backend.tools.base import Tool

# Global browser tool instance
_browser_tool: BrowserTool | None = None


def get_browser_tool() -> BrowserTool:
    """Get the global browser tool instance."""
    global _browser_tool
    if _browser_tool is None:
        _browser_tool = BrowserTool()
    return _browser_tool


class BrowserToolAdapter(Tool):
    """Adapter to make browser tools compatible with ToolRegistry."""
    
    def __init__(self, name: str, description: str, parameters: dict, browser_tool: BrowserTool):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._browser_tool = browser_tool
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters
    
    async def execute(self, **kwargs) -> str:
        """Execute the browser tool."""
        return await self._browser_tool.execute_tool(self._name, kwargs)
    
    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters (basic validation)."""
        errors = []
        # Find required parameters from schema
        required = self._parameters.get("required", [])
        for param in required:
            if param not in params:
                errors.append(f"Missing required parameter: {param}")
        return errors


def register_browser_tools(tools_registry: Any, workspace: Path | None = None) -> None:
    """Register browser tools to the ToolRegistry.
    
    Args:
        tools_registry: The ToolRegistry instance
        workspace: Workspace path (optional)
    """
    global _browser_tool
    
    if _browser_tool is None:
        _browser_tool = BrowserTool(workspace=workspace)
    
    # Register each browser tool using adapter
    tool_definitions = _browser_tool.get_tool_definitions()
    
    for tool_def in tool_definitions:
        tool_name = tool_def["function"]["name"]
        description = tool_def["function"].get("description", "")
        parameters = tool_def["function"].get("parameters", {})
        
        # Create adapter for each tool
        adapter = BrowserToolAdapter(
            name=tool_name,
            description=description,
            parameters=parameters,
            browser_tool=_browser_tool
        )
        
        tools_registry.register(adapter)
        logger.info(f"Registered browser tool: {tool_name}")
    
    logger.info(f"Registered {len(tool_definitions)} browser tools")


async def cleanup_browser_tools() -> None:
    """Cleanup all browser tools."""
    global _browser_tool
    if _browser_tool:
        await _browser_tool.cleanup_all()
        _browser_tool = None
        logger.info("Browser tools cleaned up")

