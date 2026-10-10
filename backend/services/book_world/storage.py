"""Short-lived, foreign-key enabled connections for one fixed workspace."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Commit a successful operation and close its private connection."""
    db = sqlite3.connect(str(db_path), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    try:
        with db:
            yield db
    finally:
        db.close()


def apply_source_schema(db: sqlite3.Connection) -> None:
    """Register only the source tables for the first incremental migration."""
    db.executescript(Path(__file__).with_name("source_schema.sql").read_text(encoding="utf-8"))


def disable_item_sources(db: sqlite3.Connection, item_id: int) -> None:
    """Fence prepared sources before the legacy item/file deletion begins."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='book_books'").fetchone():
        return
    db.execute(
        "UPDATE book_source_versions SET lifecycle_state='unavailable' WHERE book_id IN "
        "(SELECT id FROM book_books WHERE library_item_id=?)",
        (item_id,),
    )
    db.execute(
        "UPDATE book_books SET lifecycle_state='purging',removed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
        "WHERE library_item_id=?",
        (item_id,),
    )
