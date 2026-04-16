"""Observation / FTS5 schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_instance_id INTEGER,
            type TEXT DEFAULT 'general',
            title TEXT NOT NULL,
            narrative TEXT DEFAULT '',
            files_json TEXT DEFAULT '[]',
            concepts_json TEXT DEFAULT '[]',
            token_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
            title, narrative, concepts,
            content='observations',
            content_rowid='id'
        )
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS observations_fts_insert AFTER INSERT ON observations BEGIN
            INSERT INTO observations_fts(rowid, title, narrative, concepts)
            VALUES (new.id, new.title, new.narrative, json_extract(new.concepts_json, '$'));
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS observations_fts_update AFTER UPDATE ON observations BEGIN
            INSERT INTO observations_fts(observations_fts, rowid, title, narrative, concepts)
            VALUES ('delete', old.id, old.title, old.narrative, json_extract(old.concepts_json, '$'));
            INSERT INTO observations_fts(rowid, title, narrative, concepts)
            VALUES (new.id, new.title, new.narrative, json_extract(new.concepts_json, '$'));
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS observations_fts_delete AFTER DELETE ON observations BEGIN
            INSERT INTO observations_fts(observations_fts, rowid, title, narrative, concepts)
            VALUES ('delete', old.id, old.title, old.narrative, json_extract(old.concepts_json, '$'));
        END
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_observations_instance ON observations(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
