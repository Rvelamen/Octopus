"""Book-bound canonical extraction, semantic review and immutable logical agents."""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .discovery import BookDiscoveryService, _hash, _json, _now
from .identity_graph import clone_graph
from .persona_models import (
    EVIDENCE_PERSONA_VERSION,
    EXTRACT_PROMPT,
    EXTRACT_PROMPTS,
    REVIEW_PROMPT,
    REVIEW_PROMPTS,
    SCOPED_PERSONA_VERSION,
    STRUCTURED_PERSONA_VERSION,
    PersonaBatch,
    PersonaConfig,
    PersonaReview,
    RevisedPersonaReview,
    persona_batch_schema,
)
from .persona_publication import publish_personas
from .persona_validation import apply_life_events, validate_batch, validate_review
from .revision_storage import correction_hints
from .source import BookWorldError
from .storage import connect


def _persona_error_detail(error: ValueError | TimeoutError, phase: str) -> str:
    if isinstance(error, ValidationError):
        issues = error.errors(include_input=False, include_context=False)[:6]
        detail = f"Invalid persona {phase} fields: " + "; ".join(
            ".".join(map(str, issue["loc"]))[:80] + f" [{issue['type']}]: " + issue["msg"][:130]
            for issue in issues
        )
    else:
        detail = (
            f"Persona {phase} model timed out"
            if isinstance(error, TimeoutError)
            else f"Persona {phase}: {error}"
        )
    return detail[:300]


class BookPersonaService:
    """No user-selected root or canonical permissions cross this service boundary."""

    def __init__(self, workspace_root: str | Path):
        self.discovery = BookDiscoveryService(workspace_root)
        self.source = self.discovery.source
        self.root = self.source.root
        self.db_path = self.source.db_path

    def request_build(self, item_id: int, parent_id: str, config: PersonaConfig) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            parent = self.discovery._build(db, item_id, parent_id)
            if parent["stage"] != "discovery_complete":
                raise BookWorldError(
                    "discovery_incomplete",
                    "Complete character discovery before extracting personas",
                )
            source = self.source._source(db, item_id, parent["source_version_id"])
            self.source._verify_snapshot(source)
            fingerprint = _hash({"parent": parent_id, "config": config.model_dump()})
            cached = db.execute(
                "SELECT id FROM book_builds WHERE book_id=? AND source_version_id=? AND build_fingerprint=?",
                (parent["book_id"], parent["source_version_id"], fingerprint),
            ).fetchone()
            if cached:
                build_id = cached["id"]
            else:
                build_id = str(uuid4())
                scope = (parent["book_id"], parent["source_version_id"], build_id)
                db.execute(
                    "INSERT INTO book_builds(id,book_id,source_version_id,parent_build_id,build_fingerprint,status,stage,config_snapshot_json,policy_version) VALUES (?,?,?,?,?,'queued','persona_extract',?,?)",
                    (
                        build_id,
                        scope[0],
                        scope[1],
                        parent_id,
                        fingerprint,
                        _json(config.model_dump()),
                        config.policy_version,
                    ),
                )
                people = db.execute(
                    "SELECT 1 FROM book_characters WHERE build_id=? LIMIT 1", (parent_id,)
                ).fetchone()
                if not people:
                    raise BookWorldError(
                        "no_characters", "Discovery has no characters to construct"
                    )
                clone_graph(db, parent_id, scope)
                self.seed_evidence_steps(db, scope, config)
        return self.discovery.get_build(item_id, build_id)

    def seed_evidence_steps(
        self, db: sqlite3.Connection, scope: tuple[str, str, str], config: PersonaConfig
    ) -> None:
        scenes = db.execute(
            "SELECT * FROM book_scenes WHERE build_id=? ORDER BY narrative_order", (scope[2],)
        ).fetchall()

        unit = 0
        for scene in scenes:
            scene_id = scene["id"]
            rows = db.execute(
                "SELECT s.id,s.ordinal,s.text FROM book_scene_segments x JOIN book_segments s ON s.id=x.segment_id AND s.source_version_id=x.source_version_id WHERE x.build_id=? AND x.scene_id=? ORDER BY x.position",
                (scope[2], scene_id),
            ).fetchall()
            batch: list[dict[str, Any]] = []
            size = 0
            groups = []
            for row in rows:
                if len(row["text"]) > config.unit_char_limit:
                    raise BookWorldError(
                        "segment_too_large", "Prepare source with the latest parser"
                    )
                if batch and (
                    len(batch) >= config.unit_segment_limit
                    or size + len(row["text"]) > max(2000, config.unit_char_limit // 2)
                ):
                    groups.append(batch)
                    batch, size = [], 0
                batch.append({"id": row["id"], "ordinal": row["ordinal"], "text": row["text"]})
                size += len(row["text"])
            if batch:
                groups.append(batch)
            for segments in groups:
                payload = {
                    "scene_id": scene_id,
                    "segment_ids": [segment["id"] for segment in segments],
                }
                db.execute(
                    "INSERT INTO book_build_steps(book_id,source_version_id,build_id,stage,unit_key,input_hash,status,result_json,lease_generation) VALUES (?,?,?,'evidence',?,?,'pending',?,0)",
                    (*scope, str(unit), _hash(segments), _json(payload)),
                )
                unit += 1

    def get_character(self, item_id: int, build_id: str, character_id: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            build = self.discovery._build(db, item_id, build_id)
            person = db.execute(
                "SELECT * FROM book_characters WHERE build_id=? AND id=?", (build_id, character_id)
            ).fetchone()
            if person is None:
                raise BookWorldError("character_unavailable", "Character belongs to another build")
            claims = []
            for claim in db.execute(
                "SELECT DISTINCT c.* FROM book_claims c LEFT JOIN book_claim_access a ON a.claim_id=c.id AND a.build_id=c.build_id WHERE c.build_id=? AND (c.owner_character_id=? OR a.character_id=?) ORDER BY c.rowid",
                (build_id, character_id, character_id),
            ):
                evidence = [
                    dict(row)
                    for row in db.execute(
                        "SELECT segment_id,local_start,local_end,quote_text,support_state FROM book_evidence WHERE build_id=? AND claim_id=?",
                        (build_id, claim["id"]),
                    )
                ]
                grants = [
                    dict(row)
                    for row in db.execute(
                        "SELECT character_id,route,access_state FROM book_claim_access WHERE build_id=? AND claim_id=? AND character_id=?",
                        (build_id, claim["id"], character_id),
                    )
                ]
                claims.append({**dict(claim), "evidence": evidence, "access": grants})
            return {
                "build_id": build_id,
                "character_id": character_id,
                "agent_status": person["agent_status"],
                "public": json.loads(person["public_profile_json"]),
                "reader": {
                    "claims": claims,
                    "baseline": self._baseline(db, build_id, character_id),
                    "extensions": [
                        dict(row)
                        for row in db.execute(
                            "SELECT id,text,created_at FROM book_user_extensions WHERE build_id=? AND character_id=? ORDER BY created_at,rowid",
                            (build_id, character_id),
                        )
                    ],
                },
                "published": build["stage"] == "persona_published"
                and build["status"] in ("published", "partial_published"),
            }

    @staticmethod
    def _baseline(db: sqlite3.Connection, build_id: str, character_id: str) -> dict[str, Any]:
        baseline = {
            row["slot_key"]: {
                "claim_id": row["claim_id"],
                "proposition": row["proposition"],
                "kind": row["kind"],
            }
            for row in db.execute(
                "SELECT b.slot_key,b.claim_id,c.proposition,c.kind FROM book_character_baselines b JOIN book_claims c ON c.id=b.claim_id AND c.build_id=b.build_id JOIN book_claim_access a ON a.build_id=b.build_id AND a.character_id=b.character_id AND a.claim_id=b.claim_id WHERE b.build_id=? AND b.character_id=? AND c.support_state='accepted' AND a.access_state='accepted'",
                (build_id, character_id),
            )
        }
        for entry in baseline.values():
            entry["evidence"] = [
                dict(row)
                for row in db.execute(
                    "SELECT e.id AS evidence_id,v.approved_excerpt FROM book_access_evidence v JOIN book_evidence e ON e.id=v.evidence_id AND e.claim_id=v.claim_id AND e.build_id=v.build_id WHERE v.build_id=? AND v.character_id=? AND v.claim_id=? AND v.visibility_state='accepted' AND e.support_state='accepted'",
                    (build_id, character_id, entry["claim_id"]),
                )
            ]
        return baseline

    def get_agent_definition(
        self, item_id: int, build_id: str, character_id: str
    ) -> dict[str, Any]:
        with connect(self.db_path) as db:
            build = self.discovery._build(db, item_id, build_id)
            person = db.execute(
                "SELECT * FROM book_characters WHERE build_id=? AND id=?", (build_id, character_id)
            ).fetchone()
            if (
                build["status"] not in ("published", "partial_published")
                or person is None
                or person["agent_status"] not in ("ready", "sparse")
            ):
                raise BookWorldError(
                    "agent_not_published", "This character has no published logical agent"
                )
            baseline = self._baseline(db, build_id, character_id)
            persona = {}
            for label, prefixes in {
                "beliefs": ("belief:",),
                "traits": ("trait:",),
                "relations": ("relation:",),
                "emotion_patterns": ("emotion:",),
                "style": ("style:",),
                "motivation": ("motivation:",),
                "values": ("value:",),
            }.items():
                values = [entry for slot, entry in baseline.items() if slot.startswith(prefixes)]
                persona[label] = values or "unknown"
            return {
                "agent_id": f"book:{build_id}:{character_id}",
                "kind": "book_character",
                "name": person["name"],
                "scope": {
                    "book_id": build["book_id"],
                    "source_version_id": build["source_version_id"],
                    "build_id": build_id,
                    "character_id": character_id,
                },
                "baseline": baseline,
                "persona": persona,
                "tools": [],
                "policy": json.loads(person["runtime_policy_json"]),
            }

    def control(self, item_id: int, build_id: str, action: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.discovery._build(db, item_id, build_id)
            if row["stage"] != "persona_extract" or row["status"] in (
                "published",
                "partial_published",
            ):
                raise BookWorldError("invalid_build_state", "Cannot modify published personas")
            if action == "cancel":
                db.execute(
                    "UPDATE book_builds SET status='cancelled',cancel_requested=1,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                    (build_id,),
                )
            elif action == "retry" and row["status"] in ("failed", "cancelled"):
                db.execute(
                    "UPDATE book_build_steps SET status='pending',attempts=0 WHERE build_id=? AND stage='evidence' AND status<>'validated'",
                    (build_id,),
                )
                db.execute(
                    "UPDATE book_builds SET status='queued',cancel_requested=0,lease_generation=lease_generation+1,error_code=NULL,error_detail=NULL WHERE id=?",
                    (build_id,),
                )
            else:
                raise BookWorldError(
                    "invalid_build_state", "Only failed or cancelled personas can be retried"
                )
        return self.discovery.get_build(item_id, build_id)

    def _lease(self, build_id: str, config: PersonaConfig) -> tuple[str, int] | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM book_builds WHERE id=?", (build_id,)).fetchone()
            if (
                row is None
                or row["stage"] != "persona_extract"
                or row["status"] not in ("queued", "running")
                or row["cancel_requested"]
                or row["lifecycle_state"] != "active"
            ):
                return None
            if row["lease_owner"] and row["lease_expires_at"] > _now():
                return None
            if row["config_snapshot_json"] != _json(config.model_dump()):
                raise BookWorldError(
                    "config_changed", "Resume requires the original persona configuration"
                )
            owner, generation = str(uuid4()), row["lease_generation"] + 1
            db.execute(
                "UPDATE book_builds SET status='running',lease_owner=?,lease_generation=?,lease_expires_at=? WHERE id=?",
                (owner, generation, _now(config.call_timeout_seconds + 60), build_id),
            )
            db.execute(
                "UPDATE book_build_steps SET status='pending' WHERE build_id=? AND stage='evidence' AND status='running'",
                (build_id,),
            )
            return owner, generation

    def _input(
        self, build_id: str, owner: str, generation: int, config: PersonaConfig
    ) -> dict[str, Any] | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            build = self.discovery._fence(db, build_id, owner, generation)
            step = db.execute(
                "SELECT * FROM book_build_steps WHERE build_id=? AND stage='evidence' AND status IN ('pending','running','failed') AND attempts<2 ORDER BY CAST(unit_key AS INTEGER) LIMIT 1",
                (build_id,),
            ).fetchone()
            if step is None:
                original = self.source._source(
                    db, build["library_item_id"], build["source_version_id"]
                )
                self.source._verify_snapshot(original)
                publish_personas(db, build)
                return None
            payload = json.loads(step["result_json"])
            ids = payload["segment_ids"]
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT id,ordinal,text FROM book_segments WHERE book_id=? AND source_version_id=? AND id IN ("
                    + ",".join("?" for _ in ids)
                    + ") ORDER BY ordinal",
                    (build["book_id"], build["source_version_id"], *ids),
                )
            ]
            if len(rows) != len(ids) or _hash(rows) != step["input_hash"]:
                raise BookWorldError(
                    "source_changed", "Source no longer matches the persona checkpoint"
                )
            characters = []
            for person in db.execute(
                "SELECT c.*,x.presence FROM book_scene_characters x JOIN book_characters c ON c.id=x.character_id AND c.build_id=x.build_id WHERE x.build_id=? AND x.scene_id=? ORDER BY c.name,c.id",
                (build_id, payload["scene_id"]),
            ):
                profile = json.loads(person["public_profile_json"])
                if (
                    profile.get("entity_kind") != "person"
                    or person["agent_status"] == "needs_review"
                ):
                    continue
                aliases = [
                    row[0]
                    for row in db.execute(
                        "SELECT alias FROM book_character_aliases WHERE build_id=? AND character_id=? ORDER BY alias LIMIT 12",
                        (build_id, person["id"]),
                    )
                ]
                characters.append(
                    {
                        "id": person["id"],
                        "name": person["name"],
                        "aliases": aliases,
                        "presence": person["presence"],
                        "entity_kind": json.loads(person["public_profile_json"]).get(
                            "entity_kind", "unknown"
                        ),
                        "agent_status": person["agent_status"],
                    }
                )
            prior = []
            for previous in db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence' AND status='validated' ORDER BY CAST(unit_key AS INTEGER) DESC",
                (build_id,),
            ):
                for baseline in json.loads(previous["result_json"]).get("baselines", []):
                    if baseline["character_id"] in {person["id"] for person in characters}:
                        prior.append(
                            {
                                "id": baseline["claim_id"],
                                "owner_character_id": baseline["character_id"],
                                "slot_key": baseline["slot_key"],
                                "proposition": baseline["proposition"],
                            }
                        )
                    if len(_json(prior)) > 2000:
                        prior.pop()
                        break
                if len(_json(prior)) > 1700:
                    break
            life_states: dict[str, Any] = {}
            for previous in db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence' AND status='validated' ORDER BY CAST(unit_key AS INTEGER)",
                (build_id,),
            ):
                life_states = apply_life_events(
                    life_states, json.loads(previous["result_json"]).get("life_events", [])
                )
            data = {
                "phase": "extract",
                "unit_key": step["unit_key"],
                "scene_id": payload["scene_id"],
                "segments": rows,
                "characters": characters,
                "prior_claims": prior,
                "correction_hints": correction_hints(db, build_id, ids),
                "known_life_states": {
                    key: value
                    for key, value in life_states.items()
                    if key in {person["id"] for person in characters}
                },
                "previous_error": payload.get("error"),
            }
            db.execute(
                "UPDATE book_build_steps SET status='running',attempts=attempts+1,lease_generation=? WHERE build_id=? AND stage='evidence' AND unit_key=?",
                (generation, build_id, step["unit_key"]),
            )
            db.execute(
                "UPDATE book_builds SET lease_expires_at=? WHERE id=?",
                (_now(config.call_timeout_seconds + 60), build_id),
            )
            return data

    def _renew(self, build_id: str, owner: str, generation: int, config: PersonaConfig) -> None:
        with connect(self.db_path) as db:
            self.discovery._fence(db, build_id, owner, generation)
            db.execute(
                "UPDATE book_builds SET lease_expires_at=? WHERE id=?",
                (_now(config.call_timeout_seconds + 60), build_id),
            )

    def _save(
        self,
        build_id: str,
        owner: str,
        generation: int,
        data: dict[str, Any],
        batch: PersonaBatch,
        review: PersonaReview,
    ) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            build = self.discovery._fence(db, build_id, owner, generation)
            scope = (build["book_id"], build["source_version_id"], build_id)
            checks = {item.local_key: item for item in review.claims}
            ids = {claim.local_key: str(uuid4()) for claim in batch.claims}
            baselines = []
            for claim in batch.claims:
                verdict = checks[claim.local_key]
                accepted = (
                    verdict.supported
                    and verdict.identity_consistent
                    and claim.interpretation_level != "speculative"
                )
                state = "accepted" if accepted else "rejected"
                target = claim.supersedes_claim_id or ids.get(claim.supersedes_local_key or "")
                if (
                    not verdict.correction_supported
                    or not accepted
                    or not verdict.baseline_supported
                    or verdict.temporal_state != "current"
                ):
                    target = None
                db.execute(
                    "INSERT INTO book_claims(id,book_id,source_version_id,build_id,kind,owner_character_id,proposition,truth_state,interpretation_level,support_state,scene_id,supersedes_claim_id,search_terms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ids[claim.local_key],
                        *scope,
                        claim.kind,
                        claim.owner_character_id,
                        claim.proposition,
                        claim.truth_state,
                        claim.interpretation_level,
                        state,
                        data["scene_id"],
                        target,
                        claim.proposition,
                    ),
                )
                evidence_ids = []
                for span in claim.evidence:
                    evidence_id = str(uuid4())
                    evidence_ids.append((evidence_id, span))
                    self._evidence(db, scope, ids[claim.local_key], evidence_id, span, state)
                grants = {grant.character_id: grant for grant in verdict.access}
                for access in claim.access:
                    permission = grants[access.character_id]
                    prior_boundary = data["known_life_states"].get(access.character_id)
                    died_here = any(
                        event.character_id == access.character_id
                        and event.state == "dead"
                        and event.temporal_state != "historical"
                        for event in review.life_events
                    )
                    revived_here = any(
                        event.character_id == access.character_id and event.resurrection_supported
                        for event in review.life_events
                    )
                    has_death_boundary = died_here or (
                        prior_boundary is not None
                        and prior_boundary["state"] in ("dead", "uncertain")
                    )
                    time_allowed = (
                        not has_death_boundary
                        or (
                            permission.before_death and permission.before_death_evidence is not None
                        )
                        or (
                            revived_here
                            and permission.after_resurrection
                            and permission.after_resurrection_evidence is not None
                        )
                    )
                    authorized = accepted and permission.authorized and time_allowed
                    db.execute(
                        "INSERT INTO book_claim_access(book_id,source_version_id,build_id,character_id,claim_id,route,acquisition_scene_id,disclosure,access_state) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            *scope,
                            access.character_id,
                            ids[claim.local_key],
                            access.route,
                            data["scene_id"],
                            access.disclosure,
                            "accepted" if authorized else "revoked",
                        ),
                    )
                    self._evidence(
                        db, scope, ids[claim.local_key], str(uuid4()), access.acquisition, state
                    )
                    if access.identity_evidence:
                        self._evidence(
                            db,
                            scope,
                            ids[claim.local_key],
                            str(uuid4()),
                            access.identity_evidence,
                            state,
                        )
                    for evidence_id, span in evidence_ids:
                        excerpt = (
                            access.approved_excerpt
                            if permission.excerpt_safe and access.approved_excerpt in span.quote
                            else ""
                        )
                        db.execute(
                            "INSERT INTO book_access_evidence(book_id,source_version_id,build_id,character_id,claim_id,evidence_id,approved_excerpt,visibility_state) VALUES (?,?,?,?,?,?,?,?)",
                            (
                                *scope,
                                access.character_id,
                                ids[claim.local_key],
                                evidence_id,
                                excerpt,
                                "accepted" if authorized else "rejected",
                            ),
                        )
                if claim.slot_key and accepted:
                    baselines.append(
                        {
                            "character_id": claim.owner_character_id,
                            "slot_key": claim.slot_key,
                            "claim_id": ids[claim.local_key],
                            "proposition": claim.proposition,
                            "temporal_state": verdict.temporal_state
                            if verdict.temporal_state == "historical" or verdict.baseline_supported
                            else "uncertain",
                            "supersedes_claim_id": target,
                        }
                    )
            for event in review.life_events:
                life_id = str(uuid4())
                name = next(
                    person["name"]
                    for person in data["characters"]
                    if person["id"] == event.character_id
                )
                proposition = (
                    f"{name}死亡" if event.state == "dead" else f"{name}原著生命状态为存活"
                )
                db.execute(
                    "INSERT INTO book_claims(id,book_id,source_version_id,build_id,kind,owner_character_id,proposition,interpretation_level,support_state,scene_id) VALUES (?,?,?,?,'episode',?,?,'explicit','accepted',?)",
                    (life_id, *scope, event.character_id, proposition, data["scene_id"]),
                )
                self._evidence(db, scope, life_id, str(uuid4()), event.evidence, "accepted")
            result = {
                "scene_id": data["scene_id"],
                "segment_ids": [row["id"] for row in data["segments"]],
                "baselines": baselines,
                "life_events": [event.model_dump() for event in review.life_events],
                "confirmed_identities": [
                    identity.character_id for identity in review.identities if identity.confirmed
                ],
                "review": review.model_dump(),
                "proposals": batch.model_dump(),
                "claim_ids": ids,
            }
            db.execute(
                "UPDATE book_build_steps SET status='validated',result_json=? WHERE build_id=? AND stage='evidence' AND unit_key=? AND lease_generation=?",
                (_json(result), build_id, data["unit_key"], generation),
            )

    @staticmethod
    def _evidence(
        db: sqlite3.Connection,
        scope: tuple[str, str, str],
        claim_id: str,
        evidence_id: str,
        span: Any,
        state: str,
    ) -> None:
        import hashlib

        db.execute(
            "INSERT INTO book_evidence(id,book_id,source_version_id,build_id,claim_id,segment_id,local_start,local_end,quote_text,quote_hash,support_state) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                evidence_id,
                *scope,
                claim_id,
                span.segment_id,
                span.local_start,
                span.local_end,
                span.quote,
                hashlib.sha256(span.quote.encode()).hexdigest(),
                state,
            ),
        )

    def _attempt_failed(
        self, build_id: str, owner: str, generation: int, unit_key: str, detail: str
    ) -> None:
        with connect(self.db_path) as db:
            self.discovery._fence(db, build_id, owner, generation)
            row = db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence' AND unit_key=?",
                (build_id, unit_key),
            ).fetchone()
            payload = json.loads(row["result_json"])
            payload["error"] = detail[:300]
            db.execute(
                "UPDATE book_build_steps SET status='failed',result_json=? WHERE build_id=? AND stage='evidence' AND unit_key=? AND lease_generation=?",
                (_json(payload), build_id, unit_key, generation),
            )

    async def run(self, build_id: str, provider: Any, config: PersonaConfig) -> None:
        lease = await asyncio.to_thread(self._lease, build_id, config)
        if lease is None:
            return
        owner, generation = lease
        options: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": 0,
        }
        if config.reasoning_effort:
            options["reasoning_effort"] = config.reasoning_effort

        async def call(prompt: str, schema: dict[str, Any], data: dict[str, Any]) -> str:
            encoded = _json(data)
            if len(encoded) > config.unit_char_limit * 2:
                raise ValueError(
                    "Persona input exceeds context budget; reduce proposed claims/quotes"
                )
            await asyncio.to_thread(self._renew, build_id, owner, generation, config)
            if data.get("correction_hints"):
                prompt += "\ncorrection_hints 是经过原文审查的归属纠错请求。依据本单元原文重新提取相应 kind 的内容，使用新版 target_character_id 和提示指定的 local_key；proposition 也应按正确归属改写。独立复核必须验证这些要求，不允许继续授权错误原人物。无法确认就拒绝，不凭请求增加原著事实。\n"
                if data["phase"] == "review":
                    prompt += "逐项返回 revision_checks：same_claim_repaired 判断指定 local_key 的新断言是否修复了提示 proposition 的同一语义内容，不能用同段另一个特征冒充；original_assignment_removed 判断全部 proposals 中是否已不存在原错误归属，改写或同义表达也视为残留。分别审查并说明原文理由；不能确定就 false。\n"
            response = await asyncio.wait_for(
                provider.chat(
                    [
                        {"role": "system", "content": prompt + _json(schema)},
                        {"role": "user", "content": encoded},
                    ],
                    **options,
                ),
                config.call_timeout_seconds,
            )
            if response.finish_reason not in ("stop", "end_turn") or response.tool_calls:
                raise ValueError("Persona response truncated, failed or requested tools")
            return response.content or ""

        try:
            while True:
                data = await asyncio.to_thread(self._input, build_id, owner, generation, config)
                if data is None:
                    return
                try:
                    failed_phase = "extract"
                    batch = validate_batch(
                        await call(
                            EXTRACT_PROMPTS.get(config.prompt_version, EXTRACT_PROMPT),
                            persona_batch_schema(config.prompt_version),
                            data,
                        ),
                        data,
                        require_explicit_excerpt=config.prompt_version == SCOPED_PERSONA_VERSION,
                    )
                    checked = {
                        **data,
                        "phase": "review",
                        "proposals": {
                            "claims": [
                                claim.model_dump(exclude_defaults=True, exclude_none=True)
                                for claim in batch.claims
                            ]
                        },
                    }
                    failed_phase = "review"
                    review = validate_review(
                        await call(
                            REVIEW_PROMPTS.get(config.review_prompt_version, REVIEW_PROMPT),
                            (
                                RevisedPersonaReview
                                if data.get("correction_hints")
                                else PersonaReview
                            ).model_json_schema(),
                            checked,
                        ),
                        batch,
                        data,
                    )
                    await asyncio.to_thread(
                        self._save, build_id, owner, generation, data, batch, review
                    )
                except (ValueError, TimeoutError) as error:
                    if config.prompt_version in (
                        STRUCTURED_PERSONA_VERSION,
                        EVIDENCE_PERSONA_VERSION,
                        SCOPED_PERSONA_VERSION,
                    ):
                        detail = _persona_error_detail(error, failed_phase)
                    else:
                        detail = (
                            "Invalid persona fields: "
                            + ",".join(
                                ".".join(map(str, issue["loc"]))
                                for issue in error.errors(
                                    include_input=False, include_context=False
                                )[:6]
                            )
                            if isinstance(error, ValidationError)
                            else "Persona model timed out"
                            if isinstance(error, TimeoutError)
                            else str(error)
                        )
                    await asyncio.to_thread(
                        self._attempt_failed, build_id, owner, generation, data["unit_key"], detail
                    )
        except BookWorldError as error:
            if error.code != "stale_build":
                await asyncio.to_thread(
                    self.discovery._fail_build, build_id, owner, generation, error.code, str(error)
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.to_thread(
                self.discovery._fail_build,
                build_id,
                owner,
                generation,
                "persona_failed",
                "Persona provider or storage failed; validated checkpoints are retained",
            )
