"""Async task schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            parent_session TEXT NOT NULL,
            parent_instance_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            input_params TEXT DEFAULT '{}',
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT,
            current_step TEXT,
            pending_auth TEXT,
            auth_payload TEXT,
            auth_timeout_at TIMESTAMP,
            result_summary TEXT,
            result_details TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            started_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            completed_at TIMESTAMP,
            FOREIGN KEY (parent_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(parent_session)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_instance ON tasks(parent_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_pending_auth ON tasks(pending_auth, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
