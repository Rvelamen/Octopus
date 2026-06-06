"""PDF Chat schema for session and message persistence."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pdf_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            pdf_path TEXT,
            title TEXT NOT NULL DEFAULT 'New Chat',
            agent_config_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (agent_config_id) REFERENCES subagents(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pdf_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            page_number INTEGER,
            selected_text TEXT,
            metadata TEXT DEFAULT '{}',
            tool_calls TEXT,
            tool_call_id TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES pdf_chat_sessions(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_chat_sessions_item ON pdf_chat_sessions(item_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_chat_sessions_pdf_path ON pdf_chat_sessions(pdf_path)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_chat_messages_session ON pdf_chat_messages(session_id)"
    )
