"""LLM provider, model, and service config schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            provider_type TEXT NOT NULL,
            api_key TEXT DEFAULT '',
            api_host TEXT DEFAULT '',
            api_version TEXT DEFAULT '',
            enabled BOOLEAN DEFAULT 1,
            is_system BOOLEAN DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL,
            model_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            model_type TEXT DEFAULT 'chat',
            model_types TEXT DEFAULT '["chat"]',
            group_name TEXT DEFAULT 'Chat Models',
            max_tokens INTEGER DEFAULT 4096,
            context_window INTEGER DEFAULT 128000,
            supports_vision BOOLEAN DEFAULT 0,
            supports_function_calling BOOLEAN DEFAULT 1,
            supports_streaming BOOLEAN DEFAULT 1,
            enabled BOOLEAN DEFAULT 1,
            is_default BOOLEAN DEFAULT 0,
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
            UNIQUE(provider_id, model_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT,
            value_type TEXT DEFAULT 'string',
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_service_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT UNIQUE NOT NULL,
            default_model_id INTEGER,
            default_size TEXT DEFAULT '1024x1024',
            default_quality TEXT DEFAULT 'standard',
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tts_service_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT UNIQUE NOT NULL,
            default_model_id INTEGER,
            default_voice TEXT DEFAULT 'alloy',
            default_format TEXT DEFAULT 'mp3',
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_providers_type ON providers(provider_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_providers_enabled ON providers(enabled)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_models_enabled ON models(enabled)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_image_service_config_type ON image_service_config(config_type)")


def seed_data(conn: sqlite3.Connection) -> None:
    conn.execute("""
        INSERT OR IGNORE INTO image_service_config (config_type, default_model_id, default_size, default_quality)
        VALUES ('understanding', NULL, NULL, NULL)
    """)
    conn.execute("""
        INSERT OR IGNORE INTO image_service_config (config_type, default_model_id, default_size, default_quality)
        VALUES ('generation', NULL, '1024x1024', 'standard')
    """)
    conn.execute("""
        INSERT OR IGNORE INTO tts_service_config (config_type, default_model_id, default_voice, default_format)
        VALUES ('tts', NULL, 'alloy', 'mp3')
    """)
