"""Tool registry for dynamic tool management."""

from typing import Any

from backend.tools.base import Tool


class ToolRegistry:
    """
    Registry for agent tools.
    
    Allows dynamic registration and execution of tools.
    Includes support for MCP tools.
    """
    
    def __init__(self, mcp_bridge=None):
        self._tools: dict[str, Tool] = {}
        self._mcp_bridge = mcp_bridge
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        if name in self._tools:
            return True
        if self._mcp_bridge and name.startswith("mcp_"):
            return True
        return False
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        tools = [tool.to_schema() for tool in self._tools.values()]
        
        if self._mcp_bridge:
            mcp_tools = self._mcp_bridge.get_tool_definitions()
            tools.extend(mcp_tools)
        
        return tools
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.
        
        Args:
            name: Tool name.
            params: Tool parameters.
        
        Returns:
            Tool execution result as string.
        
        Raises:
            KeyError: If tool not found.
        """
        if self._mcp_bridge and name.startswith("mcp_"):
            import uuid
            try:
                result = await self._mcp_bridge.execute_tool(
                    tool_call_id=str(uuid.uuid4()),
                    tool_name=name,
                    arguments=params
                )
                return str(result.get("content", result))
            except Exception as e:
                return f"Error executing MCP tool {name}: {str(e)}"
        
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        try:
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        names = list(self._tools.keys())
        if self._mcp_bridge:
            mcp_tools = self._mcp_bridge.get_tool_definitions()
            names.extend([t["function"]["name"] for t in mcp_tools])
        return names
    
    def __len__(self) -> int:
        count = len(self._tools)
        if self._mcp_bridge:
            count += len(self._mcp_bridge.get_tool_definitions())
        return count
    
    def __contains__(self, name: str) -> bool:
        return self.has(name)
