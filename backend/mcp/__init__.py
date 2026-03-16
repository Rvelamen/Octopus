"""MCP (Model Control Protocol) module for backend.

This module provides MCP integration capabilities, including:
- Configuration management
- Connection lifecycle management
- Tool management
- LLM integration (via bridge)
- State management
- Database persistence

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                      MCP Module                             │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Config    │  │ Connection  │  │   Tool Registry     │ │
│  │  (config.py)│  │(connection. │  │ (tool_registry.py)  │ │
│  └─────────────┘  │    py)      │  └─────────────────────┘ │
│                   └─────────────┘                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Manager   │  │   Security  │  │   LLM Bridge        │ │
│  │ (manager.py)│  │ (security.  │  │  (llm_bridge.py)    │ │
│  └─────────────┘  │    py)      │  └─────────────────────┘ │
│                   └─────────────┘                           │
│  ┌─────────────┐                                            │
│  │  Database   │  ← SQLite persistence                      │
│  │(database.py)│                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘

Note: MCP API is integrated into Desktop WebSocket channel.
- Use desktop WS messages (mcp_get_status, mcp_get_servers, etc.)
- Real-time state updates via mcp_state_change events

Note: This module does NOT replace provider.py.
- provider.py: Handles LLM API calls (OpenAI, Anthropic)
- llm_bridge.py: Adapts MCP tools to agent's tool system
"""

from backend.mcp.manager import MCPManager, get_mcp_manager
from backend.mcp.config import MCPConfig, MCPServerConfig, MCPToolConfig
from backend.mcp.server.connection import MCPConnection, ConnectionState
from backend.mcp.server.tool_registry import MCPToolRegistry, ToolState
from backend.mcp.server.security import MCPPermissionManager
from backend.mcp.llm_bridge import MCPToolBridge, MCPBridgeIntegration, get_mcp_bridge
from backend.mcp.server.tool_adapter import (
    MCPToolAdapter,
    MCPAdapterFactory,
    HybridToolRegistry,
    create_hybrid_registry,
)
from backend.data.mcp_store import MCPRepository, MCPServerRecord, MCPToolRecord, MCPToolStats

__all__ = [
    # Core components
    "MCPManager",
    "get_mcp_manager",
    "MCPConfig",
    "MCPServerConfig",
    "MCPToolConfig",
    "MCPConnection",
    "ConnectionState",
    "MCPToolRegistry",
    "ToolState",
    "MCPPermissionManager",
    # Database
    "MCPRepository",
    "MCPServerRecord",
    "MCPToolRecord",
    "MCPToolStats",
    # LLM Bridge (tool adapter, not LLM provider)
    "MCPToolBridge",
    "MCPBridgeIntegration",
    "get_mcp_bridge",
    # Tool Adapter (for local tool registry integration)
    "MCPToolAdapter",
    "MCPAdapterFactory",
    "HybridToolRegistry",
    "create_hybrid_registry",
]