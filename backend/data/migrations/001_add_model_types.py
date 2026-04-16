"""Add model_types column to models table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(models)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and 'model_types' not in columns:
        conn.execute("ALTER TABLE models ADD COLUMN model_types TEXT DEFAULT '[\"chat\"]'")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
