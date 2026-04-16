"""Add compression fields to session_instances table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(session_instances)")
    columns = [row[1] for row in cursor.fetchall()]
    if not columns:
        return
    if 'compressed_context' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_context TEXT DEFAULT ''")
    if 'compressed_message_count' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_message_count INTEGER DEFAULT 0")
    if 'last_compressed_turn' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN last_compressed_turn INTEGER DEFAULT 0")
    if 'compressed_at' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_at TIMESTAMP")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
