"""Add is_builtin column to subagents table."""

from yoyo import step


def apply(conn):
    cursor = conn.execute("PRAGMA table_info(subagents)")
    columns = [row[1] for row in cursor.fetchall()]

    if columns and "is_builtin" not in columns:
        conn.execute("""
            ALTER TABLE subagents
            ADD COLUMN is_builtin BOOLEAN DEFAULT 0
        """)

    # Mark existing built-in subagents
    conn.execute("""
        UPDATE subagents
        SET is_builtin = 1
        WHERE name IN ('knowledge-distiller', 'library-distiller')
    """)


def rollback(conn):
    pass


steps = [step(apply, rollback)]
