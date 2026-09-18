"""Add pdf_annotation_chat_sessions and pdf_annotation_chat_messages tables."""

from yoyo import step


def apply(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_annotation_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            pdf_path TEXT,
            annotation_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'Annotation Chat',
            agent_config_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (agent_config_id) REFERENCES subagents(id) ON DELETE SET NULL,
            FOREIGN KEY (annotation_id) REFERENCES library_annotations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_annot "
        "ON pdf_annotation_chat_sessions(annotation_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_item "
        "ON pdf_annotation_chat_sessions(item_id)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_annotation_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            page_number INTEGER,
            selected_text TEXT,
            metadata TEXT DEFAULT '{}',
            tool_calls TEXT,
            tool_call_id TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (session_id) REFERENCES pdf_annotation_chat_sessions(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_msgs_session "
        "ON pdf_annotation_chat_messages(session_id)"
    )


def rollback(conn):
    pass


steps = [step(apply, rollback)]
