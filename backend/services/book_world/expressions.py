"""Build and select reviewed expression derivatives without changing canonical authority."""

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from .discovery import _hash, _json, _now
from .expression_models import (
    EXTRACT_PROMPT,
    REVIEW_PROMPT,
    ExpressionBatch,
    ExpressionConfig,
    ExpressionContext,
    ExpressionMaterial,
    ExpressionProposal,
    ExpressionReference,
    ExpressionReview,
)
from .knowledge import CharacterKnowledgeService
from .knowledge_models import AllowedEvidence, CanonicalScope
from .persona_validation import parse_json
from .search_terms import query_terms, terms
from .source import BookWorldError
from .storage import connect


class CharacterExpressionService:
    def __init__(self, workspace_root: str | Path):
        self.knowledge = CharacterKnowledgeService(workspace_root)
        self.db_path = self.knowledge.db_path

    def _scope(self, row: sqlite3.Row) -> CanonicalScope:
        return CanonicalScope(
            workspace_id=self.knowledge.workspace_id,
            book_id=row["book_id"],
            source_version_id=row["source_version_id"],
            build_id=row["build_id"],
            character_id=row["character_id"],
            canonical_policy_version=row["canonical_policy_version"],
            knowledge_policy_version=row["knowledge_policy_version"],
        )

    def _row(self, db: sqlite3.Connection, scope: CanonicalScope, set_id: str) -> sqlite3.Row:
        self.knowledge.validate_scope(db, scope)
        row = db.execute(
            "SELECT * FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND id=? AND lifecycle_state='active'",
            (*scope.binding, set_id),
        ).fetchone()
        if row is None:
            raise BookWorldError(
                "expression_unavailable",
                "Expression set belongs to another scope or is unavailable",
            )
        return cast(sqlite3.Row, row)

    def _snapshot(self, scope: CanonicalScope) -> tuple[list[AllowedEvidence], dict[str, Any]]:
        items: list[AllowedEvidence] = []
        offset = 0
        while True:
            page = self.knowledge.catalog(scope, 50, offset)
            items.extend(page.items)
            if len(page.items) < 50:
                break
            offset += 50
        baseline = {
            slot: {"claim_id": item.claim_id, "kind": item.kind, "proposition": item.proposition}
            for slot, item in self.knowledge.baseline(scope).slots.items()
        }
        return items, baseline

    def create_set(self, scope: CanonicalScope, config: ExpressionConfig) -> dict[str, Any]:
        items, baseline = self._snapshot(scope)
        fingerprint = _hash(
            {
                "scope": scope.model_dump(),
                "items": [item.model_dump() for item in items],
                "baseline": baseline,
                "config": config.model_dump(),
            }
        )
        units = []
        current: list[AllowedEvidence] = []
        size = 0
        for item in items:
            if not item.approved_excerpt:
                continue
            encoded_size = len(_json(item.model_dump()))
            if encoded_size > config.unit_char_limit:
                raise BookWorldError(
                    "expression_budget", "A safe projection exceeds the expression unit budget"
                )
            if current and (size + encoded_size > config.unit_char_limit or len(current) >= 6):
                units.append(current)
                current = []
                size = 0
            current.append(item)
            size += encoded_size
        if current:
            units.append(current)
        progress = [
            {
                "ids": [[item.claim_id, item.evidence_id] for item in unit],
                "input_hash": _hash([item.model_dump() for item in unit]),
                "status": "pending",
                "attempts": 0,
            }
            for unit in units
        ]
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.knowledge.validate_scope(db, scope)
            cached = db.execute(
                "SELECT id FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND input_fingerprint=?",
                (*scope.binding, fingerprint),
            ).fetchone()
            if cached:
                identifier = cached["id"]
            else:
                identifier = str(uuid4())
                db.execute(
                    "INSERT INTO book_expression_sets(id,book_id,source_version_id,build_id,character_id,canonical_policy_version,knowledge_policy_version,input_fingerprint,baseline_hash,config_json,status,progress_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        *scope.binding,
                        scope.canonical_policy_version,
                        scope.knowledge_policy_version,
                        fingerprint,
                        _hash(baseline),
                        _json(config.model_dump()),
                        "queued",
                        _json(progress),
                    ),
                )
                for slot, entry in baseline.items():
                    if not slot.startswith("style:"):
                        continue
                    proof = next(
                        (item for item in items if item.claim_id == entry["claim_id"]), None
                    )
                    if proof:
                        proposal = ExpressionProposal(
                            local_key=slot,
                            kind="style_rule",
                            text=proof.proposition,
                            refs=[
                                {
                                    "claim_id": proof.claim_id,
                                    "evidence_id": proof.evidence_id,
                                    "purpose": "style",
                                }
                            ],
                        )
                        self._material(
                            db,
                            scope,
                            identifier,
                            proposal,
                            [proof],
                            {"origin": "existing_current_style_baseline"},
                            True,
                        )
                if not units:
                    db.execute(
                        "UPDATE book_expression_sets SET status='ready' WHERE id=?", (identifier,)
                    )
        return self.get_set(scope, identifier)

    def get_set(self, scope: CanonicalScope, set_id: str | None = None) -> dict[str, Any]:
        with connect(self.db_path) as db:
            self.knowledge.validate_scope(db, scope)
            if set_id:
                row = self._row(db, scope, set_id)
            else:
                row = db.execute(
                    "SELECT * FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND lifecycle_state='active' ORDER BY created_at DESC,rowid DESC LIMIT 1",
                    scope.binding,
                ).fetchone()
            if row is None:
                return {
                    "set_id": None,
                    "status": "not_built",
                    "total_units": 0,
                    "completed_units": 0,
                }
            progress = json.loads(row["progress_json"])
            accepted = db.execute(
                "SELECT COUNT(*) FROM book_expression_materials WHERE set_id=? AND review_state='accepted'",
                (row["id"],),
            ).fetchone()[0]
            return {
                "set_id": row["id"],
                "status": row["status"],
                "config": json.loads(row["config_json"]),
                "total_units": len(progress),
                "completed_units": sum(unit["status"] == "validated" for unit in progress),
                "failed_units": sum(unit["status"] == "failed" for unit in progress),
                "accepted_materials": accepted,
                "window_calls": row["window_calls"],
                "total_calls": row["total_calls"],
                "error_code": row["error_code"],
                "error_detail": row["error_detail"],
                "can_resume": row["status"] == "paused"
                or (row["status"] == "queued" and not row["lease_owner"])
                or (row["status"] == "running" and row["lease_expires_at"] <= _now()),
            }

    def control(self, scope: CanonicalScope, set_id: str, action: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, scope, set_id)
            if action == "cancel" and row["status"] in ("queued", "running", "paused", "failed"):
                db.execute(
                    "UPDATE book_expression_sets SET status='cancelled',cancel_requested=1,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                    (set_id,),
                )
            elif action in ("resume", "retry") and (
                row["status"] in ("paused", "failed", "cancelled")
                or (row["status"] == "queued" and not row["lease_owner"])
                or (row["status"] == "running" and row["lease_expires_at"] <= _now())
            ):
                progress = json.loads(row["progress_json"])
                for unit in progress:
                    if unit["status"] != "validated":
                        unit.update(status="pending", attempts=0)
                        unit.pop("error", None)
                db.execute(
                    "UPDATE book_expression_sets SET status='queued',cancel_requested=0,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,window_calls=0,error_code=NULL,error_detail=NULL,progress_json=? WHERE id=?",
                    (_json(progress), set_id),
                )
            else:
                raise BookWorldError(
                    "invalid_expression_state",
                    "Completed expressions cannot be reopened, or this state cannot be controlled",
                )
        return self.get_set(scope, set_id)

    def _lease(
        self, set_id: str, config: ExpressionConfig
    ) -> tuple[CanonicalScope, str, int] | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM book_expression_sets WHERE id=?", (set_id,)).fetchone()
            if (
                row is None
                or row["lifecycle_state"] != "active"
                or row["cancel_requested"]
                or row["status"] not in ("queued", "running")
            ):
                return None
            scope = self._scope(row)
            self._row(db, scope, set_id)
            if row["lease_owner"] and row["lease_expires_at"] > _now():
                return None
            if row["config_json"] != _json(config.model_dump()):
                raise BookWorldError(
                    "config_changed", "Expression recovery requires its original model and policy"
                )
            owner, generation = str(uuid4()), row["lease_generation"] + 1
            progress = json.loads(row["progress_json"])
            for unit in progress:
                if unit["status"] == "running":
                    unit["status"] = "pending"
            db.execute(
                "UPDATE book_expression_sets SET status='running',lease_owner=?,lease_generation=?,lease_expires_at=?,progress_json=? WHERE id=?",
                (
                    owner,
                    generation,
                    _now(config.call_timeout_seconds + 60),
                    _json(progress),
                    set_id,
                ),
            )
            return scope, owner, generation

    def _fence(
        self,
        db: sqlite3.Connection,
        scope: CanonicalScope,
        set_id: str,
        owner: str,
        generation: int,
    ) -> sqlite3.Row:
        row = self._row(db, scope, set_id)
        if (
            row["status"] != "running"
            or row["cancel_requested"]
            or row["lease_owner"] != owner
            or row["lease_generation"] != generation
            or row["lease_expires_at"] <= _now()
        ):
            raise BookWorldError("stale_expression", "Expression worker lease is no longer valid")
        return row

    def _input(
        self,
        scope: CanonicalScope,
        set_id: str,
        owner: str,
        generation: int,
        config: ExpressionConfig,
        processed: int,
    ) -> dict[str, Any] | None:
        items, baseline = self._snapshot(scope)
        lookup = {(item.claim_id, item.evidence_id): item for item in items}
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._fence(db, scope, set_id, owner, generation)
            if row["baseline_hash"] != _hash(baseline):
                raise BookWorldError(
                    "expression_input_changed",
                    "Canonical baseline no longer matches this derivative",
                )
            progress = json.loads(row["progress_json"])
            index = next(
                (
                    i
                    for i, unit in enumerate(progress)
                    if unit["status"] in ("pending", "failed") and unit["attempts"] < 2
                ),
                None,
            )
            if index is None:
                partial = any(unit["status"] == "failed" for unit in progress) or bool(
                    db.execute(
                        "SELECT 1 FROM book_expression_materials WHERE set_id=? AND review_state='rejected' LIMIT 1",
                        (set_id,),
                    ).fetchone()
                )
                db.execute(
                    "UPDATE book_expression_sets SET status=?,lease_owner=NULL,lease_expires_at=NULL,error_code=?,error_detail=? WHERE id=?",
                    (
                        "partial" if partial else "ready",
                        "partial_expressions" if partial else None,
                        "Some expression candidates or units remain unresolved"
                        if partial
                        else None,
                        set_id,
                    ),
                )
                return None
            if (
                processed >= config.max_units_per_window
                or row["window_calls"] + 2 > config.max_calls_per_window
            ):
                db.execute(
                    "UPDATE book_expression_sets SET status='paused',lease_owner=NULL,lease_expires_at=NULL,lease_generation=lease_generation+1,error_code='expression_budget',error_detail='Expression call or unit budget exhausted; continue manually' WHERE id=?",
                    (set_id,),
                )
                return None
            unit = progress[index]
            selected = [lookup.get(tuple(identifier)) for identifier in unit["ids"]]
            if (
                any(item is None for item in selected)
                or _hash([item.model_dump() for item in selected if item is not None])
                != unit["input_hash"]
            ):
                raise BookWorldError(
                    "expression_input_changed",
                    "Safe projections no longer match this derivative checkpoint",
                )
            person = self.knowledge.validate_scope(db, scope)
            aliases = [
                entry[0]
                for entry in db.execute(
                    "SELECT alias FROM book_character_aliases WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND review_state<>'ambiguous' ORDER BY alias",
                    scope.binding,
                )
            ]
            unit.update(status="running", attempts=unit["attempts"] + 1)
            db.execute(
                "UPDATE book_expression_sets SET progress_json=? WHERE id=?",
                (_json(progress), set_id),
            )
            return {
                "phase": "extract",
                "unit_index": index,
                "character": {"name": person["name"], "aliases": aliases[:24]},
                "items": [item.model_dump() for item in selected if item is not None],
                "baseline": baseline,
                "previous_error": unit.get("error"),
            }

    def _reserve_call(
        self,
        scope: CanonicalScope,
        set_id: str,
        owner: str,
        generation: int,
        config: ExpressionConfig,
    ) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._fence(db, scope, set_id, owner, generation)
            if row["window_calls"] >= config.max_calls_per_window:
                raise BookWorldError("expression_budget", "Expression call budget exhausted")
            db.execute(
                "UPDATE book_expression_sets SET window_calls=window_calls+1,total_calls=total_calls+1,lease_expires_at=? WHERE id=?",
                (_now(config.call_timeout_seconds + 60), set_id),
            )

    @staticmethod
    def _validate(batch: ExpressionBatch, data: dict[str, Any]) -> list[AllowedEvidence]:
        items = [AllowedEvidence.model_validate(item) for item in data["items"]]
        lookup = {(item.claim_id, item.evidence_id): item for item in items}
        seen = set()
        style_ids = {
            entry["claim_id"]
            for slot, entry in data["baseline"].items()
            if slot.startswith("style:")
        }
        for material in batch.materials:
            if material.local_key in seen or not material.text.strip():
                raise ValueError("Duplicate expression key or empty text")
            seen.add(material.local_key)
            proofs = []
            references = set()
            for ref in material.refs:
                proof = lookup.get((ref.claim_id, ref.evidence_id))
                if proof is None or (ref.claim_id, ref.evidence_id, ref.purpose) in references:
                    raise ValueError("Expression reference is foreign or duplicated")
                references.add((ref.claim_id, ref.evidence_id, ref.purpose))
                proofs.append(proof)
            if material.kind == "style_rule":
                if not any(
                    ref.purpose == "style"
                    and ref.claim_id in style_ids
                    and lookup[(ref.claim_id, ref.evidence_id)].kind == "style"
                    and material.text == lookup[(ref.claim_id, ref.evidence_id)].proposition
                    for ref in material.refs
                ):
                    raise ValueError("Style rule must copy an existing current style baseline")
            elif not any(
                ref.purpose == "speaker"
                and material.text in lookup[(ref.claim_id, ref.evidence_id)].approved_excerpt
                and lookup[(ref.claim_id, ref.evidence_id)].approved_excerpt.count(material.text)
                == 1
                and (
                    lookup[(ref.claim_id, ref.evidence_id)].kind == "style"
                    or any(
                        alias in lookup[(ref.claim_id, ref.evidence_id)].approved_excerpt
                        for alias in data["character"]["aliases"]
                    )
                )
                for ref in material.refs
            ):
                raise ValueError("Dialogue must be a verbatim substring of its speaker projection")
            if any(
                not term.strip()
                or len(term) > 80
                or not any(
                    term in proof.approved_excerpt or term in proof.proposition for proof in proofs
                )
                for term in material.topic_terms
            ):
                raise ValueError("Expression topic term must appear in its permitted materials")
        return items

    def _material(
        self,
        db: sqlite3.Connection,
        scope: CanonicalScope,
        set_id: str,
        proposal: ExpressionProposal,
        items: list[AllowedEvidence],
        review: dict[str, Any],
        accepted: bool,
    ) -> None:
        fingerprint = _hash(
            {
                "kind": proposal.kind,
                "text": proposal.text,
                "action": proposal.dialogue_action,
                "refs": [ref.model_dump() for ref in proposal.refs],
            }
        )
        identifier = str(uuid4())
        result = db.execute(
            "INSERT OR IGNORE INTO book_expression_materials(id,set_id,book_id,source_version_id,build_id,character_id,kind,text,dialogue_action,topic_terms_json,review_state,material_fingerprint,review_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                set_id,
                *scope.binding,
                proposal.kind,
                proposal.text,
                proposal.dialogue_action,
                _json(proposal.topic_terms),
                "accepted" if accepted else "rejected",
                fingerprint,
                _json(review),
            ),
        )
        if result.rowcount == 0:
            return
        lookup = {(item.claim_id, item.evidence_id): item for item in items}
        refs = [(ref.claim_id, ref.evidence_id, ref.purpose) for ref in proposal.refs]
        for claim_id in review.get("fact_claim_ids", []):
            proof = next(item for item in items if item.claim_id == claim_id)
            if (proof.claim_id, proof.evidence_id, "fact") not in refs:
                refs.append((proof.claim_id, proof.evidence_id, "fact"))
        for claim_id, evidence_id, purpose in refs:
            proof = lookup[(claim_id, evidence_id)]
            start, end = proof.local_start, proof.local_end
            if proposal.kind == "dialogue_example" and purpose == "speaker":
                start += proof.approved_excerpt.index(proposal.text)
                end = start + len(proposal.text)
            db.execute(
                "INSERT INTO book_expression_refs(material_id,set_id,book_id,source_version_id,build_id,character_id,claim_id,evidence_id,purpose,segment_id,local_start,local_end,approved_excerpt_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    set_id,
                    *scope.binding,
                    claim_id,
                    evidence_id,
                    purpose,
                    proof.segment_id,
                    start,
                    end,
                    hashlib.sha256(proof.approved_excerpt.encode()).hexdigest(),
                ),
            )

    def _save(
        self,
        scope: CanonicalScope,
        set_id: str,
        owner: str,
        generation: int,
        data: dict[str, Any],
        batch: ExpressionBatch,
        review: ExpressionReview,
    ) -> None:
        checks = {check.local_key: check for check in review.materials}
        if len(checks) != len(review.materials) or set(checks) != {
            material.local_key for material in batch.materials
        }:
            raise ValueError("Review must cover each expression exactly once")
        items = self._validate(batch, data)
        allowed_ids = {item.claim_id for item in items}
        if any(not set(check.fact_claim_ids) <= allowed_ids for check in review.materials):
            raise ValueError("Review added a foreign fact reference")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._fence(db, scope, set_id, owner, generation)
            for proposal in batch.materials:
                check = checks[proposal.local_key]
                accepted = (
                    check.supported
                    and check.speaker_confirmed
                    and check.safe
                    and check.baseline_compatible
                    and check.purpose_supported
                    and check.facts_complete
                )
                self._material(db, scope, set_id, proposal, items, check.model_dump(), accepted)
            progress = json.loads(row["progress_json"])
            progress[data["unit_index"]]["status"] = "validated"
            db.execute(
                "UPDATE book_expression_sets SET progress_json=? WHERE id=?",
                (_json(progress), set_id),
            )

    def _unit_failed(
        self,
        scope: CanonicalScope,
        set_id: str,
        owner: str,
        generation: int,
        index: int,
        detail: str,
    ) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._fence(db, scope, set_id, owner, generation)
            progress = json.loads(row["progress_json"])
            progress[index].update(status="failed", error=detail[:200])
            db.execute(
                "UPDATE book_expression_sets SET progress_json=? WHERE id=?",
                (_json(progress), set_id),
            )

    def _failed(self, set_id: str, owner: str, generation: int, code: str) -> None:
        with connect(self.db_path) as db:
            db.execute(
                "UPDATE book_expression_sets SET status=?,error_code=?,error_detail=?,lease_owner=NULL,lease_expires_at=NULL,lease_generation=lease_generation+1 WHERE id=? AND status='running' AND lifecycle_state='active' AND cancel_requested=0 AND lease_owner=? AND lease_generation=? AND lease_expires_at>?",
                (
                    "paused" if code == "expression_budget" else "failed",
                    code,
                    "Expression worker stopped; validated units are retained",
                    set_id,
                    owner,
                    generation,
                    _now(),
                ),
            )

    async def run(self, set_id: str, provider: Any, config: ExpressionConfig) -> None:
        lease = await asyncio.to_thread(self._lease, set_id, config)
        if lease is None:
            return
        scope, owner, generation = lease
        options: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": 0,
        }
        if config.reasoning_effort:
            options["reasoning_effort"] = config.reasoning_effort
        processed = 0

        async def call(prompt: str, schema: dict[str, Any], data: dict[str, Any]) -> str:
            encoded = _json(data)
            if len(encoded) > min(
                32000, max(0, (config.context_window - config.max_tokens - 6000) // 2)
            ):
                raise ValueError("Expression input exceeds the model context budget")
            await asyncio.to_thread(self._reserve_call, scope, set_id, owner, generation, config)
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
                raise ValueError("Expression response was incomplete or requested tools")
            return response.content or ""

        try:
            while True:
                data = await asyncio.to_thread(
                    self._input, scope, set_id, owner, generation, config, processed
                )
                if data is None:
                    return
                processed += 1
                try:
                    batch = ExpressionBatch.model_validate_json(
                        parse_json(
                            await call(EXTRACT_PROMPT, ExpressionBatch.model_json_schema(), data)
                        )
                    )
                    self._validate(batch, data)
                    checked = {**data, "phase": "review", "proposals": batch.model_dump()}
                    review = ExpressionReview.model_validate_json(
                        parse_json(
                            await call(REVIEW_PROMPT, ExpressionReview.model_json_schema(), checked)
                        )
                    )
                    await asyncio.to_thread(
                        self._save, scope, set_id, owner, generation, data, batch, review
                    )
                except (ValueError, TimeoutError):
                    await asyncio.to_thread(
                        self._unit_failed,
                        scope,
                        set_id,
                        owner,
                        generation,
                        data["unit_index"],
                        "Expression output invalid, context exhausted or timed out",
                    )
        except BookWorldError as error:
            if error.code != "stale_expression":
                await asyncio.to_thread(self._failed, set_id, owner, generation, error.code)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.to_thread(self._failed, set_id, owner, generation, "expression_failed")

    def list_materials(
        self, scope: CanonicalScope, set_id: str, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 100:
            raise BookWorldError("invalid_request", "Invalid expression page")
        with connect(self.db_path) as db:
            self._row(db, scope, set_id)
            rows = db.execute(
                "SELECT id,kind,text,dialogue_action,review_state,review_json FROM book_expression_materials WHERE set_id=? ORDER BY rowid LIMIT ? OFFSET ?",
                (set_id, limit, offset),
            ).fetchall()
            materials = []
            for row in rows:
                refs = [
                    dict(ref)
                    for ref in db.execute(
                        "SELECT claim_id,evidence_id,purpose,segment_id,local_start,local_end FROM book_expression_refs WHERE material_id=?",
                        (row["id"],),
                    )
                ]
                materials.append(
                    {**dict(row), "review": json.loads(row["review_json"]), "refs": refs}
                )
            total = db.execute(
                "SELECT COUNT(*) FROM book_expression_materials WHERE set_id=?", (set_id,)
            ).fetchone()[0]
            return {
                "set_id": set_id,
                "materials": materials,
                "total": total,
                "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            }

    def retrieve(
        self,
        scope: CanonicalScope,
        query: str,
        dialogue_action: str = "other",
        *,
        set_id: str | None = None,
        knowledge_context=None,
    ) -> ExpressionContext:
        if not isinstance(query, str) or len(query) > 1000:
            raise BookWorldError("invalid_request", "Invalid expression query")
        allowed = knowledge_context or self.knowledge.retrieve(scope, query)
        if allowed.scope != scope:
            raise BookWorldError(
                "invalid_scope", "Expression facts belong to another character scope"
            )
        baseline = self.knowledge.baseline(scope)
        allowed_ids = {item.claim_id for item in allowed.items} | {
            item.claim_id for item in baseline.slots.values()
        }
        candidates, _ = self._snapshot(scope)
        lookup = {(item.claim_id, item.evidence_id): item for item in candidates}
        with connect(self.db_path) as db:
            self.knowledge.validate_scope(db, scope)
            if set_id:
                row = self._row(db, scope, set_id)
            else:
                row = db.execute(
                    "SELECT * FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND lifecycle_state='active' AND status IN ('ready','partial') ORDER BY created_at DESC,rowid DESC LIMIT 1",
                    scope.binding,
                ).fetchone()
            rules = []
            examples = []
            selected_id = row["id"] if row else None
            if (
                row
                and row["status"] in ("ready", "partial")
                and row["baseline_hash"]
                == _hash(
                    {
                        slot: {
                            "claim_id": item.claim_id,
                            "kind": item.kind,
                            "proposition": item.proposition,
                        }
                        for slot, item in baseline.slots.items()
                    }
                )
            ):
                scored_examples: list[tuple[int, ExpressionMaterial]] = []
                for material in db.execute(
                    "SELECT * FROM book_expression_materials WHERE set_id=? AND review_state='accepted' ORDER BY rowid",
                    (selected_id,),
                ):
                    refs = [
                        dict(ref)
                        for ref in db.execute(
                            "SELECT claim_id,evidence_id,purpose,segment_id,local_start,local_end,approved_excerpt_hash FROM book_expression_refs WHERE material_id=?",
                            (material["id"],),
                        )
                    ]
                    if not refs or any(
                        (ref["claim_id"], ref["evidence_id"]) not in lookup
                        or hashlib.sha256(
                            lookup[(ref["claim_id"], ref["evidence_id"])].approved_excerpt.encode()
                        ).hexdigest()
                        != ref["approved_excerpt_hash"]
                        or (
                            ref["purpose"] in ("fact", "stance")
                            and ref["claim_id"] not in allowed_ids
                        )
                        for ref in refs
                    ):
                        continue
                    projected = ExpressionMaterial(
                        material_id=material["id"],
                        kind=material["kind"],
                        text=material["text"],
                        refs=tuple(
                            ExpressionReference(
                                **{
                                    key: ref[key]
                                    for key in (
                                        "claim_id",
                                        "evidence_id",
                                        "purpose",
                                        "segment_id",
                                        "local_start",
                                        "local_end",
                                    )
                                }
                            )
                            for ref in refs
                        ),
                    )
                    if material["kind"] == "style_rule":
                        rules.append(projected)
                    else:
                        overlap = sum(
                            term
                            in terms(
                                material["text"]
                                + " "
                                + " ".join(json.loads(material["topic_terms_json"]))
                            )
                            for term in query_terms(query, [])
                        )
                        matches_action = (
                            dialogue_action != "other"
                            and material["dialogue_action"] == dialogue_action
                        )
                        if overlap or matches_action:
                            scored_examples.append((overlap + 3 * matches_action, projected))
                dedup: dict[str, ExpressionMaterial] = {}
                for _score, item in sorted(scored_examples, key=lambda pair: -pair[0]):
                    dedup.setdefault(item.text, item)
                examples = list(dedup.values())[:2]
                rules = list({item.text: item for item in rules}.values())[:3]
            return ExpressionContext(
                scope=scope,
                set_id=selected_id,
                status="known" if rules or examples else "unknown",
                rules=tuple(rules),
                examples=tuple(examples),
            )
