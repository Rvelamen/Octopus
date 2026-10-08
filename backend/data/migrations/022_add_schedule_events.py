"""Add schedule_events table for the Schedule (日程) feature."""

from yoyo import step


def apply(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            location TEXT DEFAULT '',
            color TEXT DEFAULT '#4F8EF7',
            start_at_ms INTEGER NOT NULL,
            end_at_ms   INTEGER NOT NULL,
            all_day INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_start "
        "ON schedule_events(start_at_ms)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_range "
        "ON schedule_events(start_at_ms, end_at_ms)"
    )


def rollback(conn):
    conn.execute("DROP INDEX IF EXISTS idx_schedule_events_range")
    conn.execute("DROP INDEX IF EXISTS idx_schedule_events_start")
    conn.execute("DROP TABLE IF EXISTS schedule_events")


steps = [step(apply, rollback)]
