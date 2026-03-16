"""MCP configuration management module.

Provides configuration schema and loading mechanisms for MCP integration.
Supports self.config.mcp.xxx style access with error handling and fallback.
"""

from typing import Any, Literal
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from loguru import logger


class MCPToolConfig(BaseModel):
    """Configuration for an MCP tool."""
    
    name: str
    description: str = ""
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    timeout: int = 30
    retry_count: int = 3
    
    class Config:
        extra = "allow"


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""
    
    name: str
    url: str
    protocol: Literal["stdio", "sse", "websocket"] = "stdio"
    enabled: bool = True
    auto_connect: bool = True
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 10
    connection_timeout: int = 30
    heartbeat_interval: int = 30
    auth_token: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    working_dir: str | None = None
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str, info) -> str:
        """Validate URL based on protocol."""
        protocol = info.data.get("protocol", "stdio")
        if protocol == "stdio":
            return v
        if not v.startswith(("http://", "https://", "ws://", "wss://")):
            raise ValueError(f"Invalid URL for protocol {protocol}: {v}")
        return v
    
    class Config:
        extra = "allow"


class MCPSecurityConfig(BaseModel):
    """Security configuration for MCP."""
    
    enabled: bool = True
    require_auth: bool = True
    allowed_origins: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    encryption_enabled: bool = True
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    class Config:
        extra = "allow"


class MCPMetricsConfig(BaseModel):
    """Metrics and monitoring configuration."""
    
    enabled: bool = True
    collect_latency: bool = True
    collect_usage: bool = True
    retention_days: int = 30
    export_interval: int = 300  # 5 minutes
    
    class Config:
        extra = "allow"


class MCPConfig(BaseModel):
    """Root MCP configuration.
    
    This configuration is designed to be accessed via self.config.mcp.xxx
    and supports automatic loading with fallback to defaults.
    """
    
    enabled: bool = True
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    tools: dict[str, MCPToolConfig] = Field(default_factory=dict)
    security: MCPSecurityConfig = Field(default_factory=MCPSecurityConfig)
    metrics: MCPMetricsConfig = Field(default_factory=MCPMetricsConfig)
    default_server: str | None = None
    tool_discovery_interval: int = 300  # 5 minutes
    max_concurrent_connections: int = 10
    connection_pool_size: int = 5
    
    class Config:
        extra = "allow"
        env_prefix = "OCTOPUS_MCP_"
        env_nested_delimiter = "__"
    
    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get server configuration by name with fallback handling."""
        if name in self.servers:
            return self.servers[name]
        
        # Try case-insensitive lookup
        name_lower = name.lower()
        for key, config in self.servers.items():
            if key.lower() == name_lower:
                return config
        
        return None
    
    def get_tool(self, name: str) -> MCPToolConfig | None:
        """Get tool configuration by name with fallback handling."""
        if name in self.tools:
            return self.tools[name]
        
        # Try case-insensitive lookup
        name_lower = name.lower()
        for key, config in self.tools.items():
            if key.lower() == name_lower:
                return config
        
        return None
    
    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get list of enabled server configurations."""
        return [s for s in self.servers.values() if s.enabled]
    
    def get_enabled_tools(self) -> list[MCPToolConfig]:
        """Get list of enabled tool configurations."""
        return [t for t in self.tools.values() if t.enabled]
    
    def add_server(self, name: str, config: MCPServerConfig | dict) -> None:
        """Add or update a server configuration."""
        if isinstance(config, dict):
            config = MCPServerConfig(name=name, **config)
        else:
            config.name = name
        self.servers[name] = config
        logger.info(f"Added MCP server configuration: {name}")
    
    def add_tool(self, name: str, config: MCPToolConfig | dict) -> None:
        """Add or update a tool configuration."""
        if isinstance(config, dict):
            config = MCPToolConfig(name=name, **config)
        else:
            config.name = name
        self.tools[name] = config
        logger.info(f"Added MCP tool configuration: {name}")
    
    def remove_server(self, name: str) -> bool:
        """Remove a server configuration."""
        if name in self.servers:
            del self.servers[name]
            logger.info(f"Removed MCP server configuration: {name}")
            return True
        return False
    
    def remove_tool(self, name: str) -> bool:
        """Remove a tool configuration."""
        if name in self.tools:
            del self.tools[name]
            logger.info(f"Removed MCP tool configuration: {name}")
            return True
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPConfig":
        """Create configuration from dictionary with error handling."""
        try:
            return cls.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to validate MCP config: {e}")
            # Return default config on validation error
            return cls()
    
    @classmethod
    def load_from_file(cls, path: Path | str) -> "MCPConfig":
        """Load configuration from JSON file with fallback."""
        import json
        
        path = Path(path)
        if not path.exists():
            logger.warning(f"MCP config file not found: {path}, using defaults")
            return cls()
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP config file {path}: {e}")
            return cls()
        except Exception as e:
            logger.error(f"Failed to load MCP config from {path}: {e}")
            return cls()
    
    def save_to_file(self, path: Path | str) -> bool:
        """Save configuration to JSON file."""
        import json
        
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved MCP config to: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save MCP config to {path}: {e}")
            return False