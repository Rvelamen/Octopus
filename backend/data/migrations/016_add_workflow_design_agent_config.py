"""Add agent_config_id to workflow_design_sessions."""

from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(workflow_design_sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and "agent_config_id" not in columns:
        conn.execute("ALTER TABLE workflow_design_sessions ADD COLUMN agent_config_id INTEGER")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
