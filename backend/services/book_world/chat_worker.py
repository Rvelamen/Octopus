"""Finite generation/review/rewrite with no public tokens before fenced publication."""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from .chat_models import GENERATE_PROMPTS, REVIEW_PROMPTS, UNKNOWN_REPLY, ChatCandidate, ChatReview
from .chat_validation import validate_candidate, validate_review
from .context import CharacterContext, CharacterContextBuilder
from .discovery import _json
from .memory import RoomMemoryService
from .memory_models import (
    MEMORY_PROMPTS,
    MemoryCandidate,
    MemoryReview,
)
from .persona_validation import parse_json
from .room_models import CharacterChatConfig, RoomScope
from .round_execution import RoundExecution
from .rounds import BookRoundService
from .source import BookWorldError


class BookChatWorker:
    def __init__(
        self, workspace_root: str | Path, *, monotonic: Callable[[], float] = time.monotonic
    ):
        self.rounds = BookRoundService(workspace_root)
        self.contexts = CharacterContextBuilder(workspace_root)
        self.execution = RoundExecution(self.rounds)
        self.memory = RoomMemoryService(workspace_root)
        self.monotonic = monotonic

    async def run(
        self, scope: RoomScope, round_id: str, provider: Any, config: CharacterChatConfig
    ) -> None:
        started = self.monotonic()
        try:
            snapshot = await asyncio.to_thread(self.rounds.get_round, scope, round_id)
        except BookWorldError:
            return
        window_before_run = int(snapshot["window_elapsed_ms"])

        def elapsed_window() -> int:
            return window_before_run + int(max(0, self.monotonic() - started) * 1000)

        while True:
            if not await self._run_slot(scope, round_id, provider, config, elapsed_window):
                return
            try:
                remaining = await asyncio.to_thread(self.rounds.get_round, scope, round_id)
            except BookWorldError:
                return
            if remaining["status"] != "queued":
                return

    async def _run_slot(
        self,
        scope: RoomScope,
        round_id: str,
        provider: Any,
        config: CharacterChatConfig,
        elapsed_window: Callable[[], int],
    ) -> bool:
        try:
            lease = await asyncio.to_thread(self.execution.lease, scope, round_id, config)
        except BookWorldError as error:
            await asyncio.to_thread(self.execution.fail_before_start, scope, round_id, error.code)
            return False
        if lease is None:
            return False
        window_before_slot = lease.window_before

        def elapsed() -> int:
            return max(0, elapsed_window() - window_before_slot)

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(0.5)
                try:
                    if not await asyncio.to_thread(
                        self.execution.tick, lease, elapsed, verify_member=False
                    ):
                        return
                except BookWorldError:
                    return

        ticker = asyncio.create_task(heartbeat())
        try:
            context: CharacterContext | None = None

            async def call(
                phase: str, prompt: str, schema, *, candidate=None, feedback=None, context_data=None
            ) -> str:
                if not await asyncio.to_thread(
                    self.execution.tick,
                    lease,
                    elapsed,
                    attempt=phase == "generate",
                    phase="validating" if phase in ("review", "summary_review") else "generating",
                ):
                    raise BookWorldError("round_timeout", "Execution window reached its limit")
                remaining = lease.seconds - (lease.window_before + elapsed()) / 1000
                payload = {
                    "phase": phase,
                    "context": context_data
                    if context_data is not None
                    else context.payload
                    if context
                    else {},
                    "candidate": candidate,
                    "feedback": feedback,
                }
                messages = [
                    {"role": "system", "content": prompt + _json(schema)},
                    {"role": "user", "content": _json(payload)},
                ]
                if (
                    sum(len(message["content"].encode("utf-8")) for message in messages)
                    + lease.config.max_tokens
                    > lease.config.context_window
                ):
                    raise BookWorldError(
                        "context_insufficient", "Generation/review exceeds the context window"
                    )
                options: dict[str, Any] = {
                    "model": lease.config.model,
                    "max_tokens": lease.config.max_tokens,
                    "temperature": 0,
                }
                if lease.config.reasoning_effort:
                    options["reasoning_effort"] = lease.config.reasoning_effort
                response = await asyncio.wait_for(
                    provider.chat(messages, **options),
                    min(remaining, lease.config.call_timeout_seconds),
                )
                if response.finish_reason == "error":
                    raise BookWorldError(
                        "model_unavailable", "The chat model returned an execution error"
                    )
                if response.tool_calls or response.finish_reason not in ("stop", "end_turn"):
                    raise ValueError("Reply requested tools or was incomplete")
                return response.content or ""

            if lease.config.memory_policy_version == "typed-room-memory-v1":
                plan = await asyncio.to_thread(
                    self.memory.prepare_for_turn,
                    scope,
                    round_id,
                    max_input_bytes=min(18000, lease.config.max_input_tokens),
                )
                if plan is not None:
                    memory_prompt, memory_review_prompt = MEMORY_PROMPTS[
                        lease.config.memory_prompt_version
                    ]
                    try:
                        proposal = MemoryCandidate.model_validate_json(
                            parse_json(
                                await call(
                                    "summary_generate",
                                    memory_prompt,
                                    MemoryCandidate.model_json_schema(),
                                    context_data=plan.payload,
                                )
                            )
                        )
                        review = MemoryReview.model_validate_json(
                            parse_json(
                                await call(
                                    "summary_review",
                                    memory_review_prompt,
                                    MemoryReview.model_json_schema(),
                                    context_data=plan.payload,
                                    candidate=proposal.model_dump(),
                                )
                            )
                        )
                        if not await asyncio.to_thread(self.execution.tick, lease, elapsed):
                            raise BookWorldError(
                                "round_timeout", "Memory processing reached the time limit"
                            )
                        await asyncio.to_thread(
                            self.memory.publish,
                            plan,
                            proposal.model_dump(),
                            review.model_dump(),
                            fence=lease,
                            elapsed=elapsed,
                        )
                    except BookWorldError:
                        raise
                    except ValueError:
                        raise BookWorldError(
                            "memory_validation_failed", "Room memory could not be safely reviewed"
                        ) from None

            context = await asyncio.to_thread(
                self.contexts.compose, scope, round_id, lease.member_id
            )

            feedback = None
            for _attempt in range(2):
                try:
                    candidate = validate_candidate(
                        await call(
                            "generate",
                            GENERATE_PROMPTS[lease.config.prompt_version],
                            ChatCandidate.model_json_schema(),
                            feedback=feedback,
                        ),
                        context,
                    )
                    validate_review(
                        candidate,
                        await call(
                            "review",
                            REVIEW_PROMPTS[lease.config.review_prompt_version],
                            ChatReview.model_json_schema(),
                            candidate=candidate.model_dump(),
                        ),
                    )
                    return await asyncio.to_thread(
                        self.execution.publish, lease, context, candidate, elapsed
                    )
                except BookWorldError:
                    raise
                except ValueError as error:
                    feedback = "Every claims.text must copy a verbatim substring of content, without paraphrasing. Use only the supplied source pairs and do not add scene details or later experiences."
                    if type(error) is ValueError and str(error).startswith("Independent"):
                        feedback += " The independent reviewer rejected the body or its support; remove unsupported assertions and correct attribution."
            fallback = validate_candidate(
                _json({"content": UNKNOWN_REPLY, "dialogue_action": "express_unknown"}), context
            )
            try:
                validate_review(
                    fallback,
                    await call(
                        "review",
                        REVIEW_PROMPTS[lease.config.review_prompt_version],
                        ChatReview.model_json_schema(),
                        candidate=fallback.model_dump(),
                    ),
                )
            except BookWorldError:
                raise
            except ValueError:
                await asyncio.to_thread(
                    self.execution.stop, lease, "fallback_validation_failed", elapsed
                )
                return False
            return await asyncio.to_thread(
                self.execution.publish, lease, context, fallback, elapsed, fallback=True
            )
        except TimeoutError:
            await asyncio.to_thread(
                self.execution.stop,
                lease,
                "round_timeout"
                if lease.window_before + elapsed() >= lease.seconds * 1000
                else "model_timeout",
                elapsed,
            )
        except BookWorldError as error:
            if error.code == "stale_round":
                await asyncio.to_thread(self.execution.checkpoint_revoked, lease, elapsed)
                remaining = await asyncio.to_thread(self.rounds.get_round, scope, round_id)
                revoked = next(
                    (slot for slot in remaining["slots"] if slot["id"] == lease.slot_id), None
                )
                if (
                    remaining["status"] == "queued"
                    and revoked
                    and revoked.get("skip_reason") == "source_unavailable"
                ):
                    return True
            else:
                await asyncio.to_thread(self.execution.stop, lease, error.code, elapsed)
                if error.code in (
                    "character_unavailable",
                    "source_unavailable",
                    "member_unavailable",
                ):
                    remaining = await asyncio.to_thread(self.rounds.get_round, scope, round_id)
                    return bool(remaining["status"] == "queued")
        except asyncio.CancelledError:
            await asyncio.shield(
                asyncio.to_thread(self.execution.checkpoint_revoked, lease, elapsed, cancelled=True)
            )
            raise
        except Exception:
            await asyncio.to_thread(self.execution.stop, lease, "chat_failed", elapsed)
        finally:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
        # Deletion can race any provider outcome, including a timeout or transport
        # failure. Only source revocation hands off automatically in this window.
        try:
            remaining = await asyncio.to_thread(self.rounds.get_round, scope, round_id)
            revoked = next(
                (slot for slot in remaining["slots"] if slot["id"] == lease.slot_id), None
            )
            if (
                remaining["status"] == "queued"
                and revoked
                and revoked.get("skip_reason") == "source_unavailable"
            ):
                await asyncio.to_thread(self.execution.checkpoint_revoked, lease, elapsed)
                return True
        except BookWorldError:
            pass
        return False
