"""Add TTS fields to session_instances table."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(session_instances)")
    columns = [row[1] for row in cursor.fetchall()]
    if not columns:
        return
    if 'tts_enabled' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN tts_enabled BOOLEAN DEFAULT 0")
    if 'tts_config' not in columns:
        conn.execute("ALTER TABLE session_instances ADD COLUMN tts_config TEXT DEFAULT '{}'")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
