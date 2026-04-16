"""APScheduler job store schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apscheduler_jobs (
            id TEXT NOT NULL PRIMARY KEY,
            next_run_time FLOAT,
            job_state BLOB NOT NULL
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    pass


def seed_data(conn: sqlite3.Connection) -> None:
    pass
