"""Session and message schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            session_key TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            metadata TEXT DEFAULT '{}',
            UNIQUE(channel, chat_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            instance_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            compressed_context TEXT DEFAULT '',
            compressed_message_count INTEGER DEFAULT 0,
            last_compressed_turn INTEGER DEFAULT 0,
            compressed_at TIMESTAMP,
            tts_enabled BOOLEAN DEFAULT 0,
            tts_config TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_instance_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            metadata TEXT DEFAULT '{}',
            is_compressed BOOLEAN DEFAULT 0,
            FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_instances_session ON session_instances(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_instances_active ON session_instances(session_id, is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_instance ON messages(session_instance_id)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
