"""Tool config schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tool_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            timeout INTEGER DEFAULT 60,
            restrict_to_workspace BOOLEAN DEFAULT 1,
            search_api_key TEXT DEFAULT '',
            search_max_results INTEGER DEFAULT 5,
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_configs_name ON tool_configs(tool_name)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
