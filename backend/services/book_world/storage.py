"""Short-lived, foreign-key enabled connections for one fixed workspace."""

import hashlib
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .search_terms import register_search_functions


def workspace_identity(root: Path) -> str:
    """Identify a canonical workspace without exposing an absolute path."""
    return hashlib.sha256(os.path.normcase(str(root.resolve())).encode("utf-8")).hexdigest()


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Commit a successful operation and close its private connection."""
    db = sqlite3.connect(str(db_path), timeout=10)
    db.row_factory = sqlite3.Row
    register_search_functions(db)
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


def disable_item_sources(db: sqlite3.Connection, item_id: int, *, workspace_id: str) -> None:
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
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='book_builds'").fetchone():
        db.execute(
            "UPDATE book_builds SET lifecycle_state='unavailable',cancel_requested=1,"
            "lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL "
            "WHERE book_id IN (SELECT id FROM book_books WHERE library_item_id=?)",
            (item_id,),
        )
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='book_expression_sets'").fetchone():
        db.execute(
            "UPDATE book_expression_sets SET lifecycle_state='unavailable',cancel_requested=1,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE book_id IN (SELECT id FROM book_books WHERE library_item_id=?)",
            (item_id,),
        )
    from .lifecycle import fence_book_rooms

    books = db.execute("SELECT id FROM book_books WHERE library_item_id=?", (item_id,)).fetchall()
    for book in books:
        fence_book_rooms(db, book["id"], workspace_id)
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='book_source_purges'").fetchone():
            row = db.execute(
                "SELECT library_path FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            db.execute(
                "INSERT OR IGNORE INTO book_source_purges(book_id,library_item_id,library_rel_path) VALUES (?,?,?)",
                (book["id"], item_id, row["library_path"]),
            )
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='book_auto_imports'").fetchone():
        db.execute(
            "UPDATE book_auto_imports SET status='cancelled',generation=generation+1,error_code='source_removed',error_detail=NULL WHERE library_item_id=? OR book_id IN (SELECT id FROM book_books WHERE library_item_id=?)",
            (item_id, item_id),
        )
