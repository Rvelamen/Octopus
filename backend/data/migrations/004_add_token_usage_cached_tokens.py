"""Add cached_tokens column to token_usage table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(token_usage)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'cached_tokens' not in columns:
        conn.execute("ALTER TABLE token_usage ADD COLUMN cached_tokens INTEGER DEFAULT 0")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
