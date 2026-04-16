"""Add is_compressed column to messages table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'is_compressed' not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN is_compressed BOOLEAN DEFAULT 0")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
