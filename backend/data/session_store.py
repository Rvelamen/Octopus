"""Session database models and repository."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class SessionRecord:
    """Session record data class."""
    id: int
    channel: str
    chat_id: str
    session_key: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


@dataclass
class SessionInstance:
    """Session instance for multi-session support."""
    id: int
    session_id: int
    instance_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    tts_enabled: bool = False
    tts_config: dict[str, Any] = None
    
    def __post_init__(self):
        if self.tts_config is None:
            self.tts_config = {}


@dataclass
class MessageRecord:
    """Message record data class."""
    id: int
    session_instance_id: int
    role: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any]


class SessionRepository:
    """Repository for session-related database operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    # ========== Session Operations ==========
    
    def get_or_create_session(self, channel: str, chat_id: str, 
                              metadata: dict[str, Any] | None = None) -> SessionRecord:
        """Get or create a session for the given channel and chat_id."""
        session_key = f"{channel}:{chat_id}"
        metadata = metadata or {}
        
        with self.db._get_connection() as conn:
            # Try to get existing session
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?",
                (session_key,)
            ).fetchone()
            
            if row:
                return self._row_to_session(row)
            
            # Create new session
            cursor = conn.execute(
                """INSERT INTO sessions (channel, chat_id, session_key, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (channel, chat_id, session_key, json.dumps(metadata, ensure_ascii=False))
            )
            
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            logger.info(f"Created new session: {session_key}")
            return self._row_to_session(row)
    
    def get_session(self, session_key: str) -> Optional[SessionRecord]:
        """Get session by session_key."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?",
                (session_key,)
            ).fetchone()
            
            return self._row_to_session(row) if row else None
    
    def get_session_by_id(self, session_id: int) -> Optional[SessionRecord]:
        """Get session by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            
            return self._row_to_session(row) if row else None
    
    def update_session_metadata(self, session_key: str, metadata: dict[str, Any]) -> bool:
        """Update session metadata."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE sessions
                   SET metadata = ?, updated_at = (datetime('now', 'localtime'))
                   WHERE session_key = ?""",
                (json.dumps(metadata, ensure_ascii=False), session_key)
            )
            return cursor.rowcount > 0
    
    def delete_session(self, session_key: str) -> bool:
        """Delete a session and all its instances/messages (cascade)."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_key = ?",
                (session_key,)
            )
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted session: {session_key}")
                return True
            return False
    
    # ========== Instance Operations ==========
    
    def create_instance(self, session_id: int, instance_name: str, 
                        is_active: bool = False) -> SessionInstance:
        """Create a new session instance."""
        with self.db._get_connection() as conn:
            # If setting as active, deactivate other instances first
            if is_active:
                conn.execute(
                    """UPDATE session_instances
                       SET is_active = 0, updated_at = (datetime('now', 'localtime'))
                       WHERE session_id = ?""",
                    (session_id,)
                )
            
            cursor = conn.execute(
                """INSERT INTO session_instances (session_id, instance_name, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (session_id, instance_name, is_active)
            )
            
            row = conn.execute(
                "SELECT * FROM session_instances WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            logger.info(f"Created session instance: {instance_name} for session {session_id}")
            return self._row_to_instance(row)
    
    def get_instance(self, session_id: int, instance_name: str) -> Optional[SessionInstance]:
        """Get session instance by session_id and name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM session_instances 
                   WHERE session_id = ? AND instance_name = ?""",
                (session_id, instance_name)
            ).fetchone()
            
            return self._row_to_instance(row) if row else None
    
    def get_instance_by_id(self, instance_id: int) -> Optional[SessionInstance]:
        """Get session instance by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_instances WHERE id = ?",
                (instance_id,)
            ).fetchone()
            
            return self._row_to_instance(row) if row else None
    
    def list_instances(self, session_id: int) -> list[SessionInstance]:
        """List all instances for a session."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM session_instances 
                   WHERE session_id = ?
                   ORDER BY created_at DESC""",
                (session_id,)
            ).fetchall()
            
            return [self._row_to_instance(row) for row in rows]
    
    def get_active_instance(self, session_id: int) -> Optional[SessionInstance]:
        """Get the active instance for a session."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM session_instances 
                   WHERE session_id = ? AND is_active = 1
                   LIMIT 1""",
                (session_id,)
            ).fetchone()
            
            return self._row_to_instance(row) if row else None
    
    def get_or_create_active_instance(self, session_id: int, instance_name: str = "default") -> SessionInstance:
        """Get the active instance for a session, or create one if none exists."""
        # Try to get existing active instance
        instance = self.get_active_instance(session_id)
        if instance:
            return instance
        
        # Try to get instance by name
        instance = self.get_instance(session_id, instance_name)
        if instance:
            # Set it as active
            self.set_active_instance(session_id, instance.id)
            return instance
        
        # Create new instance as active
        return self.create_instance(session_id, instance_name, is_active=True)
    
    def set_active_instance(self, session_id: int, instance_id: int) -> bool:
        """Set an instance as active (deactivate all other instances globally)."""
        with self.db._get_connection() as conn:
            # Deactivate ALL instances globally
            conn.execute(
                """UPDATE session_instances
                   SET is_active = 0, updated_at = (datetime('now', 'localtime'))"""
            )

            # Activate the specified instance
            cursor = conn.execute(
                """UPDATE session_instances
                   SET is_active = 1, updated_at = (datetime('now', 'localtime'))
                   WHERE id = ? AND session_id = ?""",
                (instance_id, session_id)
            )

            return cursor.rowcount > 0
    
    def delete_instance(self, instance_id: int) -> bool:
        """Delete a session instance and all its messages (cascade)."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM session_instances WHERE id = ?",
                (instance_id,)
            )
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted session instance: {instance_id}")
                return True
            return False
    
    def update_instance_tts_config(
        self,
        instance_id: int,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None
    ) -> bool:
        """Update TTS config for a session instance.
        
        Args:
            instance_id: Session instance ID
            enabled: TTS enabled status (None to keep current)
            config: TTS config dict (None to keep current, partial update supported)
            
        Returns:
            True if update successful
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT tts_enabled, tts_config FROM session_instances WHERE id = ?",
                (instance_id,)
            ).fetchone()
            
            if not row:
                logger.warning(f"Instance {instance_id} not found for TTS config update")
                return False
            
            current_enabled = bool(row["tts_enabled"]) if row["tts_enabled"] is not None else False
            current_config = {}
            if row["tts_config"]:
                try:
                    current_config = json.loads(row["tts_config"])
                except (json.JSONDecodeError, TypeError):
                    current_config = {}
            
            new_enabled = enabled if enabled is not None else current_enabled
            new_config = {**current_config, **config} if config else current_config
            
            logger.info(f"Updating TTS config for instance {instance_id}: enabled={new_enabled}, config={new_config}")
            
            conn.execute(
                """UPDATE session_instances 
                   SET tts_enabled = ?, tts_config = ?, updated_at = (datetime('now', 'localtime'))
                   WHERE id = ?""",
                (1 if new_enabled else 0, json.dumps(new_config, ensure_ascii=False), instance_id)
            )
            
            return True
    
    # ========== Message Operations ==========
    
    def add_message(self, session_instance_id: int, role: str, content: str,
                    metadata: dict[str, Any] | None = None) -> MessageRecord:
        """Add a message to a session instance."""
        metadata = metadata or {}
        
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO messages (session_instance_id, role, content, metadata, timestamp)
                   VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
                (session_instance_id, role, content, json.dumps(metadata, ensure_ascii=False))
            )
            
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            # Update session updated_at
            conn.execute(
                """UPDATE sessions SET updated_at = (datetime('now', 'localtime'))
                   WHERE id = (SELECT session_id FROM session_instances WHERE id = ?)""",
                (session_instance_id,)
            )
            
            return self._row_to_message(row)
    
    def get_messages(self, session_instance_id: int, limit: int = 100,
                     offset: int = 0) -> list[MessageRecord]:
        """Get messages for a session instance."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages 
                   WHERE session_instance_id = ?
                   ORDER BY timestamp ASC
                   LIMIT ? OFFSET ?""",
                (session_instance_id, limit, offset)
            ).fetchall()
            
            return [self._row_to_message(row) for row in rows]
    
    def get_recent_messages(self, session_instance_id: int, count: int = 10) -> list[MessageRecord]:
        """Get recent messages for a session instance."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages 
                   WHERE session_instance_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (session_instance_id, count)
            ).fetchall()
            
            # Reverse to get chronological order
            return [self._row_to_message(row) for row in reversed(rows)]
    
    def get_message_count(self, session_instance_id: int) -> int:
        """Get message count for a session instance."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as count FROM messages 
                   WHERE session_instance_id = ?""",
                (session_instance_id,)
            ).fetchone()
            
            return row["count"] if row else 0
    
    def delete_message(self, message_id: int) -> bool:
        """Delete a message."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (message_id,)
            )
            return cursor.rowcount > 0
    
    def clear_instance_messages(self, session_instance_id: int) -> int:
        """Clear all messages from a session instance."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE session_instance_id = ?",
                (session_instance_id,)
            )
            deleted_count = cursor.rowcount
            logger.info(f"Cleared {deleted_count} messages from instance {session_instance_id}")
            return deleted_count
    
    def update_latest_message_tts(
        self, 
        session_instance_id: int, 
        role: str,
        tts_data: dict[str, Any]
    ) -> bool:
        """Update the latest message's metadata with TTS audio data.
        
        Args:
            session_instance_id: The session instance ID
            role: The role of the message (e.g., "assistant")
            tts_data: TTS audio data dict with keys: audio, format, text, duration_ms
            
        Returns:
            True if updated successfully
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT id, metadata FROM messages 
                   WHERE session_instance_id = ? AND role = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (session_instance_id, role)
            ).fetchone()
            
            if not row:
                logger.warning(f"No {role} message found for instance {session_instance_id}")
                return False
            
            message_id = row["id"]
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            metadata["tts"] = tts_data
            
            cursor = conn.execute(
                "UPDATE messages SET metadata = ? WHERE id = ?",
                (json.dumps(metadata, ensure_ascii=False), message_id)
            )
            
            logger.debug(f"Updated message {message_id} with TTS data")
            return cursor.rowcount > 0
    
    # ========== Context Compression Methods ==========
    
    def update_compressed_context(
        self,
        instance_id: int,
        summary: str,
        compressed_count: int,
        last_compressed_turn: int
    ) -> bool:
        """Update compressed context for a session instance.
        
        Args:
            instance_id: The session instance ID
            summary: The compressed context summary
            compressed_count: Total number of compressed messages
            last_compressed_turn: The turn number when last compressed
            
        Returns:
            True if updated successfully
        """
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE session_instances 
                   SET compressed_context = ?,
                       compressed_message_count = ?,
                       last_compressed_turn = ?,
                       compressed_at = datetime('now', 'localtime'),
                       updated_at = datetime('now', 'localtime')
                   WHERE id = ?""",
                (summary, compressed_count, last_compressed_turn, instance_id)
            )
            logger.info(f"Updated compressed context for instance {instance_id}: {compressed_count} messages, turn {last_compressed_turn}")
            return cursor.rowcount > 0
    
    def get_compressed_context(self, instance_id: int) -> dict | None:
        """Get compressed context for a session instance.
        
        Args:
            instance_id: The session instance ID
            
        Returns:
            Dict with summary, compressed_count, last_compressed_turn, compressed_at or None
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT compressed_context, compressed_message_count, 
                          last_compressed_turn, compressed_at
                   FROM session_instances 
                   WHERE id = ?""",
                (instance_id,)
            ).fetchone()
            
            if row and row["compressed_context"]:
                return {
                    "summary": row["compressed_context"],
                    "compressed_count": row["compressed_message_count"] or 0,
                    "last_compressed_turn": row["last_compressed_turn"] or 0,
                    "compressed_at": row["compressed_at"]
                }
            return None
    
    def get_uncompressed_messages(self, instance_id: int, limit: int = 100, offset: int = 0) -> list:
        """Get uncompressed messages for a session instance.
        
        Args:
            instance_id: The session instance ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List of MessageRecord that are not compressed
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages 
                   WHERE session_instance_id = ? AND (is_compressed = 0 OR is_compressed IS NULL)
                   ORDER BY timestamp ASC
                   LIMIT ? OFFSET ?""",
                (instance_id, limit, offset)
            ).fetchall()
            
            return [self._row_to_message(row) for row in rows]
    
    def mark_messages_compressed(self, instance_id: int, message_ids: list[int]) -> int:
        """Mark messages as compressed.
        
        Args:
            instance_id: The session instance ID
            message_ids: List of message IDs to mark as compressed
            
        Returns:
            Number of messages marked
        """
        if not message_ids:
            return 0
            
        with self.db._get_connection() as conn:
            placeholders = ",".join("?" * len(message_ids))
            cursor = conn.execute(
                f"""UPDATE messages 
                   SET is_compressed = 1
                   WHERE session_instance_id = ? AND id IN ({placeholders})""",
                [instance_id] + list(message_ids)
            )
            marked_count = cursor.rowcount
            logger.info(f"Marked {marked_count} messages as compressed for instance {instance_id}")
            return marked_count
    
    def get_message_count_by_compression(self, instance_id: int, is_compressed: bool = False) -> int:
        """Get message count by compression status.
        
        Args:
            instance_id: The session instance ID
            is_compressed: Whether to count compressed or uncompressed messages
            
        Returns:
            Number of messages
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as count FROM messages 
                   WHERE session_instance_id = ? AND (is_compressed = ? OR (is_compressed IS NULL AND ? = 0))""",
                (instance_id, 1 if is_compressed else 0, 1 if is_compressed else 0)
            ).fetchone()
            
            return row["count"] if row else 0
    
    # ========== Helper Methods ==========
    
    def _row_to_session(self, row) -> SessionRecord:
        """Convert database row to SessionRecord."""
        return SessionRecord(
            id=row["id"],
            channel=row["channel"],
            chat_id=row["chat_id"],
            session_key=row["session_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"])
        )
    
    def _row_to_instance(self, row) -> SessionInstance:
        """Convert database row to SessionInstance."""
        tts_config = {}
        if "tts_config" in row.keys() and row["tts_config"]:
            try:
                tts_config = json.loads(row["tts_config"])
            except (json.JSONDecodeError, TypeError):
                tts_config = {}
        
        return SessionInstance(
            id=row["id"],
            session_id=row["session_id"],
            instance_name=row["instance_name"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            tts_enabled=bool(row["tts_enabled"]) if "tts_enabled" in row.keys() else False,
            tts_config=tts_config
        )
    
    def _row_to_message(self, row) -> MessageRecord:
        """Convert database row to MessageRecord."""
        return MessageRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            role=row["role"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"])
        )
