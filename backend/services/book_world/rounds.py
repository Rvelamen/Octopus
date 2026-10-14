"""Atomic bounded turns: a fixed discussion/model snapshot, slots and one user message."""

import json
import sqlite3
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from .coordinator import select_speakers
from .discovery import _json, _now
from .knowledge_models import CanonicalScope
from .room_models import CharacterChatConfig, RoomScope
from .rooms import BookRoomService
from .round_queue import advance_cursor
from .source import BookWorldError
from .storage import connect


class BookRoundService:
    def __init__(self, workspace_root: str | Path):
        self.rooms = BookRoomService(workspace_root)
        self.db_path = self.rooms.db_path

    def _round(self, db: sqlite3.Connection, scope: RoomScope, round_id: str) -> sqlite3.Row:
        self.rooms._room(db, scope)
        row = db.execute(
            "SELECT * FROM book_room_rounds WHERE room_id=? AND epoch=? AND id=?",
            (scope.room_id, scope.epoch, round_id),
        ).fetchone()
        if row is None:
            raise BookWorldError("round_unavailable", "Turn belongs to another room or epoch")
        return cast(sqlite3.Row, row)

    def recover_interrupted(self) -> list[str]:
        """Called once at server startup: revoke old work, never schedule a model."""
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            identifiers = [
                row["id"]
                for row in db.execute(
                    "SELECT r.id FROM book_room_rounds r JOIN book_rooms room ON room.id=r.room_id AND room.current_epoch=r.epoch WHERE r.status IN ('queued','running') ORDER BY r.created_at,r.id"
                )
            ]
            for identifier in identifiers:
                db.execute(
                    "UPDATE book_room_rounds SET status='interrupted',error_code='service_interrupted',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_phase=NULL WHERE id=?",
                    (identifier,),
                )
                db.execute(
                    "UPDATE book_round_slots SET status='pending' WHERE round_id=? AND status='running'",
                    (identifier,),
                )
        return identifiers

    def get_round(self, scope: RoomScope, round_id: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._round(db, scope, round_id)
            if row["status"] == "running" and row["lease_expires_at"] <= _now():
                db.execute(
                    "UPDATE book_room_rounds SET status='interrupted',error_code='lease_expired',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_phase=NULL WHERE id=?",
                    (round_id,),
                )
                db.execute(
                    "UPDATE book_round_slots SET status='pending' WHERE round_id=? AND status='running'",
                    (round_id,),
                )
                row = self._round(db, scope, round_id)
            slots = [
                dict(slot)
                for slot in db.execute(
                    "SELECT id,position,member_id,status,attempts,member_generation,skip_reason FROM book_round_slots WHERE room_id=? AND epoch=? AND round_id=? ORDER BY position",
                    (scope.room_id, scope.epoch, round_id),
                )
            ]
            generation = None
            if (
                row["status"] == "running"
                and not row["cancel_requested"]
                and row["lease_expires_at"] > _now()
                and row["window_elapsed_ms"] < row["time_limit_seconds"] * 1000
                and self.rooms._room(db, scope)["status"] == "active"
            ):
                from .round_execution import RoundExecution

                slot = db.execute(
                    "SELECT * FROM book_round_slots WHERE room_id=? AND epoch=? AND round_id=? AND position=? AND status='running'",
                    (scope.room_id, scope.epoch, round_id, row["cursor"]),
                ).fetchone()
                try:
                    if slot is not None:
                        RoundExecution(self)._member(db, scope, slot)
                        generation = {
                            "round_id": round_id,
                            "slot_id": slot["id"],
                            "member_id": slot["member_id"],
                            "epoch": scope.epoch,
                            "lease_generation": row["lease_generation"],
                            "execution_window": row["execution_window"],
                            "phase": row["progress_phase"] or "preparing",
                            "expires_at": row["lease_expires_at"],
                        }
                except BookWorldError:
                    pass
            return {
                "round_id": row["id"],
                "room_id": scope.room_id,
                "epoch": scope.epoch,
                **{
                    key: row[key]
                    for key in (
                        "status",
                        "mode",
                        "cursor",
                        "time_limit_seconds",
                        "execution_window",
                        "window_elapsed_ms",
                        "total_elapsed_ms",
                        "error_code",
                        "run_started_at",
                    )
                },
                "discussion": json.loads(row["discussion_snapshot_json"]),
                "generation_config": json.loads(row["generation_snapshot_json"]),
                "can_resume": row["status"] in ("paused", "interrupted")
                or (row["status"] == "queued" and not row["lease_owner"])
                or (row["status"] == "running" and row["lease_expires_at"] <= _now()),
                "slots": slots,
                "generation": generation,
                "timeLimitSeconds": row["time_limit_seconds"],
                "executionWindow": row["execution_window"],
                "elapsedSeconds": row["window_elapsed_ms"] / 1000,
                "remainingSeconds": max(
                    0, row["time_limit_seconds"] - row["window_elapsed_ms"] / 1000
                ),
                "timeoutReason": row["error_code"] if row["status"] == "paused" else None,
            }

    @staticmethod
    def _submitted(
        db: sqlite3.Connection,
        scope: RoomScope,
        client_turn_id: str,
        content: str,
        mode: str = "directed",
        target_member_ids: list[str] | None = None,
    ) -> sqlite3.Row | None:
        existing = db.execute(
            "SELECT r.id,r.mode,r.discussion_snapshot_json,m.content FROM book_room_rounds r JOIN book_room_messages m ON m.round_id=r.id AND m.room_id=r.room_id AND m.epoch=r.epoch AND m.speaker_type='user' WHERE r.room_id=? AND r.epoch=? AND r.client_turn_id=?",
            (scope.room_id, scope.epoch, client_turn_id),
        ).fetchone()
        if existing is not None and (
            existing["content"] != content
            or existing["mode"] != mode
            or json.loads(existing["discussion_snapshot_json"])
            .get("speaker_request", {})
            .get("target_member_ids")
            != target_member_ids
        ):
            raise BookWorldError(
                "idempotency_conflict", "Turn identity was used for another message"
            )
        return cast(sqlite3.Row | None, existing)

    def find_submission(
        self,
        scope: RoomScope,
        client_turn_id: str,
        content: str,
        *,
        mode: str = "directed",
        target_member_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Look up an acknowledged turn before resolving model defaults for a new turn."""
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            room = self.rooms._room(db, scope)
            if room["status"] != "active":
                raise BookWorldError("room_readonly", "Room no longer accepts new turns")
            existing = self._submitted(db, scope, client_turn_id, content, mode, target_member_ids)
        return self.get_round(scope, existing["id"]) if existing is not None else None

    def submit(
        self,
        scope: RoomScope,
        client_turn_id: str,
        content: str,
        config: CharacterChatConfig,
        *,
        time_limit_seconds: int,
        mode: str = "directed",
        target_member_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(client_turn_id, str)
            or not 1 <= len(client_turn_id.strip()) <= 100
            or not isinstance(content, str)
            or not 1 <= len(content.strip()) <= 4000
            or len(content) > 4000
            or type(time_limit_seconds) is not int
            or time_limit_seconds <= 0
        ):
            raise BookWorldError("invalid_request", "Invalid user message or execution window")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            room = self.rooms._room(db, scope)
            if room["status"] != "active":
                raise BookWorldError("room_readonly", "Room no longer accepts new turns")
            existing = self._submitted(db, scope, client_turn_id, content, mode, target_member_ids)
            if existing:
                round_id = existing["id"]
            else:
                if (
                    not config.model
                    or config.provider_id is None
                    or config.policy_version != scope.policy_version
                ):
                    raise BookWorldError(
                        "blocked_config", "Configure a compatible character chat model"
                    )
                if db.execute(
                    "SELECT 1 FROM book_room_rounds WHERE room_id=? AND status IN ('queued','running','paused','interrupted')",
                    (scope.room_id,),
                ).fetchone():
                    raise BookWorldError("room_busy", "Complete or cancel the current turn first")
                members = select_speakers(db, scope, content, mode, target_member_ids)
                discussion = {
                    "revision": room["discussion_revision"],
                    "mode": room["discussion_mode"],
                    "topic": room["discussion_topic"],
                    "goal": room["discussion_goal"],
                    "speaker_request": {
                        "mode": mode,
                        "target_member_ids": target_member_ids,
                        "selection_policy": "public-room-selection-v1",
                    },
                }
                round_id = str(uuid4())
                expression_sets: dict[str, str | None] = {}
                for member in members:
                    if mode == "all" and member["skip_reason"]:
                        expression_sets[member["id"]] = None
                        continue
                    character = CanonicalScope(
                        workspace_id=scope.workspace_id,
                        canonical_policy_version=member["policy_version"],
                        **{
                            key: member[key]
                            for key in ("book_id", "source_version_id", "build_id", "character_id")
                        },
                    )
                    self.rooms.knowledge.validate_scope(db, character)
                    expression = (
                        db.execute(
                            "SELECT id FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND lifecycle_state='active' AND status IN ('ready','partial') ORDER BY created_at DESC,rowid DESC LIMIT 1",
                            character.binding,
                        ).fetchone()
                        if config.expression_enabled
                        else None
                    )
                    expression_sets[member["id"]] = expression["id"] if expression else None
                snapshot_config = config.model_copy(update={"expression_sets": expression_sets})
                db.execute(
                    "INSERT INTO book_room_rounds(id,room_id,epoch,client_turn_id,mode,discussion_snapshot_json,generation_snapshot_json,time_limit_seconds) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        round_id,
                        scope.room_id,
                        scope.epoch,
                        client_turn_id,
                        mode,
                        _json(discussion),
                        _json(snapshot_config.model_dump()),
                        time_limit_seconds,
                    ),
                )
                for position, member in enumerate(members):
                    skip = member["skip_reason"] if mode == "all" else None
                    db.execute(
                        "INSERT INTO book_round_slots(id,room_id,epoch,round_id,position,member_id,member_generation,status,skip_reason) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            str(uuid4()),
                            scope.room_id,
                            scope.epoch,
                            round_id,
                            position,
                            member["id"],
                            member["membership_generation"],
                            "no_comment" if skip else "pending",
                            skip,
                        ),
                    )
                db.execute(
                    "INSERT INTO book_room_messages(id,room_id,epoch,seq,round_id,speaker_type,content,validation_state) VALUES (?,?,?,?,?,'user',?,'not_applicable')",
                    (str(uuid4()), scope.room_id, scope.epoch, room["next_seq"], round_id, content),
                )
                advance_cursor(db, scope, round_id)
        return self.get_round(scope, round_id)

    def control(
        self, scope: RoomScope, round_id: str, action: str, *, time_limit_seconds: int | None = None
    ) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._round(db, scope, round_id)
            if action == "pause":
                if row["status"] not in ("queued", "running", "paused"):
                    raise BookWorldError("invalid_round_state", "Only an active turn can pause")
                if row["status"] != "paused":
                    db.execute(
                        "UPDATE book_room_rounds SET status='paused',error_code='user_pause',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_phase=NULL WHERE id=?",
                        (round_id,),
                    )
                    db.execute(
                        "UPDATE book_round_slots SET status='pending' WHERE round_id=? AND status='running'",
                        (round_id,),
                    )
            elif action == "cancel":
                if row["status"] not in ("completed", "cancelled"):
                    db.execute(
                        "UPDATE book_room_rounds SET status='cancelled',cancel_requested=1,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                        (round_id,),
                    )
                    db.execute(
                        "UPDATE book_round_slots SET status='cancelled' WHERE round_id=? AND status IN ('pending','running','failed')",
                        (round_id,),
                    )
            elif action == "resume":
                if self.rooms._room(db, scope)["status"] != "active":
                    raise BookWorldError(
                        "room_readonly", "Room no longer accepts execution windows"
                    )
                if type(time_limit_seconds) is not int or not 1 <= time_limit_seconds <= 2147483647:
                    raise BookWorldError(
                        "invalid_request", "Continue requires a positive seconds snapshot"
                    )
                if db.execute(
                    "SELECT 1 FROM book_room_rounds WHERE room_id=? AND id<>? AND status IN ('queued','running','paused','interrupted')",
                    (scope.room_id, round_id),
                ).fetchone():
                    raise BookWorldError(
                        "room_busy", "Finish the newer active turn before continuing"
                    )
                if not (
                    row["status"] in ("paused", "interrupted", "failed")
                    or (row["status"] == "queued" and not row["lease_owner"])
                    or (row["status"] == "running" and row["lease_expires_at"] <= _now())
                ):
                    raise BookWorldError("invalid_round_state", "Turn is active or completed")
                # Ending the old window precedes changing its immutable running snapshot.
                if row["status"] == "running":
                    db.execute(
                        "UPDATE book_room_rounds SET status='interrupted',lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                        (round_id,),
                    )
                db.execute(
                    "UPDATE book_room_rounds SET status='queued',cancel_requested=0,error_code=NULL,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,time_limit_seconds=?,execution_window=execution_window+1,window_elapsed_ms=0,run_started_at=NULL WHERE id=?",
                    (time_limit_seconds, round_id),
                )
                db.execute(
                    "UPDATE book_round_slots SET status='pending' WHERE round_id=? AND status IN ('running','failed')",
                    (round_id,),
                )
            else:
                raise BookWorldError("invalid_request", "Unknown round control")
        return self.get_round(scope, round_id)
