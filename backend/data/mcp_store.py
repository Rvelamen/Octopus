"""MCP database models and repository."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class MCPServerRecord:
    """MCP server record data class."""
    id: int
    name: str
    url: str
    protocol: str
    enabled: bool
    auto_connect: bool
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class MCPToolRecord:
    """MCP tool record data class."""
    id: int
    server_id: Optional[int]
    name: str
    description: str
    enabled: bool
    parameters: dict[str, Any]
    dependencies: list[str]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class MCPToolStats:
    """MCP tool usage statistics."""
    id: int
    tool_id: int
    use_count: int
    last_used_at: Optional[datetime]


class MCPRepository:
    """Repository for MCP-related database operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    # ========== Server Operations ==========
    
    def get_or_create_server(self, name: str, url: str, protocol: str = "stdio",
                             enabled: bool = True, auto_connect: bool = True,
                             config: dict[str, Any] | None = None) -> MCPServerRecord:
        """Get or create a server record."""
        config = config or {}
        config_json = json.dumps(config, ensure_ascii=False)
        
        with self.db._get_connection() as conn:
            # Try to get existing
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE name = ?",
                (name,)
            ).fetchone()
            
            if row:
                return self._row_to_server(row)
            
            # Create new
            cursor = conn.execute(
                """INSERT INTO mcp_servers (name, url, protocol, enabled, auto_connect, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (name, url, protocol, enabled, auto_connect, config_json)
            )
            
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            logger.info(f"Created MCP server record: {name}")
            return self._row_to_server(row)
    
    def get_server(self, name: str) -> Optional[MCPServerRecord]:
        """Get server by name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE name = ?",
                (name,)
            ).fetchone()
            
            return self._row_to_server(row) if row else None
    
    def get_server_by_id(self, server_id: int) -> Optional[MCPServerRecord]:
        """Get server by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE id = ?",
                (server_id,)
            ).fetchone()
            
            return self._row_to_server(row) if row else None
    
    def list_servers(self, enabled_only: bool = False) -> list[MCPServerRecord]:
        """List all servers."""
        with self.db._get_connection() as conn:
            if enabled_only:
                rows = conn.execute(
                    "SELECT * FROM mcp_servers WHERE enabled = 1 ORDER BY name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mcp_servers ORDER BY name"
                ).fetchall()
            
            return [self._row_to_server(row) for row in rows]
    
    def update_server(self, name: str, **kwargs) -> bool:
        """Update server configuration."""
        allowed_fields = {"url", "protocol", "enabled", "auto_connect", "config"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        with self.db._get_connection() as conn:
            # Check if server exists
            row = conn.execute(
                "SELECT id FROM mcp_servers WHERE name = ?",
                (name,)
            ).fetchone()
            
            if not row:
                return False
            
            # Build update query
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key == "config":
                    set_clauses.append("config_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                else:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            set_clauses.append("updated_at = (datetime('now', 'localtime'))")
            values.append(name)
            
            conn.execute(
                f"UPDATE mcp_servers SET {', '.join(set_clauses)} WHERE name = ?",
                values
            )
            
            logger.info(f"Updated MCP server: {name}")
            return True
    
    def delete_server(self, name: str) -> bool:
        """Delete a server and all its tools (cascade)."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM mcp_servers WHERE name = ?",
                (name,)
            )
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted MCP server: {name}")
                return True
            return False
    
    # ========== Tool Operations ==========
    
    def get_or_create_tool(self, name: str, server_id: Optional[int] = None,
                           description: str = "", enabled: bool = True,
                           parameters: dict[str, Any] | None = None,
                           dependencies: list[str] | None = None,
                           config: dict[str, Any] | None = None) -> MCPToolRecord:
        """Get or create a tool record."""
        parameters = parameters or {}
        dependencies = dependencies or []
        config = config or {}
        
        parameters_json = json.dumps(parameters, ensure_ascii=False)
        dependencies_json = json.dumps(dependencies, ensure_ascii=False)
        config_json = json.dumps(config, ensure_ascii=False)
        
        with self.db._get_connection() as conn:
            # Try to get existing
            row = conn.execute(
                """SELECT * FROM mcp_tools
                   WHERE name = ? AND (server_id = ? OR (server_id IS NULL AND ? IS NULL))""",
                (name, server_id, server_id)
            ).fetchone()
            
            if row:
                return self._row_to_tool(row)
            
            # Create new
            cursor = conn.execute(
                """INSERT INTO mcp_tools
                   (server_id, name, description, enabled, parameters_json, dependencies_json, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (server_id, name, description, enabled, parameters_json, dependencies_json, config_json)
            )

            tool_id = cursor.lastrowid

            # Create stats record
            conn.execute(
                "INSERT INTO mcp_tool_stats (tool_id, use_count, last_used_at) VALUES (?, 0, datetime('now', 'localtime'))",
                (tool_id,)
            )
            
            row = conn.execute(
                "SELECT * FROM mcp_tools WHERE id = ?",
                (tool_id,)
            ).fetchone()
            
            logger.info(f"Created MCP tool record: {name}")
            return self._row_to_tool(row)
    
    def get_tool(self, name: str, server_id: Optional[int] = None) -> Optional[MCPToolRecord]:
        """Get tool by name and optional server_id."""
        with self.db._get_connection() as conn:
            if server_id is not None:
                row = conn.execute(
                    "SELECT * FROM mcp_tools WHERE name = ? AND server_id = ?",
                    (name, server_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM mcp_tools WHERE name = ?",
                    (name,)
                ).fetchone()
            
            return self._row_to_tool(row) if row else None
    
    def get_tool_by_id(self, tool_id: int) -> Optional[MCPToolRecord]:
        """Get tool by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_tools WHERE id = ?",
                (tool_id,)
            ).fetchone()
            
            return self._row_to_tool(row) if row else None
    
    def list_tools(self, server_id: Optional[int] = None,
                   enabled_only: bool = False) -> list[MCPToolRecord]:
        """List all tools, optionally filtered by server and enabled status."""
        with self.db._get_connection() as conn:
            query = "SELECT * FROM mcp_tools WHERE 1=1"
            params = []
            
            if server_id is not None:
                query += " AND server_id = ?"
                params.append(server_id)
            
            if enabled_only:
                query += " AND enabled = 1"
            
            query += " ORDER BY name"
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_tool(row) for row in rows]
    
    def update_tool(self, name: str, server_id: Optional[int] = None, **kwargs) -> bool:
        """Update tool configuration."""
        allowed_fields = {"description", "enabled", "parameters", "dependencies", "config"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        with self.db._get_connection() as conn:
            # Check if tool exists
            if server_id is not None:
                row = conn.execute(
                    "SELECT id FROM mcp_tools WHERE name = ? AND server_id = ?",
                    (name, server_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM mcp_tools WHERE name = ?",
                    (name,)
                ).fetchone()
            
            if not row:
                return False
            
            # Build update query
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key == "parameters":
                    set_clauses.append("parameters_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                elif key == "dependencies":
                    set_clauses.append("dependencies_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                elif key == "config":
                    set_clauses.append("config_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                else:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            set_clauses.append("updated_at = (datetime('now', 'localtime'))")
            values.extend([name, server_id] if server_id is not None else [name])
            
            if server_id is not None:
                conn.execute(
                    f"UPDATE mcp_tools SET {', '.join(set_clauses)} WHERE name = ? AND server_id = ?",
                    values
                )
            else:
                conn.execute(
                    f"UPDATE mcp_tools SET {', '.join(set_clauses)} WHERE name = ?",
                    values
                )
            
            logger.info(f"Updated MCP tool: {name}")
            return True
    
    def set_tool_enabled(self, name: str, enabled: bool, server_id: Optional[int] = None) -> bool:
        """Set tool enabled state."""
        return self.update_tool(name, server_id=server_id, enabled=enabled)
    
    def delete_tool(self, name: str, server_id: Optional[int] = None) -> bool:
        """Delete a tool."""
        with self.db._get_connection() as conn:
            if server_id is not None:
                cursor = conn.execute(
                    "DELETE FROM mcp_tools WHERE name = ? AND server_id = ?",
                    (name, server_id)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM mcp_tools WHERE name = ?",
                    (name,)
                )
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted MCP tool: {name}")
                return True
            return False
    
    # ========== Tool Statistics ==========
    
    def record_tool_use(self, tool_id: int) -> bool:
        """Record tool usage."""
        with self.db._get_connection() as conn:
            conn.execute(
                """UPDATE mcp_tool_stats
                   SET use_count = use_count + 1, last_used_at = (datetime('now', 'localtime'))
                   WHERE tool_id = ?""",
                (tool_id,)
            )
            return True
    
    def get_tool_stats(self, tool_id: int) -> Optional[MCPToolStats]:
        """Get tool usage statistics."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_tool_stats WHERE tool_id = ?",
                (tool_id,)
            ).fetchone()
            
            return self._row_to_stats(row) if row else None
    
    def get_all_tool_stats(self) -> dict[int, MCPToolStats]:
        """Get statistics for all tools."""
        with self.db._get_connection() as conn:
            rows = conn.execute("SELECT * FROM mcp_tool_stats").fetchall()
            return {row["tool_id"]: self._row_to_stats(row) for row in rows}
    
    # ========== Bulk Operations ==========
    
    def sync_servers_from_config(self, servers_config: dict[str, dict]) -> None:
        """Sync servers from configuration dictionary."""
        with self.db._get_connection() as conn:
            for name, config in servers_config.items():
                url = config.get("url", "")
                protocol = config.get("protocol", "stdio")
                enabled = config.get("enabled", True)
                auto_connect = config.get("auto_connect", True)
                
                other_config = {k: v for k, v in config.items()
                               if k not in {"name", "url", "protocol", "enabled", "auto_connect"}}
                
                row = conn.execute(
                    "SELECT id, enabled, auto_connect FROM mcp_servers WHERE name = ?",
                    (name,)
                ).fetchone()
                
                if row:
                    enabled = bool(row["enabled"])
                    auto_connect = bool(row["auto_connect"])
                    
                    conn.execute(
                        """UPDATE mcp_servers
                           SET url = ?, protocol = ?, config_json = ?,
                               updated_at = (datetime('now', 'localtime'))
                           WHERE name = ?""",
                        (url, protocol, json.dumps(other_config, ensure_ascii=False), name)
                    )
                else:
                    conn.execute(
                        """INSERT INTO mcp_servers (name, url, protocol, enabled, auto_connect, config_json, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                        (name, url, protocol, enabled, auto_connect, json.dumps(other_config, ensure_ascii=False))
                    )
            
            logger.info(f"Synced {len(servers_config)} servers from config")
    
    def sync_tools_from_config(self, tools_config: dict[str, dict]) -> None:
        """Sync tools from configuration dictionary."""
        with self.db._get_connection() as conn:
            for name, config in tools_config.items():
                description = config.get("description", "")
                enabled = config.get("enabled", True)
                parameters = config.get("parameters", {})
                dependencies = config.get("dependencies", [])
                
                other_config = {k: v for k, v in config.items()
                               if k not in {"name", "description", "enabled", "parameters", "dependencies"}}
                
                row = conn.execute(
                    "SELECT id, enabled FROM mcp_tools WHERE name = ? AND server_id IS NULL",
                    (name,)
                ).fetchone()
                
                if row:
                    enabled = bool(row["enabled"])
                    
                    conn.execute(
                        """UPDATE mcp_tools
                           SET description = ?, parameters_json = ?,
                               dependencies_json = ?, config_json = ?, updated_at = (datetime('now', 'localtime'))
                           WHERE name = ? AND server_id IS NULL""",
                        (description, json.dumps(parameters, ensure_ascii=False),
                         json.dumps(dependencies, ensure_ascii=False), json.dumps(other_config, ensure_ascii=False), name)
                    )
                else:
                    cursor = conn.execute(
                        """INSERT INTO mcp_tools
                           (name, description, enabled, parameters_json, dependencies_json, config_json, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                        (name, description, enabled, json.dumps(parameters, ensure_ascii=False),
                         json.dumps(dependencies, ensure_ascii=False), json.dumps(other_config, ensure_ascii=False))
                    )

                    conn.execute(
                        "INSERT INTO mcp_tool_stats (tool_id, use_count, last_used_at) VALUES (?, 0, datetime('now', 'localtime'))",
                        (cursor.lastrowid,)
                    )
            
            logger.info(f"Synced {len(tools_config)} tools from config")
    
    def get_tools_by_server(self, server_name: str) -> list[MCPToolRecord]:
        """Get all tools for a specific server."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT t.* FROM mcp_tools t
                   JOIN mcp_servers s ON t.server_id = s.id
                   WHERE s.name = ?
                   ORDER BY t.name""",
                (server_name,)
            ).fetchall()
            return [self._row_to_tool(row) for row in rows]
    
    def get_server_with_tools(self, server_name: str) -> tuple[Optional[MCPServerRecord], list[MCPToolRecord]]:
        """Get a server and all its tools."""
        server = self.get_server(server_name)
        if not server:
            return None, []
        tools = self.get_tools_by_server(server_name)
        return server, tools
    
    def get_all_servers_with_tools(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """Get all servers with their tools."""
        servers = self.list_servers(enabled_only=enabled_only)
        result = []
        for server in servers:
            tools = self.get_tools_by_server(server.name)
            result.append({
                "server": server,
                "tools": tools
            })
        return result
    
    def save_discovered_tools(self, server_name: str, tools_data: list[dict[str, Any]]) -> list[MCPToolRecord]:
        """Save discovered tools for a server."""
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Server '{server_name}' not found")
        
        created_tools = []
        with self.db._get_connection() as conn:
            for tool_data in tools_data:
                name = tool_data.get("name")
                if not name:
                    continue
                
                description = tool_data.get("description", "")
                parameters = tool_data.get("parameters", tool_data.get("inputSchema", {}))
                
                # Check if tool already exists for this server
                row = conn.execute(
                    "SELECT id FROM mcp_tools WHERE name = ? AND server_id = ?",
                    (name, server.id)
                ).fetchone()
                
                if row:
                    # Update existing
                    conn.execute(
                        """UPDATE mcp_tools
                           SET description = ?, parameters_json = ?, updated_at = (datetime('now', 'localtime'))
                           WHERE id = ?""",
                        (description, json.dumps(parameters, ensure_ascii=False), row["id"])
                    )
                    tool_id = row["id"]
                else:
                    # Insert new (enabled by default)
                    cursor = conn.execute(
                        """INSERT INTO mcp_tools
                           (server_id, name, description, enabled, parameters_json, dependencies_json, config_json, created_at, updated_at)
                           VALUES (?, ?, ?, 1, ?, '[]', '{}', datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                        (server.id, name, description, json.dumps(parameters, ensure_ascii=False))
                    )
                    tool_id = cursor.lastrowid

                    # Create stats record
                    conn.execute(
                        "INSERT INTO mcp_tool_stats (tool_id, use_count, last_used_at) VALUES (?, 0, datetime('now', 'localtime'))",
                        (tool_id,)
                    )
                
                # Get the created/updated record
                row = conn.execute(
                    "SELECT * FROM mcp_tools WHERE id = ?",
                    (tool_id,)
                ).fetchone()
                if row:
                    created_tools.append(self._row_to_tool(row))
        
        logger.info(f"Saved {len(created_tools)} discovered tools for server '{server_name}'")
        return created_tools
    
    def export_to_config(self) -> dict[str, Any]:
        """Export all configuration to dictionary format."""
        config = {"servers": {}, "tools": {}}
        
        with self.db._get_connection() as conn:
            # Export servers
            rows = conn.execute("SELECT * FROM mcp_servers").fetchall()
            for row in rows:
                server = self._row_to_server(row)
                config["servers"][server.name] = {
                    "name": server.name,
                    "url": server.url,
                    "protocol": server.protocol,
                    "enabled": server.enabled,
                    "auto_connect": server.auto_connect,
                    **server.config
                }
            
            # Export tools (global only, server-specific tools are managed per-server)
            rows = conn.execute(
                "SELECT * FROM mcp_tools WHERE server_id IS NULL"
            ).fetchall()
            for row in rows:
                tool = self._row_to_tool(row)
                config["tools"][tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "enabled": tool.enabled,
                    "parameters": tool.parameters,
                    "dependencies": tool.dependencies,
                    **tool.config
                }
        
        return config
    
    # ========== Helper Methods ==========
    
    def _row_to_server(self, row) -> MCPServerRecord:
        """Convert database row to MCPServerRecord."""
        return MCPServerRecord(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            protocol=row["protocol"],
            enabled=bool(row["enabled"]),
            auto_connect=bool(row["auto_connect"]),
            config=json.loads(row["config_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
    
    def _row_to_tool(self, row) -> MCPToolRecord:
        """Convert database row to MCPToolRecord."""
        return MCPToolRecord(
            id=row["id"],
            server_id=row["server_id"],
            name=row["name"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            parameters=json.loads(row["parameters_json"]),
            dependencies=json.loads(row["dependencies_json"]),
            config=json.loads(row["config_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
    
    def _row_to_stats(self, row) -> MCPToolStats:
        """Convert database row to MCPToolStats."""
        last_used = row["last_used_at"]
        return MCPToolStats(
            id=row["id"],
            tool_id=row["tool_id"],
            use_count=row["use_count"],
            last_used_at=datetime.fromisoformat(last_used) if last_used else None
        )
