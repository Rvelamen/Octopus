"""MCP Manager - Central management component for MCP integration.

The MCP Manager is the core component that coordinates all MCP functionality:
- Connection management
- Tool registry
- Security
- State management
- Event handling
- LLM integration
- Database persistence
"""

import asyncio
import json
from typing import Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger

from backend.mcp.config import MCPConfig, MCPServerConfig, MCPToolConfig
from backend.mcp.server.connection import MCPConnection, ConnectionState
from backend.mcp.server.tool_registry import MCPToolRegistry, ToolState
from backend.mcp.server.security import MCPPermissionManager, PermissionLevel
from backend.data import Database, MCPRepository


@dataclass
class MCPState:
    """MCP system state."""
    initialized: bool = False
    connections: dict[str, ConnectionState] = field(default_factory=dict)
    tools: dict[str, ToolState] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)


@dataclass
class MCPMetrics:
    """MCP usage metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    tool_usage: dict[str, int] = field(default_factory=dict)
    connection_uptime: dict[str, float] = field(default_factory=dict)


class MCPManager:
    """Central manager for MCP functionality.
    
    This is the main entry point for MCP integration. It provides:
    - Unified configuration access (self.config.mcp.xxx)
    - Connection lifecycle management
    - Tool management
    - State monitoring
    - Event notifications
    - LLM integration interface
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one manager instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        config: MCPConfig | None = None,
        config_path: Path | str | None = None,
        db: Database | None = None,
    ):
        # Avoid re-initialization
        if hasattr(self, '_initialized'):
            return

        self._initialized = True

        # Configuration
        if config:
            self.config = config
        elif config_path:
            self.config = MCPConfig.load_from_file(config_path)
        else:
            self.config = MCPConfig()

        # Database - use unified database
        if db is None:
            db = Database()
        self.db = MCPRepository(db)

        # Components
        self.connections: dict[str, MCPConnection] = {}
        self.tool_registry = MCPToolRegistry()
        self.security = MCPPermissionManager(self.config.security)

        # State
        self.state = MCPState()
        self.metrics = MCPMetrics()
        self._running = False
        self._state_callbacks: list[Callable[[str, Any, Any], None]] = []

        # Tasks
        self._monitor_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Initialize
        # NOTE: 不在构造函数中自动初始化，避免阻塞主进程
        # 初始化应该由外部显式调用 initialize()
    
    @property
    def is_enabled(self) -> bool:
        """Check if MCP is enabled."""
        return self.config.enabled
    
    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running
    
    def register_state_callback(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Register a callback for state changes.
        
        Callback signature: callback(event_type, old_value, new_value)
        """
        self._state_callbacks.append(callback)
    
    def unregister_state_callback(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Unregister a state change callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def _notify_state_change(self, event_type: str, old_value: Any, new_value: Any) -> None:
        """Notify all registered callbacks of state change."""
        for callback in self._state_callbacks:
            try:
                callback(event_type, old_value, new_value)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    async def initialize(self) -> bool:
        """Initialize the MCP manager."""
        if not self.config.enabled:
            logger.info("MCP is disabled, skipping initialization")
            return False

        # 防止重复初始化
        if self.state.initialized:
            logger.info("MCP Manager already initialized")
            return True

        logger.info("Initializing MCP Manager...")

        try:
            # Sync config to database (在后台线程中执行，避免阻塞)
            loop = asyncio.get_event_loop()
            if self.config.servers:
                servers_config = {name: config.model_dump() for name, config in self.config.servers.items()}
                await loop.run_in_executor(
                    None,
                    lambda: self.db.sync_servers_from_config(servers_config)
                )
            if self.config.tools:
                tools_config = {name: config.model_dump() for name, config in self.config.tools.items()}
                await loop.run_in_executor(
                    None,
                    lambda: self.db.sync_tools_from_config(tools_config)
                )

            # Load servers from database (后台线程)
            db_servers = await loop.run_in_executor(None, self.db.list_servers)
            for db_server in db_servers:
                server_config = MCPServerConfig(
                    name=db_server.name,
                    url=db_server.url,
                    protocol=db_server.protocol,
                    enabled=db_server.enabled,
                    auto_connect=db_server.auto_connect,
                    **db_server.config
                )
                self.config.servers[db_server.name] = server_config

            # Load tools from database (后台线程)
            db_tools = await loop.run_in_executor(None, self.db.list_tools)
            # 并行注册工具，避免顺序阻塞
            tool_tasks = []
            for db_tool in db_tools:
                tool_config = MCPToolConfig(
                    name=db_tool.name,
                    description=db_tool.description,
                    enabled=db_tool.enabled,
                    parameters=db_tool.parameters,
                    dependencies=db_tool.dependencies,
                    **db_tool.config
                )
                self.config.tools[db_tool.name] = tool_config
                # 不立即注册，先收集任务
                tool_tasks.append(self.tool_registry.register_tool(tool_config))
            
            # 并行执行所有工具注册
            if tool_tasks:
                await asyncio.gather(*tool_tasks, return_exceptions=True)

            # Setup connection state callbacks
            def on_connection_state_change(conn, old_state, new_state):
                self.state.connections[conn.name] = new_state
                self.state.last_updated = datetime.now()
                self._notify_state_change(
                    f"connection.{conn.name}",
                    old_state.name,
                    new_state.name
                )

            # Initialize connections (使用 gather 并行连接，带超时)
            connection_tasks = []
            for server_name, server_config in self.config.servers.items():
                if server_config.enabled and server_config.auto_connect:
                    task = self._connect_server_with_timeout(
                        server_name, server_config, on_connection_state_change
                    )
                    connection_tasks.append(task)

            if connection_tasks:
                await asyncio.gather(*connection_tasks, return_exceptions=True)

            # Setup tool state callbacks
            def on_tool_state_change(tool_name, old_state, new_state):
                self.state.tools[tool_name] = new_state
                self.state.last_updated = datetime.now()
                self._notify_state_change(
                    f"tool.{tool_name}",
                    old_state.name,
                    new_state.name
                )
                is_enabled = new_state in (ToolState.ENABLED, ToolState.LOADED)
                self.db.set_tool_enabled(tool_name, is_enabled)

            self.tool_registry.register_state_callback(on_tool_state_change)

            # Start background tasks
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self.state.initialized = True
            logger.info("MCP Manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}")
            self.state.errors.append(str(e))
            return False

    async def _connect_server_with_timeout(
        self,
        server_name: str,
        server_config: MCPServerConfig,
        on_state_change
    ) -> None:
        """Connect to a server with timeout to avoid blocking."""
        try:
            connection = await asyncio.wait_for(
                self.create_connection(server_config, on_state_change),
                timeout=10.0  # 10秒超时
            )
            if connection and connection.is_available:
                asyncio.create_task(self._auto_discover_tools(server_name))
        except asyncio.TimeoutError:
            logger.warning(f"Connection to server '{server_name}' timed out")
        except Exception as e:
            logger.error(f"Failed to connect to server '{server_name}': {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the MCP manager."""
        logger.info("Shutting down MCP Manager...")
        
        self._running = False
        
        # Cancel background tasks
        if self._monitor_task:
            self._monitor_task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Disconnect all connections
        for conn in list(self.connections.values()):
            await conn.disconnect()
        
        self.connections.clear()
        
        # Disable all tools
        await self.tool_registry.disable_all_tools()
        
        self.state.initialized = False
        logger.info("MCP Manager shutdown complete")
    
    async def create_connection(
        self,
        config: MCPServerConfig,
        on_state_change: Callable | None = None,
        on_message: Callable | None = None,
    ) -> MCPConnection | None:
        """Create a new MCP connection."""
        if not self.config.enabled:
            logger.warning("MCP is disabled, cannot create connection")
            return None
        
        # Check connection limit
        if len(self.connections) >= self.config.max_concurrent_connections:
            logger.error(f"Max concurrent connections reached ({self.config.max_concurrent_connections})")
            return None
        
        # Create connection
        connection = MCPConnection(
            config=config,
            on_state_change=on_state_change,
            on_message=on_message or self._handle_connection_message,
        )
        
        self.connections[config.name] = connection
        
        # Connect
        if await connection.connect():
            logger.info(f"Created MCP connection: {config.name}")
            return connection
        else:
            logger.error(f"Failed to create MCP connection: {config.name}")
            del self.connections[config.name]
            return None
    
    async def remove_connection(self, name: str) -> bool:
        """Remove an MCP connection."""
        connection = self.connections.get(name)
        if not connection:
            return False
        
        await connection.disconnect()
        del self.connections[name]
        logger.info(f"Removed MCP connection: {name}")
        return True
    
    def get_connection(self, name: str) -> MCPConnection | None:
        """Get a connection by name."""
        return self.connections.get(name)
    
    def get_connection_status(self, name: str) -> dict[str, Any] | None:
        """Get connection status."""
        connection = self.connections.get(name)
        if not connection:
            return None
        return connection.get_info()
    
    def get_all_connections_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all connections."""
        return {name: conn.get_info() for name, conn in self.connections.items()}
    
    async def call_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        connection_name: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        """Call an MCP tool.

        This is the main interface for LLM to use MCP tools.
        """
        if not self.config.enabled:
            return {"error": "MCP is disabled"}

        # Check if tool is available
        if not self.tool_registry.is_tool_available(tool_name):
            return {"error": f"Tool '{tool_name}' is not available"}

        # Record tool usage in registry and database
        self.tool_registry.record_tool_use(tool_name)
        self.metrics.tool_usage[tool_name] = self.metrics.tool_usage.get(tool_name, 0) + 1

        # Record in database
        db_tool = self.db.get_tool(tool_name)
        if db_tool:
            self.db.record_tool_use(db_tool.id)

        # Get connection
        if connection_name:
            connection = self.connections.get(connection_name)
        elif self.config.default_server:
            connection = self.connections.get(self.config.default_server)
        else:
            # Use first available connection
            connection = next(
                (c for c in self.connections.values() if c.is_available),
                None
            )

        if not connection:
            return {"error": "No available MCP connection"}

        # Make request
        start_time = datetime.now()
        self.metrics.total_requests += 1

        try:
            response = await connection.request(
                method=f"tools/{tool_name}",
                params=params,
                timeout=timeout,
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics.total_latency_ms += latency

            if response:
                self.metrics.successful_requests += 1
                return response.get("result", response)
            else:
                self.metrics.failed_requests += 1
                return {"error": "Request failed"}

        except Exception as e:
            self.metrics.failed_requests += 1
            logger.error(f"Tool call error for '{tool_name}': {e}")
            return {"error": str(e)}
    
    async def discover_tools(self, connection_name: str | None = None) -> list[dict[str, Any]]:
        """Discover available tools from MCP server and save to database."""
        if not self.config.enabled:
            return []

        # Get connection
        if connection_name:
            connection = self.connections.get(connection_name)
        else:
            connection = next(
                (c for c in self.connections.values() if c.is_available),
                None
            )

        if not connection or not connection.is_available:
            return []

        try:
            response = await connection.request(
                method="tools/list",
                params={},
                timeout=30,
            )

            if response:
                tools = response.get("result", {}).get("tools", [])

                # Save discovered tools to database (associated with the server)
                server_name = connection.config.name
                try:
                    saved_tools = self.db.save_discovered_tools(server_name, tools)

                    # Register tools in registry
                    for tool_record in saved_tools:
                        if tool_record.name not in self.config.tools:
                            config = MCPToolConfig(
                                name=tool_record.name,
                                description=tool_record.description,
                                enabled=tool_record.enabled,
                                parameters=tool_record.parameters,
                                dependencies=tool_record.dependencies,
                            )
                            await self.tool_registry.register_tool(config)
                            self.config.tools[tool_record.name] = config

                    logger.info(f"Discovered and saved {len(saved_tools)} tools from server '{server_name}'")
                except Exception as e:
                    logger.error(f"Failed to save discovered tools: {e}")

                return tools

        except Exception as e:
            logger.error(f"Tool discovery error: {e}")

        return []
    
    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Get tool definitions formatted for LLM consumption."""
        tools = []
        
        for tool in self.tool_registry.get_enabled_tools():
            tool_def = {
                "type": "function",
                "function": {
                    "name": f"mcp_{tool.name}",
                    "description": tool.config.description,
                    "parameters": tool.config.parameters or {"type": "object", "properties": {}},
                },
            }
            tools.append(tool_def)
        
        return tools
    
    async def _auto_discover_tools(self, server_name: str) -> None:
        """Auto-discover tools from a server after connection."""
        try:
            # Wait a moment for connection to stabilize
            await asyncio.sleep(1)
            
            logger.info(f"Auto-discovering tools from server: {server_name}")
            tools = await self.discover_tools(server_name)
            
            if tools:
                logger.info(f"Auto-discovered {len(tools)} tools from server '{server_name}'")
            else:
                logger.warning(f"No tools discovered from server '{server_name}'")
                
        except Exception as e:
            logger.error(f"Auto-discover tools error for server '{server_name}': {e}")
    
    def _handle_connection_message(self, connection: MCPConnection, message: dict) -> None:
        """Handle messages from connections."""
        msg_type = message.get("type")
        
        if msg_type == "tool_update":
            # Handle tool updates from server
            logger.info(f"Received tool update from {connection.name}")
            # Trigger async discovery
            asyncio.create_task(self.discover_tools(connection.name))
        
        elif msg_type == "error":
            logger.error(f"Error from {connection.name}: {message.get('error')}")
    
    async def _monitor_loop(self) -> None:
        """Monitor connections and tools."""
        while self._running:
            try:
                # Monitor connection health
                for name, connection in self.connections.items():
                    if connection.state == ConnectionState.ERROR:
                        logger.warning(f"Connection {name} in error state")
                
                # Update metrics
                for name, connection in self.connections.items():
                    if connection.is_connected and connection.stats.connect_time:
                        uptime = (datetime.now() - connection.stats.connect_time).total_seconds()
                        self.metrics.connection_uptime[name] = uptime
                
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(10)
    
    async def _cleanup_loop(self) -> None:
        """Periodic cleanup task."""
        while self._running:
            try:
                # Cleanup expired tokens
                self.security.cleanup_expired_tokens()
                
                # Cleanup rate limits
                self.security.cleanup_rate_limits()
                
                await asyncio.sleep(300)  # Every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(300)
    
    def get_status(self) -> dict[str, Any]:
        """Get comprehensive MCP status."""
        return {
            "enabled": self.config.enabled,
            "initialized": self.state.initialized,
            "running": self._running,
            "connections": {
                "total": len(self.connections),
                "connected": sum(1 for c in self.connections.values() if c.is_connected),
                "details": self.get_all_connections_status(),
            },
            "tools": {
                "total": len(self.tool_registry.list_tools()),
                "enabled": len(self.tool_registry.get_enabled_tools()),
                "details": self.tool_registry.get_tools_info(),
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "average_latency_ms": (
                    self.metrics.total_latency_ms / self.metrics.successful_requests
                    if self.metrics.successful_requests > 0 else 0
                ),
                "tool_usage": self.metrics.tool_usage,
                "connection_uptime": self.metrics.connection_uptime,
            },
            "security": self.security.get_security_status(),
            "last_updated": self.state.last_updated.isoformat(),
            "errors": self.state.errors,
        }
    
    def get_config_dict(self) -> dict[str, Any]:
        """Get configuration as dictionary."""
        return self.config.to_dict()
    
    async def update_config(self, config_dict: dict[str, Any]) -> bool:
        """Update configuration."""
        try:
            new_config = MCPConfig.from_dict(config_dict)

            # Shutdown current instance
            await self.shutdown()

            # Update config
            self.config = new_config

            # Sync to database
            if self.config.servers:
                self.db.sync_servers_from_config({
                    name: cfg.model_dump() for name, cfg in self.config.servers.items()
                })
            if self.config.tools:
                self.db.sync_tools_from_config({
                    name: cfg.model_dump() for name, cfg in self.config.tools.items()
                })

            # Re-initialize if enabled
            if self.config.enabled:
                await self.initialize()

            logger.info("MCP configuration updated")
            return True

        except Exception as e:
            logger.error(f"Failed to update MCP config: {e}")
            return False

    async def save_config(self, path: Path | str | None = None) -> bool:
        """Save configuration to file (for backup/export)."""
        if path is None:
            from backend.utils.helpers import get_data_path
            path = get_data_path() / "mcp.json"

        # Export from database to ensure we save the current state
        db_config = self.db.export_to_config()
        export_config = MCPConfig(
            enabled=self.config.enabled,
            default_server=self.config.default_server,
            **db_config
        )
        return export_config.save_to_file(path)


# Convenience function to get manager instance
async def get_mcp_manager(
    config: MCPConfig | None = None,
    config_path: Path | str | None = None,
    db: Database | None = None,
) -> MCPManager:
    """Get or create the MCP manager instance."""
    manager = MCPManager(config=config, config_path=config_path, db=db)

    if not manager.state.initialized and manager.config.enabled:
        await manager.initialize()

    return manager