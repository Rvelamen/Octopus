"""MCP server/tool schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            protocol TEXT DEFAULT 'stdio',
            enabled BOOLEAN DEFAULT 1,
            auto_connect BOOLEAN DEFAULT 1,
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id INTEGER,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            enabled BOOLEAN DEFAULT 1,
            parameters_json TEXT DEFAULT '{}',
            dependencies_json TEXT DEFAULT '[]',
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(server_id, name),
            FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_tool_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_id INTEGER NOT NULL UNIQUE,
            use_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (tool_id) REFERENCES mcp_tools(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_servers_name ON mcp_servers(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON mcp_tools(server_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_tools_name ON mcp_tools(name)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
