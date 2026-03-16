# MCP (Model Control Protocol) Integration

This module provides comprehensive MCP integration for octopus, enabling seamless connection to MCP servers, tool management, and integration with the agent's tool system.

## Important Clarification

**This module does NOT replace `provider.py`.** They serve completely different purposes:

| Module | Purpose | Direction |
|--------|---------|-----------|
| `provider.py` | LLM API client (OpenAI, Anthropic) | Agent → LLM |
| `api.py` | Frontend management API | Frontend → Agent |
| `llm_bridge.py` | MCP tool adapter | Agent Tool System ↔ MCP Server |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              octopus                                    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         MCP Module                               │   │
│  │                                                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   Config    │  │ Connection  │  │     Tool Registry       │  │   │
│  │  │  (config)   │  │(connection) │  │   (tool_registry)       │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  │                                                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   Manager   │  │   Security  │  │     LLM Bridge          │  │   │
│  │  │  (manager)  │  │  (security) │  │    (llm_bridge)         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  │                                                                  │   │
│  │  ┌─────────────┐                                                │   │
│  │  │     API     │  ← Frontend interface (WebSocket/REST)         │   │
│  │  │   (api)     │                                                │   │
│  │  └─────────────┘                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Other Modules                               │   │
│  │                                                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   Agent     │  │  Provider   │  │       Frontend          │  │   │
│  │  │   (loop)    │  │ (provider)  │  │      (React UI)         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. LLM Tool Call Flow:
   
   Agent Loop → provider.py → LLM API
        ↓
   LLM returns tool_call (mcp_*)
        ↓
   Agent Loop → llm_bridge.py → MCP Manager → MCP Server
        ↓
   Result returned to Agent Loop → provider.py (as tool response)

2. Frontend Management Flow:
   
   Frontend → api.py (WebSocket/REST) → MCP Manager
        ↓
   State changes broadcast to all connected frontends
```

## Module Descriptions

### 1. Configuration Management (`config.py`)
- Supports `self.config.mcp.xxx` access pattern
- JSON-based configuration with Pydantic validation
- Automatic fallback to defaults
- Environment variable support

```python
from backend.mcp.config import MCPConfig, MCPServerConfig, MCPToolConfig

# Create configuration
config = MCPConfig(
    enabled=True,
    servers={
        "my-server": MCPServerConfig(
            name="my-server",
            url="ws://localhost:8080",
            protocol="websocket",
        )
    },
    tools={
        "my-tool": MCPToolConfig(
            name="my-tool",
            description="A useful tool",
            enabled=True,
        )
    }
)

# Access via config
config.get_server("my-server")
config.get_tool("my-tool")
```

### 2. Connection Management (`connection.py`)
- Full lifecycle management (connect, maintain, disconnect)
- Auto-reconnection with exponential backoff
- Heartbeat monitoring
- Multiple protocol support (stdio, SSE, WebSocket)
- Connection pooling

```python
from backend.mcp.connection import MCPConnection

# Create connection
connection = MCPConnection(
    config=server_config,
    on_state_change=on_state_change_callback,
)

# Connect
await connection.connect()

# Make request
response = await connection.request("tools/list", {})

# Disconnect
await connection.disconnect()
```

### 3. Tool Management (`tool_registry.py`)
- Enable/disable tools
- Dependency resolution
- Tool lifecycle management
- Conflict detection

```python
from backend.mcp.tool_registry import MCPToolRegistry

registry = MCPToolRegistry()

# Register tool
await registry.register_tool(tool_config)

# Enable/disable
await registry.enable_tool("my-tool")
await registry.disable_tool("my-tool")

# Check dependencies
conflicts = registry.check_dependency_conflicts("my-tool")
```

### 4. Security (`security.py`)
- Token-based authentication
- Permission levels (NONE, READ, WRITE, ADMIN)
- Rate limiting
- Origin validation
- Request size limits
- Data encryption support

```python
from backend.mcp.security import MCPPermissionManager, PermissionLevel

security = MCPPermissionManager(config)

# Generate token
token = security.generate_token(PermissionLevel.READ)

# Validate
access_token = security.validate_token(token)

# Check permission
has_access = security.check_permission(token, PermissionLevel.WRITE)

# Rate limiting
allowed, info = security.check_rate_limit("client-id")
```

### 5. MCP Manager (`manager.py`)
Central coordination component (Singleton).

```python
from backend.mcp.manager import MCPManager, get_mcp_manager

# Get manager instance
manager = await get_mcp_manager()

# Check status
status = manager.get_status()

# Call tool
result = await manager.call_tool("my-tool", {"arg": "value"})

# Register state callback
manager.register_state_callback(on_state_change)
```

### 6. LLM Bridge (`llm_bridge.py`)
**IMPORTANT**: This is a tool adapter, NOT an LLM provider.

It adapts MCP tools to the format expected by the agent's tool registry.

```python
from backend.mcp.llm_bridge import MCPBridgeIntegration

# In agent loop
mcp_bridge = MCPBridgeIntegration()

# Get tool definitions for LLM
mcp_tools = mcp_bridge.get_tool_definitions()
# Returns: [{"type": "function", "function": {"name": "mcp_toolname", ...}}]

# These are passed to provider.py along with other tools

# When LLM calls an MCP tool:
result = await mcp_bridge.execute_tool(
    tool_call_id="call-1",
    tool_name="mcp_my-tool",  # LLM sees this name
    arguments={"arg": "value"}
)
# Returns formatted result for provider.py
```

### 7. Tool Adapter (`tool_adapter.py`)
**For integrating MCP tools with local ToolRegistry.**

This module allows MCP tools to be used **alongside local tools** in a unified way:

```python
from backend.mcp.tool_adapter import (
    MCPToolAdapter,
    MCPAdapterFactory,
    HybridToolRegistry,
    create_hybrid_registry,
)
from backend.agent.tools.filesystem import ReadFileTool
from backend.agent.tools.shell import ShellTool

# Method 1: Use HybridToolRegistry (Recommended)
registry = create_hybrid_registry(
    local_tools=[ReadFileTool(), ShellTool()],
    mcp_manager=mcp_manager,
)

# Get all tool definitions (local + MCP)
tool_definitions = registry.get_definitions()

# Execute any tool uniformly
result = await registry.execute("read_file", {"path": "/tmp/test.txt"})
result = await registry.execute("mcp_read_file", {"path": "/tmp/test.txt"})

# Method 2: Manual registration with existing registry
from backend.agent.tools.registry import ToolRegistry

registry = ToolRegistry()

# Register local tools
registry.register(ReadFileTool())
registry.register(ShellTool())

# Register MCP tools via adapter
factory = MCPAdapterFactory(mcp_manager)
factory.register_all(registry)

# All tools now available in registry
print(registry.tool_names)  # ["read_file", "shell", "mcp_read_file", "mcp_write_file", ...]
```

**Key Features:**
- `MCPToolAdapter`: Wraps MCP tools to conform to local `Tool` interface
- `MCPAdapterFactory`: Bulk creates and registers MCP tool adapters
- `HybridToolRegistry`: Unified registry for both local and MCP tools
- `create_hybrid_registry`: Convenience function for quick setup

### 8. API (`api.py`)
Frontend management interface (WebSocket + REST).

**WebSocket Endpoint:**
- `ws://host/ws/mcp` - Real-time MCP communication

**REST Endpoints:**
- `GET /api/mcp/status` - Get MCP status
- `GET /api/mcp/config` - Get configuration
- `POST /api/mcp/config` - Update configuration
- `GET /api/mcp/tools` - List tools
- `POST /api/mcp/tools/{name}/enable` - Enable tool
- `POST /api/mcp/tools/{name}/disable` - Disable tool
- `GET /api/mcp/connections` - List connections
- `POST /api/mcp/connections/{name}/connect` - Connect to server
- `POST /api/mcp/connections/{name}/disconnect` - Disconnect from server

## Configuration File Format

```json
{
  "enabled": true,
  "servers": {
    "filesystem": {
      "name": "filesystem",
      "url": "stdio",
      "protocol": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
      "enabled": true,
      "autoConnect": true
    },
    "remote-server": {
      "name": "remote-server",
      "url": "wss://example.com/mcp",
      "protocol": "websocket",
      "authToken": "your-token",
      "enabled": true
    }
  },
  "tools": {
    "read-file": {
      "name": "read-file",
      "description": "Read file contents",
      "enabled": true,
      "timeout": 30
    }
  },
  "security": {
    "enabled": true,
    "requireAuth": true,
    "encryptionEnabled": true,
    "rateLimitRequests": 100,
    "rateLimitWindow": 60
  }
}
```

## Integration with Agent Loop

### Method 1: Using HybridToolRegistry (Recommended)

This is the cleanest approach - use `HybridToolRegistry` to manage both local and MCP tools uniformly:

```python
from backend.agent.loop import AgentLoop
from backend.mcp.tool_adapter import create_hybrid_registry
from backend.agent.tools.filesystem import ReadFileTool
from backend.agent.tools.shell import ShellTool

class AgentLoopWithMCP(AgentLoop):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Create hybrid registry with both local and MCP tools
        self.tools = create_hybrid_registry(
            local_tools=[ReadFileTool(), ShellTool()],
            mcp_manager=self.config.mcp,  # or get_mcp_manager()
        )
    
    async def _handle_tool_call(self, tool_call):
        # All tools (local + MCP) are handled uniformly
        return await self.tools.execute(
            tool_call.name,
            tool_call.arguments
        )
```

### Method 2: Using MCPBridgeIntegration

Use this if you need more control over how MCP tools are integrated:

```python
from backend.agent.loop import AgentLoop
from backend.mcp.llm_bridge import MCPBridgeIntegration

class AgentLoopWithMCP(AgentLoop):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp_bridge = MCPBridgeIntegration()
    
    def _register_tools(self):
        # Register native tools
        super()._register_default_tools()
        
        # Register MCP tools through bridge
        mcp_tools = self.mcp_bridge.get_tool_definitions()
        for tool_def in mcp_tools:
            self.tools.register(MCPToolAdapter(tool_def))
    
    async def _handle_tool_call(self, tool_call):
        # Check if this is an MCP tool
        if self.mcp_bridge.is_mcp_tool(tool_call.name):
            return await self.mcp_bridge.execute_tool(
                tool_call.id,
                tool_call.name,
                tool_call.arguments
            )
        else:
            # Handle native tools
            return await super()._handle_tool_call(tool_call)
```

## Testing

```bash
# Run tests
pytest tests/test_mcp.py -v

# Run with coverage
pytest tests/test_mcp.py --cov=backend.mcp --cov-report=html
```

## Performance Considerations

1. **Connection Pooling**: Connections are pooled for reuse
2. **Async Operations**: All I/O is non-blocking
3. **Rate Limiting**: Built-in rate limiting prevents overload
4. **Lazy Loading**: Tools are loaded on-demand
5. **Metrics**: Performance metrics collected for monitoring

## Security Best Practices

1. Always enable authentication in production
2. Use HTTPS/WSS for remote connections
3. Set appropriate permission levels
4. Enable rate limiting
5. Regular token rotation
6. Monitor usage patterns

## Troubleshooting

### Connection Issues
- Check server URL and protocol
- Verify network connectivity
- Check authentication tokens
- Review connection logs

### Tool Execution Failures
- Verify tool is enabled
- Check tool dependencies
- Review tool configuration
- Check permission levels

### Performance Issues
- Monitor connection pool usage
- Check rate limiting status
- Review metrics for bottlenecks
- Adjust timeout values

## FAQ

**Q: Does this replace provider.py?**
A: No. provider.py handles LLM API calls. This module provides MCP server connectivity and tool management.

**Q: Why do we need api.py?**
A: api.py provides the frontend management interface (WebSocket/REST) for users to configure and monitor MCP connections. provider.py is for backend LLM communication.

**Q: What's the difference between llm_bridge.py and provider.py?**
A: 
- provider.py: Calls LLM APIs (OpenAI, Anthropic) - "How to talk to AI"
- llm_bridge.py: Adapts MCP tools to agent's tool format - "How to expose external tools to AI"

**Q: Can I use MCP without the frontend?**
A: Yes. The core functionality (manager, connection, tools) works independently. api.py is only needed if you want the web UI for management.

**Q: How do local tools and MCP tools work together?**
A: Use `tool_adapter.py` which provides `HybridToolRegistry` or `MCPToolAdapter`:

```python
from backend.mcp.tool_adapter import create_hybrid_registry

# Create unified registry
registry = create_hybrid_registry(
    local_tools=[ReadFileTool(), ShellTool()],
    mcp_manager=mcp_manager,
)

# Both local and MCP tools are now in the same registry
# and can be called uniformly
result = await registry.execute("read_file", {...})  # local
result = await registry.execute("mcp_read_file", {...})  # MCP
```

**Q: What's the difference between llm_bridge.py and tool_adapter.py?**
A:
- `llm_bridge.py`: Low-level bridge for direct LLM tool call handling
- `tool_adapter.py`: Higher-level adapter that wraps MCP tools to conform to local `Tool` interface, enabling unified registry with local tools

**Q: Which integration method should I use?**
A:
- **For new projects**: Use `HybridToolRegistry` from `tool_adapter.py` - it's the cleanest approach
- **For existing projects with custom tool handling**: Use `MCPBridgeIntegration` from `llm_bridge.py`
- **For maximum control**: Use `MCPAdapterFactory` to manually register MCP tools with your existing registry