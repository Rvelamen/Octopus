"""Bounded reviewed room memory with literal provenance and epoch publication fencing."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .discovery import _json, _now
from .memory_models import MEMORY_POLICY, MemoryCandidate, MemoryReview
from .room_models import RoomScope
from .rooms import BookRoomService
from .search_terms import query_terms
from .source import BookWorldError
from .storage import connect


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class MemoryPlan:
    scope: RoomScope
    through_seq: int
    previous_id: str | None
    previous_items: tuple[dict, ...]
    messages: tuple[dict, ...]
    input_hash: str
    omitted_previous_items: int = 0

    @property
    def payload(self) -> dict:
        return {
            "policy_version": MEMORY_POLICY,
            "room": self.scope.model_dump(),
            "through_seq": self.through_seq,
            "previous": list(self.previous_items),
            "messages": list(self.messages),
            "omitted_previous_items": self.omitted_previous_items,
        }


class RoomMemoryService:
    def __init__(self, workspace_root: str | Path):
        self.rooms = BookRoomService(workspace_root)
        self.db_path = self.rooms.db_path

    @staticmethod
    def _message(row) -> dict:
        return {
            "id": row["id"],
            "seq": row["seq"],
            "speaker_type": row["speaker_type"],
            "speaker_member_id": row["speaker_member_id"],
            "content": row["content"],
            "identity": json.loads(row["identity_snapshot_json"]),
        }

    @staticmethod
    def _read(db, scope: RoomScope, before_seq: int | None = None) -> dict | None:
        row = db.execute(
            "SELECT * FROM book_room_summaries WHERE room_id=? AND epoch=? AND validation_state='accepted' AND (? IS NULL OR through_seq<?) ORDER BY through_seq DESC LIMIT 1",
            (scope.room_id, scope.epoch, before_seq, before_seq),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["summary_json"])
        if payload.get("policy_version") != MEMORY_POLICY:
            raise BookWorldError("memory_unavailable", "Unsupported room memory policy")
        candidate = MemoryCandidate.model_validate({"items": payload["items"]})
        ids = {source for item in candidate.items for source in item.source_message_ids}
        stored = {
            entry[0]
            for entry in db.execute(
                "SELECT message_id FROM book_summary_sources WHERE room_id=? AND epoch=? AND summary_id=?",
                (scope.room_id, scope.epoch, row["id"]),
            )
        }
        if ids != stored:
            raise BookWorldError("memory_unavailable", "Memory source links are incomplete")
        return {
            "id": row["id"],
            "room_id": scope.room_id,
            "epoch": scope.epoch,
            "through_seq": row["through_seq"],
            "policy_version": MEMORY_POLICY,
            "items": [item.model_dump() for item in candidate.items],
        }

    def read(self, scope: RoomScope, *, before_seq: int | None = None) -> dict | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self.rooms._room(db, scope)
            return self._read(db, scope, before_seq)

    def prepare_for_turn(
        self, scope: RoomScope, round_id: str, *, max_input_bytes: int
    ) -> MemoryPlan | None:
        with connect(self.db_path) as db:
            self.rooms._room(db, scope)
            user = db.execute(
                "SELECT seq,content FROM book_room_messages WHERE room_id=? AND epoch=? AND round_id=? AND speaker_type='user'",
                (scope.room_id, scope.epoch, round_id),
            ).fetchone()
            if user is None:
                raise BookWorldError("invalid_turn", "Memory has no scoped user submission")
        return self.prepare(
            scope, before_seq=user["seq"], query=user["content"], max_input_bytes=max_input_bytes
        )

    def recall(
        self, scope: RoomScope, query: str, *, before_seq: int, limit: int = 6
    ) -> list[dict]:
        words = query_terms(query, [])
        if not words:
            return []
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self.rooms._room(db, scope)
            rows = db.execute(
                "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND seq<? AND ("
                + " OR ".join("content LIKE ?" for _ in words)
                + ") ORDER BY seq DESC LIMIT 100",
                (scope.room_id, scope.epoch, before_seq, *(f"%{word}%" for word in words)),
            ).fetchall()
            selected = sorted(
                rows, key=lambda row: (-sum(word in row["content"] for word in words), -row["seq"])
            )[:limit]
            return [self._message(row) for row in selected]

    def sources(self, scope: RoomScope, message_ids: list[str], *, before_seq: int) -> list[dict]:
        if not message_ids:
            return []
        if len(message_ids) > 40:
            raise BookWorldError("invalid_request", "Too many memory source messages")
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self.rooms._room(db, scope)
            rows = db.execute(
                "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND seq<? AND id IN (SELECT value FROM json_each(?)) ORDER BY seq",
                (scope.room_id, scope.epoch, before_seq, _json(message_ids)),
            ).fetchall()
            if {row["id"] for row in rows} != set(message_ids):
                raise BookWorldError(
                    "memory_unavailable", "Memory trigger is outside this room or epoch"
                )
            return [self._message(row) for row in rows]

    def prepare(
        self,
        scope: RoomScope,
        *,
        before_seq: int,
        keep_recent: int = 20,
        trigger_messages: int = 40,
        max_messages: int = 20,
        max_input_bytes: int = 18000,
        query: str = "",
    ) -> MemoryPlan | None:
        if (
            type(before_seq) is not int
            or before_seq < 1
            or not 1 <= keep_recent <= 60
            or not 1 <= trigger_messages <= 100
            or not 1 <= max_messages <= 40
            or not 2000 <= max_input_bytes <= 200000
        ):
            raise BookWorldError("invalid_request", "Invalid memory snapshot bounds")
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            room = self.rooms._room(db, scope)
            if before_seq > room["next_seq"]:
                raise BookWorldError("invalid_request", "Memory cannot include future messages")
            previous = self._read(db, scope, before_seq)
            after = previous["through_seq"] if previous else 0
            rows = db.execute(
                "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND seq>? AND seq<? ORDER BY seq",
                (scope.room_id, scope.epoch, after, before_seq),
            ).fetchall()
            if len(rows) <= keep_recent or (previous is None and len(rows) < trigger_messages):
                return None
            words = query_terms(query, [])
            old_items = previous["items"] if previous else []
            retained = [
                item
                for _, item in sorted(
                    enumerate(old_items),
                    key=lambda pair: (-sum(word in pair[1]["text"] for word in words), -pair[0]),
                )
            ]
            selected: list[dict[str, Any]] = []
            previous_id = previous["id"] if previous else None

            def draft(messages: list[dict]) -> MemoryPlan:
                return MemoryPlan(
                    scope,
                    messages[-1]["seq"],
                    previous_id,
                    tuple(retained),
                    tuple(messages),
                    "",
                    len(old_items) - len(retained),
                )

            for row in rows[:-keep_recent][:max_messages]:
                message = self._message(row)
                # Make room for one complete new message by evicting whole old entries.
                # Their original public sources remain available to scoped recall.
                while (
                    not selected
                    and retained
                    and len(_json(draft([message]).payload).encode()) > max_input_bytes
                ):
                    retained.pop()
                if len(_json(draft([*selected, message]).payload).encode()) > max_input_bytes:
                    break
                selected.append(message)
            if not selected:
                raise BookWorldError(
                    "memory_context_insufficient",
                    "A complete public message exceeds the memory input budget",
                )
        plan = draft(selected)
        return MemoryPlan(
            scope,
            plan.through_seq,
            plan.previous_id,
            plan.previous_items,
            plan.messages,
            _digest(plan.payload),
            plan.omitted_previous_items,
        )

    @staticmethod
    def validate(plan: MemoryPlan, candidate: dict, review: dict) -> MemoryCandidate:
        if _digest(plan.payload) != plan.input_hash:
            raise BookWorldError("invalid_memory", "Memory input changed after snapshot")
        proposal: MemoryCandidate = MemoryCandidate.model_validate(candidate)
        checks = MemoryReview.model_validate(review)
        if (
            not all((checks.supported, checks.attribution_correct, checks.uncertainty_preserved))
            or sorted(item.ordinal for item in checks.items) != list(range(len(proposal.items)))
            or any(not (item.supported and item.origin_correct) for item in checks.items)
        ):
            raise BookWorldError(
                "memory_validation_failed", "Independent memory review rejected the summary"
            )
        messages = {item["id"]: item for item in plan.messages}
        previous = {_json(item) for item in plan.previous_items}
        for item in proposal.items:
            if _json(item.model_dump()) in previous:
                continue
            if any(source not in messages for source in item.source_message_ids):
                raise BookWorldError(
                    "invalid_memory",
                    "New memory must cite this snapshot; old memory cannot be rewritten",
                )
            if any(
                (messages[source]["speaker_type"], messages[source]["speaker_member_id"])
                != (item.speaker_type, item.speaker_member_id)
                for source in item.source_message_ids
            ):
                raise BookWorldError(
                    "invalid_memory", "Memory attribution differs from its actual sources"
                )
        return proposal

    def publish(
        self,
        plan: MemoryPlan,
        candidate: dict,
        review: dict,
        *,
        fence=None,
        elapsed: Callable[[], int] | None = None,
    ) -> dict:
        proposal = self.validate(plan, candidate, review)
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.rooms._room(db, plan.scope)
            if fence is not None:
                row = db.execute(
                    "SELECT * FROM book_room_rounds WHERE room_id=? AND epoch=? AND id=?",
                    (plan.scope.room_id, plan.scope.epoch, fence.round_id),
                ).fetchone()
                if (
                    fence.scope != plan.scope
                    or row is None
                    or row["status"] != "running"
                    or row["cancel_requested"]
                    or row["lease_owner"] != fence.owner
                    or row["lease_generation"] != fence.generation
                    or row["lease_expires_at"] <= _now()
                ):
                    raise BookWorldError("stale_round", "Memory worker lease changed")
                member = db.execute(
                    "SELECT m.id FROM book_round_slots s JOIN book_room_members m ON m.room_id=s.room_id AND m.id=s.member_id JOIN book_room_sources src ON src.room_id=m.room_id AND src.book_id=m.book_id AND src.source_version_id=m.source_version_id AND src.build_id=m.build_id JOIN book_books b ON b.id=m.book_id JOIN book_source_versions v ON v.book_id=m.book_id AND v.id=m.source_version_id JOIN book_builds p ON p.book_id=m.book_id AND p.source_version_id=m.source_version_id AND p.id=m.build_id WHERE s.room_id=? AND s.epoch=? AND s.id=? AND s.round_id=? AND s.member_id=? AND s.status='running' AND m.active=1 AND m.speaking_mode<>'muted' AND m.state_epoch=s.epoch AND m.membership_generation=s.member_generation AND src.status='active' AND b.lifecycle_state='active' AND v.lifecycle_state='available' AND p.lifecycle_state='active'",
                    (
                        plan.scope.room_id,
                        plan.scope.epoch,
                        fence.slot_id,
                        fence.round_id,
                        fence.member_id,
                    ),
                ).fetchone()
                if member is None:
                    raise BookWorldError(
                        "member_unavailable", "Memory worker member authorization changed"
                    )
                if elapsed is not None and fence.window_before + elapsed() >= fence.seconds * 1000:
                    raise BookWorldError(
                        "round_timeout", "Memory publication reached its time limit"
                    )
            for message in plan.messages:
                row = db.execute(
                    "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND id=? AND seq<=?",
                    (plan.scope.room_id, plan.scope.epoch, message["id"], plan.through_seq),
                ).fetchone()
                if row is None or self._message(row) != message:
                    raise BookWorldError(
                        "invalid_memory", "Memory source changed or is outside its range"
                    )
            latest = self._read(db, plan.scope, plan.through_seq + 1)
            if latest is not None and latest["through_seq"] == plan.through_seq:
                return latest
            if (latest["id"] if latest else None) != plan.previous_id:
                raise BookWorldError(
                    "memory_conflict", "Another summary advanced the source snapshot"
                )
            identifier = str(uuid4())
            db.execute(
                "INSERT INTO book_room_summaries(id,room_id,epoch,through_seq,summary_json,validation_state) VALUES (?,?,?,?,?,'accepted')",
                (
                    identifier,
                    plan.scope.room_id,
                    plan.scope.epoch,
                    plan.through_seq,
                    _json(
                        {
                            "policy_version": MEMORY_POLICY,
                            "input_sha256": plan.input_hash,
                            "items": [item.model_dump() for item in proposal.items],
                        }
                    ),
                ),
            )
            for source in sorted(
                {source for item in proposal.items for source in item.source_message_ids}
            ):
                db.execute(
                    "INSERT INTO book_summary_sources(room_id,epoch,summary_id,message_id) VALUES (?,?,?,?)",
                    (plan.scope.room_id, plan.scope.epoch, identifier, source),
                )
            if (
                fence is not None
                and elapsed is not None
                and fence.window_before + elapsed() >= fence.seconds * 1000
            ):
                raise BookWorldError(
                    "round_timeout", "Memory publication crossed its time boundary"
                )
        result = self.read(plan.scope, before_seq=plan.through_seq + 1)
        assert result is not None
        return result
