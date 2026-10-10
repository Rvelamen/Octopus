"""Add the `cancelled` column to schedule_events so individual events can be
marked inactive (reversibly) without losing history. Cancellation is distinct
from hard delete — the modal offers a Restore button, the LLM-callable
cancel_event tool uses this, and the front-end renders cancelled events with
a strikethrough / faded style.
"""

from yoyo import step


def apply(conn):
    # ALTER TABLE is a no-op if the column already exists (yoyo skips already-
    # applied migrations, but this guards against partial states).
    cols = [row[1] for row in conn.execute("PRAGMA table_info(schedule_events)").fetchall()]
    if "cancelled" not in cols:
        conn.execute(
            "ALTER TABLE schedule_events ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0"
        )
    # Cheap partial index — most events are not cancelled, so a plain index is fine.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_cancelled "
        "ON schedule_events(cancelled)"
    )


def rollback(conn):
    conn.execute("DROP INDEX IF EXISTS idx_schedule_events_cancelled")
    # SQLite < 3.35 cannot drop a column; leave the column in place on rollback
    # so we don't break existing rows. Future rollback would need a table rebuild.


steps = [step(apply, rollback)]
