"""Library Chat service for session and message management."""

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.data.database import Database


@dataclass
class LibraryChatSession:
    id: int
    scope_type: str
    scope_value: str
    title: str
    agent_config_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class LibraryChatMessage:
    id: int
    session_id: int
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    metadata: dict[str, Any]
    created_at: datetime | None


class LibraryChatService:
    """Service for Library chat session and message operations."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    # ── Sessions ──

    def list_sessions(
        self, scope_type: str | None = None, scope_value: str | None = None
    ) -> list[LibraryChatSession]:
        """List sessions, optionally filtered by scope."""
        with self.db._get_connection() as conn:
            if scope_type is not None and scope_value is not None:
                rows = conn.execute(
                    "SELECT * FROM library_chat_sessions WHERE scope_type = ? AND scope_value = ? ORDER BY updated_at DESC",
                    (scope_type, scope_value),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM library_chat_sessions ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_session(row) for row in rows]

    def get_session(self, session_id: int) -> LibraryChatSession | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM library_chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None

    def create_session(
        self,
        scope_type: str = "collection",
        scope_value: str = "",
        title: str = "New Chat",
        agent_config_id: int | None = None,
    ) -> LibraryChatSession:
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO library_chat_sessions (scope_type, scope_value, title, agent_config_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (scope_type, scope_value, title, agent_config_id),
            )
            session_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM library_chat_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row)

    def update_session_title(self, session_id: int, title: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE library_chat_sessions SET title = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (title, session_id),
            )

    def touch_session(self, session_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE library_chat_sessions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (session_id,),
            )

    def delete_session(self, session_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM library_chat_sessions WHERE id = ?", (session_id,))

    # ── Messages ──

    def list_messages(self, session_id: int) -> list[LibraryChatMessage]:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM library_chat_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            return [self._row_to_message(row) for row in rows]

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> LibraryChatMessage:
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO library_chat_messages
                (session_id, role, content, metadata, tool_calls, tool_call_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                """,
                (
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}),
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    tool_call_id,
                ),
            )
            msg_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM library_chat_messages WHERE id = ?", (msg_id,)
            ).fetchone()
            self.touch_session(session_id)
            return self._row_to_message(row)

    def delete_message(self, message_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM library_chat_messages WHERE id = ?", (message_id,))

    # ── Helpers ──

    def _row_to_session(self, row) -> LibraryChatSession:
        return LibraryChatSession(
            id=row["id"],
            scope_type=row["scope_type"],
            scope_value=row["scope_value"],
            title=row["title"],
            agent_config_id=row["agent_config_id"],
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(str(row["updated_at"])) if row["updated_at"] else None
            ),
        )

    def _row_to_message(self, row) -> LibraryChatMessage:
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
        return LibraryChatMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            tool_calls=tool_calls,
            tool_call_id=row["tool_call_id"] if row["tool_call_id"] else None,
            metadata=meta,
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
        )
