"""Add persistent book-character room timeout preferences in seconds."""

import sqlite3

from yoyo import step

from backend.data.schema.agent import ensure_book_room_timeout_columns


def apply(conn: sqlite3.Connection) -> None:
    """Add missing columns without replacing existing defaults or preferences."""
    ensure_book_room_timeout_columns(conn)


def rollback(conn: sqlite3.Connection) -> None:
    """Keep additive preference columns to preserve saved values on rollback."""


steps = [step(apply, rollback)]
