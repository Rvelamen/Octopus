"""Add context_compression_token_threshold to agent_defaults table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(agent_defaults)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'context_compression_token_threshold' not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN context_compression_token_threshold INTEGER DEFAULT 200000")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
