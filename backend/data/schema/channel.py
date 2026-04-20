"""Channel config schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT UNIQUE NOT NULL,
            channel_type TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 0,
            app_id TEXT DEFAULT '',
            app_secret TEXT DEFAULT '',
            encrypt_key TEXT DEFAULT '',
            verification_token TEXT DEFAULT '',
            allow_from TEXT DEFAULT '[]',
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_channel_configs_name ON channel_configs(channel_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_channel_configs_enabled ON channel_configs(enabled)")


def seed_data(conn: sqlite3.Connection) -> None:
    _CHANNELS = [
        ('feishu', 'feishu'),
        ('wechat', 'wechat'),
        ('telegram', 'telegram'),
        ('dingtalk', 'dingtalk'),
        ('slack', 'slack'),
        ('discord', 'discord'),
        ('email', 'email'),
    ]
    for name, ctype in _CHANNELS:
        conn.execute("""
            INSERT OR IGNORE INTO channel_configs
            (channel_name, channel_type, enabled, app_id, app_secret, encrypt_key, verification_token, allow_from, config_json)
            VALUES (?, ?, 0, '', '', '', '', '[]', '{}')
        """, (name, ctype))
