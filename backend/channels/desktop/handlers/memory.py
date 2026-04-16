"""Memory Stream handlers for Desktop channel."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.schemas import (
    MemoryListRequest,
    MemorySearchRequest,
    MemoryReadRequest,
    MemoryTimelineRequest,
    MemoryDeleteRequest,
)
from backend.data import Database, ObservationRepository


class MemoryListHandler(MessageHandler):
    """Handle list observations requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            instance_id = message.data.get("instance_id")
            limit = message.data.get("limit", 50)
            offset = message.data.get("offset", 0)

            repo = ObservationRepository(Database())
            if instance_id is not None:
                records = repo.get_by_instance(instance_id, limit=limit, offset=offset)
            else:
                records = repo.get_recent(limit=limit)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "instance_id": instance_id,
                    "limit": limit,
                    "offset": offset,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list observations: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list observations: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: MemoryListRequest) -> None:
        try:
            instance_id = validated.instance_id
            limit = validated.limit
            offset = validated.offset

            repo = ObservationRepository(Database())
            if instance_id is not None:
                records = repo.get_by_instance(instance_id, limit=limit, offset=offset)
            else:
                records = repo.get_recent(limit=limit)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "instance_id": instance_id,
                    "limit": limit,
                    "offset": offset,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list observations: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list observations: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemorySearchHandler(MessageHandler):
    """Handle search observations requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            query = message.data.get("query", "")
            limit = message.data.get("limit", 20)
            type_filter = message.data.get("type_filter")
            instance_id = message.data.get("instance_id")

            if not query:
                await self._send_error(websocket, message.request_id, "Query is required")
                return

            repo = ObservationRepository(Database())
            records = repo.search_fts(
                query=query,
                limit=limit,
                type_filter=type_filter,
                instance_id=instance_id,
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_SEARCH_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "query": query,
                    "limit": limit,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to search observations: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to search observations: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: MemorySearchRequest) -> None:
        try:
            query = validated.query
            limit = validated.limit
            type_filter = validated.type_filter
            instance_id = validated.instance_id

            if not query:
                await self._send_error(websocket, message.request_id, "Query is required")
                return

            repo = ObservationRepository(Database())
            records = repo.search_fts(
                query=query,
                limit=limit,
                type_filter=type_filter,
                instance_id=instance_id,
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_SEARCH_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "query": query,
                    "limit": limit,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to search observations: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to search observations: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemoryReadHandler(MessageHandler):
    """Handle read single observation requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            obs_id = message.data.get("observation_id")
            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            record = repo.get_by_id(obs_id)
            if not record:
                await self._send_error(websocket, message.request_id, f"Observation #{obs_id} not found")
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_READ_RESULT,
                request_id=message.request_id,
                data={"observation": _record_to_dict(record)}
            ))
        except Exception as e:
            logger.error(f"Failed to read observation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read observation: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: MemoryReadRequest) -> None:
        try:
            obs_id = validated.observation_id
            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            record = repo.get_by_id(obs_id)
            if not record:
                await self._send_error(websocket, message.request_id, f"Observation #{obs_id} not found")
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_READ_RESULT,
                request_id=message.request_id,
                data={"observation": _record_to_dict(record)}
            ))
        except Exception as e:
            logger.error(f"Failed to read observation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read observation: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemoryTimelineHandler(MessageHandler):
    """Handle get observation timeline requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            obs_id = message.data.get("observation_id")
            depth_before = message.data.get("depth_before", 2)
            depth_after = message.data.get("depth_after", 2)

            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            records = repo.get_timeline(obs_id, depth_before=depth_before, depth_after=depth_after)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_TIMELINE_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "anchor_id": obs_id,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get observation timeline: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get observation timeline: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: MemoryTimelineRequest) -> None:
        try:
            obs_id = validated.observation_id
            depth_before = validated.depth_before
            depth_after = validated.depth_after

            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            records = repo.get_timeline(obs_id, depth_before=depth_before, depth_after=depth_after)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_TIMELINE_RESULT,
                request_id=message.request_id,
                data={
                    "observations": [_record_to_dict(r) for r in records],
                    "anchor_id": obs_id,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get observation timeline: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get observation timeline: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemoryDeleteHandler(MessageHandler):
    """Handle delete observation requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            obs_id = message.data.get("observation_id")
            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            success = repo.delete_observation(obs_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_DELETED,
                request_id=message.request_id,
                data={"success": success, "observation_id": obs_id}
            ))
        except Exception as e:
            logger.error(f"Failed to delete observation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete observation: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: MemoryDeleteRequest) -> None:
        try:
            obs_id = validated.observation_id
            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            repo = ObservationRepository(Database())
            success = repo.delete_observation(obs_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_DELETED,
                request_id=message.request_id,
                data={"success": success, "observation_id": obs_id}
            ))
        except Exception as e:
            logger.error(f"Failed to delete observation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete observation: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemoryExtractHandler(MessageHandler):
    """Handle manual observation extraction requests."""

    def __init__(self, bus, agent_loop=None):
        super().__init__(bus)
        self.agent_loop = agent_loop

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            instance_id = message.data.get("instance_id")
            if not instance_id:
                await self._send_error(websocket, message.request_id, "instance_id is required")
                return

            # Fetch recent uncompressed messages for this instance
            from backend.data import Database, SessionRepository
            db = Database()
            repo = SessionRepository(db)
            messages = repo.get_uncompressed_messages(instance_id, limit=50)

            msg_dicts = []
            for msg in messages:
                msg_dicts.append({
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata or {},
                })

            extracted_count = 0
            if self.agent_loop and hasattr(self.agent_loop, 'observation_manager') and self.agent_loop.observation_manager:
                extracted = await self.agent_loop.observation_manager.extract_from_messages(
                    session_instance_id=instance_id,
                    messages=msg_dicts,
                )
                extracted_count = len(extracted)
            else:
                await self._send_error(websocket, message.request_id, "Observation manager not available")
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_EXTRACT_RESULT,
                request_id=message.request_id,
                data={
                    "success": True,
                    "instance_id": instance_id,
                    "extracted_count": extracted_count,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to extract observations: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to extract observations: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MemoryPromoteHandler(MessageHandler):
    """Handle promotion of an observation into curated memory."""

    def __init__(self, bus, agent_loop=None):
        super().__init__(bus)
        self.agent_loop = agent_loop

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            obs_id = message.data.get("observation_id")
            target = message.data.get("target", "memory")

            if obs_id is None:
                await self._send_error(websocket, message.request_id, "observation_id is required")
                return

            if target not in ("memory", "user"):
                await self._send_error(websocket, message.request_id, "target must be 'memory' or 'user'")
                return

            # Fetch observation
            from backend.data import ObservationRepository, Database
            obs_repo = ObservationRepository(Database())
            record = obs_repo.get_by_id(obs_id)
            if not record:
                await self._send_error(websocket, message.request_id, f"Observation #{obs_id} not found")
                return

            # Format as curated entry
            entry = f"[{record.type.upper()}] {record.title}\n{record.narrative}"
            if record.files:
                entry += f"\nFiles: {', '.join(record.files)}"
            if record.concepts:
                entry += f"\nConcepts: {', '.join(record.concepts)}"

            # Write to curated memory
            if not self.agent_loop or not hasattr(self.agent_loop, 'memory_manager') or not self.agent_loop.memory_manager:
                await self._send_error(websocket, message.request_id, "Memory manager not available")
                return

            result = self.agent_loop.memory_manager.builtin.add(target, entry)
            if not result.get("success"):
                await self._send_error(
                    websocket,
                    message.request_id,
                    result.get("error", "Promotion failed")
                )
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.MEMORY_PROMOTED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "observation_id": obs_id,
                    "target": target,
                    "usage": result.get("usage"),
                    "entry_count": result.get("entry_count"),
                }
            ))
        except Exception as e:
            logger.error(f"Failed to promote observation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to promote observation: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


def _record_to_dict(record) -> dict:
    return {
        "id": record.id,
        "session_instance_id": record.session_instance_id,
        "type": record.type,
        "title": record.title,
        "narrative": record.narrative,
        "files": record.files,
        "concepts": record.concepts,
        "token_count": record.token_count,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
