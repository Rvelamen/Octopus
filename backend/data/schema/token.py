"""Token usage schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_instance_id INTEGER,
            provider_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            request_type TEXT DEFAULT 'chat',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type TEXT NOT NULL,
            scope_id TEXT,
            provider_name TEXT,
            model_id TEXT,
            total_prompt_tokens INTEGER DEFAULT 0,
            total_completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            request_count INTEGER DEFAULT 0,
            date_date TEXT,
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(scope_type, scope_id, provider_name, model_id, date_date)
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_instance ON token_usage(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_summary_scope ON token_usage_summary(scope_type, scope_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_summary_date ON token_usage_summary(date_date)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
