"""Rebuild token_usage table without foreign key cascade."""
from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA foreign_key_list(token_usage)")
    has_fk = any(row for row in cursor.fetchall())
    if not has_fk:
        return
    conn.execute("ALTER TABLE token_usage RENAME TO token_usage_old")
    conn.execute("""
        CREATE TABLE token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_instance_id INTEGER,
            provider_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            request_type TEXT DEFAULT 'chat',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        INSERT INTO token_usage
            (id, session_instance_id, provider_name, model_id,
             prompt_tokens, completion_tokens, cached_tokens, total_tokens,
             request_type, created_at)
        SELECT
            id, session_instance_id, provider_name, model_id,
            prompt_tokens, completion_tokens,
            COALESCE(cached_tokens, 0) as cached_tokens,
            total_tokens, request_type, created_at
        FROM token_usage_old
    """)
    conn.execute("DROP TABLE token_usage_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_instance ON token_usage(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at)")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
