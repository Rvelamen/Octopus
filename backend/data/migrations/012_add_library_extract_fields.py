"""Add library_extract_provider_id and library_extract_model_id to agent_defaults."""

from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(agent_defaults)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and "library_extract_provider_id" not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN library_extract_provider_id INTEGER")
    if columns and "library_extract_model_id" not in columns:
        conn.execute("ALTER TABLE agent_defaults ADD COLUMN library_extract_model_id INTEGER")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
