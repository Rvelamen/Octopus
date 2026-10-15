"""Book-world desktop boundary with a fixed server workspace per request."""

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pydantic import ValidationError

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.services.book_world import BookSourceService, BookWorldError
from backend.services.book_world.contracts import BookWorldRequest
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.discovery_provider import DiscoveryModel, resolve_discovery_model
from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig
from backend.services.book_world.features import require_world_action
from backend.services.book_world.knowledge import CharacterKnowledgeService
from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.revisions import BookRevisionService
from backend.services.book_world.storage import workspace_identity
from backend.services.book_world.worker_pool import build_slot
from backend.utils.helpers import get_workspace_path


class BookWorldHandler(MessageHandler):
    """Run synchronous PDF/SQLite work off the desktop event loop."""

    _build_tasks: dict[tuple[str, str], asyncio.Task] = {}
    _revision_requests: set[asyncio.Task] = set()
    _revision_slots: dict[tuple[Any, str], asyncio.Semaphore] = {}
    _expression_controls: dict[tuple[Any, str, str], asyncio.Lock] = {}
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
        tasks = [*cls._build_tasks.values(), *cls._revision_requests]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        from backend.services.book_world.lifecycle import BookLifecycleService

        for root in cls._worker_roots.values():
            if not (root / "knowledge/.knowledge_index.db").exists():
                continue
            lifecycle = await asyncio.to_thread(BookLifecycleService, root)
            await asyncio.to_thread(lifecycle.interrupt_builds)
        cls._build_tasks.clear()
        cls._revision_requests.clear()
        cls._worker_roots.clear()

    @classmethod
    def _expression_lock(cls, root: Path, set_id: str) -> asyncio.Lock:
        key = (asyncio.get_running_loop(), workspace_identity(root), set_id)
        return cls._expression_controls.setdefault(key, asyncio.Lock())

    @classmethod
    async def _stop_worker(cls, root: Path, build_id: str) -> None:
        task = cls._build_tasks.get((workspace_identity(root), build_id))
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @classmethod
    def _schedule(
        cls, root: Path, build_id: str, model: DiscoveryModel, phase: str = "discovery"
    ) -> None:
        key = (
            workspace_identity(root),
            f"expression:{build_id}" if phase == "expression" else build_id,
        )
        task = cls._build_tasks.get(key)
        cls._worker_roots[key[0]] = root
        if task is not None and not task.done():
            return

        async def execute() -> None:
            try:
                async with build_slot(root):
                    if phase == "expression":
                        expression_service = await asyncio.to_thread(
                            CharacterExpressionService, root
                        )
                        await expression_service.run(
                            build_id,
                            model.provider,
                            ExpressionConfig.from_model(model.config, model.context_window),
                        )
                    elif phase == "persona":
                        service = await asyncio.to_thread(BookPersonaService, root)
                        await service.run(
                            build_id, model.provider, PersonaConfig.from_model(model.config)
                        )
                    else:
                        discovery = await asyncio.to_thread(BookDiscoveryService, root)
                        await discovery.run(build_id, model.provider, model.config)
            except Exception:
                logger.error("Book discovery worker failed before completion")
            finally:
                if cls._build_tasks.get(key) is asyncio.current_task():
                    cls._build_tasks.pop(key, None)

        cls._build_tasks[key] = asyncio.create_task(execute())

    async def _discovery(self, root: Path, request: BookWorldRequest) -> dict[str, Any]:
        service = await asyncio.to_thread(BookDiscoveryService, root)
        if request.action in ("start_persona", "get_character"):
            return await self._persona(root, request)
        if request.action in ("cancel_build", "retry_build", "resume_build"):
            current = await asyncio.to_thread(service.get_build, request.item_id, request.build_id)
            if current["stage"] in ("persona_extract", "persona_published"):
                return await self._persona(root, request)
        model = None
        if request.action == "start_discovery":
            assert request.source_version_id is not None
            try:
                model = await asyncio.to_thread(resolve_discovery_model)
                result = await asyncio.to_thread(
                    service.create_build, request.item_id, request.source_version_id, model.config
                )
            except BookWorldError as error:
                if error.code != "blocked_config":
                    raise
                result = await asyncio.to_thread(
                    service.create_build,
                    request.item_id,
                    request.source_version_id,
                    DiscoveryConfig(),
                    config_error=str(error),
                )
        elif request.action in ("retry_build", "resume_build"):
            assert request.build_id is not None
            model = await asyncio.to_thread(resolve_discovery_model)
            previous = await asyncio.to_thread(service.get_build, request.item_id, request.build_id)
            if previous["config"] != model.config.model_dump():
                raise BookWorldError("config_changed", "Configuration changed; start a new build")
            if request.action == "retry_build":
                result = await asyncio.to_thread(
                    service.retry_build, request.item_id, request.build_id
                )
                await self._stop_worker(root, request.build_id)
            elif previous["can_resume"]:
                result = previous
                await self._stop_worker(root, request.build_id)
            else:
                raise BookWorldError(
                    "invalid_build_state", "Build is still active or cannot be resumed"
                )
        elif request.action == "cancel_build":
            assert request.build_id is not None
            result = await asyncio.to_thread(
                service.cancel_build, request.item_id, request.build_id
            )
            await self._stop_worker(root, request.build_id)
        elif request.action == "list_characters":
            assert request.build_id is not None
            result = await asyncio.to_thread(
                service.list_characters,
                request.item_id,
                request.build_id,
                request.offset,
                request.limit,
            )
        else:
            result = await asyncio.to_thread(
                service.get_build, request.item_id, request.build_id, request.source_version_id
            )
        if (
            model
            and result.get("stage") == "character_discovery"
            and result.get("status") in ("queued", "running")
        ):
            self._schedule(root, result["build_id"], model)
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            **result,
        }

    async def _persona(self, root: Path, request: BookWorldRequest) -> dict[str, Any]:
        service = await asyncio.to_thread(BookPersonaService, root)
        assert request.build_id is not None
        model = None
        if request.action == "get_character":
            assert request.character_id is not None
            result = await asyncio.to_thread(
                service.get_character, request.item_id, request.build_id, request.character_id
            )
        elif request.action == "cancel_build":
            result = await asyncio.to_thread(
                service.control, request.item_id, request.build_id, "cancel"
            )
            await self._stop_worker(root, request.build_id)
        else:
            model = await asyncio.to_thread(resolve_discovery_model)
            config = PersonaConfig.from_model(model.config)
            if request.action == "start_persona":
                result = await asyncio.to_thread(
                    service.request_build, request.item_id, request.build_id, config
                )
            else:
                current = await asyncio.to_thread(
                    service.discovery.get_build, request.item_id, request.build_id
                )
                if current["config"] != config.model_dump():
                    raise BookWorldError(
                        "config_changed", "Resume requires original persona model configuration"
                    )
                if request.action == "retry_build":
                    result = await asyncio.to_thread(
                        service.control, request.item_id, request.build_id, "retry"
                    )
                elif request.action == "resume_build" and current["can_resume"]:
                    result = current
                else:
                    raise BookWorldError("invalid_build_state", "Persona build cannot be resumed")
                await self._stop_worker(root, request.build_id)
        if (
            model
            and result.get("stage") == "persona_extract"
            and result.get("status") in ("queued", "running")
        ):
            self._schedule(root, result["build_id"], model, phase="persona")
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            **result,
        }

    async def _revision(self, root: Path, request: BookWorldRequest) -> dict[str, Any]:
        service = await asyncio.to_thread(BookRevisionService, root)
        assert request.build_id is not None
        if request.action == "get_revision_context":
            result = await asyncio.to_thread(service.get_context, request.item_id, request.build_id)
        elif request.action == "save_extension":
            assert request.character_id is not None and request.extension_text is not None
            result = await asyncio.to_thread(
                service.save_extension,
                request.item_id,
                request.build_id,
                request.character_id,
                request.extension_text,
            )
        else:
            assert (
                request.expected_revision is not None
                and request.patches is not None
                and request.revision_request_id is not None
            )
            model = await asyncio.to_thread(resolve_discovery_model)
            result = await service.create_revision(
                request.item_id,
                request.build_id,
                request.expected_revision,
                request.patches,
                request.revision_request_id,
                model.provider,
                PersonaConfig.from_model(model.config),
            )
            if result["status"] in ("queued", "running"):
                self._schedule(root, result["build_id"], model, phase="persona")
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            **result,
        }

    async def _knowledge(self, root: Path, request: BookWorldRequest) -> dict[str, Any]:
        assert request.build_id is not None and request.character_id is not None
        knowledge = await asyncio.to_thread(CharacterKnowledgeService, root)
        scope = await asyncio.to_thread(
            knowledge.bind_character, request.item_id, request.build_id, request.character_id
        )
        expressions = await asyncio.to_thread(CharacterExpressionService, root)
        model = None
        if request.action == "preview_knowledge":
            facts = await asyncio.to_thread(
                knowledge.retrieve,
                scope,
                request.query,
                request.knowledge_limit,
                request.retrospective,
            )
            baseline = await asyncio.to_thread(knowledge.baseline, scope)
            expression = await asyncio.to_thread(
                expressions.retrieve,
                scope,
                request.query,
                request.dialogue_action,
                knowledge_context=facts,
            )
            result = {
                "knowledge": facts.model_dump(mode="json"),
                "baseline": baseline.model_dump(mode="json"),
                "expression": expression.model_dump(mode="json"),
            }
        elif request.action == "list_expression_materials":
            assert request.expression_set_id is not None
            if request.limit > 100:
                raise BookWorldError("invalid_request", "Expression page limit must not exceed 100")
            result = await asyncio.to_thread(
                expressions.list_materials,
                scope,
                request.expression_set_id,
                request.offset,
                request.limit,
            )
        elif request.action == "get_expression_set":
            result = await asyncio.to_thread(expressions.get_set, scope, request.expression_set_id)
        elif request.action == "cancel_expression_set":
            assert request.expression_set_id is not None
            async with self._expression_lock(root, request.expression_set_id):
                result = await asyncio.to_thread(
                    expressions.control, scope, request.expression_set_id, "cancel"
                )
                await self._stop_worker(root, f"expression:{request.expression_set_id}")
        else:
            model = await asyncio.to_thread(resolve_discovery_model)
            config = ExpressionConfig.from_model(model.config, model.context_window)
            if request.action == "start_expression_set":
                result = await asyncio.to_thread(expressions.create_set, scope, config)
                async with self._expression_lock(root, result["set_id"]):
                    result = await asyncio.to_thread(expressions.get_set, scope, result["set_id"])
                    if result["status"] in ("queued", "running"):
                        self._schedule(root, result["set_id"], model, phase="expression")
            else:
                assert request.expression_set_id is not None
                async with self._expression_lock(root, request.expression_set_id):
                    current = await asyncio.to_thread(
                        expressions.get_set, scope, request.expression_set_id
                    )
                    if current["config"] != config.model_dump():
                        raise BookWorldError(
                            "config_changed",
                            "Resume requires the original expression configuration",
                        )
                    result = await asyncio.to_thread(
                        expressions.control,
                        scope,
                        request.expression_set_id,
                        "retry" if request.action == "retry_expression_set" else "resume",
                    )
                    await self._stop_worker(root, f"expression:{request.expression_set_id}")
                    self._schedule(root, result["set_id"], model, phase="expression")
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            "build_id": request.build_id,
            "character_id": request.character_id,
            **result,
        }

    @staticmethod
    def _execute(root: Path, request: BookWorldRequest) -> dict[str, Any]:
        service = BookSourceService(root)
        if request.action == "prepare_source":
            result = service.prepare_source(
                request.item_id, expected_attachment_sha256=request.expected_attachment_sha256
            )
        elif request.action == "get_source":
            result = service.get_source(request.item_id, request.source_version_id)
        elif request.action == "list_segments":
            assert request.source_version_id is not None
            result = service.list_segments(
                request.item_id, request.source_version_id, request.after_ordinal, request.limit
            )
        elif request.action == "resolve_evidence":
            assert request.source_version_id is not None and request.segment_id is not None
            result = service.resolve_evidence(
                request.item_id,
                request.source_version_id,
                request.segment_id,
                request.local_start,
                request.local_end,
            )
        elif request.action == "read_source":
            assert request.source_version_id is not None
            result = service.read_source(
                request.item_id, request.source_version_id, request.offset, request.text_limit
            )
        else:
            raise BookWorldError("invalid_request", "Unknown source operation")
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            **result,
        }

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
        try:
            request = BookWorldRequest.model_validate(message.data)
        except ValidationError as error:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={
                        "error": "Invalid book-world request",
                        "code": "invalid_request",
                        "details": error.errors(include_context=False),
                    },
                ),
            )
            return
        root = Path(get_workspace_path()).resolve()
        try:
            require_world_action(request.action)
        except BookWorldError as error:
            await self.send_response(websocket, WSMessage(type=MessageType.ERROR, request_id=message.request_id, data={"code": error.code, "error": str(error)}))
            return
        if request.action == "create_revision":
            if len(self._revision_requests) >= 32:
                await self.send_response(
                    websocket,
                    WSMessage(
                        type=MessageType.ERROR,
                        request_id=message.request_id,
                        data={
                            "error": "Too many pending correction requests",
                            "code": "revision_busy",
                        },
                    ),
                )
                return

            async def execute_revision() -> None:
                key = (asyncio.get_running_loop(), workspace_identity(root))
                slots = self._revision_slots.setdefault(key, asyncio.Semaphore(2))
                async with slots:
                    await self._respond(websocket, message, root, request)

            task = asyncio.create_task(execute_revision())
            self._worker_roots[workspace_identity(root)] = root
            self._revision_requests.add(task)

            def finished(completed: asyncio.Task) -> None:
                self._revision_requests.discard(completed)
                if not completed.cancelled() and completed.exception():
                    logger.warning(
                        "Correction result could not reach the disconnected client; inspect persisted build history"
                    )

            task.add_done_callback(finished)
            return
        await self._respond(websocket, message, root, request)

    async def _respond(
        self, websocket: WebSocket, message: WSMessage, root: Path, request: BookWorldRequest
    ) -> None:
        try:
            if request.action in (
                "get_auto_import",
                "cancel_auto_import",
                "retry_auto_import",
                "continue_auto_import",
                "restart_auto_import",
            ):
                from backend.services.book_world.automatic import AutoImportService
                from backend.services.book_world.automatic_runner import AutoImportRunner

                service = await asyncio.to_thread(AutoImportService, root)
                if (
                    request.workspace_id is not None
                    and request.workspace_id != service.workspace_id
                ):
                    raise BookWorldError(
                        "invalid_scope", "Workspace changed; reload the current import"
                    )
                if request.action == "get_auto_import":
                    result = {
                        "workspace_id": service.workspace_id,
                        "job": await asyncio.to_thread(service.get_job, request.item_id),
                    }
                else:
                    assert request.automatic_job_id is not None
                    async with AutoImportRunner.control_lock(root, request.automatic_job_id):
                        controlled = await asyncio.to_thread(
                            service.control,
                            request.item_id,
                            request.automatic_job_id,
                            "cancel"
                            if request.action == "cancel_auto_import"
                            else "restart"
                            if request.action == "restart_auto_import"
                            else "continue"
                            if request.action == "continue_auto_import"
                            else "retry",
                        )
                        await AutoImportRunner.stop_job(root, request.automatic_job_id)
                    result = {"workspace_id": service.workspace_id, "job": controlled}
                    AutoImportRunner.start(root)
            elif request.action in (
                "preview_knowledge",
                "start_expression_set",
                "get_expression_set",
                "list_expression_materials",
                "cancel_expression_set",
                "resume_expression_set",
                "retry_expression_set",
            ):
                result = await self._knowledge(root, request)
            elif request.action in ("get_revision_context", "create_revision", "save_extension"):
                result = await self._revision(root, request)
            elif request.action in (
                "start_discovery",
                "get_build",
                "list_characters",
                "cancel_build",
                "retry_build",
                "resume_build",
                "start_persona",
                "get_character",
            ):
                result = await self._discovery(root, request)
            else:
                result = await asyncio.to_thread(self._execute, root, request)
            response = WSMessage(
                type=MessageType.BOOK_WORLD_RESULT, request_id=message.request_id, data=result
            )
        except BookWorldError as error:
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "error": str(error),
                    "code": error.code,
                    "workspace_id": workspace_identity(root),
                },
            )
        except Exception:
            logger.exception("Book-world source operation failed")
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "error": "Could not complete the book operation",
                    "code": "book_world_failed",
                },
            )
        await self.send_response(websocket, response)
