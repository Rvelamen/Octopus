"""Session management for conversation history with multi-session support."""

from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from backend.data import Database, SessionRepository, SessionRecord, SessionInstance


@dataclass
class Session:
    """
    A conversation session using SQLite database backend.
    """
    
    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Context compression fields (persisted to database)
    compressed_context: str = ""
    compressed_message_count: int = 0
    last_compressed_turn: int = 0
    
    # New fields for multi-session support
    session_record: SessionRecord | None = None
    active_instance: SessionInstance | None = None
    
    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()
    
    def get_turn_count(self) -> int:
        """Get the number of conversation turns (user + assistant pairs)."""
        user_count = sum(1 for m in self.messages if m.get("role") == "user")
        return user_count
    
    def set_compressed_context(self, compressed: str) -> None:
        """Set the compressed context summary."""
        self.compressed_context = compressed
        self.last_compressed_turn = self.get_turn_count()
        self.updated_at = datetime.now()
    
    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.
        
        Args:
            max_messages: Maximum messages to return.
        
        Returns:
            List of messages in LLM format, including tool_calls and tool_call_id.
        """
        result = []
        
        # Add compressed context if available
        if self.compressed_context:
            result.append({
                "role": "system",
                "content": f"# Previous Conversation Summary\n\n{self.compressed_context}"
            })
        
        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        # Convert to LLM format, preserving tool-related fields for all providers
        for m in recent:
            msg = {"role": m["role"], "content": m.get("content", "")}

            # Preserve tool_calls (OpenAI format) for assistant messages
            if m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]

            # Preserve tool_use (Anthropic format) for assistant messages
            if m.get("tool_use"):
                msg["tool_use"] = m["tool_use"]

            # Preserve tool_call_id (OpenAI format) for tool messages
            if m.get("tool_call_id"):
                msg["tool_call_id"] = m["tool_call_id"]

            # Preserve tool_use_id (Anthropic format) for tool messages
            if m.get("tool_use_id"):
                msg["tool_use_id"] = m["tool_use_id"]

            # Preserve name for tool messages (optional but helpful)
            if m.get("name"):
                msg["name"] = m["name"]

            result.append(msg)
        
        return result
    
    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions with multi-session support.
    
    Uses SQLite database for storage with the following hierarchy:
    - Session: channel:chat_id level (e.g., feishu:ou_abc123)
    - SessionInstance: multiple instances per session (multi-session support)
    - Messages: stored per instance
    """
    
    def __init__(self, workspace: Path, db: Database | None = None):
        self.workspace = workspace
        self._cache: dict[str, Session] = {}
        
        # Initialize database - use unified database
        if db is None:
            db = Database()
        self.db = SessionRepository(db)
        logger.info(f"SessionManager initialized with unified database: {db.db_path}")
    
    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.
        
        Args:
            key: Session key (channel:chat_id).
        
        Returns:
            The session object.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        return self._get_or_create_db(key)
    
    def _get_or_create_db(self, key: str) -> Session:
        """Get or create session using database."""
        parts = key.split(":", 1)
        if len(parts) != 2:
            logger.error(f"Invalid session key format: {key}")
            return Session(key=key)
        
        channel, chat_id = parts
        
        # Get or create session record
        session_record = self.db.get_or_create_session(channel, chat_id)
        
        # Get or create active instance
        instance = self.db.get_or_create_active_instance(session_record.id, "default")
        
        # Load messages from database (only uncompressed messages)
        messages = []
        message_records = self.db.get_uncompressed_messages(instance.id, limit=1000)
        for msg in message_records:
            msg_dict = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata if msg.metadata else {}
            }
            messages.append(msg_dict)
        
        # Load compressed context from database
        compressed_info = self.db.get_compressed_context(instance.id)
        compressed_context = compressed_info["summary"] if compressed_info else ""
        compressed_message_count = compressed_info["compressed_count"] if compressed_info else 0
        last_compressed_turn = compressed_info["last_compressed_turn"] if compressed_info else 0
        
        # Create session object
        session = Session(
            key=key,
            messages=messages,
            created_at=session_record.created_at,
            updated_at=instance.updated_at,
            metadata=session_record.metadata,
            compressed_context=compressed_context,
            compressed_message_count=compressed_message_count,
            last_compressed_turn=last_compressed_turn,
            session_record=session_record,
            active_instance=instance
        )
        
        self._cache[key] = session
        return session
    
    def save(self, session: Session) -> None:
        """Save a session to storage."""
        self._save_to_db(session)
        self._cache[session.key] = session
    
    def _save_to_db(self, session: Session) -> None:
        """Save session to database."""
        if not session.session_record or not session.active_instance:
            logger.error("Cannot save session without database records")
            return

        instance_id = session.active_instance.id
        self._save_messages_to_instance(session, instance_id)
        
        # Save compressed context to database
        if session.compressed_context:
            self.db.update_compressed_context(
                instance_id=instance_id,
                summary=session.compressed_context,
                compressed_count=session.compressed_message_count,
                last_compressed_turn=session.last_compressed_turn
            )

    def _save_messages_to_instance(self, session: Session, instance_id: int) -> None:
        """Save session messages to a specific instance.

        Args:
            session: The session object containing messages to save
            instance_id: The specific session_instance_id to save messages to
        """
        # Get existing messages from database for this instance
        existing_records = self.db.get_messages(instance_id, limit=10000)
        existing_count = len(existing_records)
        session_message_count = len(session.messages)

        logger.info(f"[_save_messages_to_instance] Session {session.key}, instance {instance_id}: existing={existing_count}, session={session_message_count}")

        # Only add new messages
        if session_message_count > existing_count:
            new_messages = session.messages[existing_count:]
            logger.info(f"[_save_messages_to_instance] Saving {len(new_messages)} new messages to instance {instance_id}")
            for msg in new_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                metadata = {k: v for k, v in msg.items()
                           if k not in ("role", "content", "timestamp")}
                self.db.add_message(instance_id, role, content, metadata)
                logger.info(f"[_save_messages_to_instance] Added message with role={role}, metadata={metadata}")

            logger.info(f"Saved {len(new_messages)} new messages to database for session {session.key}, instance {instance_id}")
        else:
            logger.info(f"[_save_messages_to_instance] No new messages to save for instance {instance_id}")

    def save_to_instance(self, session: Session, instance_id: int | None = None) -> None:
        """Save session messages to a specific instance.

        This is useful for longtask scenarios where messages need to be saved
        to the instance where the task was created, not the current active instance.

        Args:
            session: The session object containing messages to save
            instance_id: The specific session_instance_id to save messages to.
                        If None, uses the session's active_instance.id
        """
        if not session.session_record:
            logger.error("Cannot save session without database records")
            return

        # Use provided instance_id or fall back to active_instance
        target_instance_id = instance_id if instance_id is not None else (session.active_instance.id if session.active_instance else None)
        if target_instance_id is None:
            logger.error("Cannot save session: no instance_id provided and no active_instance")
            return

        self._save_messages_to_instance(session, target_instance_id)
        self._cache[session.key] = session
    
    def update_last_message_metadata(
        self,
        session_instance_id: int,
        update_data: dict[str, Any]
    ) -> bool:
        """Update the latest assistant message's metadata with additional data.
        
        Args:
            session_instance_id: The session instance ID
            update_data: Dict of metadata fields to update/merge
            
        Returns:
            True if updated successfully
        """
        return self.db.update_last_message_metadata(session_instance_id, update_data)
    
    # Multi-session management commands
    def create_instance(self, key: str, instance_name: str) -> tuple[bool, str]:
        """
        Create a new session instance.
        
        Args:
            key: Session key (channel:chat_id).
            instance_name: Name for the new instance.
            
        Returns:
            Tuple of (success, message).
        """
        session = self.get_or_create(key)
        if not session.session_record:
            return False, "Session not found in database"
        
        # Check if name already exists
        instances = self.db.list_instances(session.session_record.id)
        for inst in instances:
            if inst.instance_name == instance_name:
                return False, f"Instance '{instance_name}' already exists"
        
        # Create new instance
        instance = self.db.create_instance(session.session_record.id, instance_name)
        
        # Switch to new instance
        self.switch_instance(key, instance.id)
        
        return True, f"Created and switched to new session instance: {instance_name} (ID: {instance.id})"
    
    def switch_instance(self, key: str, instance_id: int) -> tuple[bool, str]:
        """
        Switch to a different session instance.
        
        Args:
            key: Session key (channel:chat_id).
            instance_id: ID of the instance to switch to.
            
        Returns:
            Tuple of (success, message).
        """
        session = self.get_or_create(key)
        if not session.session_record:
            return False, "Session not found in database"
        
        # Verify instance exists and belongs to this session
        instance = self.db.get_instance_by_id(instance_id)
        if not instance:
            return False, f"Instance {instance_id} not found"

        if instance.session_id != session.session_record.id:
            return False, f"Instance {instance_id} does not belong to this session"

        # Activate the instance
        if self.db.set_active_instance(session.session_record.id, instance_id):
            # Reload session with new instance
            self._cache.pop(key, None)
            new_session = self._get_or_create_db(key)
            
            return True, f"Switched to instance: {instance.instance_name} (ID: {instance_id}, {len(new_session.messages)} messages)"
        else:
            return False, "Failed to switch instance"
    
    def list_instances(self, key: str) -> tuple[bool, list[dict], str]:
        """
        List all instances for a session.
        
        Args:
            key: Session key (channel:chat_id).
            
        Returns:
            Tuple of (success, instances list, message).
        """
        session = self.get_or_create(key)
        if not session.session_record:
            return False, [], "Session not found in database"
        
        instances = self.db.list_instances(session.session_record.id)
        
        result = []
        for inst in instances:
            message_count = self.db.get_message_count(inst.id)
            result.append({
                "id": inst.id,
                "name": inst.instance_name,
                "is_active": inst.is_active,
                "created_at": inst.created_at.isoformat(),
                "updated_at": inst.updated_at.isoformat(),
                "message_count": message_count
            })
        
        return True, result, f"Found {len(result)} session instances"
    
    def delete_instance_by_id(self, key: str, instance_id: int) -> tuple[bool, str]:
        """
        Delete a session instance by ID.
        
        Args:
            key: Session key (channel:chat_id).
            instance_id: ID of the instance to delete.
            
        Returns:
            Tuple of (success, message).
        """
        session = self.get_or_create(key)
        if not session.session_record:
            return False, "Session not found in database"
        
        # Verify instance belongs to this session
        instance = self.db.get_instance_by_id(instance_id)
        if not instance:
            return False, f"Instance {instance_id} not found"

        if instance.session_id != session.session_record.id:
            return False, f"Instance {instance_id} does not belong to this session"

        # Delete the instance
        success = self.db.delete_instance(instance_id)
        
        if success:
            # Clear cache to force reload on next access
            self._cache.pop(key, None)
            logger.info(f"Deleted session instance {instance_id} for {key}")
            return True, f"Deleted instance {instance_id}"
        else:
            return False, f"Failed to delete instance {instance_id}"
    
    def delete(self, key: str) -> bool:
        """
        Delete a session.
        
        Args:
            key: Session key.
        
        Returns:
            True if deleted, False if not found.
        """
        self._cache.pop(key, None)
        
        success = self.db.delete_session(key)
        if success:
            logger.info(f"Deleted session: {key}")
            return True
        
        return False
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.
        
        Returns:
            List of session info dicts.
        """
        sessions = []
        
        import sqlite3
        with sqlite3.connect(self.db.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT s.*, si.id as active_instance_id, si.instance_name
                   FROM sessions s
                   LEFT JOIN session_instances si ON s.id = si.session_id AND si.is_active = 1
                   ORDER BY s.updated_at DESC"""
            ).fetchall()
            
            for row in rows:
                sessions.append({
                    "key": row["session_key"],
                    "channel": row["channel"],
                    "chat_id": row["chat_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "active_instance": row["instance_name"] if row["instance_name"] else "default"
                })
        
        return sessions
