"""Compose actor inputs from safe projections and public messages, never reader archives."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .discovery import _json
from .expressions import CharacterExpressionService
from .knowledge_models import AllowedEvidence, CanonicalScope
from .room_models import CharacterChatConfig, RoomScope
from .rounds import BookRoundService
from .search_terms import query_terms
from .source import BookWorldError
from .storage import connect


@dataclass(frozen=True)
class CharacterContext:
    room_scope: RoomScope
    character_scope: CanonicalScope
    member_id: str
    config: CharacterChatConfig
    payload: dict[str, Any]
    allowed: tuple[AllowedEvidence, ...]
    diagnostics: dict[str, Any]

    @property
    def serialized(self) -> str:
        return str(_json(self.payload))


class CharacterContextBuilder:
    def __init__(self, workspace_root: str | Path):
        self.rounds = BookRoundService(workspace_root)
        self.knowledge = self.rounds.rooms.knowledge
        self.expressions = CharacterExpressionService(workspace_root)

    @staticmethod
    def _message(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "seq": row["seq"],
            "speaker_type": row["speaker_type"],
            "speaker_member_id": row["speaker_member_id"],
            "content": row["content"],
            "identity": json.loads(row["identity_snapshot_json"]),
        }

    def compose(self, scope: RoomScope, round_id: str, member_id: str) -> CharacterContext:
        with connect(self.knowledge.db_path) as db:
            db.execute("BEGIN")
            round_row = self.rounds._round(db, scope, round_id)
            config = CharacterChatConfig.model_validate_json(round_row["generation_snapshot_json"])
            member = db.execute(
                "SELECT m.*,b.policy_version FROM book_room_members m JOIN book_builds b ON b.id=m.build_id AND b.book_id=m.book_id AND b.source_version_id=m.source_version_id WHERE m.room_id=? AND m.id=? AND m.active=1 AND m.state_epoch=?",
                (scope.room_id, member_id, scope.epoch),
            ).fetchone()
            if member is None:
                raise BookWorldError(
                    "member_unavailable", "Member is outside the current room epoch"
                )
            character = CanonicalScope(
                workspace_id=scope.workspace_id,
                canonical_policy_version=member["policy_version"],
                **{
                    key: member[key]
                    for key in ("book_id", "source_version_id", "build_id", "character_id")
                },
            )
            self.knowledge.validate_scope(db, character)
            user = db.execute(
                "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND round_id=? AND speaker_type='user'",
                (scope.room_id, scope.epoch, round_id),
            ).fetchone()
            if user is None:
                raise BookWorldError("invalid_turn", "Turn has no submitted user message")
            history = [
                self._message(row)
                for row in db.execute(
                    "SELECT * FROM book_room_messages WHERE room_id=? AND epoch=? AND id<>? ORDER BY seq DESC LIMIT 60",
                    (scope.room_id, scope.epoch, user["id"]),
                )
            ]
            history.reverse()
            aliases = [
                row[0]
                for row in db.execute(
                    "SELECT alias FROM book_character_aliases WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND review_state<>'ambiguous'",
                    character.binding,
                )
            ]
            identity = json.loads(member["identity_snapshot_json"])
            discussion = json.loads(round_row["discussion_snapshot_json"])
        words = query_terms(user["content"] + " " + (discussion.get("topic") or ""), aliases)
        query = ""
        for word in words:
            if len(query) + len(word) + 1 <= 1000:
                query += " " + word
        facts = self.knowledge.retrieve(character, query.strip())
        baseline = self.knowledge.baseline(character)
        set_id = config.expression_sets.get(member_id) if config.expression_enabled else None
        expressions = (
            self.expressions.retrieve(
                character,
                query.strip(),
                set_id=set_id,
                knowledge_context=facts,
                selection_version=config.expression_selection_version,
            )
            if set_id
            else None
        )
        payload = {
            "context_policy": "actor-context-v1",
            "room": scope.model_dump(),
            "character_scope": character.model_dump(),
            "identity": identity,
            "current_message": self._message(user),
            "discussion": discussion,
            "baseline": {slot: item.model_dump() for slot, item in baseline.slots.items()},
            "knowledge": {
                "status": facts.status,
                "query": facts.query,
                "items": [item.model_dump() for item in facts.items],
            },
            "expressions": {
                "rules": [item.model_dump() for item in expressions.rules] if expressions else [],
                "examples": [item.model_dump() for item in expressions.examples]
                if expressions
                else [],
            },
            "room_history": history,
        }
        budget = min(config.max_input_tokens, config.context_window - 2 * config.max_tokens - 6000)
        omitted_examples, omitted_history = 0, 0
        while len(_json(payload).encode("utf-8")) > budget and payload["expressions"]["examples"]:
            payload["expressions"]["examples"].pop()
            omitted_examples += 1
        while len(_json(payload).encode("utf-8")) > budget and payload["room_history"]:
            payload["room_history"].pop(0)
            omitted_history += 1
        encoded = _json(payload)
        if len(encoded.encode("utf-8")) > budget:
            raise BookWorldError(
                "context_insufficient",
                "Current question, baseline and necessary evidence exceed the model budget",
            )
        allowed = {
            (item.claim_id, item.evidence_id): item
            for item in (*facts.items, *baseline.slots.values())
        }
        diagnostics = {
            "context_policy": "actor-context-v1",
            "context_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
            "input_bytes": len(encoded.encode("utf-8")),
            "input_budget": budget,
            "budget_strategy": "conservative_utf8_bytes",
            "expression_set_id": set_id,
            "expression_selection_version": config.expression_selection_version,
            "expression_material_ids": [
                item["material_id"]
                for item in payload["expressions"]["rules"] + payload["expressions"]["examples"]
            ],
            "omitted_examples": omitted_examples,
            "omitted_history": omitted_history,
        }
        return CharacterContext(
            scope, character, member_id, config, payload, tuple(allowed.values()), diagnostics
        )
