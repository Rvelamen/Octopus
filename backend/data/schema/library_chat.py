"""Library Chat schema for session and message persistence."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS library_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type TEXT NOT NULL DEFAULT 'collection',
            scope_value TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT 'New Chat',
            agent_config_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (agent_config_id) REFERENCES subagents(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS library_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            tool_calls TEXT,
            tool_call_id TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES library_chat_sessions(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lib_chat_sessions_scope ON library_chat_sessions(scope_type, scope_value)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lib_chat_messages_session ON library_chat_messages(session_id)"
    )
