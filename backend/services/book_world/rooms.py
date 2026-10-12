"""Persistent room identity bound to public characters and immutable source versions."""

import json
import sqlite3
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from .discovery import _json
from .knowledge import CharacterKnowledgeService
from .knowledge_models import CanonicalScope
from .room_models import ROOM_POLICY_VERSION, RoomScope
from .source import BookWorldError
from .storage import connect


class BookRoomService:
    def __init__(self, workspace_root: str | Path):
        self.knowledge = CharacterKnowledgeService(workspace_root)
        self.root = self.knowledge.root
        self.db_path = self.knowledge.db_path
        self.workspace_id = self.knowledge.workspace_id

    def _room(self, db: sqlite3.Connection, scope: RoomScope) -> sqlite3.Row:
        if scope.workspace_id != self.workspace_id or scope.policy_version != ROOM_POLICY_VERSION:
            raise BookWorldError("invalid_scope", "Room belongs to another workspace or policy")
        row = db.execute(
            "SELECT r.* FROM book_rooms r JOIN book_room_epochs e ON e.room_id=r.id AND e.epoch=r.current_epoch WHERE r.id=? AND r.current_epoch=? AND e.state='active'",
            (scope.room_id, scope.epoch),
        ).fetchone()
        if row is None:
            raise BookWorldError("stale_room_epoch", "Room is missing or its memory epoch changed")
        return cast(sqlite3.Row, row)

    def bind_room(self, room_id: str, expected_epoch: int) -> RoomScope:
        scope = RoomScope(workspace_id=self.workspace_id, room_id=room_id, epoch=expected_epoch)
        with connect(self.db_path) as db:
            self._room(db, scope)
        return scope

    def create_single_room(
        self,
        character: CanonicalScope,
        *,
        client_room_id: str,
        title: str | None = None,
        reuse_existing: bool = False,
    ) -> dict[str, Any]:
        if (
            not isinstance(client_room_id, str)
            or not 1 <= len(client_room_id.strip()) <= 100
            or (
                title is not None
                and (not isinstance(title, str) or not 1 <= len(title.strip()) <= 200)
            )
        ):
            raise BookWorldError("invalid_request", "Invalid room creation identity or title")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            person = self.knowledge.validate_scope(db, character)
            existing = db.execute(
                "SELECT id,current_epoch FROM book_rooms WHERE client_room_id=?", (client_room_id,)
            ).fetchone()
            if existing is None and reuse_existing:
                existing = db.execute(
                    "SELECT r.id,r.current_epoch FROM book_rooms r JOIN book_room_members m ON m.room_id=r.id WHERE r.status='active' AND m.book_id=? AND m.source_version_id=? AND m.build_id=? AND m.character_id=? AND (SELECT COUNT(*) FROM book_room_members WHERE room_id=r.id)=1 ORDER BY r.created_at DESC,r.rowid DESC LIMIT 1",
                    character.binding,
                ).fetchone()
            if existing:
                members = db.execute(
                    "SELECT book_id,source_version_id,build_id,character_id FROM book_room_members WHERE room_id=?",
                    (existing["id"],),
                ).fetchall()
                if len(members) != 1 or tuple(members[0]) != character.binding:
                    raise BookWorldError(
                        "idempotency_conflict", "Creation identity was used for another character"
                    )
                room_id, epoch = existing["id"], existing["current_epoch"]
            else:
                room_id, epoch = str(uuid4()), 1
                book = db.execute(
                    "SELECT title_snapshot FROM book_books WHERE id=?", (character.book_id,)
                ).fetchone()
                public = {"name": person["name"], "book_title": book["title_snapshot"]}
                db.execute(
                    "INSERT INTO book_rooms(id,title,client_room_id,policy_snapshot_json) VALUES (?,?,?,?)",
                    (
                        room_id,
                        title.strip()
                        if title
                        else f"{person['name']} · {book['title_snapshot']}"[:200],
                        client_room_id,
                        _json({"policy_version": ROOM_POLICY_VERSION}),
                    ),
                )
                db.execute(
                    "INSERT INTO book_room_epochs(room_id,epoch,state) VALUES (?,1,'active')",
                    (room_id,),
                )
                db.execute(
                    "INSERT INTO book_room_sources(room_id,book_id,source_version_id,build_id,source_snapshot_json) VALUES (?,?,?,?,?)",
                    (
                        room_id,
                        *character.binding[:3],
                        _json(
                            {
                                "book_title": book["title_snapshot"],
                                "canonical_policy_version": character.canonical_policy_version,
                            }
                        ),
                    ),
                )
                db.execute(
                    "INSERT INTO book_room_members(id,room_id,book_id,source_version_id,build_id,character_id,seat_index,identity_snapshot_json,state_epoch) VALUES (?,?,?,?,?,?,0,?,1)",
                    (str(uuid4()), room_id, *character.binding, _json(public)),
                )
        return self.get_room(
            RoomScope(workspace_id=self.workspace_id, room_id=room_id, epoch=epoch)
        )

    def get_room(self, scope: RoomScope) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            row = self._room(db, scope)
            members = []
            for member in db.execute(
                "SELECT m.*,c.agent_status,b.policy_version,b.lifecycle_state AS build_state,k.lifecycle_state AS book_state,s.lifecycle_state AS source_state,rs.status AS binding_state FROM book_room_members m JOIN book_characters c ON c.book_id=m.book_id AND c.source_version_id=m.source_version_id AND c.build_id=m.build_id AND c.id=m.character_id JOIN book_builds b ON b.book_id=m.book_id AND b.source_version_id=m.source_version_id AND b.id=m.build_id JOIN book_books k ON k.id=m.book_id JOIN book_source_versions s ON s.book_id=m.book_id AND s.id=m.source_version_id JOIN book_room_sources rs ON rs.room_id=m.room_id AND rs.book_id=m.book_id AND rs.source_version_id=m.source_version_id AND rs.build_id=m.build_id WHERE m.room_id=? ORDER BY m.seat_index",
                (scope.room_id,),
            ):
                available = (
                    member["book_state"] == "active"
                    and member["source_state"] == "available"
                    and member["build_state"] == "active"
                    and member["binding_state"] == "active"
                    and member["agent_status"] in ("ready", "sparse")
                )
                members.append(
                    {
                        **{
                            key: member[key]
                            for key in (
                                "id",
                                "book_id",
                                "source_version_id",
                                "build_id",
                                "character_id",
                                "seat_index",
                                "active",
                                "speaking_mode",
                                "membership_generation",
                                "removed_reason",
                            )
                        },
                        "identity": json.loads(member["identity_snapshot_json"]),
                        "available": available,
                        "canonical_policy_version": member["policy_version"],
                    }
                )
            return {
                "workspace_id": self.workspace_id,
                "room_id": row["id"],
                "epoch": row["current_epoch"],
                "title": row["title"],
                "next_seq": row["next_seq"],
                "status": row["status"],
                "discussion": {
                    "revision": row["discussion_revision"],
                    "mode": row["discussion_mode"],
                    "topic": row["discussion_topic"],
                    "goal": row["discussion_goal"],
                },
                "scene_capacity": row["scene_capacity"],
                "scene_layout_version": row["scene_layout_version"],
                "members": members,
                "latest_round_id": (
                    db.execute(
                        "SELECT id FROM book_room_rounds WHERE room_id=? AND epoch=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                        (scope.room_id, scope.epoch),
                    ).fetchone()
                    or {"id": None}
                )["id"],
            }

    def get_message_evidence(self, scope: RoomScope, message_id: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self._room(db, scope)
            if (
                db.execute(
                    "SELECT 1 FROM book_room_messages WHERE room_id=? AND epoch=? AND id=?",
                    (scope.room_id, scope.epoch, message_id),
                ).fetchone()
                is None
            ):
                raise BookWorldError(
                    "message_unavailable", "Message belongs to another room or epoch"
                )
            rows = db.execute(
                "SELECT r.*,e.segment_id,e.local_start,e.local_end,e.quote_text,v.approved_excerpt,k.library_item_id,k.title_snapshot,k.lifecycle_state AS book_state,s.lifecycle_state AS source_state FROM book_message_refs r LEFT JOIN book_access_evidence v ON v.book_id=r.book_id AND v.source_version_id=r.source_version_id AND v.build_id=r.build_id AND v.character_id=r.character_id AND v.claim_id=r.claim_id AND v.evidence_id=r.evidence_id LEFT JOIN book_evidence e ON e.book_id=r.book_id AND e.source_version_id=r.source_version_id AND e.build_id=r.build_id AND e.claim_id=r.claim_id AND e.id=r.evidence_id LEFT JOIN book_books k ON k.id=r.book_id LEFT JOIN book_source_versions s ON s.book_id=r.book_id AND s.id=r.source_version_id WHERE r.room_id=? AND r.epoch=? AND r.message_id=? ORDER BY r.assertion_ordinal,r.rowid",
                (scope.room_id, scope.epoch, message_id),
            ).fetchall()
            return {
                "message_id": message_id,
                "evidence": [
                    {
                        **dict(row),
                        "source_available": row["book_state"] == "active"
                        and row["source_state"] == "available",
                    }
                    for row in rows
                ],
            }

    def list_rooms(self, limit: int = 25, offset: int = 0) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise BookWorldError("invalid_request", "Invalid room page")
        with connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,current_epoch FROM book_rooms ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = db.execute("SELECT COUNT(*) FROM book_rooms").fetchone()[0]
        return {
            "rooms": [
                self.get_room(
                    RoomScope(
                        workspace_id=self.workspace_id,
                        room_id=row["id"],
                        epoch=row["current_epoch"],
                    )
                )
                for row in rows
            ],
            "total": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
        }

    def read_messages(
        self, scope: RoomScope, after_seq: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        if (
            type(after_seq) is not int
            or after_seq < 0
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise BookWorldError("invalid_request", "Invalid room history cursor")
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self._room(db, scope)
            rows = db.execute(
                "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND seq>? ORDER BY seq LIMIT ?",
                (scope.room_id, scope.epoch, after_seq, limit + 1),
            ).fetchall()
            messages = []
            for row in rows[:limit]:
                refs = [
                    dict(ref)
                    for ref in db.execute(
                        "SELECT assertion_ordinal,assertion_text,origin,book_id,source_version_id,build_id,character_id,claim_id,evidence_id,heard_message_id FROM book_message_refs WHERE room_id=? AND epoch=? AND message_id=? ORDER BY assertion_ordinal,rowid",
                        (scope.room_id, scope.epoch, row["id"]),
                    )
                ]
                messages.append(
                    {
                        **{
                            key: row[key]
                            for key in (
                                "id",
                                "seq",
                                "round_id",
                                "speaker_type",
                                "speaker_member_id",
                                "content",
                                "reply_to_id",
                                "created_at",
                            )
                        },
                        "identity": json.loads(row["identity_snapshot_json"]),
                        "refs": refs,
                    }
                )
            return {
                "messages": messages,
                "next_seq": rows[limit - 1]["seq"] if len(rows) > limit else None,
            }
