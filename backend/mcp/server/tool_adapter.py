"""MCP Tool Adapter for integration with local tool registry.

This module provides adapters that allow MCP tools to be used alongside
local tools in the agent's ToolRegistry.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Tool System                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 ToolRegistry (local)                     │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │ ReadFileTool│  │  ShellTool  │  │  MCPToolAdapter │  │   │
│  │  │  (local)    │  │   (local)   │  │   (MCP wrapper) │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  │                                                          │   │
│  │  All tools implement Tool base class                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent Loop                            │   │
│  │         (uniformly handles all tool calls)               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

MCPToolAdapter wraps MCP tools to conform to the local Tool interface,
allowing seamless integration without modifying the agent loop.
"""

from typing import Any, TYPE_CHECKING, Optional
from loguru import logger

# TYPE_CHECKING avoids circular imports
if TYPE_CHECKING:
    from backend.tools.base import Tool
    from backend.mcp.manager import MCPManager
    from backend.mcp.server.tool_registry import ToolInfo


class MCPToolAdapter:
    """Adapter that wraps an MCP tool to work with the local ToolRegistry.
    
    This allows MCP tools to be registered and used alongside local tools
    without any changes to the agent loop.
    
    Example:
        registry = ToolRegistry()
        
        # Register local tool
        registry.register(ReadFileTool())
        
        # Register MCP tool (via adapter)
        mcp_tool_info = manager.tool_registry.get_tool("mcp-filesystem")
        registry.register(MCPToolAdapter(mcp_tool_info, manager))
        
        # Both can be called uniformly
        result = await registry.execute("read_file", {...})
        result = await registry.execute("mcp_read_file", {...})
    """
    
    def __init__(self, tool_info: "ToolInfo", manager: "MCPManager"):
        self._tool_info = tool_info
        self._manager = manager
        self._name = f"mcp_{tool_info.name}"
    
    @property
    def name(self) -> str:
        """Tool name with mcp_ prefix to avoid conflicts."""
        return self._name
    
    @property
    def description(self) -> str:
        """Tool description from MCP config."""
        return self._tool_info.config.description or f"MCP tool: {self._tool_info.name}"
    
    @property
    def parameters(self) -> dict[str, Any]:
        """Tool parameters schema from MCP config."""
        return self._tool_info.config.parameters or {
            "type": "object",
            "properties": {},
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the MCP tool.
        
        This method is called by ToolRegistry.execute() when the LLM
        decides to use this tool.
        
        Args:
            **kwargs: Tool parameters from LLM.
        
        Returns:
            Tool execution result as string.
        """
        try:
            # Call through MCP manager
            result = await self._manager.call_tool(
                tool_name=self._tool_info.name,
                params=kwargs,
            )
            
            # Format result as string for Tool interface
            if isinstance(result, dict):
                import json
                return json.dumps(result, ensure_ascii=False)
            elif isinstance(result, str):
                return result
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"MCP tool execution error for '{self._tool_info.name}': {e}")
            return f"Error: {str(e)}"


class MCPAdapterFactory:
    """Factory for creating MCP tool adapters.
    
    Simplifies the process of registering all enabled MCP tools
    with the local ToolRegistry.
    
    Example:
        factory = MCPAdapterFactory(manager)
        factory.register_all(registry)
    """
    
    def __init__(self, manager: "MCPManager"):
        self._manager = manager
    
    def create_adapter(self, tool_name: str) -> MCPToolAdapter | None:
        """Create an adapter for a specific MCP tool.
        
        Args:
            tool_name: Name of the MCP tool.
        
        Returns:
            MCPToolAdapter instance or None if tool not found/enabled.
        """
        tool_info = self._manager.tool_registry.get_tool(tool_name)
        if not tool_info:
            return None
        
        if not self._manager.tool_registry.is_tool_enabled(tool_name):
            return None
        
        return MCPToolAdapter(tool_info, self._manager)
    
    def create_all_adapters(self) -> list[MCPToolAdapter]:
        """Create adapters for all enabled MCP tools.
        
        Returns:
            List of MCPToolAdapter instances.
        """
        adapters = []
        for tool_info in self._manager.tool_registry.get_enabled_tools():
            adapter = MCPToolAdapter(tool_info, self._manager)
            adapters.append(adapter)
        return adapters
    
    def register_all(self, registry) -> int:
        """Register all enabled MCP tools with a ToolRegistry.
        
        Args:
            registry: ToolRegistry instance to register with.
        
        Returns:
            Number of tools registered.
        """
        count = 0
        for adapter in self.create_all_adapters():
            registry.register(adapter)
            count += 1
            logger.info(f"Registered MCP tool adapter: {adapter.name}")
        return count
    
    def unregister_all(self, registry) -> int:
        """Unregister all MCP tools from a ToolRegistry.
        
        Args:
            registry: ToolRegistry instance to unregister from.
        
        Returns:
            Number of tools unregistered.
        """
        count = 0
        for tool_info in self._manager.tool_registry.list_tools():
            adapter_name = f"mcp_{tool_info.name}"
            if registry.has(adapter_name):
                registry.unregister(adapter_name)
                count += 1
                logger.info(f"Unregistered MCP tool adapter: {adapter_name}")
        return count


class HybridToolRegistry:
    """Hybrid registry that combines local and MCP tools.
    
    This is a convenience wrapper that manages both local tools
    and MCP tools in a unified interface.
    
    Example:
        registry = HybridToolRegistry()
        
        # Register local tools
        registry.register_local(ReadFileTool())
        registry.register_local(ShellTool())
        
        # Initialize MCP (auto-registers MCP tools)
        await registry.initialize_mcp()
        
        # Use uniformly
        definitions = registry.get_definitions()  # Both local + MCP
        result = await registry.execute("read_file", {...})
        result = await registry.execute("mcp_read_file", {...})
    """
    
    def __init__(self, manager: Optional["MCPManager"] = None):
        from backend.tools.registry import ToolRegistry
        
        self._local_registry = ToolRegistry()
        self._mcp_manager = manager
        self._mcp_factory: Optional[MCPAdapterFactory] = None
        
        if manager:
            self._mcp_factory = MCPAdapterFactory(manager)
    
    def register_local(self, tool) -> None:
        """Register a local tool."""
        self._local_registry.register(tool)
    
    def unregister_local(self, name: str) -> None:
        """Unregister a local tool."""
        self._local_registry.unregister(name)
    
    async def initialize_mcp(self, manager: Optional["MCPManager"] = None) -> int:
        """Initialize MCP and register all MCP tools.
        
        Args:
            manager: Optional MCPManager instance.
        
        Returns:
            Number of MCP tools registered.
        """
        if manager:
            self._mcp_manager = manager
            self._mcp_factory = MCPAdapterFactory(manager)
        
        if not self._mcp_factory:
            raise RuntimeError("MCP manager not provided")
        
        return self._mcp_factory.register_all(self._local_registry)
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions (local + MCP)."""
        return self._local_registry.get_definitions()
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool by name (local or MCP)."""
        return await self._local_registry.execute(name, params)
    
    def has(self, name: str) -> bool:
        """Check if a tool exists (local or MCP)."""
        return self._local_registry.has(name)
    
    @property
    def tool_names(self) -> list[str]:
        """Get all tool names (local + MCP)."""
        return self._local_registry.tool_names
    
    def refresh_mcp_tools(self) -> int:
        """Refresh MCP tools (re-register if changed).
        
        Returns:
            Number of MCP tools currently registered.
        """
        if not self._mcp_factory:
            return 0
        
        # Unregister all MCP tools
        self._mcp_factory.unregister_all(self._local_registry)
        
        # Re-register
        return self._mcp_factory.register_all(self._local_registry)


# Convenience function for agent loop integration
def create_hybrid_registry(
    local_tools: Optional[list] = None,
    mcp_manager: Optional["MCPManager"] = None,
) -> HybridToolRegistry:
    """Create a hybrid registry with optional local and MCP tools.
    
    Example:
        registry = create_hybrid_registry(
            local_tools=[ReadFileTool(), ShellTool()],
            mcp_manager=mcp_manager,
        )
        
        # Get all tool definitions for LLM
        tool_definitions = registry.get_definitions()
    
    Args:
        local_tools: Optional list of local tools to register.
        mcp_manager: Optional MCPManager for MCP tools.
    
    Returns:
        Configured HybridToolRegistry.
    """
    registry = HybridToolRegistry(mcp_manager)
    
    if local_tools:
        for tool in local_tools:
            registry.register_local(tool)
    
    return registry
