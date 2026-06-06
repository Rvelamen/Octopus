"""Workflow Design Chat schema for AI-assisted workflow authoring sessions."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_design_sessions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            user_id TEXT,
            agent_config_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (agent_config_id) REFERENCES subagents(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_design_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool')),
            content TEXT NOT NULL DEFAULT '',
            tool_calls TEXT,
            tool_call_id TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES workflow_design_sessions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_design_operations (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            before_state TEXT,
            after_state TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES workflow_design_sessions(id) ON DELETE CASCADE
        )
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_design_sessions_workflow ON workflow_design_sessions(workflow_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_design_messages_session ON workflow_design_messages(session_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wf_design_operations_session ON workflow_design_operations(session_id)"
    )
