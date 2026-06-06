"""Add pricing_json and description columns to models table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(models)")
    columns = {row[1] for row in cursor.fetchall()}

    if "pricing_json" not in columns:
        conn.execute("ALTER TABLE models ADD COLUMN pricing_json TEXT")

    if "description" not in columns:
        conn.execute("ALTER TABLE models ADD COLUMN description TEXT")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
