"""Subagent message storage and retrieval."""

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from backend.data.database import Database


@dataclass
class SubagentMessageRecord:
    """Subagent message record."""
    id: int
    session_instance_id: int
    subagent_id: str
    parent_tool_call_id: str
    role: str
    content: str
    message_type: str
    tool_call_id: str | None
    timestamp: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_instance_id": self.session_instance_id,
            "subagent_id": self.subagent_id,
            "parent_tool_call_id": self.parent_tool_call_id,
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "tool_call_id": self.tool_call_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class SubagentMessageRepository:
    """Repository for subagent message operations."""

    def __init__(self, db: Database):
        self.db = db

    def save_message(
        self,
        session_instance_id: int,
        subagent_id: str,
        parent_tool_call_id: str,
        role: str,
        content: str,
        message_type: str = "subagent_tool_call",
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubagentMessageRecord:
        """Save a subagent message to the database.

        Args:
            session_instance_id: The session instance ID
            subagent_id: The subagent ID
            parent_tool_call_id: The parent tool call ID (from main agent)
            role: Message role (assistant, tool, etc.)
            content: Message content
            message_type: Message type (subagent_tool_call, subagent_tool_result, etc.)
            tool_call_id: Tool call ID (if applicable)
            metadata: Additional metadata

        Returns:
            The created SubagentMessageRecord
        """
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO subagent_messages
                   (session_instance_id, subagent_id, parent_tool_call_id, role, content,
                    message_type, tool_call_id, metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (session_instance_id, subagent_id, parent_tool_call_id, role, content,
                 message_type, tool_call_id, metadata_json)
            )

            record_id = cursor.lastrowid

            row = conn.execute(
                "SELECT * FROM subagent_messages WHERE id = ?",
                (record_id,)
            ).fetchone()

            logger.debug(f"Saved subagent message: subagent={subagent_id}, "
                        f"parent_tool_call={parent_tool_call_id}, type={message_type}")

            return self._row_to_record(row)

    def get_messages_by_parent_tool_call(
        self,
        parent_tool_call_id: str
    ) -> list[SubagentMessageRecord]:
        """Get all subagent messages for a specific parent tool call.

        Args:
            parent_tool_call_id: The parent tool call ID

        Returns:
            List of SubagentMessageRecord
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM subagent_messages
                   WHERE parent_tool_call_id = ?
                   ORDER BY timestamp ASC""",
                (parent_tool_call_id,)
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def get_messages_by_subagent(
        self,
        subagent_id: str
    ) -> list[SubagentMessageRecord]:
        """Get all messages for a specific subagent.

        Args:
            subagent_id: The subagent ID

        Returns:
            List of SubagentMessageRecord
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM subagent_messages
                   WHERE subagent_id = ?
                   ORDER BY timestamp ASC""",
                (subagent_id,)
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def get_messages_by_session_instance(
        self,
        session_instance_id: int
    ) -> list[SubagentMessageRecord]:
        """Get all subagent messages for a session instance.

        Args:
            session_instance_id: The session instance ID

        Returns:
            List of SubagentMessageRecord
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM subagent_messages
                   WHERE session_instance_id = ?
                   ORDER BY timestamp ASC""",
                (session_instance_id,)
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def delete_messages_by_session_instance(
        self,
        session_instance_id: int
    ) -> int:
        """Delete all subagent messages for a session instance.

        Args:
            session_instance_id: The session instance ID

        Returns:
            Number of deleted messages
        """
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM subagent_messages WHERE session_instance_id = ?",
                (session_instance_id,)
            )
            deleted_count = cursor.rowcount
            logger.debug(f"Deleted {deleted_count} subagent messages for instance {session_instance_id}")
            return deleted_count

    def _row_to_record(self, row) -> SubagentMessageRecord:
        """Convert a database row to a SubagentMessageRecord."""
        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata for subagent message {row['id']}")
                metadata = {}

        return SubagentMessageRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            subagent_id=row["subagent_id"],
            parent_tool_call_id=row["parent_tool_call_id"],
            role=row["role"],
            content=row["content"],
            message_type=row["message_type"],
            tool_call_id=row["tool_call_id"],
            timestamp=row["timestamp"],
            metadata=metadata,
        )
