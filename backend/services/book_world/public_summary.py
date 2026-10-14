"""An explicit, bounded public summary, using the existing sourced memory store."""

import asyncio
import time
from collections.abc import Callable

from .discovery import _json
from .memory import RoomMemoryService
from .memory_models import MEMORY_PROMPTS, MemoryCandidate, MemoryReview
from .persona_validation import parse_json
from .room_models import CharacterChatConfig, RoomScope
from .source import BookWorldError
from .storage import connect


class PublicRoomSummaryService:
    def __init__(self, workspace_root, *, monotonic=time.monotonic):
        self.memory = RoomMemoryService(workspace_root)
        self.monotonic = monotonic

    def _pending(self, scope, through_seq):
        with connect(self.memory.db_path) as db:
            self.memory.rooms._room(db, scope)
            return db.execute(
                "SELECT COUNT(*) FROM book_room_messages WHERE room_id=? AND epoch=? AND seq>?",
                (scope.room_id, scope.epoch, through_seq),
            ).fetchone()[0]

    async def summarize(
        self,
        scope: RoomScope,
        provider,
        config: CharacterChatConfig,
        *,
        time_limit_seconds: int,
        authorized: Callable[[], bool] = lambda: True,
        publication_authorized=None,
        on_commit=None,
    ) -> dict:
        if type(time_limit_seconds) is not int or time_limit_seconds <= 0:
            raise BookWorldError("invalid_request", "Summary requires a finite time window")
        deadline = self.monotonic() + time_limit_seconds

        def guard(db=None):
            if not authorized() or (
                publication_authorized is not None and not publication_authorized(db)
            ):
                raise BookWorldError("invalid_scope", "Summary workspace or authorization changed")
            if self.monotonic() >= deadline:
                raise BookWorldError("summary_timeout", "Public summary reached its time limit")

        guard()
        room = await asyncio.to_thread(self.memory.rooms.get_room, scope)
        if room["status"] != "active":
            raise BookWorldError("room_readonly", "Room cannot publish a new summary")
        budget = min(config.max_input_tokens, config.context_window - 2 * config.max_tokens - 6000)
        if budget < 4000:
            raise BookWorldError(
                "context_insufficient", "Model budget cannot hold a reviewed summary"
            )
        plan = await asyncio.to_thread(
            self.memory.prepare,
            scope,
            before_seq=room["next_seq"],
            keep_recent=0,
            trigger_messages=1,
            max_messages=40,
            max_input_bytes=min(18000, budget // 2),
        )
        if plan is None:
            existing = await asyncio.to_thread(self.memory.read, scope)
            pending = await asyncio.to_thread(
                self._pending, scope, existing["through_seq"] if existing else 0
            )
            guard()
            result = {
                "memory": existing,
                "calls": 0,
                "pending": pending,
                "timeLimitSeconds": time_limit_seconds,
            }
            if on_commit is not None:

                def complete_cached():
                    with connect(self.memory.db_path) as db:
                        db.execute("BEGIN IMMEDIATE")
                        self.memory.rooms._room(db, scope)
                        guard(db)
                        on_commit(db, result)

                await asyncio.to_thread(complete_cached)
            return result
        generate, review = MEMORY_PROMPTS[config.memory_prompt_version]

        async def call(phase, prompt, response_model, candidate=None):
            guard()
            payload = {"phase": phase, "context": plan.payload, "candidate": candidate}
            messages = [
                {"role": "system", "content": prompt + _json(response_model.model_json_schema())},
                {"role": "user", "content": _json(payload)},
            ]
            if sum(len(message["content"].encode()) for message in messages) > budget:
                raise BookWorldError(
                    "context_insufficient", "Public summary exceeds its input budget"
                )
            options = {"model": config.model, "max_tokens": config.max_tokens, "temperature": 0}
            if config.reasoning_effort:
                options["reasoning_effort"] = config.reasoning_effort
            try:
                response = await asyncio.wait_for(
                    provider.chat(messages, **options),
                    min(config.call_timeout_seconds, deadline - self.monotonic()),
                )
            except TimeoutError as error:
                raise BookWorldError(
                    "summary_timeout", "Public summary reached its time limit"
                ) from error
            guard()
            if response.tool_calls or response.finish_reason not in ("stop", "end_turn"):
                raise BookWorldError("summary_failed", "Public summary was incomplete")
            try:
                return response_model.model_validate_json(
                    parse_json(response.content or "")
                ).model_dump()
            except ValueError as error:
                raise BookWorldError(
                    "summary_failed", "Public summary returned an invalid result"
                ) from error

        candidate = await call(
            "public_summary",
            generate
            + "\n用户主动请求公共讨论总结。保留各说话者的重要观点、分歧与未知，不制造共识；听说和推测不能变为原著事实。",
            MemoryCandidate,
        )
        checks = await call("public_summary_review", review, MemoryReview, candidate)
        guard()
        completed: list[dict] = []

        def commit(db, memory):
            pending = db.execute(
                "SELECT COUNT(*) FROM book_room_messages WHERE room_id=? AND epoch=? AND seq>?",
                (scope.room_id, scope.epoch, memory["through_seq"]),
            ).fetchone()[0]
            result = {
                "memory": memory,
                "calls": 2,
                "pending": pending,
                "timeLimitSeconds": time_limit_seconds,
            }
            if on_commit is not None:
                on_commit(db, result)
            completed.append(result)

        await asyncio.to_thread(
            self.memory.publish, plan, candidate, checks, guard=guard, on_publish=commit
        )
        return completed[0]
