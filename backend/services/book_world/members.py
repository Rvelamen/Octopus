"""Atomic cross-book room membership with fixed original bindings and public identity."""

import json
from pathlib import Path
from uuid import uuid4

from .discovery import _json
from .knowledge_models import CanonicalScope
from .room_models import ROOM_POLICY_VERSION, RoomScope
from .rooms import BookRoomService
from .round_queue import advance_cursor
from .source import BookWorldError
from .storage import connect


class RoomMembershipService:
    def __init__(self, workspace_root: str | Path):
        self.rooms = BookRoomService(workspace_root)
        self.db_path = self.rooms.db_path

    @staticmethod
    def _characters(characters: list[CanonicalScope]) -> None:
        if not 1 <= len(characters) <= 100 or len(
            {actor.character_id for actor in characters}
        ) != len(characters):
            raise BookWorldError(
                "invalid_request", "Choose one to 100 distinct published characters"
            )
        bindings: dict[str, tuple[str, str]] = {}
        for actor in characters:
            binding = actor.source_version_id, actor.build_id
            if actor.book_id in bindings and bindings[actor.book_id] != binding:
                raise BookWorldError("source_binding_conflict", "A room fixes one build per book")
            bindings[actor.book_id] = binding

    def _insert(self, db, scope: RoomScope, characters: list[CanonicalScope], start: int) -> None:
        for seat, actor in enumerate(characters, start):
            person = self.rooms.knowledge.validate_scope(db, actor)
            book = db.execute(
                "SELECT title_snapshot FROM book_books WHERE id=?", (actor.book_id,)
            ).fetchone()
            bound = db.execute(
                "SELECT source_version_id,build_id FROM book_room_sources WHERE room_id=? AND book_id=?",
                (scope.room_id, actor.book_id),
            ).fetchone()
            if bound is not None and tuple(bound) != (actor.source_version_id, actor.build_id):
                raise BookWorldError(
                    "source_binding_conflict", "This book already has a different fixed build"
                )
            if bound is None:
                db.execute(
                    "INSERT INTO book_room_sources(room_id,book_id,source_version_id,build_id,source_snapshot_json) VALUES (?,?,?,?,?)",
                    (
                        scope.room_id,
                        *actor.binding[:3],
                        _json(
                            {
                                "book_title": book["title_snapshot"],
                                "canonical_policy_version": actor.canonical_policy_version,
                            }
                        ),
                    ),
                )
            db.execute(
                "INSERT INTO book_room_members(id,room_id,book_id,source_version_id,build_id,character_id,seat_index,identity_snapshot_json,state_epoch) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    scope.room_id,
                    *actor.binding,
                    seat,
                    _json({"name": person["name"], "book_title": book["title_snapshot"]}),
                    scope.epoch,
                ),
            )

    def add(self, scope: RoomScope, characters: list[CanonicalScope]) -> dict:
        self._characters(characters)
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            room = self.rooms._room(db, scope)
            if room["status"] != "active":
                raise BookWorldError("room_readonly", "Room no longer accepts members")
            if db.execute(
                "SELECT 1 FROM book_room_rounds WHERE room_id=? AND status IN ('queued','running','paused','interrupted')",
                (scope.room_id,),
            ).fetchone():
                raise BookWorldError(
                    "room_busy", "Complete or cancel the current turn before joining"
                )
            new_members = []
            for actor in characters:
                self.rooms.knowledge.validate_scope(db, actor)
                existing = db.execute(
                    "SELECT active FROM book_room_members WHERE room_id=? AND character_id=?",
                    (scope.room_id, actor.character_id),
                ).fetchone()
                if existing is None:
                    new_members.append(actor)
                elif not existing["active"]:
                    raise BookWorldError(
                        "member_removed", "Rejoin this existing member to preserve their seat"
                    )
            start = db.execute(
                "SELECT coalesce(MAX(seat_index)+1,0) FROM book_room_members WHERE room_id=?",
                (scope.room_id,),
            ).fetchone()[0]
            needed = start + len(new_members)
            if needed > room["scene_capacity"]:
                db.execute(
                    "UPDATE book_rooms SET scene_capacity=? WHERE id=?",
                    (((needed + 7) // 8) * 8, scope.room_id),
                )
            self._insert(db, scope, new_members, start)
        return self.rooms.get_room(scope)

    def control(
        self,
        scope: RoomScope,
        member_id: str,
        *,
        active: bool | None = None,
        speaking_mode: str | None = None,
    ) -> dict:
        if (
            (active is None and speaking_mode is None)
            or (active is not None and type(active) is not bool)
            or (
                speaking_mode is not None and speaking_mode not in ("auto", "mention_only", "muted")
            )
        ):
            raise BookWorldError("invalid_request", "Choose a member presence or speaking mode")
        revoked = []
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.rooms._room(db, scope)
            member = db.execute(
                "SELECT m.*,b.policy_version FROM book_room_members m JOIN book_builds b ON b.book_id=m.book_id AND b.source_version_id=m.source_version_id AND b.id=m.build_id WHERE m.room_id=? AND m.id=?",
                (scope.room_id, member_id),
            ).fetchone()
            if member is None:
                raise BookWorldError("member_unavailable", "Member belongs to another room")
            next_active = int(active) if active is not None else member["active"]
            mode = speaking_mode if speaking_mode is not None else member["speaking_mode"]
            if next_active and not member["active"]:
                if db.execute(
                    "SELECT 1 FROM book_room_rounds WHERE room_id=? AND status IN ('queued','running','paused','interrupted')",
                    (scope.room_id,),
                ).fetchone():
                    raise BookWorldError("room_busy", "Rejoin only after the current turn ends")
                actor = CanonicalScope(
                    workspace_id=scope.workspace_id,
                    canonical_policy_version=member["policy_version"],
                    **{
                        key: member[key]
                        for key in ("book_id", "source_version_id", "build_id", "character_id")
                    },
                )
                self.rooms.knowledge.validate_scope(db, actor)
                binding = db.execute(
                    "SELECT status FROM book_room_sources WHERE room_id=? AND book_id=? AND source_version_id=? AND build_id=?",
                    (scope.room_id, *actor.binding[:3]),
                ).fetchone()
                if binding is None or binding["status"] != "active":
                    raise BookWorldError(
                        "source_unavailable", "Original source binding cannot rejoin"
                    )
            if next_active != member["active"] or mode != member["speaking_mode"]:
                db.execute(
                    "UPDATE book_room_members SET active=?,speaking_mode=?,membership_generation=membership_generation+1,removed_reason=? WHERE room_id=? AND id=?",
                    (next_active, mode, None if next_active else "user", scope.room_id, member_id),
                )
                affected = db.execute(
                    "SELECT r.id,r.status,r.cursor,s.position FROM book_room_rounds r JOIN book_round_slots s ON s.room_id=r.room_id AND s.epoch=r.epoch AND s.round_id=r.id WHERE r.room_id=? AND r.epoch=? AND s.member_id=? AND r.status IN ('queued','running','paused','interrupted','failed') AND s.status IN ('pending','running','failed')",
                    (scope.room_id, scope.epoch, member_id),
                ).fetchall()
                db.execute(
                    "UPDATE book_round_slots SET status='no_comment' WHERE room_id=? AND epoch=? AND member_id=? AND status IN ('pending','running','failed') AND round_id IN (SELECT id FROM book_room_rounds WHERE room_id=? AND epoch=? AND status IN ('queued','running','paused','interrupted','failed'))",
                    (scope.room_id, scope.epoch, member_id, scope.room_id, scope.epoch),
                )
                for row in affected:
                    revoke = row["status"] == "running" and row["cursor"] == row["position"]
                    advance_cursor(db, scope, row["id"], revoke_current=revoke)
                    if revoke:
                        revoked.append(row["id"])
        return {**self.rooms.get_room(scope), "revoked_round_ids": revoked}

    def create(
        self, characters: list[CanonicalScope], *, client_room_id: str, title: str | None = None
    ) -> dict:
        self._characters(characters)
        if (
            not isinstance(client_room_id, str)
            or not 1 <= len(client_room_id.strip()) <= 100
            or (
                title is not None
                and (not isinstance(title, str) or not 1 <= len(title.strip()) <= 200)
            )
        ):
            raise BookWorldError("invalid_request", "Invalid room creation identity or title")
        creation = sorted([list(actor.binding) for actor in characters])
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            for actor in characters:
                self.rooms.knowledge.validate_scope(db, actor)
            previous = db.execute(
                "SELECT * FROM book_rooms WHERE client_room_id=?", (client_room_id,)
            ).fetchone()
            if previous is not None:
                if json.loads(previous["policy_snapshot_json"]).get("creation_members") != creation:
                    raise BookWorldError(
                        "idempotency_conflict", "Room identity was used for other characters"
                    )
                scope = RoomScope(
                    workspace_id=self.rooms.workspace_id,
                    room_id=previous["id"],
                    epoch=previous["current_epoch"],
                )
            else:
                scope = RoomScope(
                    workspace_id=self.rooms.workspace_id, room_id=str(uuid4()), epoch=1
                )
                db.execute(
                    "INSERT INTO book_rooms(id,title,client_room_id,policy_snapshot_json,scene_capacity) VALUES (?,?,?,?,?)",
                    (
                        scope.room_id,
                        title.strip() if title else "人物聊天室",
                        client_room_id,
                        _json(
                            {"policy_version": ROOM_POLICY_VERSION, "creation_members": creation}
                        ),
                        max(8, ((len(characters) + 7) // 8) * 8),
                    ),
                )
                db.execute(
                    "INSERT INTO book_room_epochs(room_id,epoch,state) VALUES (?,1,'active')",
                    (scope.room_id,),
                )
                self._insert(db, scope, characters, 0)
        return self.rooms.get_room(scope)
