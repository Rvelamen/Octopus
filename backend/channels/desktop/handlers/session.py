"""Session handlers for Desktop channel."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.schemas import (
    SessionGetChannelsRequest,
    SessionGetChannelSessionsRequest,
    SessionGetSessionDetailRequest,
    SessionGetMessagesRequest,
    SessionDeleteInstanceRequest,
    SessionCreateRequest,
    SessionSetActiveRequest,
    SessionGetInstancesRequest,
)
from backend.data import Database, SessionRepository, SessionManager
from backend.agent.compressor import estimate_message_tokens
from backend.agent.config_service import AgentConfigService
from backend.utils.helpers import get_workspace_path


class SessionGetChannelsHandler(MessageHandler):
    """Handle get channels requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all unique channel names."""
        try:
            db = Database()
            rows = db.execute("SELECT DISTINCT channel FROM sessions ORDER BY channel")
            channels = [row["channel"] for row in rows]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNELS,
                request_id=message.request_id,
                data={"channels": channels}
            ))
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channels: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionGetChannelsRequest) -> None:
        """Return all unique channel names."""
        try:
            db = Database()
            rows = db.execute("SELECT DISTINCT channel FROM sessions ORDER BY channel")
            channels = [row["channel"] for row in rows]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNELS,
                request_id=message.request_id,
                data={"channels": channels}
            ))
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channels: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetChannelSessionsHandler(MessageHandler):
    """Handle get channel sessions requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all sessions for a specific channel."""
        try:
            channel = message.data.get("channel")
            if not channel:
                await self._send_error(websocket, message.request_id, "Channel name is required")
                return

            db = Database()
            rows = db.execute(
                "SELECT * FROM sessions WHERE channel = ? ORDER BY updated_at DESC",
                (channel,)
            )

            sessions = [
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "chat_id": row["chat_id"],
                    "session_key": row["session_key"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": {}
                }
                for row in rows
            ]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNEL_SESSIONS,
                request_id=message.request_id,
                data={"channel": channel, "sessions": sessions}
            ))
        except Exception as e:
            logger.error(f"Failed to get channel sessions: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channel sessions: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionGetChannelSessionsRequest) -> None:
        """Return all sessions for a specific channel."""
        try:
            channel = validated.channel
            if not channel:
                await self._send_error(websocket, message.request_id, "Channel name is required")
                return

            db = Database()
            rows = db.execute(
                "SELECT * FROM sessions WHERE channel = ? ORDER BY updated_at DESC",
                (channel,)
            )

            sessions = [
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "chat_id": row["chat_id"],
                    "session_key": row["session_key"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": {}
                }
                for row in rows
            ]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNEL_SESSIONS,
                request_id=message.request_id,
                data={"channel": channel, "sessions": sessions}
            ))
        except Exception as e:
            logger.error(f"Failed to get channel sessions: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channel sessions: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetSessionDetailHandler(MessageHandler):
    """Handle get session detail requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return session detail with all instances."""
        try:
            channel = message.data.get("channel")
            chat_id = message.data.get("chat_id")

            if not channel or not chat_id:
                await self._send_error(websocket, message.request_id, "Channel and chat_id are required")
                return

            db = Database()
            repo = SessionRepository(db)

            session_key = f"{channel}:{chat_id}"
            session = repo.get_session(session_key)

            if not session:
                await self._send_error(websocket, message.request_id, "Session not found")
                return

            instances = repo.list_instances(session.id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_DETAIL,
                request_id=message.request_id,
                data={
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "metadata": session.metadata
                    },
                    "instances": [
                        {
                            "id": inst.id,
                            "session_id": inst.session_id,
                            "instance_name": inst.instance_name,
                            "is_active": inst.is_active,
                            "created_at": inst.created_at.isoformat(),
                            "updated_at": inst.updated_at.isoformat()
                        }
                        for inst in instances
                    ]
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get session detail: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get session detail: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionGetSessionDetailRequest) -> None:
        """Return session detail with all instances."""
        try:
            channel = validated.channel
            chat_id = validated.chat_id

            if not channel or not chat_id:
                await self._send_error(websocket, message.request_id, "Channel and chat_id are required")
                return

            db = Database()
            repo = SessionRepository(db)

            session_key = f"{channel}:{chat_id}"
            session = repo.get_session(session_key)

            if not session:
                await self._send_error(websocket, message.request_id, "Session not found")
                return

            instances = repo.list_instances(session.id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_DETAIL,
                request_id=message.request_id,
                data={
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "metadata": session.metadata
                    },
                    "instances": [
                        {
                            "id": inst.id,
                            "session_id": inst.session_id,
                            "instance_name": inst.instance_name,
                            "is_active": inst.is_active,
                            "created_at": inst.created_at.isoformat(),
                            "updated_at": inst.updated_at.isoformat()
                        }
                        for inst in instances
                    ]
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get session detail: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get session detail: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetMessagesHandler(MessageHandler):
    """Handle get messages requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return messages for a specific session instance."""
        try:
            instance_id = message.data.get("instance_id")
            limit = message.data.get("limit", 100)
            offset = message.data.get("offset", 0)

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            compressed = repo.get_compressed_context(instance_id)
            messages = repo.get_uncompressed_messages(instance_id, limit=limit, offset=offset)
            total = repo.get_message_count_by_compression(instance_id, is_compressed=False)
            compressed_total = repo.get_message_count_by_compression(instance_id, is_compressed=True)

            result_messages = []

            if compressed and compressed["summary"]:
                result_messages.append({
                    "id": "context-summary",
                    "session_instance_id": instance_id,
                    "role": "system",
                    "content": compressed["summary"],
                    "timestamp": compressed.get("compressed_at") or "",
                    "metadata": {
                        "message_type": "context_summary",
                        "is_summary": True,
                        "compression_info": {
                            "compressed_count": compressed["compressed_count"],
                            "compressed_at": compressed.get("compressed_at"),
                        }
                    }
                })

            result_messages.extend([
                {
                    "id": msg.id,
                    "session_instance_id": msg.session_instance_id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in messages
            ])

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_MESSAGES,
                request_id=message.request_id,
                data={
                    "session_instance_id": instance_id,
                    "messages": result_messages,
                    "total": total,
                    "compressed_total": compressed_total,
                    "has_compression": compressed is not None
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get messages: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionGetMessagesRequest) -> None:
        """Return messages for a specific session instance."""
        try:
            instance_id = validated.instance_id
            limit = validated.limit
            offset = validated.offset

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            compressed = repo.get_compressed_context(instance_id)
            messages = repo.get_uncompressed_messages(instance_id, limit=limit, offset=offset)
            total = repo.get_message_count_by_compression(instance_id, is_compressed=False)
            compressed_total = repo.get_message_count_by_compression(instance_id, is_compressed=True)

            result_messages = []

            if compressed and compressed["summary"]:
                result_messages.append({
                    "id": "context-summary",
                    "session_instance_id": instance_id,
                    "role": "system",
                    "content": compressed["summary"],
                    "timestamp": compressed.get("compressed_at") or "",
                    "metadata": {
                        "message_type": "context_summary",
                        "is_summary": True,
                        "compression_info": {
                            "compressed_count": compressed["compressed_count"],
                            "compressed_at": compressed.get("compressed_at"),
                        }
                    }
                })

            result_messages.extend([
                {
                    "id": msg.id,
                    "session_instance_id": msg.session_instance_id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in messages
            ])

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_MESSAGES,
                request_id=message.request_id,
                data={
                    "session_instance_id": instance_id,
                    "messages": result_messages,
                    "total": total,
                    "compressed_total": compressed_total,
                    "has_compression": compressed is not None
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get messages: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionDeleteInstanceHandler(MessageHandler):
    """Handle delete session instance requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete a session instance and all its messages."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance info before deletion for response
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Delete the instance (cascade will delete messages)
            success = repo.delete_instance(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_INSTANCE_DELETED,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "instance_name": instance.instance_name
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete instance: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionDeleteInstanceRequest) -> None:
        """Delete a session instance and all its messages."""
        try:
            instance_id = validated.instance_id

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance info before deletion for response
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Delete the instance (cascade will delete messages)
            success = repo.delete_instance(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_INSTANCE_DELETED,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "instance_name": instance.instance_name
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete instance: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionCreateHandler(MessageHandler):
    """Handle create session requests."""

    def __init__(self, bus, agent_loop=None):
        super().__init__(bus)
        self.agent_loop = agent_loop

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Create a new instance in the desktop session."""
        try:
            channel = message.data.get("channel", "desktop")
            # Use fixed chat_id for desktop channel - all instances in one session
            chat_id = "desktop_session"
            instance_name = message.data.get("instance_name", "New Chat")

            db = Database()
            repo = SessionRepository(db)

            # Get or create the single desktop session
            session = repo.get_or_create_session(channel, chat_id)
            logger.info(f"Session: {session.id}, chat_id: {session.chat_id}")

            # Create a new instance
            instance = repo.create_instance(session.id, instance_name)
            logger.info(f"Created instance: {instance.id}, is_active: {instance.is_active}")

            # Set the new instance as active
            result = repo.set_active_instance(session.id, instance.id)
            logger.info(f"set_active_instance result: {result}")

            # Refresh instance to get updated is_active
            instance = repo.get_instance_by_id(instance.id)
            logger.info(f"After refresh, instance {instance.id} is_active: {instance.is_active}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CREATED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                    },
                    "instance": {
                        "id": instance.id,
                        "session_id": instance.session_id,
                        "instance_name": instance.instance_name,
                        "is_active": instance.is_active,
                        "created_at": instance.created_at.isoformat(),
                        "updated_at": instance.updated_at.isoformat(),
                    }
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create session: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionCreateRequest) -> None:
        """Create a new instance in the desktop session."""
        try:
            channel = validated.channel or "desktop"
            # Use fixed chat_id for desktop channel - all instances in one session
            chat_id = "desktop_session"
            instance_name = validated.instance_name or "New Chat"

            db = Database()
            repo = SessionRepository(db)

            # Get or create the single desktop session
            session = repo.get_or_create_session(channel, chat_id)
            logger.info(f"Session: {session.id}, chat_id: {session.chat_id}")

            # Create a new instance
            instance = repo.create_instance(session.id, instance_name)
            logger.info(f"Created instance: {instance.id}, is_active: {instance.is_active}")

            # Set the new instance as active
            result = repo.set_active_instance(session.id, instance.id)
            logger.info(f"set_active_instance result: {result}")

            # Refresh instance to get updated is_active
            instance = repo.get_instance_by_id(instance.id)
            logger.info(f"After refresh, instance {instance.id} is_active: {instance.is_active}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CREATED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                    },
                    "instance": {
                        "id": instance.id,
                        "session_id": instance.session_id,
                        "instance_name": instance.instance_name,
                        "is_active": instance.is_active,
                        "created_at": instance.created_at.isoformat(),
                        "updated_at": instance.updated_at.isoformat(),
                    }
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create session: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionSetActiveHandler(MessageHandler):
    """Handle set active instance requests."""

    def __init__(self, bus, agent_loop=None):
        super().__init__(bus)
        self.agent_loop = agent_loop

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Set an instance as active for its session."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance to find its session
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Set as active
            success = repo.set_active_instance(instance.session_id, instance_id)

            if success:
                # Get updated instance
                instance = repo.get_instance_by_id(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_ACTIVE_SET,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "is_active": instance.is_active if instance else False
                }
            ))
        except Exception as e:
            logger.error(f"Failed to set active instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to set active instance: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionSetActiveRequest) -> None:
        """Set an instance as active for its session."""
        try:
            instance_id = validated.instance_id

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance to find its session
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Set as active
            success = repo.set_active_instance(instance.session_id, instance_id)

            if success:
                # Get updated instance
                instance = repo.get_instance_by_id(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_ACTIVE_SET,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "is_active": instance.is_active if instance else False
                }
            ))
        except Exception as e:
            logger.error(f"Failed to set active instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to set active instance: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetInstancesHandler(MessageHandler):
    """Handle get instances list with pagination."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return instances list with pagination support."""
        try:
            channel = message.data.get("channel", "desktop")
            limit = message.data.get("limit", 20)
            offset = message.data.get("offset", 0)

            db = Database()

            total_rows = db.execute(
                """SELECT COUNT(*) as count FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE s.channel = ?""",
                (channel,)
            )
            total = total_rows[0]["count"] if total_rows else 0

            rows = db.execute(
                """SELECT si.*, s.session_key, s.chat_id
                   FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE s.channel = ?
                   ORDER BY si.created_at DESC
                   LIMIT ? OFFSET ?""",
                (channel, limit, offset)
            )

            instances = [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "instance_name": row["instance_name"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "session_key": row["session_key"],
                    "chat_id": row["chat_id"]
                }
                for row in rows
            ]

            has_more = (offset + limit) < total

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_INSTANCES,
                request_id=message.request_id,
                data={
                    "instances": instances,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": has_more
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get instances: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get instances: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SessionGetInstancesRequest) -> None:
        """Return instances list with pagination support."""
        try:
            channel = validated.session_key or "desktop"
            limit = validated.limit
            offset = validated.offset

            db = Database()

            total_rows = db.execute(
                """SELECT COUNT(*) as count FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE s.channel = ?""",
                (channel,)
            )
            total = total_rows[0]["count"] if total_rows else 0

            rows = db.execute(
                """SELECT si.*, s.session_key, s.chat_id
                   FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE s.channel = ?
                   ORDER BY si.created_at DESC
                   LIMIT ? OFFSET ?""",
                (channel, limit, offset)
            )

            instances = [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "instance_name": row["instance_name"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "session_key": row["session_key"],
                    "chat_id": row["chat_id"]
                }
                for row in rows
            ]

            has_more = (offset + limit) < total

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_INSTANCES,
                request_id=message.request_id,
                data={
                    "instances": instances,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": has_more
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get instances: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get instances: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionCompressContextHandler(MessageHandler):
    """Handle manual context compression requests."""

    def __init__(self, bus, agent_loop=None):
        super().__init__(bus)
        self.agent_loop = agent_loop

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Compress context for a specific instance."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            session_record = repo.get_session_by_id(instance.session_id)
            if not session_record:
                await self._send_error(websocket, message.request_id, "Session not found")
                return

            if not self.agent_loop or not self.agent_loop.compressor:
                await self._send_error(websocket, message.request_id, "Agent loop not ready")
                return

            session_manager = SessionManager(self.agent_loop.workspace, db=db)
            session = session_manager.get_or_create(session_record.session_key)

            # Switch to the target instance so messages are loaded correctly
            session_manager.switch_instance(session_record.session_key, instance_id)
            session = session_manager.get_or_create(session_record.session_key)

            current_turns = session.get_turn_count()
            await self.agent_loop.compressor.do_compress(session, current_turns)

            # Refresh to get updated compression info
            compressed_info = repo.get_compressed_context(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CONTEXT_COMPRESSED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "instance_id": instance_id,
                    "compressed_count": compressed_info.get("compressed_count", 0) if compressed_info else 0,
                    "compressed_at": compressed_info.get("compressed_at") if compressed_info else None,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to compress context: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to compress context: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetContextStatsHandler(MessageHandler):
    """Handle context stats requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return context usage stats for a specific instance."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            session_record = repo.get_session_by_id(instance.session_id)
            if not session_record:
                await self._send_error(websocket, message.request_id, "Session not found")
                return

            session_manager = SessionManager(get_workspace_path(), db=db)
            session_manager.switch_instance(session_record.session_key, instance_id)
            session = session_manager.get_or_create(session_record.session_key)

            messages = session.get_history(max_messages=10000)
            current_tokens = estimate_message_tokens(messages)

            config_service = AgentConfigService(db)
            max_tokens = config_service.get_model_context_window()

            compressed_info = repo.get_compressed_context(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CONTEXT_STATS,
                request_id=message.request_id,
                data={
                    "instance_id": instance_id,
                    "current_tokens": current_tokens,
                    "max_tokens": max_tokens,
                    "percentage": round((current_tokens / max_tokens) * 100, 1) if max_tokens > 0 else 0,
                    "compressed_count": compressed_info.get("compressed_count", 0) if compressed_info else 0,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get context stats: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
