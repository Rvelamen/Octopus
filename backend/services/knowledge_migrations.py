"""Lightweight schema migration runner for SQLite knowledge databases."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from loguru import logger


MigrationFunc = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    id: int
    name: str
    apply: MigrationFunc


class MigrationRunner:
    """Run pending migrations for a SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._migrations: list[Migration] = []

    def register(self, migration_id: int, name: str, func: MigrationFunc) -> "MigrationRunner":
        """Register a migration. IDs must be strictly increasing."""
        if self._migrations and migration_id <= self._migrations[-1].id:
            raise ValueError(f"Migration IDs must increase. Got {migration_id} after {self._migrations[-1].id}")
        self._migrations.append(Migration(id=migration_id, name=name, apply=func))
        return self

    def run(self) -> None:
        """Ensure migration tracking table exists and run pending migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            applied = {
                row[0] for row in conn.execute("SELECT id FROM _schema_migrations").fetchall()
            }

            for migration in self._migrations:
                if migration.id in applied:
                    continue
                logger.info(f"Applying migration {migration.id} '{migration.name}' to {self.db_path.name}")
                try:
                    migration.apply(conn)
                    conn.execute(
                        "INSERT INTO _schema_migrations (id, name, applied_at) VALUES (?, ?, ?)",
                        (migration.id, migration.name, datetime.now().isoformat()),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration {migration.id} failed: {e}")
                    raise


# ---------------------------------------------------------------------------
# Knowledge index migrations
# ---------------------------------------------------------------------------


def _migration_001_create_initial_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS _schema_version (
            key TEXT PRIMARY KEY,
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT DEFAULT 'note' CHECK (type IN ('note', 'document')),
            source_path TEXT,
            mtime REAL NOT NULL,
            word_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content TEXT
        );

        CREATE TABLE IF NOT EXISTS knowledge_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_path TEXT NOT NULL,
            to_title TEXT NOT NULL,
            to_path TEXT,
            link_type TEXT DEFAULT 'outgoing',
            FOREIGN KEY (from_path) REFERENCES knowledge_nodes(path) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_links_from ON knowledge_links(from_path);
        CREATE INDEX IF NOT EXISTS idx_links_to ON knowledge_links(to_path);
        CREATE INDEX IF NOT EXISTS idx_links_resolved ON knowledge_links(to_path) WHERE to_path IS NOT NULL;

        CREATE TABLE IF NOT EXISTS knowledge_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_node_tags (
            tag_id INTEGER NOT NULL,
            node_path TEXT NOT NULL,
            PRIMARY KEY (tag_id, node_path),
            FOREIGN KEY (tag_id) REFERENCES knowledge_tags(id) ON DELETE CASCADE,
            FOREIGN KEY (node_path) REFERENCES knowledge_nodes(path) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_node_tags_path ON knowledge_node_tags(node_path);
        CREATE INDEX IF NOT EXISTS idx_node_tags_tag ON knowledge_node_tags(tag_id);

        -- FTS5 full-text search for knowledge nodes
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_nodes_fts USING fts5(
            title,
            content,
            content='knowledge_nodes',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 1'
        );

        CREATE TRIGGER IF NOT EXISTS knowledge_nodes_fts_insert
        AFTER INSERT ON knowledge_nodes
        BEGIN
            INSERT INTO knowledge_nodes_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS knowledge_nodes_fts_delete
        AFTER DELETE ON knowledge_nodes
        BEGIN
            INSERT INTO knowledge_nodes_fts(knowledge_nodes_fts, rowid, title, content)
            VALUES ('delete', old.rowid, old.title, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS knowledge_nodes_fts_update
        AFTER UPDATE ON knowledge_nodes
        BEGIN
            INSERT INTO knowledge_nodes_fts(knowledge_nodes_fts, rowid, title, content)
            VALUES ('delete', old.rowid, old.title, old.content);
            INSERT INTO knowledge_nodes_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS trg_cleanup_orphan_tags
        AFTER DELETE ON knowledge_node_tags
        BEGIN
            DELETE FROM knowledge_tags
            WHERE id = OLD.tag_id
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_node_tags WHERE tag_id = OLD.tag_id
              );
        END;

        INSERT OR REPLACE INTO _schema_version (key, version) VALUES ('knowledge_index', 1);
        """
    )


def _migration_002_add_orphan_tag_trigger(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_cleanup_orphan_tags
        AFTER DELETE ON knowledge_node_tags
        BEGIN
            DELETE FROM knowledge_tags
            WHERE id = OLD.tag_id
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_node_tags WHERE tag_id = OLD.tag_id
              );
        END;
        """
    )


def _migration_003_add_document_meta(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_documents_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256 TEXT UNIQUE NOT NULL,
            source_type TEXT,
            title TEXT,
            authors TEXT,
            year INTEGER,
            venue TEXT,
            doi TEXT,
            url TEXT,
            summary TEXT,
            page_count INTEGER,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_doc_meta_sha256 ON knowledge_documents_meta(sha256);
        CREATE INDEX IF NOT EXISTS idx_doc_meta_title ON knowledge_documents_meta(title);
        """
    )


def _migration_004_add_vault_column(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE knowledge_nodes ADD COLUMN vault TEXT DEFAULT 'default'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_vault ON knowledge_nodes(vault)")
    conn.commit()


def run_knowledge_index_migrations(db_path: Path) -> None:
    runner = MigrationRunner(db_path)
    runner.register(1, "create_initial_schema", _migration_001_create_initial_schema)
    runner.register(2, "add_orphan_tag_trigger", _migration_002_add_orphan_tag_trigger)
    runner.register(3, "add_document_meta", _migration_003_add_document_meta)
    runner.register(4, "add_vault_column", _migration_004_add_vault_column)
    runner.run()


# ---------------------------------------------------------------------------
# Distill task queue migrations
# ---------------------------------------------------------------------------


def _migration_001_create_distill_queue(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_distill_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            source_path TEXT NOT NULL,
            prompt TEXT NOT NULL,
            output_path TEXT,
            template TEXT NOT NULL DEFAULT 'custom',
            status TEXT NOT NULL DEFAULT 'pending',
            stage TEXT NOT NULL DEFAULT 'pending',
            message TEXT NOT NULL DEFAULT '',
            progress REAL NOT NULL DEFAULT 0.0,
            result_path TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_distill_status ON knowledge_distill_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_distill_created ON knowledge_distill_tasks(created_at DESC);

        CREATE TABLE IF NOT EXISTS knowledge_distill_task_iterations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            iteration_num INTEGER NOT NULL,
            reasoning TEXT,
            tools TEXT NOT NULL DEFAULT '[]',
            token_usage TEXT,
            duration REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES knowledge_distill_tasks(id) ON DELETE CASCADE,
            UNIQUE(task_id, iteration_num)
        );

        CREATE INDEX IF NOT EXISTS idx_iter_task ON knowledge_distill_task_iterations(task_id);
        CREATE INDEX IF NOT EXISTS idx_iter_task_num ON knowledge_distill_task_iterations(task_id, iteration_num);
        """
    )


def _migration_002_add_unique_iteration_constraint(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_iter_task_num_unique
        ON knowledge_distill_task_iterations(task_id, iteration_num)
        """
    )


def _migration_003_add_vault_column_to_distill_tasks(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE knowledge_distill_tasks ADD COLUMN vault TEXT DEFAULT 'default'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_distill_vault ON knowledge_distill_tasks(vault)")
    conn.commit()


def run_distill_queue_migrations(db_path: Path) -> None:
    runner = MigrationRunner(db_path)
    runner.register(1, "create_distill_queue", _migration_001_create_distill_queue)
    runner.register(2, "add_unique_iteration_constraint", _migration_002_add_unique_iteration_constraint)
    runner.register(3, "add_vault_column_to_distill_tasks", _migration_003_add_vault_column_to_distill_tasks)
    runner.run()
