"""Finite generation/review/rewrite with no public tokens before fenced publication."""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from .chat_models import GENERATE_PROMPT, REVIEW_PROMPT, UNKNOWN_REPLY, ChatCandidate, ChatReview
from .chat_validation import validate_candidate, validate_review
from .context import CharacterContextBuilder
from .discovery import _json
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
        self.monotonic = monotonic

    async def run(
        self, scope: RoomScope, round_id: str, provider: Any, config: CharacterChatConfig
    ) -> None:
        started = self.monotonic()

        def elapsed() -> int:
            return int(max(0, self.monotonic() - started) * 1000)

        try:
            lease = await asyncio.to_thread(self.execution.lease, scope, round_id, config)
        except BookWorldError as error:
            await asyncio.to_thread(self.execution.fail_before_start, scope, round_id, error.code)
            return
        if lease is None:
            return

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
            context = await asyncio.to_thread(
                self.contexts.compose, scope, round_id, lease.member_id
            )

            async def call(
                phase: str, prompt: str, schema, *, candidate=None, feedback=None
            ) -> str:
                if not await asyncio.to_thread(
                    self.execution.tick, lease, elapsed, attempt=phase == "generate"
                ):
                    raise BookWorldError("round_timeout", "Execution window reached its limit")
                remaining = lease.seconds - (lease.window_before + elapsed()) / 1000
                payload = {
                    "phase": phase,
                    "context": context.payload,
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

            feedback = None
            for _attempt in range(2):
                try:
                    candidate = validate_candidate(
                        await call(
                            "generate",
                            GENERATE_PROMPT,
                            ChatCandidate.model_json_schema(),
                            feedback=feedback,
                        ),
                        context,
                    )
                    validate_review(
                        candidate,
                        await call(
                            "review",
                            REVIEW_PROMPT,
                            ChatReview.model_json_schema(),
                            candidate=candidate.model_dump(),
                        ),
                    )
                    await asyncio.to_thread(
                        self.execution.publish, lease, context, candidate, elapsed
                    )
                    return
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
                        REVIEW_PROMPT,
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
                return
            await asyncio.to_thread(
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
            if error.code != "stale_round":
                await asyncio.to_thread(self.execution.stop, lease, error.code, elapsed)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.to_thread(self.execution.stop, lease, "chat_failed", elapsed)
        finally:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
