"""Calculate baseline slots and freeze a canonical build in its caller's transaction."""

import json
import sqlite3
from typing import Any

from .discovery import _json
from .revision_storage import advance_revision_head, check_revision_head, check_revision_identities
from .source import BookWorldError


def publish_personas(db: sqlite3.Connection, build: sqlite3.Row) -> None:
    build_id = build["id"]
    check_revision_head(db, build)
    scope = (build["book_id"], build["source_version_id"], build_id)
    steps = db.execute(
        "SELECT * FROM book_build_steps WHERE build_id=? AND stage='evidence' ORDER BY CAST(unit_key AS INTEGER)",
        (build_id,),
    ).fetchall()
    if any(step["status"] in ("pending", "running") for step in steps):
        raise BookWorldError("build_incomplete", "Evidence units are still pending")
    verified_identities: set[str] = set()
    proposals: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for step in steps:
        if step["status"] != "validated":
            continue
        payload = json.loads(step["result_json"])
        verified_identities.update(payload.get("confirmed_identities", []))
        for entry in payload.get("baselines", []):
            proposals.setdefault((entry["character_id"], entry["slot_key"]), []).append(entry)
    eligible = {
        row["id"]
        for row in db.execute(
            "SELECT c.id FROM book_claims c JOIN book_claim_access a ON a.claim_id=c.id AND a.build_id=c.build_id "
            "WHERE c.build_id=? AND c.support_state='accepted' AND a.access_state='accepted' "
            "AND a.character_id=c.owner_character_id",
            (build_id,),
        )
    }
    conflicts: dict[str, list[str]] = {}
    for (character_id, slot), entries in proposals.items():
        entries = [entry for entry in entries if entry["claim_id"] in eligible]
        superseded = {
            entry["supersedes_claim_id"] for entry in entries if entry["supersedes_claim_id"]
        }
        remaining = [
            entry
            for entry in entries
            if entry["claim_id"] not in superseded and entry["temporal_state"] != "historical"
        ]
        distinct = {entry["proposition"] for entry in remaining}
        if len(distinct) != 1 or any(entry["temporal_state"] != "current" for entry in remaining):
            if remaining:
                conflicts.setdefault(character_id, []).append(slot)
            continue
        chosen = remaining[0]  # Equivalent propositions, not a last-text-position overwrite.
        db.execute(
            "INSERT INTO book_character_baselines(book_id,source_version_id,build_id,character_id,slot_key,claim_id) VALUES (?,?,?,?,?,?)",
            (*scope, character_id, slot, chosen["claim_id"]),
        )
    people = db.execute("SELECT * FROM book_characters WHERE build_id=?", (build_id,)).fetchall()
    ready = 0
    for person in people:
        profile = json.loads(person["public_profile_json"])
        accessible = db.execute(
            "SELECT COUNT(*),COUNT(DISTINCT c.kind) FROM book_claim_access a JOIN book_claims c ON c.id=a.claim_id AND c.build_id=a.build_id WHERE a.build_id=? AND a.character_id=? AND a.access_state='accepted' AND c.support_state='accepted'",
            (build_id, person["id"]),
        ).fetchone()
        has_baseline = db.execute(
            "SELECT 1 FROM book_character_baselines WHERE build_id=? AND character_id=? LIMIT 1",
            (build_id, person["id"]),
        ).fetchone()
        safe_identity = (
            person["id"] in verified_identities
            and person["agent_status"] != "needs_review"
            and profile.get("entity_kind") == "person"
        )
        status = (
            "ready"
            if safe_identity and accessible[0] >= 3 and accessible[1] >= 2 and has_baseline
            else "sparse"
            if safe_identity
            else "needs_review"
        )
        if status in ("ready", "sparse"):
            ready += 1
        public = {
            "name": person["name"],
            "entity_kind": profile.get("entity_kind", "unknown"),
            "identity_state": "verified" if safe_identity else "needs_review",
        }
        policy = {
            "kind": "book_character",
            "policy_version": build["policy_version"],
            "scope": {
                "book_id": scope[0],
                "source_version_id": scope[1],
                "build_id": build_id,
                "character_id": person["id"],
            },
            "tools": [],
            "knowledge_policy": "authorized_canonical_only",
            "memory_policy": "room_epoch_only",
            "core_persona": "immutable",
            "unknown_policy": "express_unknown",
            "conflicting_slots": conflicts.get(person["id"], []),
        }
        db.execute(
            "UPDATE book_characters SET agent_status=?,public_profile_json=?,runtime_policy_json=? WHERE id=? AND build_id=?",
            (status, _json(public), _json(policy), person["id"], build_id),
        )
    check_revision_identities(db, build)
    if not ready:
        raise BookWorldError(
            "no_publishable_characters", "No independently verified person can be published"
        )
    failed = [step["unit_key"] for step in steps if step["status"] == "failed"]
    rejected = db.execute(
        "SELECT COUNT(*) FROM book_claims WHERE build_id=? AND support_state='rejected'",
        (build_id,),
    ).fetchone()[0]
    unresolved = len(people) - ready
    partial = bool(failed or rejected or unresolved or conflicts)
    report = {
        "failed_units": failed,
        "rejected_claims": rejected,
        "unresolved_characters": unresolved,
        "published_characters": ready,
        "baseline_conflicts": sum(map(len, conflicts.values())),
    }
    db.execute(
        "INSERT INTO book_build_steps(book_id,source_version_id,build_id,stage,unit_key,input_hash,status,result_json,lease_generation) VALUES (?,?,?,'publication','summary','summary','validated',?,?)",
        (*scope, _json(report), build["lease_generation"]),
    )
    db.execute(
        "UPDATE book_builds SET status=?,stage='persona_published',lease_owner=NULL,lease_expires_at=NULL,error_code=?,error_detail=? WHERE id=?",
        (
            "partial_published" if partial else "published",
            "partial_build" if partial else None,
            "Some identities, evidence units or baseline slots remain unresolved"
            if partial
            else None,
            build_id,
        ),
    )
    advance_revision_head(db, build)
