"""Schema for user-defined database tables (unified data storage)."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create user_tables metadata and user_data_records unified storage."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            fields_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_data_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_data TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes for user data tables."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_data_table ON user_data_records(table_name)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_data_created ON user_data_records(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_data_updated ON user_data_records(updated_at)"
    )


def seed_data(conn: sqlite3.Connection) -> None:
    """No seed data needed for user tables."""
    pass
