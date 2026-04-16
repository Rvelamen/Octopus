"""Add retry fields to agent_defaults table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(agent_defaults)")
    columns = [row[1] for row in cursor.fetchall()]
    if not columns:
        return
    if 'llm_max_retries' not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_max_retries INTEGER DEFAULT 3")
    if 'llm_retry_base_delay' not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_retry_base_delay REAL DEFAULT 1.0")
    if 'llm_retry_max_delay' not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_retry_max_delay REAL DEFAULT 30.0")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
