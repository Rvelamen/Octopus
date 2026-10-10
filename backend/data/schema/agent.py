"""Agent defaults schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_defaults (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            default_provider_id INTEGER,
            default_model_id INTEGER,
            library_extract_provider_id INTEGER,
            library_extract_model_id INTEGER,
            library_extract_language TEXT DEFAULT 'English',
            book_room_round_timeout_seconds INTEGER NOT NULL DEFAULT 60
                CHECK (typeof(book_room_round_timeout_seconds) = 'integer' AND book_room_round_timeout_seconds > 0),
            book_room_all_round_timeout_seconds INTEGER NOT NULL DEFAULT 300
                CHECK (typeof(book_room_all_round_timeout_seconds) = 'integer' AND book_room_all_round_timeout_seconds > 0),
            workspace_path TEXT DEFAULT '',
            max_tokens INTEGER DEFAULT 8192,
            temperature REAL DEFAULT 0.7,
            max_iterations INTEGER DEFAULT 20,
            context_compression_enabled BOOLEAN DEFAULT 0,
            context_compression_turns INTEGER DEFAULT 10,
            context_compression_token_threshold INTEGER DEFAULT 200000,
            llm_max_retries INTEGER DEFAULT 3,
            llm_retry_base_delay REAL DEFAULT 1.0,
            llm_retry_max_delay REAL DEFAULT 30.0,
            tools TEXT DEFAULT '[]',
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (default_provider_id) REFERENCES providers(id) ON DELETE SET NULL,
            FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
        )
    """)
    ensure_book_room_timeout_columns(conn)


def ensure_book_room_timeout_columns(conn: sqlite3.Connection) -> None:
    """Upgrade older defaults tables even when optional yoyo is unavailable."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_defaults)")}
    for column, default in (
        ("book_room_round_timeout_seconds", 60),
        ("book_room_all_round_timeout_seconds", 300),
    ):
        if columns and column not in columns:
            conn.execute(
                f"ALTER TABLE agent_defaults ADD COLUMN {column} INTEGER NOT NULL "
                f"DEFAULT {default} CHECK (typeof({column}) = 'integer' AND {column} > 0)"
            )


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_defaults_provider ON agent_defaults(default_provider_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_defaults_model ON agent_defaults(default_model_id)"
    )


def seed_data(conn: sqlite3.Connection) -> None:
    pass
