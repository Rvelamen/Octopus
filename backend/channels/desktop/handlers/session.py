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
from backend.data import Database, SessionRepository


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

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionCreateHandler(MessageHandler):
    """Handle create session requests."""

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

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionSetActiveHandler(MessageHandler):
    """Handle set active instance requests."""

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

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
