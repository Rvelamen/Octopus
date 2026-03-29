"""SQLite database module for session management."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager

from loguru import logger


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


class SessionDatabase:
    """SQLite database manager for sessions and messages."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints for cascade delete to work
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            # Main sessions table (channel:chat_id level)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    session_key TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    metadata TEXT DEFAULT '{}',
                    UNIQUE(channel, chat_id)
                )
            """)
            
            # Session instances table (multi-session support)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    instance_name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            # Messages table (linked to session_instance)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_instance_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_session ON session_instances(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_active ON session_instances(session_id, is_active)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_instance ON messages(session_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)
            """)
            
            # Migration for TTS fields
            cursor = conn.execute("PRAGMA table_info(session_instances)")
            instance_columns = [row[1] for row in cursor.fetchall()]
            
            if instance_columns:
                if 'tts_enabled' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN tts_enabled BOOLEAN DEFAULT 0")
                    logger.info("Migration: Added tts_enabled column to session_instances table")
                
                if 'tts_config' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN tts_config TEXT DEFAULT '{}'")
                    logger.info("Migration: Added tts_config column to session_instances table")
            
            # logger.info("Database initialized successfully")
    
    # Session operations
    def get_or_create_session(self, channel: str, chat_id: str) -> SessionRecord:
        """Get or create a session record."""
        session_key = f"{channel}:{chat_id}"
        
        with self._get_connection() as conn:
            # Try to get existing
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?",
                (session_key,)
            ).fetchone()
            
            if row:
                return self._row_to_session(row)
            
            # Create new
            cursor = conn.execute(
                """INSERT INTO sessions (channel, chat_id, session_key, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (channel, chat_id, session_key, '{}')
            )
            
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            logger.info(f"Created new session: {session_key}")
            return self._row_to_session(row)
    
    def get_session(self, session_key: str) -> Optional[SessionRecord]:
        """Get session by key."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?",
                (session_key,)
            ).fetchone()
            
            return self._row_to_session(row) if row else None
    
    def get_session_by_id(self, session_id: int) -> Optional[SessionRecord]:
        """Get session by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            
            return self._row_to_session(row) if row else None
    
    # Session instance operations
    def create_instance(self, session_id: int, instance_name: str) -> SessionInstance:
        """Create a new session instance."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO session_instances (session_id, instance_name, is_active, created_at, updated_at)
                   VALUES (?, ?, 0, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (session_id, instance_name)
            )
            
            row = conn.execute(
                "SELECT * FROM session_instances WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            logger.info(f"Created session instance: {instance_name} for session {session_id}")
            return self._row_to_instance(row)
    
    def get_active_instance(self, session_id: int) -> Optional[SessionInstance]:
        """Get active instance for a session."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM session_instances 
                   WHERE session_id = ? AND is_active = 1
                   ORDER BY updated_at DESC LIMIT 1""",
                (session_id,)
            ).fetchone()
            
            return self._row_to_instance(row) if row else None
    
    def set_active_instance(self, session_id: int, instance_id: int) -> bool:
        """Set an instance as active (deactivate all other instances globally)."""
        with self._get_connection() as conn:
            # Check current active instances before change
            before = conn.execute("SELECT id, is_active FROM session_instances WHERE is_active = 1").fetchall()
            logger.info(f"BEFORE set_active: {len(before)} active instances: {[r['id'] for r in before]}")
            
            # Verify instance belongs to session
            row = conn.execute(
                "SELECT id FROM session_instances WHERE id = ? AND session_id = ?",
                (instance_id, session_id)
            ).fetchone()
            
            if not row:
                logger.warning(f"Instance {instance_id} not found for session {session_id}")
                return False
            
            # Deactivate ALL instances globally (not just this session)
            conn.execute(
                "UPDATE session_instances SET is_active = 0, updated_at = (datetime('now', 'localtime'))"
            )
            
            # Activate specified instance
            conn.execute(
                "UPDATE session_instances SET is_active = 1, updated_at = (datetime('now', 'localtime')) WHERE id = ?",
                (instance_id,)
            )
            
            # Update session updated_at
            conn.execute(
                "UPDATE sessions SET updated_at = (datetime('now', 'localtime')) WHERE id = ?",
                (session_id,)
            )
            
            # Check active instances after change
            after = conn.execute("SELECT id, is_active FROM session_instances WHERE is_active = 1").fetchall()
            logger.info(f"AFTER set_active: {len(after)} active instances: {[r['id'] for r in after]}")
            
            return True
    
    def get_or_create_active_instance(self, session_id: int, default_name: str = "default") -> SessionInstance:
        """Get active instance or create default one."""
        instance = self.get_active_instance(session_id)
        if instance:
            return instance
        
        # Check if default instance exists
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_instances WHERE session_id = ? AND instance_name = ?",
                (session_id, default_name)
            ).fetchone()
            
            if row:
                instance = self._row_to_instance(row)
                self.set_active_instance(session_id, instance.id)
                return instance
        
        # Create default instance
        instance = self.create_instance(session_id, default_name)
        self.set_active_instance(session_id, instance.id)
        return instance
    
    def list_instances(self, session_id: int) -> list[SessionInstance]:
        """List all instances for a session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM session_instances 
                   WHERE session_id = ?
                   ORDER BY is_active DESC, created_at DESC""",
                (session_id,)
            ).fetchall()
            
            return [self._row_to_instance(row) for row in rows]
    
    def get_instance(self, instance_id: int) -> Optional[SessionInstance]:
        """Get instance by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_instances WHERE id = ?",
                (instance_id,)
            ).fetchone()
            
            return self._row_to_instance(row) if row else None
    
    def update_instance_tts_config(self, instance_id: int, enabled: bool | None = None, 
                                    config: dict[str, Any] | None = None) -> bool:
        """Update TTS config for a session instance.
        
        Args:
            instance_id: Session instance ID
            enabled: TTS enabled status (None to keep current)
            config: TTS config dict (None to keep current, partial update supported)
            
        Returns:
            True if update successful
        """
        with self._get_connection() as conn:
            # Get current config
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
            
            # Merge updates
            new_enabled = enabled if enabled is not None else current_enabled
            new_config = {**current_config, **config} if config else current_config
            
            logger.info(f"Updating TTS config for instance {instance_id}: enabled={new_enabled}, config={new_config}")
            
            conn.execute(
                """UPDATE session_instances 
                   SET tts_enabled = ?, tts_config = ?, updated_at = (datetime('now', 'localtime'))
                   WHERE id = ?""",
                (1 if new_enabled else 0, json.dumps(new_config, ensure_ascii=False), instance_id)
            )
            
            # Verify the update
            verify_row = conn.execute(
                "SELECT tts_enabled, tts_config FROM session_instances WHERE id = ?",
                (instance_id,)
            ).fetchone()
            logger.info(f"Verified TTS config after update: enabled={verify_row['tts_enabled']}, config={verify_row['tts_config']}")
            
            return True
    
    # Message operations
    def add_message(self, session_instance_id: int, role: str, content: str, 
                    metadata: dict[str, Any] | None = None) -> MessageRecord:
        """Add a message to a session instance."""
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO messages (session_instance_id, role, content, metadata, timestamp)
                   VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
                (session_instance_id, role, content, metadata_json)
            )
            
            # Update instance and session updated_at
            conn.execute(
                """UPDATE session_instances
                   SET updated_at = (datetime('now', 'localtime'))
                   WHERE id = ?""",
                (session_instance_id,)
            )
            
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            
            return self._row_to_message(row)
    
    def get_messages(self, session_instance_id: int, limit: int = 50, 
                     offset: int = 0) -> list[MessageRecord]:
        """Get messages for a session instance."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages 
                   WHERE session_instance_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ? OFFSET ?""",
                (session_instance_id, limit, offset)
            ).fetchall()
            
            return [self._row_to_message(row) for row in reversed(rows)]
    
    def get_message_count(self, session_instance_id: int) -> int:
        """Get total message count for a session instance."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE session_instance_id = ?",
                (session_instance_id,)
            ).fetchone()
            
            return row["count"] if row else 0
    
    def clear_messages(self, session_instance_id: int) -> int:
        """Clear all messages for a session instance. Returns deleted count."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE session_instance_id = ?",
                (session_instance_id,)
            )
            return cursor.rowcount
    
    def delete_instance(self, instance_id: int) -> tuple[bool, str]:
        """
        Delete a session instance and all its messages.
        
        Returns:
            Tuple of (success, message).
        """
        with self._get_connection() as conn:
            # Check if instance exists
            row = conn.execute(
                "SELECT instance_name, is_active, session_id FROM session_instances WHERE id = ?",
                (instance_id,)
            ).fetchone()
            
            if not row:
                return False, f"Session instance {instance_id} not found"
            
            instance_name = row["instance_name"]
            is_active = bool(row["is_active"])
            session_id = row["session_id"]
            
            # Count remaining instances for this session
            count_row = conn.execute(
                "SELECT COUNT(*) as count FROM session_instances WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            
            if count_row and count_row["count"] <= 1:
                return False, "Cannot delete the only remaining session instance"
            
            # Delete the instance (cascade will delete messages)
            cursor = conn.execute(
                "DELETE FROM session_instances WHERE id = ?",
                (instance_id,)
            )
            
            if cursor.rowcount > 0:
                # If deleted instance was active, activate another one
                if is_active:
                    new_active = conn.execute(
                        "SELECT id FROM session_instances WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                        (session_id,)
                    ).fetchone()
                    
                    if new_active:
                        conn.execute(
                            "UPDATE session_instances SET is_active = 1 WHERE id = ?",
                            (new_active["id"],)
                        )
                
                return True, f"Session '{instance_name}' (ID: {instance_id}) deleted successfully"
            
            return False, f"Failed to delete session instance {instance_id}"
    
    # Migration helpers
    def import_session_data(self, session_key: str, messages: list[dict],
                           created_at: datetime | None = None) -> bool:
        """Import session data from JSON format."""
        try:
            parts = session_key.split(":", 1)
            if len(parts) != 2:
                return False
            
            channel, chat_id = parts
            
            # Get or create session
            session = self.get_or_create_session(channel, chat_id)
            
            # Get or create default instance
            instance = self.get_or_create_active_instance(session.id, "default")
            
            # Import messages
            for msg in messages:
                if msg.get("_type") == "metadata":
                    continue
                
                role = msg.get("role", "user")
                content = msg.get("content", "")
                timestamp = msg.get("timestamp")
                
                metadata = {k: v for k, v in msg.items() 
                           if k not in ("role", "content", "timestamp")}
                
                self.add_message(instance.id, role, content, metadata)
            
            logger.info(f"Imported {len(messages)} messages for {session_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import session {session_key}: {e}")
            return False
    
    # Helper methods
    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
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
    
    def _row_to_instance(self, row: sqlite3.Row) -> SessionInstance:
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
    
    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        """Convert database row to MessageRecord."""
        return MessageRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            role=row["role"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"])
        )
