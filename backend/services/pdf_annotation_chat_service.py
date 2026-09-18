"""PDF annotation chat service.

Each session is permanently bound to a single library_annotations row (FK
ON DELETE CASCADE). Tables live in app.db (see migration 021).
"""

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.data.database import Database


@dataclass
class PdfAnnotationChatSession:
    id: int
    item_id: int | None
    pdf_path: str | None
    annotation_id: int
    title: str
    agent_config_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class PdfAnnotationChatMessage:
    id: int
    session_id: int
    role: str
    content: str
    page_number: int | None
    selected_text: str | None
    metadata: dict[str, Any]
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    created_at: datetime | None


class PdfAnnotationChatService:
    """Service for annotation-bound PDF chat sessions and messages.

    NOTE: Chat tables live in the SAME SQLite file as `library_annotations`
    (the workspace-scoped `.knowledge_index.db`), so the chat session's
    FOREIGN KEY to `library_annotations.id` resolves correctly. The handler
    passes the `LibraryEngine`'s db_path so we share its connection pool.
    """

    def __init__(self, db: Database | Path | str | None = None):
        # Three acceptable inputs:
        #   - Database instance (legacy / app.db) — kept for unit tests
        #   - Path / str to a sqlite file — we open our own connection here
        #     so the FK to library_annotations resolves.
        if isinstance(db, Database):
            self.db = db
            self._owns_connection = False
        else:
            self.db_path = Path(db) if db is not None else Path(
                Path.home() / ".octopus" / "app.db"
            )
            import sqlite3 as _sqlite3
            self._local_conn = _sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._local_conn.row_factory = _sqlite3.Row
            self._local_conn.execute("PRAGMA foreign_keys = ON")
            self._local_conn.execute("PRAGMA journal_mode = WAL")
            self._owns_connection = True
        self._ensure_schema()

    def _get_connection(self):
        """Return a sqlite3 connection (either our own or the wrapper's).

        Used as `with self._get_conn() as conn: ...`. When we own the
        connection we still commit on success / rollback on error, mirroring
        the Database wrapper's behavior.
        """
        import contextlib
        if self._owns_connection:
            @contextlib.contextmanager
            def _ctx():
                try:
                    yield self._local_conn
                    self._local_conn.commit()
                except Exception:
                    self._local_conn.rollback()
                    raise
            return _ctx()
        return self.db._get_connection()

    def _ensure_schema(self) -> None:
        """Idempotently create the chat tables and indexes on the shared db."""
        conn = self._local_conn if self._owns_connection else None
        if conn is not None:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pdf_annotation_chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    pdf_path TEXT,
                    annotation_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Annotation Chat',
                    agent_config_id INTEGER,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now','localtime'))
                );
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_annot
                    ON pdf_annotation_chat_sessions(annotation_id);
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_item
                    ON pdf_annotation_chat_sessions(item_id);

                CREATE TABLE IF NOT EXISTS pdf_annotation_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    page_number INTEGER,
                    selected_text TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (session_id) REFERENCES pdf_annotation_chat_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_msgs_session
                    ON pdf_annotation_chat_messages(session_id);
            """)
            conn.commit()
            return

        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pdf_annotation_chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    pdf_path TEXT,
                    annotation_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Annotation Chat',
                    agent_config_id INTEGER,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now','localtime'))
                );
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_annot
                    ON pdf_annotation_chat_sessions(annotation_id);
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_sessions_item
                    ON pdf_annotation_chat_sessions(item_id);

                CREATE TABLE IF NOT EXISTS pdf_annotation_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    page_number INTEGER,
                    selected_text TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (session_id) REFERENCES pdf_annotation_chat_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_pdf_annot_chat_msgs_session
                    ON pdf_annotation_chat_messages(session_id);
            """)

    # ── Sessions ──

    def list_sessions(
        self,
        annotation_id: int | None = None,
        item_id: int | None = None,
        pdf_path: str | None = None,
    ) -> list[PdfAnnotationChatSession]:
        with self._get_connection() as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if annotation_id is not None:
                clauses.append("annotation_id = ?")
                params.append(annotation_id)
            if item_id is not None:
                clauses.append("item_id = ?")
                params.append(item_id)
            if pdf_path is not None:
                clauses.append("pdf_path = ?")
                params.append(pdf_path)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM pdf_annotation_chat_sessions {where} "
                "ORDER BY updated_at DESC",
                tuple(params),
            ).fetchall()
            return [self._row_to_session(row) for row in rows]

    def get_session(self, session_id: int) -> PdfAnnotationChatSession | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pdf_annotation_chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None

    def create_session(
        self,
        annotation_id: int,
        title: str = "Annotation Chat",
        item_id: int | None = None,
        pdf_path: str | None = None,
        agent_config_id: int | None = None,
    ) -> PdfAnnotationChatSession:
        if annotation_id is None:
            raise ValueError("annotation_id is required for annotation chat sessions")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pdf_annotation_chat_sessions
                  (item_id, pdf_path, annotation_id, title, agent_config_id,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?,
                        datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (item_id, pdf_path, annotation_id, title, agent_config_id),
            )
            session_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM pdf_annotation_chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row)

    def update_session_title(self, session_id: int, title: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE pdf_annotation_chat_sessions SET title = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (title, session_id),
            )

    def touch_session(self, session_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE pdf_annotation_chat_sessions "
                "SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (session_id,),
            )

    def delete_session(self, session_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM pdf_annotation_chat_sessions WHERE id = ?", (session_id,)
            )

    # ── Messages ──

    def list_messages(self, session_id: int) -> list[PdfAnnotationChatMessage]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM pdf_annotation_chat_messages WHERE session_id = ? "
                "ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
            return [self._row_to_message(row) for row in rows]

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        page_number: int | None = None,
        selected_text: str | None = None,
        metadata: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> PdfAnnotationChatMessage:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pdf_annotation_chat_messages
                  (session_id, role, content, page_number, selected_text,
                   metadata, tool_calls, tool_call_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                """,
                (
                    session_id,
                    role,
                    content,
                    page_number,
                    selected_text,
                    json.dumps(metadata or {}),
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    tool_call_id,
                ),
            )
            msg_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM pdf_annotation_chat_messages WHERE id = ?", (msg_id,)
            ).fetchone()
            self.touch_session(session_id)
            return self._row_to_message(row)

    def delete_message(self, message_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM pdf_annotation_chat_messages WHERE id = ?", (message_id,)
            )

    # ── Helpers ──

    def _row_to_session(self, row) -> PdfAnnotationChatSession:
        return PdfAnnotationChatSession(
            id=row["id"],
            item_id=row["item_id"],
            pdf_path=row["pdf_path"],
            annotation_id=row["annotation_id"],
            title=row["title"],
            agent_config_id=row["agent_config_id"],
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(str(row["updated_at"])) if row["updated_at"] else None
            ),
        )

    def _row_to_message(self, row) -> PdfAnnotationChatMessage:
        meta: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            meta = json.loads(row["metadata"] or "{}")
        tool_calls = None
        try:
            raw = row["tool_calls"]
            if raw is not None and raw != "":
                tool_calls = json.loads(raw)
        except Exception:
            pass
        return PdfAnnotationChatMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            page_number=row["page_number"],
            selected_text=row["selected_text"],
            metadata=meta,
            tool_calls=tool_calls,
            tool_call_id=row["tool_call_id"] if row["tool_call_id"] else None,
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
        )
