"""Lease fencing and short transactions for timed character-message publication."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from .chat_models import ChatCandidate
from .context import CharacterContext
from .discovery import _json, _now
from .knowledge_models import CanonicalScope
from .room_models import CharacterChatConfig, RoomScope
from .round_queue import advance_cursor
from .rounds import BookRoundService
from .source import BookWorldError
from .storage import connect


@dataclass(frozen=True)
class RoundLease:
    scope: RoomScope
    round_id: str
    slot_id: str
    member_id: str
    owner: str
    generation: int
    config: CharacterChatConfig
    seconds: int
    window_before: int
    total_before: int
    execution_window: int = 1


class RoundExecution:
    def __init__(self, rounds: BookRoundService):
        self.rounds = rounds
        self.db_path = rounds.db_path

    def fail_before_start(self, scope: RoomScope, round_id: str, code: str) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.rounds._round(db, scope, round_id)
            if row["status"] == "queued" and not row["cancel_requested"] and not row["lease_owner"]:
                db.execute(
                    "UPDATE book_room_rounds SET status='failed',error_code=?,lease_generation=lease_generation+1 WHERE id=?",
                    (code, round_id),
                )
                db.execute(
                    "UPDATE book_round_slots SET status='failed' WHERE round_id=? AND status='pending'",
                    (round_id,),
                )

    def _member(self, db, scope: RoomScope, slot):
        member = db.execute(
            "SELECT m.*,b.policy_version FROM book_room_members m JOIN book_builds b ON b.id=m.build_id AND b.book_id=m.book_id AND b.source_version_id=m.source_version_id WHERE m.room_id=? AND m.id=?",
            (scope.room_id, slot["member_id"]),
        ).fetchone()
        if (
            member is None
            or not member["active"]
            or member["speaking_mode"] == "muted"
            or member["state_epoch"] != scope.epoch
            or member["membership_generation"] != slot["member_generation"]
        ):
            raise BookWorldError("member_unavailable", "Slot member authorization changed")
        character = CanonicalScope(
            workspace_id=scope.workspace_id,
            canonical_policy_version=member["policy_version"],
            **{
                key: member[key]
                for key in ("book_id", "source_version_id", "build_id", "character_id")
            },
        )
        self.rounds.rooms.knowledge.validate_scope(db, character)
        binding = db.execute(
            "SELECT status FROM book_room_sources WHERE room_id=? AND book_id=? AND source_version_id=? AND build_id=?",
            (scope.room_id, *character.binding[:3]),
        ).fetchone()
        if binding is None or binding["status"] != "active":
            raise BookWorldError("source_unavailable", "Slot source binding is unavailable")
        return member, character

    def lease(
        self, scope: RoomScope, round_id: str, config: CharacterChatConfig
    ) -> RoundLease | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.rounds._round(db, scope, round_id)
            if row["status"] != "queued" or row["cancel_requested"]:
                return None
            if self.rounds.rooms._room(db, scope)["status"] != "active":
                raise BookWorldError("room_readonly", "Room no longer permits generation")
            original = CharacterChatConfig.model_validate_json(row["generation_snapshot_json"])
            if original.model_dump(exclude={"expression_sets"}) != config.model_dump(
                exclude={"expression_sets"}
            ):
                raise BookWorldError(
                    "config_changed", "Continue with the original chat model and policy"
                )
            while True:
                slot = db.execute(
                    "SELECT * FROM book_round_slots WHERE room_id=? AND epoch=? AND round_id=? AND position=? AND status IN ('pending','failed')",
                    (scope.room_id, scope.epoch, round_id, row["cursor"]),
                ).fetchone()
                if slot is None:
                    raise BookWorldError("invalid_round", "No unfinished slot matches the cursor")
                try:
                    self._member(db, scope, slot)
                    break
                except BookWorldError as error:
                    if error.code not in (
                        "member_unavailable",
                        "source_unavailable",
                        "character_unavailable",
                    ):
                        raise
                    db.execute(
                        "UPDATE book_round_slots SET status='no_comment',skip_reason=? WHERE id=?",
                        (
                            "authorization_changed"
                            if error.code == "member_unavailable"
                            else "source_unavailable",
                            slot["id"],
                        ),
                    )
                    advance_cursor(db, scope, round_id)
                    row = self.rounds._round(db, scope, round_id)
                    if row["status"] == "completed":
                        return None
            owner, generation = str(uuid4()), row["lease_generation"] + 1
            db.execute(
                "UPDATE book_room_rounds SET status='running',lease_owner=?,lease_generation=?,lease_expires_at=?,run_started_at=?,error_code=NULL,progress_phase='preparing' WHERE id=?",
                (owner, generation, _now(row["time_limit_seconds"] + 60), _now(), round_id),
            )
            db.execute("UPDATE book_round_slots SET status='running' WHERE id=?", (slot["id"],))
            return RoundLease(
                scope,
                round_id,
                slot["id"],
                slot["member_id"],
                owner,
                generation,
                original,
                row["time_limit_seconds"],
                row["window_elapsed_ms"],
                row["total_elapsed_ms"],
                row["execution_window"],
            )

    def checkpoint_revoked(
        self, lease: RoundLease, elapsed: Callable[[], int], *, cancelled: bool = False
    ) -> None:
        """Keep spent time when member control revokes a worker before handing off its queue."""
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM book_room_rounds WHERE room_id=? AND epoch=? AND id=?",
                (lease.scope.room_id, lease.scope.epoch, lease.round_id),
            ).fetchone()
            if (
                row is None
                or row["execution_window"] != lease.execution_window
                or row["lease_generation"] != lease.generation + 1
                or row["lease_owner"] is not None
                or row["status"] not in ("queued", "paused", "completed", "cancelled")
                or (row["status"] == "paused" and not cancelled)
            ):
                return
            try:
                self.rounds.rooms._room(db, lease.scope)
            except BookWorldError:
                return
            spent = max(row["window_elapsed_ms"], lease.window_before + elapsed())
            db.execute(
                "UPDATE book_room_rounds SET window_elapsed_ms=?,total_elapsed_ms=? WHERE id=?",
                (
                    spent,
                    max(row["total_elapsed_ms"], lease.total_before + spent - lease.window_before),
                    lease.round_id,
                ),
            )

    def _fence(self, db, lease: RoundLease):
        if self.rounds.rooms._room(db, lease.scope)["status"] != "active":
            raise BookWorldError("room_readonly", "Room no longer permits generation")
        row = self.rounds._round(db, lease.scope, lease.round_id)
        if (
            row["status"] != "running"
            or row["cancel_requested"]
            or row["lease_owner"] != lease.owner
            or row["lease_generation"] != lease.generation
            or row["lease_expires_at"] <= _now()
        ):
            raise BookWorldError("stale_round", "Round lease is no longer valid")
        slot = db.execute(
            "SELECT * FROM book_round_slots WHERE room_id=? AND epoch=? AND round_id=? AND id=? AND member_id=? AND status='running'",
            (
                lease.scope.room_id,
                lease.scope.epoch,
                lease.round_id,
                lease.slot_id,
                lease.member_id,
            ),
        ).fetchone()
        if slot is None:
            raise BookWorldError("stale_round", "Slot is no longer running")
        return row, slot

    def _elapsed(self, db, lease: RoundLease, elapsed_ms: int) -> bool:
        elapsed_ms = max(0, elapsed_ms)
        window = lease.window_before + elapsed_ms
        db.execute(
            "UPDATE book_room_rounds SET window_elapsed_ms=?,total_elapsed_ms=? WHERE id=?",
            (window, lease.total_before + elapsed_ms, lease.round_id),
        )
        if window >= lease.seconds * 1000:
            db.execute(
                "UPDATE book_room_rounds SET status='paused',error_code='round_timeout',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                (lease.round_id,),
            )
            db.execute(
                "UPDATE book_round_slots SET status='pending' WHERE id=? AND status='running'",
                (lease.slot_id,),
            )
            return False
        return True

    def tick(
        self,
        lease: RoundLease,
        elapsed: Callable[[], int],
        *,
        attempt: bool = False,
        verify_member: bool = True,
        phase: str | None = None,
    ) -> bool:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            _, slot = self._fence(db, lease)
            if verify_member:
                self._member(db, lease.scope, slot)
            if not self._elapsed(db, lease, elapsed()):
                return False
            if attempt:
                db.execute(
                    "UPDATE book_round_slots SET attempts=attempts+1 WHERE id=?", (lease.slot_id,)
                )
            if phase is not None:
                db.execute(
                    "UPDATE book_room_rounds SET progress_phase=? WHERE id=?",
                    (phase, lease.round_id),
                )
            return True

    def stop(self, lease: RoundLease, code: str, elapsed: Callable[[], int]) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._fence(db, lease)
            except BookWorldError:
                return
            if not self._elapsed(db, lease, elapsed()):
                return
            if code in ("character_unavailable", "source_unavailable", "member_unavailable"):
                db.execute(
                    "UPDATE book_round_slots SET status='no_comment',skip_reason=? WHERE id=? AND status='running'",
                    (
                        "authorization_changed"
                        if code == "member_unavailable"
                        else "source_unavailable",
                        lease.slot_id,
                    ),
                )
                advance_cursor(db, lease.scope, lease.round_id, revoke_current=True)
                return
            paused = code in (
                "context_insufficient",
                "memory_context_insufficient",
                "model_timeout",
            )
            db.execute(
                "UPDATE book_room_rounds SET status=?,error_code=?,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_phase=NULL WHERE id=?",
                ("paused" if paused else "failed", code, lease.round_id),
            )
            db.execute(
                "UPDATE book_round_slots SET status=? WHERE id=? AND status='running'",
                ("pending" if paused else "failed", lease.slot_id),
            )

    def publish(
        self,
        lease: RoundLease,
        context: CharacterContext,
        candidate: ChatCandidate,
        elapsed: Callable[[], int],
        *,
        fallback: bool = False,
    ) -> bool:
        if context.room_scope != lease.scope or context.member_id != lease.member_id:
            raise BookWorldError(
                "invalid_scope", "Approved candidate belongs to another room member"
            )
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row, slot = self._fence(db, lease)
            member, character = self._member(db, lease.scope, slot)
            if context.character_scope != character:
                raise BookWorldError(
                    "invalid_scope", "Canonical source differs from approved actor context"
                )
            if not self._elapsed(db, lease, elapsed()):
                return False
            if candidate.dialogue_action == "no_comment":
                self._finish_slot(db, lease, elapsed, "no_comment")
                return True
            room = self.rounds.rooms._room(db, lease.scope)
            message_id = str(uuid4())
            db.execute(
                "INSERT INTO book_room_messages(id,room_id,epoch,seq,round_id,slot_id,speaker_type,speaker_member_id,identity_snapshot_json,reply_to_id,content,validation_state,publish_lease_generation,publish_member_generation,display_snapshot_json) VALUES (?,?,?,?,?,?,'character',?,?,?,?,'accepted',?,?,?)",
                (
                    message_id,
                    lease.scope.room_id,
                    lease.scope.epoch,
                    room["next_seq"],
                    lease.round_id,
                    lease.slot_id,
                    lease.member_id,
                    member["identity_snapshot_json"],
                    context.payload["current_message"]["id"],
                    candidate.content,
                    lease.generation,
                    member["membership_generation"],
                    _json(
                        {
                            "generation": context.diagnostics,
                            "fallback": fallback,
                            "dialogue_action": candidate.dialogue_action,
                            "action_basis_claim_ids": candidate.action_basis_claim_ids,
                            "action_basis_scope": context.character_scope.model_dump(),
                            "ephemeral_emotion": candidate.ephemeral_emotion.model_dump()
                            if candidate.ephemeral_emotion
                            else None,
                        }
                    ),
                ),
            )
            for ordinal, assertion in enumerate(candidate.claims):
                for ref in assertion.refs:
                    db.execute(
                        "INSERT INTO book_message_refs(id,room_id,epoch,message_id,speaker_member_id,assertion_ordinal,assertion_text,origin,book_id,source_version_id,build_id,character_id,claim_id,evidence_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            str(uuid4()),
                            lease.scope.room_id,
                            lease.scope.epoch,
                            message_id,
                            lease.member_id,
                            ordinal,
                            assertion.text,
                            assertion.origin,
                            *character.binding,
                            ref.claim_id,
                            ref.evidence_id,
                        ),
                    )
                for heard in assertion.message_ids:
                    db.execute(
                        "INSERT INTO book_message_refs(id,room_id,epoch,message_id,speaker_member_id,assertion_ordinal,assertion_text,origin,heard_message_id) VALUES (?,?,?,?,?,?,?,'room_hearsay',?)",
                        (
                            str(uuid4()),
                            lease.scope.room_id,
                            lease.scope.epoch,
                            message_id,
                            lease.member_id,
                            ordinal,
                            assertion.text,
                            heard,
                        ),
                    )
            if candidate.ephemeral_emotion:
                db.execute(
                    "UPDATE book_room_members SET ephemeral_state_json=? WHERE room_id=? AND id=? AND state_epoch=? AND membership_generation=?",
                    (
                        _json(candidate.ephemeral_emotion.model_dump()),
                        lease.scope.room_id,
                        lease.member_id,
                        lease.scope.epoch,
                        member["membership_generation"],
                    ),
                )
            self._finish_slot(db, lease, elapsed, "published")
            return True

    @staticmethod
    def _finish_slot(db, lease: RoundLease, elapsed: Callable[[], int], status: str) -> None:
        final_ms = elapsed()
        if lease.window_before + final_ms >= lease.seconds * 1000:
            raise BookWorldError("round_timeout", "Publication crossed its time boundary")
        db.execute(
            "UPDATE book_round_slots SET status=?,skip_reason=? WHERE id=?",
            (status, "no_comment" if status == "no_comment" else None, lease.slot_id),
        )
        db.execute(
            "UPDATE book_room_rounds SET window_elapsed_ms=?,total_elapsed_ms=? WHERE id=?",
            (lease.window_before + final_ms, lease.total_before + final_ms, lease.round_id),
        )
        advance_cursor(db, lease.scope, lease.round_id, revoke_current=True)
