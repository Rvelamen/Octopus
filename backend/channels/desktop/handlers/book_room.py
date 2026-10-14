"""Workspace-bound user room actions and finite background character workers."""

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pydantic import ValidationError

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.services.book_world.chat_provider import (
    CharacterChatModel,
    list_character_chat_models,
    resolve_character_chat_model,
)
from backend.services.book_world.chat_worker import BookChatWorker
from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.memory import RoomMemoryService
from backend.services.book_world.room_catalog import RoomCharacterCatalog
from backend.services.book_world.room_contracts import BookRoomRequest
from backend.services.book_world.room_models import CharacterChatConfig, RoomScope
from backend.services.book_world.rooms import BookRoomService
from backend.services.book_world.rounds import BookRoundService
from backend.services.book_world.source import BookWorldError
from backend.services.book_world.storage import workspace_identity
from backend.utils.helpers import get_workspace_path


class BookRoomHandler(MessageHandler):
    _tasks: dict[tuple[str, str], asyncio.Task] = {}
    _slots: dict[tuple[Any, str], asyncio.Semaphore] = {}
    _controls: dict[tuple[Any, str, str], asyncio.Lock] = {}
    _cleanup_tasks: dict[tuple[str, str], asyncio.Task] = {}
    _initialized_workspaces: set[tuple[Any, str]] = set()
    _initialization_locks: dict[tuple[Any, str], asyncio.Lock] = {}

    @classmethod
    async def initialize_workspace(cls, root: Path) -> list[str]:
        """First entry interrupts old work; same-process reentry preserves live workers."""
        key = asyncio.get_running_loop(), workspace_identity(root)
        lock = cls._initialization_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in cls._initialized_workspaces:
                return []
            rounds = await asyncio.to_thread(BookRoundService, root)
            interrupted = await asyncio.to_thread(rounds.recover_interrupted)
            cls._initialized_workspaces.add(key)
            return interrupted

    async def _original_model(
        self, generation: dict, preferred: CharacterChatModel | None = None
    ) -> CharacterChatModel:
        original = CharacterChatConfig.model_validate(generation)
        keys = (
            "provider_id",
            "model_record_id",
            "model",
            "provider_signature",
            "prompt_version",
            "review_prompt_version",
            "policy_version",
        )
        if preferred is not None and all(
            getattr(preferred.config, key) == getattr(original, key) for key in keys
        ):
            current = preferred
        else:
            current = (
                await asyncio.to_thread(
                    resolve_character_chat_model,
                    original.provider_id,
                    original.model_record_id,
                    original_config=original,
                )
                if original.model_record_id
                else await asyncio.to_thread(resolve_character_chat_model, original_config=original)
            )
        if any(getattr(current.config, key) != getattr(original, key) for key in keys):
            raise BookWorldError(
                "config_changed", "Original model endpoint or generation policy changed"
            )
        return CharacterChatModel(current.provider, original, current.timeouts)

    def _lock(self, root: Path, round_id: str) -> asyncio.Lock:
        return self._controls.setdefault(
            (asyncio.get_running_loop(), workspace_identity(root), round_id), asyncio.Lock()
        )

    async def _stop(self, root: Path, round_id: str) -> None:
        task = self._tasks.get((workspace_identity(root), round_id))
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def _schedule_cleanup(self, root: Path, scope: RoomScope) -> None:
        key = scope.workspace_id, scope.room_id
        if key in self._cleanup_tasks and not self._cleanup_tasks[key].done():
            return

        async def cleanup():
            try:
                rooms = await asyncio.to_thread(BookRoomService, root)
                await asyncio.to_thread(rooms.cleanup_cleared_memory, scope)
            except Exception:
                logger.warning("Cleared room memory cleanup deferred until the next room read")
            finally:
                if self._cleanup_tasks.get(key) is asyncio.current_task():
                    self._cleanup_tasks.pop(key, None)

        self._cleanup_tasks[key] = asyncio.create_task(cleanup())

    def _schedule(
        self, root: Path, scope: RoomScope, round_id: str, model: CharacterChatModel
    ) -> None:
        key = workspace_identity(root), round_id
        if key in self._tasks and not self._tasks[key].done():
            return

        async def execute():
            try:
                slots = self._slots.setdefault(
                    (asyncio.get_running_loop(), scope.workspace_id), asyncio.Semaphore(2)
                )
                async with slots:
                    worker = await asyncio.to_thread(BookChatWorker, root)
                    await worker.run(scope, round_id, model.provider, model.config)
            except Exception:
                logger.error("Character room worker failed before completion")
            finally:
                if self._tasks.get(key) is asyncio.current_task():
                    self._tasks.pop(key, None)

        self._tasks[key] = asyncio.create_task(execute())

    async def _execute(self, root: Path, request: BookRoomRequest) -> dict[str, Any]:
        rooms = await asyncio.to_thread(BookRoomService, root)
        if request.workspace_id is not None and request.workspace_id != rooms.workspace_id:
            raise BookWorldError("invalid_scope", "Workspace changed; reload the current room")
        if request.action == "list_room_characters":
            catalog = await asyncio.to_thread(RoomCharacterCatalog, root)
            return await asyncio.to_thread(
                catalog.list, limit=request.limit, offset=request.offset, query=request.query
            )
        if request.action == "create_group_room":
            assert request.characters and request.client_room_id
            selections = [
                await asyncio.to_thread(
                    rooms.knowledge.bind_character,
                    entry.item_id,
                    entry.build_id,
                    entry.character_id,
                )
                for entry in request.characters
            ]
            membership = await asyncio.to_thread(RoomMembershipService, root)
            return await asyncio.to_thread(
                membership.create,
                selections,
                client_room_id=request.client_room_id,
                title=request.title,
            )
        if request.action == "create_single_room":
            assert (
                request.item_id is not None
                and request.build_id
                and request.character_id
                and request.client_room_id
            )
            character = await asyncio.to_thread(
                rooms.knowledge.bind_character,
                request.item_id,
                request.build_id,
                request.character_id,
            )
            return await asyncio.to_thread(
                rooms.create_single_room,
                character,
                client_room_id=request.client_room_id,
                title=request.title,
                reuse_existing=request.reuse_existing,
            )
        if request.action == "list_rooms":
            return {
                "workspace_id": rooms.workspace_id,
                **await asyncio.to_thread(rooms.list_rooms, request.limit, request.offset),
            }
        if request.action == "list_chat_models":
            return {"models": await asyncio.to_thread(list_character_chat_models)}
        assert request.room_id and request.expected_epoch is not None
        scope = await asyncio.to_thread(rooms.bind_room, request.room_id, request.expected_epoch)
        if request.action in (
            "submit_turn",
            "cancel_round",
            "pause_round",
            "resume_round",
            "set_member",
            "add_members",
            "reset_memory",
        ):
            async with self._lock(root, f"room:{scope.room_id}"):
                return await self._scoped_action(root, scope, request, rooms)
        return await self._scoped_action(root, scope, request, rooms)

    async def _scoped_action(
        self, root: Path, scope: RoomScope, request: BookRoomRequest, rooms: BookRoomService
    ) -> dict[str, Any]:
        rounds = await asyncio.to_thread(BookRoundService, root)
        if request.action == "add_members":
            assert request.characters
            selections = [
                await asyncio.to_thread(
                    rooms.knowledge.bind_character,
                    entry.item_id,
                    entry.build_id,
                    entry.character_id,
                )
                for entry in request.characters
            ]
            membership = await asyncio.to_thread(RoomMembershipService, root)
            return await asyncio.to_thread(membership.add, scope, selections)
        if request.action == "set_member":
            assert request.member_id
            membership = await asyncio.to_thread(RoomMembershipService, root)
            controlled = await asyncio.to_thread(
                membership.control,
                scope,
                request.member_id,
                active=request.active,
                speaking_mode=request.speaking_mode,
            )
            for identifier in controlled["revoked_round_ids"]:
                async with self._lock(root, identifier):
                    await self._stop(root, identifier)
                    remaining = await asyncio.to_thread(rounds.get_round, scope, identifier)
                    if remaining["status"] == "queued":
                        selected_model = await self._original_model(remaining["generation_config"])
                        self._schedule(root, scope, identifier, selected_model)
            return controlled
        if request.action == "get_room":
            room_result = await asyncio.to_thread(rooms.get_room, scope)
            self._schedule_cleanup(root, scope)
            return room_result
        if request.action == "get_memory":
            memory = await asyncio.to_thread(RoomMemoryService, root)
            return {"memory": await asyncio.to_thread(memory.read, scope)}
        if request.action == "reset_memory":
            reset_result = await asyncio.to_thread(rooms.reset_memory, scope)
            for round_id in reset_result["cancelled_round_ids"]:
                try:
                    async with self._lock(root, round_id):
                        await self._stop(root, round_id)
                except Exception:
                    logger.warning("Reset revoked publication; worker cancellation failed")
            current = scope.model_copy(update={"epoch": reset_result["epoch"]})
            self._schedule_cleanup(root, current)
            return reset_result
        if request.action == "read_messages":
            return await asyncio.to_thread(
                rooms.read_messages, scope, request.after_seq, request.limit
            )
        if request.action == "get_message_evidence":
            assert request.message_id
            return await asyncio.to_thread(rooms.get_message_evidence, scope, request.message_id)
        if request.action == "get_round":
            assert request.round_id
            return await asyncio.to_thread(rounds.get_round, scope, request.round_id)
        if request.action == "submit_turn":
            assert request.client_turn_id and request.content is not None
            result = await asyncio.to_thread(
                rounds.find_submission,
                scope,
                request.client_turn_id,
                request.content,
                mode=request.mode,
                target_member_ids=request.target_member_ids,
            )
            model = None
            if result is None:
                model = (
                    await asyncio.to_thread(
                        resolve_character_chat_model, request.provider_id, request.model_record_id
                    )
                    if request.provider_id is not None
                    else await asyncio.to_thread(resolve_character_chat_model)
                )
                result = await asyncio.to_thread(
                    rounds.submit,
                    scope,
                    request.client_turn_id,
                    request.content,
                    model.config,
                    time_limit_seconds=model.timeouts.seconds_for_mode(request.mode),
                    mode=request.mode,
                    target_member_ids=request.target_member_ids,
                )
            async with self._lock(root, result["round_id"]):
                current = await asyncio.to_thread(rounds.get_round, scope, result["round_id"])
                if current["status"] == "queued":
                    model = await self._original_model(current["generation_config"], model)
                    self._schedule(root, scope, current["round_id"], model)
            return result
        assert request.round_id
        async with self._lock(root, request.round_id):
            if request.action in ("cancel_round", "pause_round"):
                result = await asyncio.to_thread(
                    rounds.control,
                    scope,
                    request.round_id,
                    "cancel" if request.action == "cancel_round" else "pause",
                )
                await self._stop(root, request.round_id)
                result = await asyncio.to_thread(rounds.get_round, scope, request.round_id)
            else:
                current = await asyncio.to_thread(rounds.get_round, scope, request.round_id)
                model = await self._original_model(current["generation_config"])
                result = await asyncio.to_thread(
                    rounds.control,
                    scope,
                    request.round_id,
                    "resume",
                    time_limit_seconds=model.timeouts.seconds_for_mode(current["mode"]),
                )
                await self._stop(root, request.round_id)
                self._schedule(root, scope, request.round_id, model)
            return result

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        root = Path(get_workspace_path()).resolve()
        try:
            request = BookRoomRequest.model_validate(message.data)
            result = await self._execute(root, request)
            response = WSMessage(
                type=MessageType.BOOK_ROOM_RESULT,
                request_id=message.request_id,
                data={"action": request.action, "workspace_id": workspace_identity(root), **result},
            )
        except ValidationError:
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={"code": "invalid_request", "error": "Invalid book-room request"},
            )
        except BookWorldError as error:
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "code": error.code,
                    "error": str(error),
                    "workspace_id": workspace_identity(root),
                },
            )
        except Exception:
            logger.error("Book-room user operation failed")
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "code": "book_room_failed",
                    "error": "Could not complete this room operation",
                },
            )
        await self.send_response(websocket, response)
