"""Rename workflow_version_id to version_id in workflow tables."""
from yoyo import step


def apply(conn):
    # Rename column in workflow_nodes if it exists
    cursor = conn.execute("PRAGMA table_info(workflow_nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'workflow_version_id' in columns and 'version_id' not in columns:
        conn.execute("ALTER TABLE workflow_nodes RENAME COLUMN workflow_version_id TO version_id")

    # Rename column in workflow_edges if it exists
    cursor = conn.execute("PRAGMA table_info(workflow_edges)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'workflow_version_id' in columns and 'version_id' not in columns:
        conn.execute("ALTER TABLE workflow_edges RENAME COLUMN workflow_version_id TO version_id")
    # Add missing columns if not present (schema evolved after initial table creation)
    if columns and 'source_handle' not in columns:
        conn.execute("ALTER TABLE workflow_edges ADD COLUMN source_handle TEXT DEFAULT ''")
    if columns and 'target_handle' not in columns:
        conn.execute("ALTER TABLE workflow_edges ADD COLUMN target_handle TEXT DEFAULT ''")
    if columns and 'created_at' not in columns:
        conn.execute("ALTER TABLE workflow_edges ADD COLUMN created_at TIMESTAMP")

    # Rename column in workflow_variables if it exists
    cursor = conn.execute("PRAGMA table_info(workflow_variables)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'workflow_version_id' in columns and 'version_id' not in columns:
        conn.execute("ALTER TABLE workflow_variables RENAME COLUMN workflow_version_id TO version_id")


    # Rename column in workflow_runs if it exists
    cursor = conn.execute("PRAGMA table_info(workflow_runs)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'workflow_version_id' in columns and 'version_id' not in columns:
        conn.execute("ALTER TABLE workflow_runs RENAME COLUMN workflow_version_id TO version_id")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
