"""Add the `deleted_at` column to schedule_events for soft-delete + recycle bin.

When a user deletes an event from the UI it gets stamped with `deleted_at`
instead of being removed. A daily purge (called from the recycle-bin list
and on service startup) hard-deletes anything older than 30 days. The
column is nullable; an event is "in the recycle bin" iff ``deleted_at IS NOT NULL``.
"""

from yoyo import step


def apply(conn):
    cols = [row[1] for row in conn.execute("PRAGMA table_info(schedule_events)").fetchall()]
    if "deleted_at" not in cols:
        conn.execute(
            "ALTER TABLE schedule_events ADD COLUMN deleted_at TIMESTAMP"
        )
    # Index on deleted_at so list_recycle_bin / purge_old_deleted are fast even
    # when the calendar grows large. Composite (deleted_at, start_at_ms) so the
    # day-grouped recycle-bin view (which orders by start_at_ms within each
    # bin) can also use this index.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_deleted_at "
        "ON schedule_events(deleted_at, start_at_ms)"
    )


def rollback(conn):
    conn.execute("DROP INDEX IF EXISTS idx_schedule_events_deleted_at")
    # SQLite < 3.35 cannot drop a column; leave the column in place on rollback
    # so we don't break existing rows. Future rollback would need a table rebuild.


steps = [step(apply, rollback)]
