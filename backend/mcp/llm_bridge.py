"""MCP LLM Bridge module.

This module acts as a bridge between MCP tools and the Agent's LLM tool system.
It is NOT a replacement for provider.py - they serve different purposes:

- provider.py: Handles LLM API calls (OpenAI, Anthropic, etc.)
- llm_bridge.py: Adapts MCP tools to the agent's tool registry format

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                         Agent Loop                          │
│  ┌─────────────────┐      ┌─────────────────────────────┐  │
│  │  provider.py    │      │   llm_bridge.py (this file) │  │
│  │  (LLM Provider) │      │   (MCP Tool Adapter)        │  │
│  │                 │      │                             │  │
│  │ - Calls OpenAI  │      │ - Adapts MCP tools          │  │
│  │ - Calls Claude  │      │ - Provides tool schemas     │  │
│  │ - Streaming     │      │ - Handles tool execution    │  │
│  └─────────────────┘      └─────────────────────────────┘  │
│           │                            │                    │
│           ▼                            ▼                    │
│    ┌─────────────┐              ┌─────────────┐            │
│    │  LLM APIs   │              │  MCP Server │            │
│    └─────────────┘              └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
"""

import json
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from backend.mcp.manager import MCPManager


@dataclass
class MCPBridgeResult:
    """Result of an MCP tool call through the bridge."""
    tool_call_id: str
    name: str
    result: Any
    success: bool
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)


class MCPToolBridge:
    """Bridge to expose MCP tools to the Agent's tool system.
    
    This class adapts MCP tools to the format expected by the agent's
    tool registry, allowing seamless integration without modifying
    the core LLM provider.
    """
    
    def __init__(self, manager: MCPManager):
        self.manager = manager
        self._usage_stats: dict[str, dict[str, Any]] = {}
    
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get MCP tool definitions formatted for the agent's tool registry.
        
        These definitions are passed to provider.py as part of the 'tools'
        parameter in chat completion calls.
        
        Returns:
            List of tool definitions in OpenAI function format.
        """
        if not self.manager.is_enabled:
            return []
        
        tools = []
        for tool in self.manager.tool_registry.get_enabled_tools():
            params = tool.config.parameters or {
                "type": "object",
                "properties": {},
            }
            
            tool_def = {
                "type": "function",
                "function": {
                    "name": f"mcp_{tool.name}",
                    "description": tool.config.description or f"MCP tool: {tool.name}",
                    "parameters": params,
                },
            }
            tools.append(tool_def)
        
        return tools
    
    async def execute_tool(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPBridgeResult:
        """Execute an MCP tool call from the agent.
        
        This method is called by the agent loop when the LLM decides to
        use an MCP tool. It bridges the call to the MCP manager.
        
        Args:
            tool_call_id: Unique identifier for this tool call
            tool_name: Name of the MCP tool (may include 'mcp_' prefix)
            arguments: Tool arguments from the LLM
        
        Returns:
            MCPBridgeResult containing the execution result
        """
        start_time = datetime.now()
        
        # Remove mcp_ prefix if present
        if tool_name.startswith("mcp_"):
            tool_name = tool_name[4:]
        
        try:
            # Call through MCP manager
            mcp_result = await self.manager.call_tool(
                tool_name=tool_name,
                params=arguments,
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            success = "error" not in (mcp_result or {})
            
            result = MCPBridgeResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                result=mcp_result,
                success=success,
                execution_time_ms=execution_time,
            )
            
            # Update stats
            self._update_stats(tool_name, success, execution_time)
            
        except Exception as e:
            logger.error(f"MCP bridge execution error for '{tool_name}': {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = MCPBridgeResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                result={"error": str(e)},
                success=False,
                execution_time_ms=execution_time,
            )
        
        return result
    
    def _update_stats(self, tool_name: str, success: bool, execution_time_ms: float) -> None:
        """Update usage statistics."""
        if tool_name not in self._usage_stats:
            self._usage_stats[tool_name] = {
                "calls": 0,
                "successful": 0,
                "failed": 0,
                "total_time_ms": 0,
            }
        
        stats = self._usage_stats[tool_name]
        stats["calls"] += 1
        stats["successful"] += 1 if success else 0
        stats["failed"] += 0 if success else 1
        stats["total_time_ms"] += execution_time_ms
    
    def format_result_for_agent(self, result: MCPBridgeResult) -> dict[str, Any]:
        """Format bridge result for the agent's message history.
        
        Returns a tool response message in the format expected by
        OpenAI-compatible APIs.
        """
        content = result.result
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        elif not isinstance(content, str):
            content = str(content)
        
        return {
            "tool_call_id": result.tool_call_id,
            "role": "tool",
            "name": f"mcp_{result.name}",
            "content": content,
        }
    
    def get_usage_stats(self) -> dict[str, dict[str, Any]]:
        """Get usage statistics for all bridged tools."""
        return self._usage_stats.copy()


class MCPBridgeIntegration:
    """Integration helper for connecting MCP bridge to agent loop.
    
    Usage example in agent loop:
    
        class AgentLoop:
            def __init__(self):
                self.mcp_bridge = MCPBridgeIntegration()
            
            def _register_tools(self):
                # Register native tools
                self.tools.register(ReadFileTool())
                ...
                
                # Register MCP tools through bridge
                mcp_tools = self.mcp_bridge.get_tool_definitions()
                for tool_def in mcp_tools:
                    self.tools.register(MCPToolAdapter(tool_def))
            
            async def _handle_tool_call(self, tool_call):
                if tool_call.name.startswith("mcp_"):
                    result = await self.mcp_bridge.execute_tool(
                        tool_call.id,
                        tool_call.name,
                        tool_call.arguments
                    )
                    return self.mcp_bridge.format_result_for_agent(result)
    """
    
    def __init__(self, manager: MCPManager | None = None):
        if manager is None:
            manager = MCPManager()
        self.manager = manager
        self.bridge = MCPToolBridge(manager)
    
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for agent registration."""
        return self.bridge.get_tool_definitions()
    
    async def execute_tool(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute tool and return formatted result for agent."""
        result = await self.bridge.execute_tool(tool_call_id, tool_name, arguments)
        return self.bridge.format_result_for_agent(result)
    
    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool."""
        return tool_name.startswith("mcp_")


# Singleton instance for convenience
_bridge_integration: MCPBridgeIntegration | None = None


def get_mcp_bridge() -> MCPBridgeIntegration:
    """Get or create the MCP bridge integration singleton."""
    global _bridge_integration
    
    if _bridge_integration is None:
        _bridge_integration = MCPBridgeIntegration()
    
    return _bridge_integration
