"""Add tool_calls and tool_call_id to pdf_chat_messages."""

from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(pdf_chat_messages)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns:
        if "tool_calls" not in columns:
            conn.execute("ALTER TABLE pdf_chat_messages ADD COLUMN tool_calls TEXT")
        if "tool_call_id" not in columns:
            conn.execute("ALTER TABLE pdf_chat_messages ADD COLUMN tool_call_id TEXT")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
