"""Finite speaker selection from public identity and room history only."""

import json

from .room_models import RoomScope
from .search_terms import query_terms
from .source import BookWorldError


def select_speakers(
    db, scope: RoomScope, content: str, mode: str, target_member_ids: list[str] | None
):
    if mode not in ("directed", "natural") or (
        target_member_ids is not None
        and (
            not 1 <= len(target_member_ids) <= 100
            or any(
                not isinstance(member, str) or not 1 <= len(member) <= 100
                for member in target_member_ids
            )
            or len(set(target_member_ids)) != len(target_member_ids)
        )
    ):
        raise BookWorldError("invalid_request", "Invalid bounded speaker request")
    members = db.execute(
        "SELECT m.*,b.policy_version FROM book_room_members m JOIN book_builds b ON b.book_id=m.book_id AND b.source_version_id=m.source_version_id AND b.id=m.build_id JOIN book_room_sources rs ON rs.room_id=m.room_id AND rs.book_id=m.book_id AND rs.source_version_id=m.source_version_id AND rs.build_id=m.build_id JOIN book_books k ON k.id=m.book_id JOIN book_source_versions v ON v.book_id=m.book_id AND v.id=m.source_version_id JOIN book_characters c ON c.book_id=m.book_id AND c.source_version_id=m.source_version_id AND c.build_id=m.build_id AND c.id=m.character_id WHERE m.room_id=? AND m.state_epoch=? AND m.active=1 AND m.speaking_mode<>'muted' AND rs.status='active' AND k.lifecycle_state='active' AND v.lifecycle_state='available' AND b.lifecycle_state='active' AND c.agent_status IN ('ready','sparse') ORDER BY m.seat_index",
        (scope.room_id, scope.epoch),
    ).fetchall()
    if mode == "directed":
        by_id = {member["id"]: member for member in members}
        if target_member_ids is None:
            if len(members) != 1:
                raise BookWorldError(
                    "invalid_room_mode", "Choose member identities for a group turn"
                )
            return members
        if not set(target_member_ids) <= by_id.keys():
            raise BookWorldError(
                "member_unavailable", "A requested member cannot speak in this room"
            )
        return [by_id[identifier] for identifier in target_member_ids]
    if target_member_ids is not None:
        raise BookWorldError("invalid_request", "Natural selection cannot carry directed targets")
    members = [member for member in members if member["speaking_mode"] == "auto"]
    if not members:
        raise BookWorldError("member_unavailable", "No automatic speaker is available")
    words = query_terms(content, [])
    aliases: dict[str, list[str]] = {}
    for member in members:
        aliases[member["id"]] = [
            row["alias"]
            for row in db.execute(
                "SELECT alias FROM book_character_aliases WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND review_state='accepted' ORDER BY alias",
                tuple(
                    member[key]
                    for key in ("book_id", "source_version_id", "build_id", "character_id")
                ),
            )
        ]
    last_spoken = {
        row["speaker_member_id"]: row["last_seq"]
        for row in db.execute(
            "SELECT speaker_member_id,MAX(seq) AS last_seq FROM book_room_messages WHERE room_id=? AND epoch=? AND speaker_type='character' GROUP BY speaker_member_id",
            (scope.room_id, scope.epoch),
        )
    }
    opportunities = {
        row["member_id"]: row["n"]
        for row in db.execute(
            "SELECT member_id,COUNT(*) AS n FROM book_round_slots WHERE room_id=? AND epoch=? AND status IN ('published','no_comment') GROUP BY member_id",
            (scope.room_id, scope.epoch),
        )
    }

    def rank(member):
        identity = json.loads(member["identity_snapshot_json"])
        name, label = identity.get("name", ""), identity.get("book_title", "")
        names = [name, *aliases[member["id"]]]
        score = (100 if any(len(value) > 1 and value in content for value in names) else 0) + sum(
            word in label or word in name for word in words
        )
        return (
            -score,
            opportunities.get(member["id"], 0),
            last_spoken.get(member["id"], 0),
            member["seat_index"],
        )

    ordered = sorted(members, key=rank)
    related = [member for member in ordered if rank(member)[0] < 0]
    return related[:3] if related else ordered[:1]
