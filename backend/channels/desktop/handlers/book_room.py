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
    _summary_tasks: dict[tuple[str, str], asyncio.Task] = {}
    _initialized_workspaces: set[tuple[Any, str]] = set()
    _initialization_locks: dict[tuple[Any, str], asyncio.Lock] = {}
    _worker_roots: dict[str, Path] = {}
    _inflight: set[asyncio.Future] = set()
    _stopping = False

    @classmethod
    def startup(cls) -> None:
        cls._stopping = False

    @classmethod
    async def shutdown(cls) -> None:
        cls._stopping = True
        await asyncio.gather(*cls._inflight, return_exceptions=True)
        for root in cls._worker_roots.values():
            if not (root / "knowledge/.knowledge_index.db").exists():
                continue
            rounds = await asyncio.to_thread(BookRoundService, root)
            await asyncio.to_thread(rounds.recover_interrupted)
            from backend.services.book_world.summary_jobs import RoomSummaryJobs
            await asyncio.to_thread(RoomSummaryJobs(root).recover)
        tasks = [*cls._tasks.values(), *cls._cleanup_tasks.values(), *cls._summary_tasks.values()]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        cls._tasks.clear()
        cls._cleanup_tasks.clear()
        cls._summary_tasks.clear()
        cls._worker_roots.clear()

    @classmethod
    async def initialize_workspace(cls, root: Path) -> list[str]:
        """First entry interrupts old work; same-process reentry preserves live workers."""
        key = asyncio.get_running_loop(), workspace_identity(root)
        lock = cls._initialization_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in cls._initialized_workspaces:
                return []
            rounds = await asyncio.to_thread(BookRoundService, root)
            from backend.services.book_world.summary_jobs import RoomSummaryJobs
            jobs = await asyncio.to_thread(RoomSummaryJobs, root)
            await asyncio.to_thread(jobs.recover)
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
        self._worker_roots[key[0]] = root
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
        if request.action == "get_room_character":
            assert request.item_id is not None and request.build_id and request.character_id
            catalog = await asyncio.to_thread(RoomCharacterCatalog, root)
            return await asyncio.to_thread(catalog.get, request.item_id, request.build_id, request.character_id)
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
        if request.action == "open_room":
            assert request.room_id
            return await asyncio.to_thread(rooms.open_room, request.room_id)
        assert request.room_id and request.expected_epoch is not None
        scope = await asyncio.to_thread(rooms.bind_room, request.room_id, request.expected_epoch)
        if request.action in (
            "submit_turn",
            "cancel_round",
            "pause_round",
            "resume_round",
            "set_member",
            "set_discussion",
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
        if request.action in ("summarize_room", "get_summary_job", "cancel_summary"):
            from backend.services.book_world.public_summary import PublicRoomSummaryService
            from backend.services.book_world.summary_jobs import RoomSummaryJobs

            jobs = await asyncio.to_thread(RoomSummaryJobs, root)
            if request.action == "get_summary_job":
                return {"summary_job": await asyncio.to_thread(jobs.latest, scope)}
            if request.action == "cancel_summary":
                assert request.summary_job_id
                state = await asyncio.to_thread(jobs.cancel, scope, request.summary_job_id)
                task = self._summary_tasks.get((scope.workspace_id, request.summary_job_id))
                if task is not None:
                    task.cancel()
                return {"summary_job": state}
            async with self._lock(root, f"summary:{scope.room_id}"):
                summary_model = await asyncio.to_thread(resolve_character_chat_model, request.provider_id, request.model_record_id)
                assert request.client_summary_id
                state = await asyncio.to_thread(jobs.create, scope, request.client_summary_id, summary_model.timeouts.seconds_for_mode("directed"))
                key = scope.workspace_id, state["id"]
                if state["status"] == "queued" and key not in self._summary_tasks:
                    self._worker_roots[scope.workspace_id] = root
                    async def execute_summary():
                        generation = None
                        try:
                            generation = await asyncio.to_thread(jobs.start, scope, state["id"])
                            if generation is None:
                                return
                            summary = await asyncio.to_thread(PublicRoomSummaryService, root)
                            await summary.summarize(scope, summary_model.provider, summary_model.config,
                                time_limit_seconds=state["time_limit_seconds"],
                                authorized=lambda: not self._stopping and Path(get_workspace_path()).resolve() == root,
                                publication_authorized=lambda db: jobs.authorized(scope, state["id"], generation, db),
                                on_commit=lambda db, result: jobs.finish(scope, state["id"], generation, result=result, db=db))
                        except asyncio.CancelledError:
                            await asyncio.to_thread(jobs.finish, scope, state["id"], generation if generation is not None else 0, error="service_interrupted")
                            raise
                        except Exception as error:
                            await asyncio.to_thread(jobs.finish, scope, state["id"], generation if generation is not None else 0, error=error.code if isinstance(error, BookWorldError) else "summary_failed")
                        finally:
                            self._summary_tasks.pop(key, None)
                    self._summary_tasks[key] = asyncio.create_task(execute_summary())
                    def discard(task):
                        if self._summary_tasks.get(key) is task:
                            self._summary_tasks.pop(key, None)
                        if not task.cancelled():
                            task.exception()
                    self._summary_tasks[key].add_done_callback(discard)
                return {"summary_job": state}
        if request.action == "set_discussion":
            from backend.services.book_world.discussion import RoomDiscussionService

            assert request.expected_discussion_revision is not None and request.discussion_mode
            discussion = await asyncio.to_thread(RoomDiscussionService, root)
            return await asyncio.to_thread(discussion.set, scope, request.expected_discussion_revision, request.discussion_mode, request.topic, request.goal)
        if request.action == "get_member_profile":
            assert request.member_id
            return await asyncio.to_thread(rooms.get_member_profile, scope, request.member_id)
        if request.action == "retry_source_cleanup":
            from backend.services.book_world.lifecycle import BookLifecycleService

            snapshot = await asyncio.to_thread(rooms.get_room, scope)
            if not any(
                source["book_id"] == request.source_book_id and source["status"] == "source_removed"
                for source in snapshot["sources"]
            ):
                raise BookWorldError(
                    "invalid_scope", "Cleanup must refer to a removed source bound to this room"
                )
            assert request.source_book_id is not None
            lifecycle = await asyncio.to_thread(BookLifecycleService, root)
            return await asyncio.to_thread(lifecycle.purge, request.source_book_id)
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
                expected_discussion_revision=request.expected_discussion_revision,
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
                    expected_discussion_revision=request.expected_discussion_revision,
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
        if self._stopping:
            await self.send_response(websocket, WSMessage(type=MessageType.ERROR, request_id=message.request_id, data={"code": "service_stopping", "error": "Service is shutting down"}))
            return
        finished = asyncio.get_running_loop().create_future()
        self._inflight.add(finished)
        try:
            await self._handle_active(websocket, message)
        finally:
            finished.set_result(None)
            self._inflight.discard(finished)

    async def _handle_active(self, websocket: WebSocket, message: WSMessage) -> None:
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
