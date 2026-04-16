"""Add tools column to agent_defaults table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(agent_defaults)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'tools' not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN tools TEXT DEFAULT '[]'")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
