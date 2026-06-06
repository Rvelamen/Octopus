"""PDF Chat service for session and message management."""

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.data.database import Database


@dataclass
class PdfChatSession:
    id: int
    item_id: int | None
    pdf_path: str | None
    title: str
    agent_config_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class PdfChatMessage:
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


class PdfChatService:
    """Service for PDF chat session and message operations."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    # ── Sessions ──

    def list_sessions(
        self, item_id: int | None = None, pdf_path: str | None = None
    ) -> list[PdfChatSession]:
        """List sessions for a given item or pdf_path."""
        with self.db._get_connection() as conn:
            if item_id is not None:
                rows = conn.execute(
                    "SELECT * FROM pdf_chat_sessions WHERE item_id = ? ORDER BY updated_at DESC",
                    (item_id,),
                ).fetchall()
            elif pdf_path is not None:
                rows = conn.execute(
                    "SELECT * FROM pdf_chat_sessions WHERE pdf_path = ? ORDER BY updated_at DESC",
                    (pdf_path,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pdf_chat_sessions ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_session(row) for row in rows]

    def get_session(self, session_id: int) -> PdfChatSession | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pdf_chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None

    def create_session(
        self,
        title: str = "New Chat",
        item_id: int | None = None,
        pdf_path: str | None = None,
        agent_config_id: int | None = None,
    ) -> PdfChatSession:
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pdf_chat_sessions (item_id, pdf_path, title, agent_config_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (item_id, pdf_path, title, agent_config_id),
            )
            session_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM pdf_chat_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row)

    def update_session_title(self, session_id: int, title: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE pdf_chat_sessions SET title = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (title, session_id),
            )

    def touch_session(self, session_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE pdf_chat_sessions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (session_id,),
            )

    def delete_session(self, session_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM pdf_chat_sessions WHERE id = ?", (session_id,))

    # ── Messages ──

    def list_messages(self, session_id: int) -> list[PdfChatMessage]:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM pdf_chat_messages WHERE session_id = ? ORDER BY created_at ASC",
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
    ) -> PdfChatMessage:
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pdf_chat_messages
                (session_id, role, content, page_number, selected_text, metadata, tool_calls, tool_call_id, created_at)
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
            row = conn.execute("SELECT * FROM pdf_chat_messages WHERE id = ?", (msg_id,)).fetchone()
            self.touch_session(session_id)
            return self._row_to_message(row)

    def delete_message(self, message_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM pdf_chat_messages WHERE id = ?", (message_id,))

    # ── Helpers ──

    def _row_to_session(self, row) -> PdfChatSession:
        return PdfChatSession(
            id=row["id"],
            item_id=row["item_id"],
            pdf_path=row["pdf_path"],
            title=row["title"],
            agent_config_id=row["agent_config_id"],
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(str(row["updated_at"])) if row["updated_at"] else None
            ),
        )

    def _row_to_message(self, row) -> PdfChatMessage:
        meta = {}
        with contextlib.suppress(Exception):
            meta = json.loads(row["metadata"] or "{}")
        tool_calls = None
        try:
            raw = row["tool_calls"]
            if raw is not None and raw != "":
                tool_calls = json.loads(raw)
        except Exception:
            pass
        return PdfChatMessage(
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
