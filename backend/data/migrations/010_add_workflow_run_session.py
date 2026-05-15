"""Add session_instance_id to workflow_runs table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(workflow_runs)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'session_instance_id' not in columns:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN session_instance_id INTEGER")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_session ON workflow_runs(session_instance_id)")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
