"""Add the `archived_at` column to session_instances for the Chat archive feature.

When a user archives a conversation card from the Chat sidebar it gets
stamped with `archived_at` instead of being deleted. Hard-delete still
removes the row entirely. The column is nullable; an instance is
"in the archived section" iff ``archived_at IS NOT NULL``.

The composite index covers both the active-only list query (filtered by
``archived_at IS NULL``, ordered by created_at DESC) and the archived
section header count without a separate table scan.
"""

from yoyo import step


def apply(conn):
    cols = [row[1] for row in conn.execute("PRAGMA table_info(session_instances)").fetchall()]
    if "archived_at" not in cols:
        conn.execute(
            "ALTER TABLE session_instances ADD COLUMN archived_at TIMESTAMP"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_instances_archived "
        "ON session_instances(session_id, archived_at)"
    )


def rollback(conn):
    conn.execute("DROP INDEX IF EXISTS idx_instances_archived")
    # SQLite < 3.35 cannot drop a column; leave the column in place on rollback
    # so we don't break existing rows. Future rollback would need a table rebuild.


steps = [step(apply, rollback)]
