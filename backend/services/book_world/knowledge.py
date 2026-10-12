"""Allowlist-first retrieval for one fixed workspace and canonical character."""

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from .knowledge_models import (
    KNOWLEDGE_POLICY_VERSION,
    ActorBaselineContext,
    AllowedEvidence,
    AllowlistedContext,
    CanonicalScope,
)
from .persona import BookPersonaService
from .search_terms import query_terms, terms
from .source import BookWorldError
from .storage import connect, workspace_identity

_VIEWS = """FROM book_access_evidence v
JOIN book_claim_access a ON a.book_id=v.book_id AND a.source_version_id=v.source_version_id AND a.build_id=v.build_id AND a.character_id=v.character_id AND a.claim_id=v.claim_id
JOIN book_claims c ON c.book_id=v.book_id AND c.source_version_id=v.source_version_id AND c.build_id=v.build_id AND c.id=v.claim_id
JOIN book_evidence e ON e.book_id=v.book_id AND e.source_version_id=v.source_version_id AND e.build_id=v.build_id AND e.claim_id=v.claim_id AND e.id=v.evidence_id
"""
_PERMITTED = """v.book_id=? AND v.source_version_id=? AND v.build_id=? AND v.character_id=?
AND a.access_state='accepted' AND v.visibility_state='accepted' AND c.support_state='accepted' AND e.support_state='accepted'
AND (c.kind='fact' OR c.owner_character_id=v.character_id)
AND (v.approved_excerpt='' OR (instr(e.quote_text,v.approved_excerpt)>0
AND instr(substr(e.quote_text,instr(e.quote_text,v.approved_excerpt)+1),v.approved_excerpt)=0))
"""
_COLUMNS = "v.rowid AS view_rowid,c.id AS claim_id,c.kind,c.proposition,c.supersedes_claim_id,v.evidence_id,v.approved_excerpt,e.segment_id,e.local_start,e.local_end,e.quote_text,a.route"


class CharacterKnowledgeService:
    def __init__(self, workspace_root: str | Path):
        self.persona = BookPersonaService(workspace_root)
        self.root = self.persona.root
        self.db_path = self.persona.db_path
        self.workspace_id = workspace_identity(self.root)
        self._metadata: dict[CanonicalScope, dict[str, dict[str, Any]]] = {}

    def bind_character(self, item_id: int, build_id: str, character_id: str) -> CanonicalScope:
        with connect(self.db_path) as db:
            build = self.persona.discovery._build(db, item_id, build_id)
            scope = CanonicalScope(
                workspace_id=self.workspace_id,
                book_id=build["book_id"],
                source_version_id=build["source_version_id"],
                build_id=build_id,
                character_id=character_id,
                canonical_policy_version=build["policy_version"],
            )
            self.validate_scope(db, scope)
            return scope

    def validate_scope(self, db: sqlite3.Connection, scope: CanonicalScope) -> sqlite3.Row:
        if (
            scope.workspace_id != self.workspace_id
            or scope.knowledge_policy_version != KNOWLEDGE_POLICY_VERSION
        ):
            raise BookWorldError(
                "invalid_scope", "Canonical scope belongs to another workspace or policy"
            )
        row = db.execute(
            "SELECT b.*,k.library_item_id,c.name FROM book_builds b JOIN book_books k ON k.id=b.book_id JOIN book_source_versions s ON s.book_id=b.book_id AND s.id=b.source_version_id JOIN book_characters c ON c.book_id=b.book_id AND c.source_version_id=b.source_version_id AND c.build_id=b.id WHERE b.book_id=? AND b.source_version_id=? AND b.id=? AND c.id=? AND b.policy_version=? AND k.lifecycle_state='active' AND s.lifecycle_state='available' AND b.lifecycle_state='active' AND b.stage='persona_published' AND b.status IN ('published','partial_published') AND c.agent_status IN ('ready','sparse')",
            (*scope.binding, scope.canonical_policy_version),
        ).fetchone()
        if row is None:
            raise BookWorldError(
                "character_unavailable",
                "No available published character matches this complete scope",
            )
        source = self.persona.source._source(db, row["library_item_id"], scope.source_version_id)
        self.persona.source._verify_snapshot(source)
        return cast(sqlite3.Row, row)

    def _meta(self, db: sqlite3.Connection, scope: CanonicalScope) -> dict[str, dict[str, Any]]:
        if scope in self._metadata:
            return self._metadata[scope]
        owned = {
            row[0]
            for row in db.execute(
                "SELECT DISTINCT c.id " + _VIEWS + " WHERE " + _PERMITTED, scope.binding
            )
        }
        result = {}
        for row in db.execute(
            "SELECT result_json FROM book_build_steps WHERE book_id=? AND source_version_id=? AND build_id=? AND stage='evidence' AND status='validated'",
            scope.binding[:3],
        ):
            payload = json.loads(row[0])
            reviews = {
                entry["local_key"]: entry for entry in payload.get("review", {}).get("claims", [])
            }
            for proposed in payload.get("proposals", {}).get("claims", []):
                identifier = payload.get("claim_ids", {}).get(proposed["local_key"])
                if identifier in owned:
                    result[identifier] = {
                        "kind": proposed["kind"],
                        "slot_key": proposed.get("slot_key"),
                        "temporal_state": reviews.get(proposed["local_key"], {}).get(
                            "temporal_state", "uncertain"
                        ),
                    }
        self._metadata[scope] = result
        return result

    def _eligible(
        self, db: sqlite3.Connection, scope: CanonicalScope, retrospective: bool
    ) -> dict[str, str]:
        meta = self._meta(db, scope)
        baseline = {
            row[0]
            for row in db.execute(
                "SELECT claim_id FROM book_character_baselines WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=?",
                scope.binding,
            )
        }
        superseded = {
            row[0]
            for row in db.execute(
                "SELECT supersedes_claim_id FROM book_claims WHERE book_id=? AND source_version_id=? AND build_id=? AND owner_character_id=? AND support_state='accepted' AND supersedes_claim_id IS NOT NULL",
                scope.binding,
            )
        }
        eligible = {}
        for row in db.execute(
            "SELECT DISTINCT c.id,c.kind " + _VIEWS + " WHERE " + _PERMITTED, scope.binding
        ):
            identifier, kind = row[0], row[1]
            data = meta.get(identifier, {})
            temporal = data.get("temporal_state", "uncertain")
            if kind in ("fact", "episode"):
                eligible[identifier] = "historical" if temporal == "historical" else "unspecified"
            elif identifier in baseline:
                eligible[identifier] = "current"
            elif retrospective and (temporal == "historical" or identifier in superseded):
                eligible[identifier] = "historical"
            elif kind != "belief" and not data.get("slot_key") and temporal == "current":
                eligible[identifier] = "current"
        return eligible

    @staticmethod
    def project(row: sqlite3.Row, temporal: str) -> AllowedEvidence:
        start = row["local_start"] + row["quote_text"].index(row["approved_excerpt"])
        end = start + len(row["approved_excerpt"]) if row["approved_excerpt"] else row["local_end"]
        return AllowedEvidence(
            claim_id=row["claim_id"],
            evidence_id=row["evidence_id"],
            kind=row["kind"],
            proposition=row["proposition"],
            approved_excerpt=row["approved_excerpt"],
            segment_id=row["segment_id"],
            local_start=start,
            local_end=end,
            temporal_state=temporal,
            route=row["route"],
        )

    def retrieve(
        self, scope: CanonicalScope, query: str, limit: int = 6, retrospective: bool = False
    ) -> AllowlistedContext:
        return self._retrieve(scope, query, limit, retrospective)

    def catalog(
        self, scope: CanonicalScope, limit: int = 50, offset: int = 0
    ) -> AllowlistedContext:
        return self._retrieve(scope, "", limit, False, offset=offset, catalog=True)

    def baseline(self, scope: CanonicalScope) -> ActorBaselineContext:
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self.validate_scope(db, scope)
            rows = db.execute(
                "SELECT "
                + _COLUMNS
                + ",b.slot_key "
                + _VIEWS
                + " JOIN book_character_baselines b ON b.book_id=v.book_id AND b.source_version_id=v.source_version_id AND b.build_id=v.build_id AND b.character_id=v.character_id AND b.claim_id=v.claim_id WHERE "
                + _PERMITTED
                + " ORDER BY b.slot_key,v.rowid",
                scope.binding,
            ).fetchall()
            slots: dict[str, AllowedEvidence] = {}
            for row in rows:
                slots.setdefault(row["slot_key"], self.project(row, "current"))
            return ActorBaselineContext(scope=scope, slots=slots)

    def _retrieve(
        self,
        scope: CanonicalScope,
        query: str,
        limit: int,
        retrospective: bool,
        *,
        offset: int = 0,
        catalog: bool = False,
    ) -> AllowlistedContext:
        if (
            not isinstance(query, str)
            or len(query) > 1000
            or type(limit) is not int
            or not 1 <= limit <= 50
            or type(offset) is not int
            or offset < 0
            or type(retrospective) is not bool
        ):
            raise BookWorldError("invalid_request", "Invalid scoped knowledge query")
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            self.validate_scope(db, scope)
            eligible = self._eligible(db, scope, retrospective)
            aliases = [
                row[0]
                for row in db.execute(
                    "SELECT alias FROM book_character_aliases WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND review_state<>'ambiguous'",
                    scope.binding,
                )
            ]
            selected_terms = query_terms(query, aliases)
            filter_sql = _PERMITTED + " AND c.id IN (SELECT value FROM json_each(?))"
            params = (*scope.binding, json.dumps(list(eligible)))
            strategy = "catalog" if catalog else "fts"
            rows = []
            if catalog:
                rows = db.execute(
                    "SELECT "
                    + _COLUMNS
                    + " "
                    + _VIEWS
                    + " WHERE "
                    + filter_sql
                    + " ORDER BY c.rowid,v.rowid LIMIT ? OFFSET ?",
                    (*params, limit, offset),
                ).fetchall()
            elif selected_terms and eligible:
                match = " OR ".join('"' + term + '"' for term in selected_terms)
                try:
                    rows = db.execute(
                        "SELECT "
                        + _COLUMNS
                        + " "
                        + _VIEWS
                        + " JOIN book_claims_fts ON book_claims_fts.rowid=v.rowid WHERE "
                        + filter_sql
                        + " AND book_claims_fts MATCH ? ORDER BY bm25(book_claims_fts),c.rowid,v.rowid LIMIT ?",
                        (*params, match, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    # FTS failure never changes the permitted or temporal candidate set.
                    strategy = "allowlist_scan"
                    candidates = db.execute(
                        "SELECT " + _COLUMNS + " " + _VIEWS + " WHERE " + filter_sql, params
                    ).fetchall()
                    scored = [
                        (
                            sum(
                                term in terms(row["proposition"] + " " + row["approved_excerpt"])
                                for term in selected_terms
                            ),
                            row,
                        )
                        for row in candidates
                    ]
                    rows = [
                        row
                        for score, row in sorted(scored, key=lambda entry: -entry[0])
                        if score > 0
                    ][:limit]
            items = tuple(self.project(row, eligible[row["claim_id"]]) for row in rows)
        return AllowlistedContext(
            scope=scope,
            query=query,
            status="known" if items else "unknown",
            items=items,
            reason="matched" if items else "no_relevant_evidence",
            retrieval_strategy=strategy,
        )
