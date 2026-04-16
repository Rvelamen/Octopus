"""Image upload/generation schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_instance_id INTEGER,
            image_type TEXT NOT NULL,
            source TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            mime_type TEXT DEFAULT 'image/png',
            file_size INTEGER DEFAULT 0,
            width INTEGER,
            height INTEGER,
            description TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_session ON images(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
