"""Resumable, leased whole-source discovery; publication belongs to the evidence stage."""

import asyncio
import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import ValidationError

from .discovery_grouped import GROUPED_PROMPT, GROUPED_VERSION, GroupedDiscovery, assemble_grouped
from .discovery_inline import INLINE_PROMPT, INLINE_VERSION, InlineDiscovery, assemble_inline
from .discovery_models import (
    DISCOVERY_PROMPTS,
    DiscoveryConfig,
    DiscoveryCoverageError,
    DiscoveryResult,
    DiscoverySpan,
    StrictModel,
    discovery_model_input,
    validate_local_identities,
)
from .discovery_numbered import (
    NUMBERED_LATEST_PROMPT,
    NUMBERED_LATEST_VERSION,
    NUMBERED_PROMPT,
    NUMBERED_VERSIONS,
    NumberedDiscovery,
    assemble_numbered,
    prepare_numbered,
)
from .discovery_repair import (
    REPAIR_PROMPT,
    REPAIR_V9_PROMPT,
    REPAIR_V10_PROMPT,
    DiscoveryRepairs,
    apply_repair,
    prepare_repair,
)
from .discovery_selection import (
    SELECTION_PROMPT,
    SelectedRepairs,
    apply_selection,
    prepare_selection,
    selection_input,
)
from .discovery_unit_repair import (
    UNIT_PROMPT,
    UNIT_PROTOCOL,
    UNIT_REPAIR_VERSIONS,
    UnitDiscovery,
    apply_unit_repair,
    can_repair_unit,
    prepare_unit_repair,
    unit_repair_input,
)
from .discovery_window_repair import (
    WINDOW_REPAIR_PROMPT,
    WindowRepairs,
    apply_window_repair,
    prepare_window_repair,
    window_repair_input,
)
from .source import BookSourceService, BookWorldError
from .storage import connect, workspace_identity


def _now(seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="milliseconds"
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _normalize(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip().casefold()


class BookDiscoveryService:
    """Every operation is scoped to the creating root and B = book/source/build."""

    def __init__(self, workspace_root: str | Path):
        self.source = BookSourceService(workspace_root)
        self.root = self.source.root
        self.db_path = self.source.db_path

    def _build(self, db: sqlite3.Connection, item_id: int, build_id: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT b.* FROM book_builds b JOIN book_books k ON k.id=b.book_id "
            "JOIN book_source_versions s ON s.id=b.source_version_id AND s.book_id=b.book_id "
            "WHERE k.library_item_id=? AND b.id=? AND k.lifecycle_state='active' "
            "AND b.lifecycle_state='active' AND s.lifecycle_state='available'",
            (item_id, build_id),
        ).fetchone()
        if row is None:
            raise BookWorldError(
                "build_unavailable", "Build does not belong to this available book"
            )
        return cast(sqlite3.Row, row)

    def create_build(
        self,
        item_id: int,
        source_version_id: str,
        config: DiscoveryConfig,
        *,
        config_error: str | None = None,
    ) -> dict[str, Any]:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            source = self.source._source(db, item_id, source_version_id)
            self.source._verify_snapshot(source)
            if json.loads(source["quality_json"])["status"] != "ready":
                raise BookWorldError(
                    "needs_ocr", "Prepare a complete readable source before discovery"
                )
            snapshot = config.model_dump()
            fingerprint = _hash({"source": source_version_id, "config": snapshot})
            existing = db.execute(
                "SELECT id FROM book_builds WHERE book_id=? AND source_version_id=? AND build_fingerprint=?",
                (source["book_id"], source_version_id, fingerprint),
            ).fetchone()
            if existing:
                build_id = existing["id"]
            else:
                build_id = str(uuid4())
                db.execute(
                    "INSERT INTO book_builds(id,book_id,source_version_id,build_fingerprint,status,stage,"
                    "config_snapshot_json,policy_version,error_code,error_detail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        build_id,
                        source["book_id"],
                        source_version_id,
                        fingerprint,
                        "blocked_config" if config_error else "queued",
                        "character_discovery",
                        _json(snapshot),
                        config.policy_version,
                        "blocked_config" if config_error else None,
                        config_error,
                    ),
                )
                rows = db.execute(
                    "SELECT * FROM book_segments WHERE book_id=? AND source_version_id=? ORDER BY ordinal",
                    (source["book_id"], source_version_id),
                ).fetchall()
                units: list[list[dict[str, Any]]] = []
                current: list[dict[str, Any]] = []
                size = 0
                chapter = None
                for row in rows:
                    if len(row["text"]) > config.unit_char_limit:
                        raise BookWorldError(
                            "segment_too_large",
                            "A source segment exceeds model budget; prepare the source with the latest parser",
                        )
                    if current and (
                        len(current) >= config.unit_segment_limit
                        or size + len(row["text"]) > config.unit_char_limit
                        or row["chapter"] != chapter
                    ):
                        units.append(current)
                        current, size = [], 0
                    current.append(
                        {"id": row["id"], "text": row["text"], "ordinal": row["ordinal"]}
                    )
                    size += len(row["text"])
                    chapter = row["chapter"]
                if current:
                    units.append(current)
                for index, unit in enumerate(units):
                    db.execute(
                        "INSERT INTO book_build_steps(book_id,source_version_id,build_id,stage,unit_key,"
                        "input_hash,status,result_json,lease_generation) VALUES (?,?,?,'discovery',?,?,'pending',?,0)",
                        (
                            source["book_id"],
                            source_version_id,
                            build_id,
                            str(index),
                            _hash(unit),
                            _json({"segment_ids": [segment["id"] for segment in unit]}),
                        ),
                    )
        return self.get_build(item_id, build_id)

    def get_build(
        self, item_id: int, build_id: str | None = None, source_version_id: str | None = None
    ) -> dict[str, Any]:
        with connect(self.db_path) as db:
            if build_id is None:
                row = db.execute(
                    "SELECT b.id FROM book_builds b JOIN book_books k ON k.id=b.book_id "
                    "WHERE k.library_item_id=? AND (? IS NULL OR b.source_version_id=?) "
                    "AND b.lifecycle_state='active' ORDER BY b.created_at DESC,b.rowid DESC LIMIT 1",
                    (item_id, source_version_id, source_version_id),
                ).fetchone()
                if row is None:
                    return {"status": "not_built"}
                build_id = row["id"]
            row = self._build(db, item_id, build_id)
            progress_stage = (
                "evidence"
                if row["stage"] in ("persona_extract", "persona_published")
                else "discovery"
            )
            steps = db.execute(
                "SELECT status,COUNT(*) AS n FROM book_build_steps WHERE build_id=? AND stage=? GROUP BY status",
                (build_id, progress_stage),
            ).fetchall()
            counts = {step["status"]: step["n"] for step in steps}
            processed = db.execute(
                "SELECT COUNT(DISTINCT segment_id) FROM book_scene_segments WHERE build_id=?",
                (build_id,),
            ).fetchone()[0]
            if progress_stage == "evidence":
                processed = len(
                    {
                        segment
                        for step in db.execute(
                            "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence' AND status='validated'",
                            (build_id,),
                        )
                        for segment in json.loads(step["result_json"]).get("segment_ids", [])
                    }
                )
            total = db.execute(
                "SELECT COUNT(*) FROM book_segments WHERE book_id=? AND source_version_id=?",
                (row["book_id"], row["source_version_id"]),
            ).fetchone()[0]
            report = db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='publication' AND unit_key='summary'",
                (build_id,),
            ).fetchone()
            history = db.execute(
                "SELECT id FROM book_builds WHERE book_id=? AND source_version_id=? "
                "AND stage='persona_published' AND status IN ('published','partial_published') "
                "AND lifecycle_state='active' ORDER BY created_at DESC,rowid DESC LIMIT 1",
                (row["book_id"], row["source_version_id"]),
            ).fetchone()
            return {
                "build_id": row["id"],
                "book_id": row["book_id"],
                "source_version_id": row["source_version_id"],
                "parent_build_id": row["parent_build_id"],
                "history_build_id": history["id"] if history else None,
                "status": row["status"],
                "stage": row["stage"],
                "total_units": sum(counts.values()),
                "completed_units": counts.get("validated", 0),
                "failed_units": counts.get("failed", 0),
                "processed_segments": processed,
                "total_segments": total,
                "error_code": row["error_code"],
                "error_detail": row["error_detail"],
                "can_resume": row["stage"] in ("character_discovery", "persona_extract")
                and row["status"] in ("queued", "running")
                and (not row["lease_owner"] or row["lease_expires_at"] <= _now()),
                "config": json.loads(row["config_snapshot_json"]),
                "publication_report": json.loads(report["result_json"]) if report else None,
            }

    def list_characters(
        self, item_id: int, build_id: str, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 200:
            raise BookWorldError("invalid_request", "Invalid character page")
        with connect(self.db_path) as db:
            self._build(db, item_id, build_id)
            rows = db.execute(
                "SELECT * FROM book_characters WHERE build_id=? ORDER BY name,id LIMIT ? OFFSET ?",
                (build_id, limit, offset),
            ).fetchall()
            total = db.execute(
                "SELECT COUNT(*) FROM book_characters WHERE build_id=?", (build_id,)
            ).fetchone()[0]
            characters = []
            for row in rows:
                aliases = db.execute(
                    "SELECT alias,review_state,provenance_json FROM book_character_aliases WHERE build_id=? AND character_id=? ORDER BY alias",
                    (build_id, row["id"]),
                ).fetchall()
                appearances = db.execute(
                    "SELECT scene_id,presence FROM book_scene_characters WHERE build_id=? AND character_id=?",
                    (build_id, row["id"]),
                ).fetchall()
                characters.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "agent_status": row["agent_status"],
                        "entity_kind": json.loads(row["public_profile_json"]).get(
                            "entity_kind", "unknown"
                        ),
                        "aliases": [
                            {
                                "alias": alias["alias"],
                                "review_state": alias["review_state"],
                                "evidence": json.loads(alias["provenance_json"])["evidence"],
                            }
                            for alias in aliases
                        ],
                        "appearances": [dict(appearance) for appearance in appearances],
                    }
                )
            return {
                "build_id": build_id,
                "characters": characters,
                "total": total,
                "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            }

    def cancel_build(self, item_id: int, build_id: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            row = self._build(db, item_id, build_id)
            if row["stage"] != "character_discovery" or row["status"] not in (
                "queued",
                "running",
                "failed",
                "blocked_config",
            ):
                raise BookWorldError(
                    "invalid_build_state", "Discovery cannot be cancelled in this state"
                )
            db.execute(
                "UPDATE book_builds SET cancel_requested=1,status='cancelled',lease_generation=lease_generation+1,"
                "lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                (build_id,),
            )
        return self.get_build(item_id, build_id)

    def retry_build(self, item_id: int, build_id: str) -> dict[str, Any]:
        with connect(self.db_path) as db:
            row = self._build(db, item_id, build_id)
            if (
                row["status"] not in ("failed", "cancelled")
                or row["stage"] != "character_discovery"
            ):
                raise BookWorldError("invalid_build_state", "Only failed discovery can be retried")
            db.execute(
                "UPDATE book_build_steps SET status='pending',attempts=0 WHERE build_id=? AND status<>'validated'",
                (build_id,),
            )
            db.execute(
                "UPDATE book_builds SET status='queued',cancel_requested=0,lease_generation=lease_generation+1,error_code=NULL,error_detail=NULL WHERE id=?",
                (build_id,),
            )
        return self.get_build(item_id, build_id)

    def _lease(self, build_id: str, config: DiscoveryConfig) -> tuple[str, int] | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM book_builds WHERE id=?", (build_id,)).fetchone()
            if (
                row is None
                or row["stage"] != "character_discovery"
                or row["status"] not in ("queued", "running")
            ):
                return None
            if row["cancel_requested"] or row["lifecycle_state"] != "active":
                return None
            if row["lease_owner"] and row["lease_expires_at"] > _now():
                return None
            if row["config_snapshot_json"] != _json(config.model_dump()):
                raise BookWorldError(
                    "config_changed", "Retry requires the original model configuration"
                )
            owner, generation = str(uuid4()), row["lease_generation"] + 1
            db.execute(
                "UPDATE book_builds SET status='running',lease_owner=?,lease_generation=?,lease_expires_at=? WHERE id=?",
                (owner, generation, _now(config.call_timeout_seconds + 60), build_id),
            )
            db.execute(
                "UPDATE book_build_steps SET status='pending' WHERE build_id=? AND status='running'",
                (build_id,),
            )
            return owner, generation

    def _fence(
        self, db: sqlite3.Connection, build_id: str, owner: str, generation: int
    ) -> sqlite3.Row:
        row = db.execute(
            "SELECT b.*,k.library_item_id FROM book_builds b JOIN book_books k ON k.id=b.book_id "
            "JOIN book_source_versions s ON s.id=b.source_version_id AND s.book_id=b.book_id "
            "WHERE b.id=? AND b.lease_owner=? AND b.lease_generation=? AND b.lease_expires_at>? "
            "AND b.cancel_requested=0 AND b.status='running' AND b.lifecycle_state='active' "
            "AND k.lifecycle_state='active' AND s.lifecycle_state='available'",
            (build_id, owner, generation, _now()),
        ).fetchone()
        if row is None:
            raise BookWorldError("stale_build", "Build lease or source authorization has expired")
        return cast(sqlite3.Row, row)

    def _input(
        self, build_id: str, owner: str, generation: int, config: DiscoveryConfig
    ) -> dict[str, Any] | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            build = self._fence(db, build_id, owner, generation)
            step = db.execute(
                "SELECT * FROM book_build_steps WHERE build_id=? AND status<>'validated' "
                "ORDER BY CAST(unit_key AS INTEGER) LIMIT 1",
                (build_id,),
            ).fetchone()
            if step is None:
                db.execute(
                    "UPDATE book_builds SET status='queued',stage='discovery_complete',lease_owner=NULL,"
                    "lease_expires_at=NULL WHERE id=?",
                    (build_id,),
                )
                return None
            if step["attempts"] >= 2:
                previous_error = (
                    json.loads(step["result_json"]).get("error") or "Invalid model result"
                )
                raise BookWorldError(
                    "discovery_failed",
                    f"Discovery unit {step['unit_key']} failed twice: {previous_error}",
                )
            ids = json.loads(step["result_json"])["segment_ids"]
            rows = db.execute(
                "SELECT id,text,ordinal FROM book_segments WHERE book_id=? AND source_version_id=? "
                "AND id IN (" + ",".join("?" for _ in ids) + ") ORDER BY ordinal",
                (build["book_id"], build["source_version_id"], *ids),
            ).fetchall()
            segments = [dict(row) for row in rows]
            if len(segments) != len(ids) or _hash(segments) != step["input_hash"]:
                raise BookWorldError(
                    "source_changed", "Discovery checkpoint no longer matches source"
                )
            text = "\n".join(row["text"] for row in rows)
            known = db.execute(
                "SELECT c.id,c.name,a.alias,a.normalized_alias,a.review_state FROM book_characters c "
                "JOIN book_character_aliases a ON a.character_id=c.id AND a.build_id=c.build_id "
                "WHERE c.build_id=? ORDER BY c.id,a.normalized_alias",
                (build_id,),
            ).fetchall()
            candidates: dict[str, dict[str, Any]] = {}
            for alias in known:
                if alias["alias"] in text:
                    candidate = candidates.setdefault(
                        alias["id"], {"id": alias["id"], "name": alias["name"], "aliases": []}
                    )
                    candidate["aliases"].append(
                        {"alias": alias["alias"], "review_state": alias["review_state"]}
                    )
            known_characters = []
            context_size = 0
            for candidate in list(candidates.values())[:64]:
                candidate["aliases"] = candidate["aliases"][:12]
                candidate_size = len(_json(candidate))
                if context_size + candidate_size > 4000:
                    break
                known_characters.append(candidate)
                context_size += candidate_size
            db.execute(
                "UPDATE book_build_steps SET status='running',attempts=attempts+1,lease_generation=? "
                "WHERE build_id=? AND unit_key=?",
                (generation, build_id, step["unit_key"]),
            )
            db.execute(
                "UPDATE book_builds SET lease_expires_at=? WHERE id=?",
                (_now(config.call_timeout_seconds + 60), build_id),
            )
            result = {
                "unit_key": step["unit_key"],
                "segments": segments,
                "known_characters": known_characters,
                "previous_error": json.loads(step["result_json"]).get("error"),
            }
            if config.prompt_version in (
                "character-discovery-v8",
                "character-discovery-v9",
                "character-discovery-v10",
                "character-discovery-v11",
                "character-discovery-v12",
                *NUMBERED_VERSIONS,
                INLINE_VERSION,
                GROUPED_VERSION,
            ):
                result["repair_packet"] = (
                    json.loads(step["result_json"]).get("repair_packet")
                    if step["attempts"] == 1
                    else None
                )
            return result

    @staticmethod
    def _validate_result(raw: str, data: dict[str, Any]) -> DiscoveryResult:
        if len(raw) > 100000:
            raise ValueError("Discovery result is too large")
        stripped = raw.strip()
        if stripped.startswith("```json") and stripped.endswith("```"):
            stripped = stripped[7:-3].strip()
        result = DiscoveryResult.model_validate_json(stripped)
        flattened = [segment for scene in result.scenes for segment in scene.segment_ids]
        if flattened != [row["id"] for row in data["segments"]]:
            raise DiscoveryCoverageError("Scenes must cover every input segment once, in order")
        rows = {row["id"]: row["text"] for row in data["segments"]}
        known = {candidate["id"]: candidate for candidate in data["known_characters"]}

        def span_matches(
            span: DiscoverySpan, scene_ids: list[str], label: str | None = None
        ) -> DiscoverySpan:
            text = rows.get(span.segment_id)
            if text is None or span.segment_id not in scene_ids:
                raise ValueError("Discovery evidence does not belong to this scene")
            resolution = "model"
            start = span.local_start
            if span.local_end > len(text) or text[start : span.local_end] != span.quote:
                start = text.find(span.quote)
                if start < 0 or text.find(span.quote, start + 1) >= 0:
                    raise ValueError(
                        "Quote is absent or ambiguous; provide exact offsets or a longer verbatim quote"
                    )
                resolution = "unique_quote"
            if label is not None and label.strip() not in span.quote:
                raise ValueError(
                    f"Unsupported name/alias {label.strip()!r}; choose a literal label present in its quote"
                )
            return cast(
                DiscoverySpan,
                span.model_copy(
                    update={
                        "local_start": start,
                        "local_end": start + len(span.quote),
                        "offset_resolution": resolution,
                    }
                ),
            )

        validate_local_identities(result)
        normalized_scenes = []
        for scene in result.scenes:
            normalized_characters = []
            for character in scene.characters:
                if character.entity_kind == "person" and "、" in character.name:
                    raise ValueError(
                        f"Split combined person name {character.name!r} into independent candidates; group mentions require entity_kind=group"
                    )
                evidence = span_matches(
                    character.evidence,
                    scene.segment_ids,
                    None if character.anonymous else character.name,
                )
                aliases = [
                    alias.model_copy(
                        update={
                            "evidence": span_matches(alias.evidence, scene.segment_ids, alias.alias)
                        }
                    )
                    for alias in character.aliases
                ]
                if character.existing_character_id:
                    candidate = known.get(character.existing_character_id)
                    if candidate is None:
                        raise ValueError("Existing identity was not supplied in this unit")
                    matching = [
                        alias
                        for alias in candidate["aliases"]
                        if _normalize(alias["alias"]) == _normalize(character.name)
                    ]
                    if not matching or any(
                        alias["review_state"] == "ambiguous" for alias in matching
                    ):
                        raise ValueError("Existing identity has no unambiguous matching alias")
                normalized_characters.append(
                    character.model_copy(update={"evidence": evidence, "aliases": aliases})
                )
            normalized_scenes.append(scene.model_copy(update={"characters": normalized_characters}))
        return cast(DiscoveryResult, result.model_copy(update={"scenes": normalized_scenes}))

    def _save_result(
        self,
        build_id: str,
        owner: str,
        generation: int,
        data: dict[str, Any],
        result: DiscoveryResult,
    ) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            build = self._fence(db, build_id, owner, generation)
            scope = (build["book_id"], build["source_version_id"], build_id)
            local_characters: dict[str, str] = {}
            for index, scene in enumerate(result.scenes):
                scene_id = str(uuid4())
                db.execute(
                    "INSERT INTO book_scenes(id,book_id,source_version_id,build_id,narrative_order,location_label) VALUES (?,?,?,?,?,?)",
                    (scene_id, *scope, int(data["unit_key"]) * 1000 + index, scene.location_label),
                )
                db.executemany(
                    "INSERT INTO book_scene_segments(book_id,source_version_id,build_id,scene_id,position,segment_id) VALUES (?,?,?,?,?,?)",
                    [
                        (*scope, scene_id, position, segment_id)
                        for position, segment_id in enumerate(scene.segment_ids)
                    ],
                )
                seen: set[str] = set()
                for character in scene.characters:
                    character_id = (
                        local_characters.get(character.local_character_key)
                        or character.existing_character_id
                        or str(uuid4())
                    )
                    if character_id in seen:
                        raise ValueError("Duplicate identity within a scene")
                    seen.add(character_id)
                    if (
                        not character.existing_character_id
                        and character.local_character_key not in local_characters
                    ):
                        db.execute(
                            "INSERT INTO book_characters(id,book_id,source_version_id,build_id,lineage_id,name,agent_status,public_profile_json) VALUES (?,?,?,?,?,?,?,?)",
                            (
                                character_id,
                                *scope,
                                str(uuid4()),
                                character.name.strip(),
                                "needs_review"
                                if character.identity == "uncertain"
                                or character.entity_kind != "person"
                                else "candidate",
                                _json(
                                    {
                                        "anonymous": character.anonymous,
                                        "entity_kind": character.entity_kind,
                                        "identity_state": "candidate",
                                    }
                                ),
                            ),
                        )
                    local_characters[character.local_character_key] = character_id
                    if character.identity == "uncertain" or character.entity_kind != "person":
                        db.execute(
                            "UPDATE book_characters SET agent_status='needs_review' WHERE id=? AND build_id=?",
                            (character_id, build_id),
                        )
                    aliases = [(character.name.strip(), character.evidence)] + [
                        (alias.alias.strip(), alias.evidence) for alias in character.aliases
                    ]
                    for name, evidence in aliases:
                        normalized = _normalize(name)
                        collisions = db.execute(
                            "SELECT character_id FROM book_character_aliases WHERE build_id=? AND normalized_alias=? AND character_id<>?",
                            (build_id, normalized, character_id),
                        ).fetchall()
                        provenance = _json(
                            {
                                "scene_id": scene_id,
                                "evidence": evidence.model_dump(),
                                "identity_state": "candidate",
                            }
                        )
                        db.execute(
                            "INSERT INTO book_character_aliases(book_id,source_version_id,build_id,character_id,alias,normalized_alias,review_state,provenance_json) "
                            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(book_id,source_version_id,build_id,character_id,normalized_alias) DO NOTHING",
                            (
                                *scope,
                                character_id,
                                name,
                                normalized,
                                "ambiguous" if collisions else "candidate",
                                provenance,
                            ),
                        )
                        if collisions:
                            db.execute(
                                "UPDATE book_character_aliases SET review_state='ambiguous' WHERE build_id=? AND normalized_alias=?",
                                (build_id, normalized),
                            )
                            for conflicting_id in [
                                character_id,
                                *(row["character_id"] for row in collisions),
                            ]:
                                db.execute(
                                    "UPDATE book_characters SET agent_status='needs_review' WHERE id=? AND build_id=?",
                                    (conflicting_id, build_id),
                                )
                    db.execute(
                        "INSERT INTO book_scene_characters(book_id,source_version_id,build_id,scene_id,character_id,presence) VALUES (?,?,?,?,?,?)",
                        (*scope, scene_id, character_id, character.presence),
                    )
            payload = {
                "segment_ids": [row["id"] for row in data["segments"]],
                "result": result.model_dump(),
            }
            if (data.get("repair_packet") or {}).get("selection_protocol") == UNIT_PROTOCOL:
                payload["repair_provenance"] = data["repair_packet"]
            db.execute(
                "UPDATE book_build_steps SET status='validated',result_json=? WHERE build_id=? AND unit_key=? AND lease_generation=?",
                (_json(payload), build_id, data["unit_key"], generation),
            )

    def _repair_scope(self, build_id: str, owner: str, generation: int, data: dict) -> dict:
        with connect(self.db_path) as db:
            db.execute("BEGIN")
            build = self._fence(db, build_id, owner, generation)
            step = db.execute(
                "SELECT input_hash,lease_generation,status FROM book_build_steps "
                "WHERE book_id=? AND source_version_id=? AND build_id=? "
                "AND stage='discovery' AND unit_key=?",
                (build["book_id"], build["source_version_id"], build_id, data["unit_key"]),
            ).fetchone()
            if (
                step is None or step["lease_generation"] != generation
                or step["status"] != "running" or step["input_hash"] != _hash(data["segments"])
            ):
                raise BookWorldError("repair_scope_changed", "Unit repair no longer matches the claimed source checkpoint")
            return {
                "workspace_id": workspace_identity(self.root),
                "book_id": build["book_id"], "source_version_id": build["source_version_id"],
                "build_id": build_id, "unit_key": data["unit_key"], "input_hash": step["input_hash"],
            }

    def _failed_attempt(
        self,
        build_id: str,
        owner: str,
        generation: int,
        unit_key: str,
        detail: str,
        *,
        repair_packet=None,
        record_repair=False,
    ) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, build_id, owner, generation)
            row = db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND unit_key=?",
                (build_id, unit_key),
            ).fetchone()
            payload = json.loads(row["result_json"])
            payload["error"] = detail
            if record_repair:
                payload["repair_packet"] = repair_packet
            db.execute(
                "UPDATE book_build_steps SET status='failed',result_json=? WHERE build_id=? AND unit_key=? AND lease_generation=?",
                (_json(payload), build_id, unit_key, generation),
            )

    def _fail_build(
        self, build_id: str, owner: str, generation: int, code: str, detail: str
    ) -> None:
        with connect(self.db_path) as db:
            db.execute(
                "UPDATE book_builds SET status='failed',error_code=?,error_detail=?,lease_owner=NULL,lease_expires_at=NULL "
                "WHERE id=? AND lease_owner=? AND lease_generation=? AND status='running'",
                (code, detail, build_id, owner, generation),
            )

    async def run(self, build_id: str, provider: Any, config: DiscoveryConfig) -> None:
        lease = await asyncio.to_thread(self._lease, build_id, config)
        if lease is None:
            return
        owner, generation = lease
        prompt = DISCOVERY_PROMPTS.get(
            config.prompt_version, DISCOVERY_PROMPTS["character-discovery-v5"]
        ) + _json(DiscoveryResult.model_json_schema())
        try:
            while True:
                data = await asyncio.to_thread(self._input, build_id, owner, generation, config)
                if data is None:
                    return
                repair_protocol = (data.get("repair_packet") or {}).get("selection_protocol")
                selected = repair_protocol == "source-choices-v1"
                windowed = repair_protocol == "source-windows-v1"
                unit_repair = repair_protocol == UNIT_PROTOCOL
                unit_scope: dict[str, Any] = {}
                numbered = prepare_numbered(data) if config.prompt_version in (*NUMBERED_VERSIONS, INLINE_VERSION, GROUPED_VERSION) and not data.get("repair_packet") else None
                if unit_repair:
                    if config.prompt_version not in UNIT_REPAIR_VERSIONS:
                        raise BookWorldError("repair_scope_changed", "Unit repair is unavailable for this saved strategy")
                    unit_scope = await asyncio.to_thread(self._repair_scope, build_id, owner, generation, data)
                    try:
                        model_input = unit_repair_input(data["repair_packet"], data, unit_scope)
                    except ValueError:
                        raise BookWorldError("repair_scope_changed", "Saved unit repair does not match this source and build") from None
                    system_prompt = UNIT_PROMPT + _json(UnitDiscovery.model_json_schema())
                elif numbered is not None:
                    schema: type[StrictModel]
                    if config.prompt_version == GROUPED_VERSION:
                        numbered_prompt, schema = GROUPED_PROMPT, GroupedDiscovery
                        numbered["input"]["phase"] = "discovery_grouped"
                    elif config.prompt_version == INLINE_VERSION:
                        numbered_prompt, schema = INLINE_PROMPT, InlineDiscovery
                        numbered["input"]["phase"] = "discovery_inline"
                    else:
                        numbered_prompt = NUMBERED_LATEST_PROMPT if config.prompt_version == NUMBERED_LATEST_VERSION else NUMBERED_PROMPT
                        schema = NumberedDiscovery
                    system_prompt = numbered_prompt + _json(schema.model_json_schema())
                    model_input = numbered["input"]
                elif windowed:
                    system_prompt = WINDOW_REPAIR_PROMPT + _json(WindowRepairs.model_json_schema())
                    model_input = window_repair_input(data["repair_packet"])
                elif selected:
                    system_prompt = SELECTION_PROMPT + _json(SelectedRepairs.model_json_schema())
                    model_input = selection_input(data["repair_packet"])
                else:
                    repair_prompt = (
                        REPAIR_V10_PROMPT
                        if config.prompt_version
                        in ("character-discovery-v10", "character-discovery-v11", "character-discovery-v12", *NUMBERED_VERSIONS, INLINE_VERSION, GROUPED_VERSION)
                        else REPAIR_V9_PROMPT
                        if config.prompt_version == "character-discovery-v9"
                        else REPAIR_PROMPT
                    )
                    system_prompt = (
                        repair_prompt + _json(DiscoveryRepairs.model_json_schema())
                        if data.get("repair_packet")
                        else prompt
                    )
                    model_input = discovery_model_input(data, config.prompt_version)
                messages = [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": _json(model_input),
                    },
                ]
                raw_for_repair = None
                wire_raw = None
                wire_failed = False
                try:
                    options: dict[str, Any] = {
                        "model": config.model,
                        "max_tokens": config.max_tokens,
                        "temperature": 0,
                    }
                    if config.reasoning_effort:
                        options["reasoning_effort"] = config.reasoning_effort
                    response = await asyncio.wait_for(
                        provider.chat(messages, **options),
                        timeout=config.call_timeout_seconds,
                    )
                    if response.finish_reason not in ("stop", "end_turn") or response.tool_calls:
                        raise ValueError("Discovery response is truncated or requests a tool")
                    raw_for_repair = response.content or ""
                    wire_raw = raw_for_repair
                    if numbered is not None:
                        try:
                            if config.prompt_version == GROUPED_VERSION:
                                expanded = assemble_grouped(raw_for_repair, numbered)
                            elif config.prompt_version == INLINE_VERSION:
                                expanded = assemble_inline(raw_for_repair, numbered)
                            else:
                                expanded = assemble_numbered(raw_for_repair, numbered, allow_implicit_name=config.prompt_version == NUMBERED_LATEST_VERSION)
                        except ValueError:
                            wire_failed = True
                            raise
                        raw_for_repair = _json(expanded)
                    result = (
                        apply_unit_repair(raw_for_repair, data["repair_packet"], data, unit_scope, self._validate_result)
                        if unit_repair
                        else apply_window_repair(
                            raw_for_repair, data["repair_packet"], data, self._validate_result
                        )
                        if windowed
                        else apply_selection(
                            raw_for_repair, data["repair_packet"], data, self._validate_result
                        )
                        if selected
                        else apply_repair(
                            raw_for_repair, data["repair_packet"], data, self._validate_result
                        )
                        if data.get("repair_packet")
                        else self._validate_result(raw_for_repair, data)
                    )
                    await asyncio.to_thread(
                        self._save_result, build_id, owner, generation, data, result
                    )
                except (ValueError, ValidationError, TimeoutError) as error:
                    detail = (
                        "Invalid structured fields: "
                        + ", ".join(
                            ".".join(map(str, issue["loc"]))
                            for issue in error.errors(include_input=False, include_context=False)[
                                :8
                            ]
                        )
                        if isinstance(error, ValidationError)
                        else "Model request timed out"
                        if isinstance(error, TimeoutError)
                        else str(error)[:300]
                    )
                    packet = None
                    if (
                        config.prompt_version
                        in (
                            "character-discovery-v8",
                            "character-discovery-v9",
                            "character-discovery-v10",
                            "character-discovery-v11",
                            "character-discovery-v12",
                            *NUMBERED_VERSIONS,
                            INLINE_VERSION,
                            GROUPED_VERSION,
                        )
                        and raw_for_repair
                        and not data.get("repair_packet")
                    ):
                        packet = await asyncio.to_thread(
                            prepare_repair,
                            raw_for_repair,
                            data,
                            self._validate_result,
                            allow_anonymous_split=config.prompt_version == "character-discovery-v9",
                            allow_uncertain_split=config.prompt_version
                            in (
                                "character-discovery-v10",
                                "character-discovery-v11",
                                "character-discovery-v12",
                                *NUMBERED_VERSIONS,
                                INLINE_VERSION,
                                GROUPED_VERSION,
                            ),
                            allow_binding_split=config.prompt_version in ("character-discovery-v12", *NUMBERED_VERSIONS, INLINE_VERSION, GROUPED_VERSION),
                        )
                        if (
                            packet is not None
                            and config.prompt_version in ("character-discovery-v12", *NUMBERED_VERSIONS, INLINE_VERSION, GROUPED_VERSION)
                        ):
                            selection = await asyncio.to_thread(prepare_selection, packet, data)
                            if selection is None and config.prompt_version in (NUMBERED_LATEST_VERSION, INLINE_VERSION, GROUPED_VERSION):
                                selection = await asyncio.to_thread(prepare_window_repair, packet, data)
                            packet = selection
                    if (
                        config.prompt_version in UNIT_REPAIR_VERSIONS
                        and packet is None and not data.get("repair_packet")
                        and isinstance(error, ValueError)
                        and can_repair_unit(error, wire_failed, wire_raw)
                    ):
                        scope = await asyncio.to_thread(self._repair_scope, build_id, owner, generation, data)
                        packet = await asyncio.to_thread(
                            prepare_unit_repair, data, scope, detail,
                            hashlib.sha256((wire_raw or "").encode()).hexdigest(),
                        )
                    await asyncio.to_thread(
                        self._failed_attempt,
                        build_id,
                        owner,
                        generation,
                        data["unit_key"],
                        detail,
                        repair_packet=packet,
                        record_repair=config.prompt_version
                        in (
                            "character-discovery-v8",
                            "character-discovery-v9",
                            "character-discovery-v10",
                            "character-discovery-v11",
                            "character-discovery-v12",
                            *NUMBERED_VERSIONS,
                            INLINE_VERSION,
                            GROUPED_VERSION,
                        ),
                    )
        except BookWorldError as error:
            if error.code != "stale_build":
                await asyncio.to_thread(
                    self._fail_build, build_id, owner, generation, error.code, str(error)
                )
        except asyncio.CancelledError:
            # A stopped process leaves its lease to expire; accepted checkpoints remain reusable.
            raise
        except Exception:
            await asyncio.to_thread(
                self._fail_build,
                build_id,
                owner,
                generation,
                "provider_failed",
                "Model service failed; retry after checking configuration",
            )
