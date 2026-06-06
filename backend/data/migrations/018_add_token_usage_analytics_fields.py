"""Add analytics fields to token_usage table for cost, latency, and call chain tracking."""

from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(token_usage)")
    columns = {row[1] for row in cursor.fetchall()}

    new_columns = {
        "response_time_ms": "INTEGER DEFAULT NULL",
        "cost_usd": "REAL DEFAULT NULL",
        "tool_calls_count": "INTEGER DEFAULT 0",
        "is_error": "INTEGER DEFAULT 0",
        "error_type": "TEXT DEFAULT NULL",
        "cache_creation_tokens": "INTEGER DEFAULT 0",
        "parent_instance_id": "INTEGER DEFAULT NULL",
    }

    for col, dtype in new_columns.items():
        if col not in columns:
            conn.execute(f"ALTER TABLE token_usage ADD COLUMN {col} {dtype}")

    # Add indexes for new fields
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_token_usage_parent ON token_usage(parent_instance_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_error ON token_usage(is_error)")


def rollback(conn):
    pass


steps = [step(apply, rollback)]
