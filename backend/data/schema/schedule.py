"""Schedule (日程) schema for calendar event persistence."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
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
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
        """
    )


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_start "
        "ON schedule_events(start_at_ms)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schedule_events_range "
        "ON schedule_events(start_at_ms, end_at_ms)"
    )
