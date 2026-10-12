"""Canonical head CAS happens inside the same transaction as persona publication."""

import json
import sqlite3

from .source import BookWorldError


def check_revision_head(db: sqlite3.Connection, build: sqlite3.Row) -> None:
    revision = db.execute(
        "SELECT * FROM book_revisions WHERE build_id=?", (build["id"],)
    ).fetchone()
    if revision:
        head = db.execute(
            "SELECT * FROM book_revision_heads WHERE book_id=? AND source_version_id=?",
            (build["book_id"], build["source_version_id"]),
        ).fetchone()
        if (
            not head
            or head["build_id"] != revision["base_build_id"]
            or head["revision"] != revision["reserved_revision"]
        ):
            raise BookWorldError(
                "revision_conflict", "A newer edit or canonical version superseded this revision"
            )
        mapping = json.loads(revision["character_map_json"])
        resolutions: dict[str, list[str]] = {}
        semantic_checks: dict[str, list[dict]] = {}
        for step in db.execute(
            "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence' AND status='validated'",
            (build["id"],),
        ):
            payload = json.loads(step["result_json"])
            for check in payload.get("review", {}).get("revision_checks", []):
                semantic_checks.setdefault(check["local_key"], []).append(check)
            for key, identifier in payload.get("claim_ids", {}).items():
                resolutions.setdefault(key, []).append(identifier)
        for index, change in enumerate(json.loads(revision["changes_json"])):
            if change["operation"] != "correct_owner":
                continue
            proof = change["evidence"]
            target = mapping[change["target_character_id"]]
            original = mapping[change["character_id"]]
            eligible = [
                dict(row)
                for row in db.execute(
                    "SELECT c.id,c.owner_character_id,c.proposition FROM book_claims c JOIN book_evidence e ON e.build_id=c.build_id AND e.claim_id=c.id JOIN book_claim_access a ON a.build_id=c.build_id AND a.claim_id=c.id AND a.character_id=c.owner_character_id WHERE c.build_id=? AND c.kind=? AND c.support_state='accepted' AND a.access_state='accepted' AND e.support_state='accepted' AND e.segment_id=? AND e.local_start<? AND e.local_end>?",
                    (
                        build["id"],
                        change["kind"],
                        proof["segment_id"],
                        proof["local_end"],
                        proof["local_start"],
                    ),
                )
            ]
            confirmed = any(
                row["owner_character_id"] == target
                and row["id"] in resolutions.get(f"revision:{index}", [])
                for row in eligible
            )
            checks = semantic_checks.get(f"revision:{index}", [])
            confirmed = (
                confirmed
                and bool(checks)
                and all(
                    check["same_claim_repaired"] and check["original_assignment_removed"]
                    for check in checks
                )
            )
            repeated_error = any(
                row["owner_character_id"] == original
                and row["proposition"] == change["proposition"]
                for row in eligible
            )
            if not confirmed or (original != target and repeated_error):
                raise BookWorldError(
                    "revision_unresolved",
                    "Ownership correction was not confirmed by the new evidence extraction",
                )


def correction_hints(db: sqlite3.Connection, build_id: str, segment_ids: list[str]) -> list[dict]:
    audit = db.execute(
        "SELECT changes_json,character_map_json FROM book_revisions WHERE build_id=?", (build_id,)
    ).fetchone()
    if not audit:
        return []
    mapping = json.loads(audit["character_map_json"])
    return [
        {
            **change,
            "local_key": f"revision:{index}",
            "character_id": mapping[change["character_id"]],
            "target_character_id": mapping.get(change["target_character_id"]),
            "claim_id": None,
        }
        for index, change in enumerate(json.loads(audit["changes_json"]))
        if change["operation"] == "correct_owner"
        and change["evidence"]["segment_id"] in segment_ids
    ]


def advance_revision_head(db: sqlite3.Connection, build: sqlite3.Row) -> None:
    db.execute(
        "INSERT INTO book_revision_heads(book_id,source_version_id,build_id,revision) VALUES (?,?,?,1) ON CONFLICT(book_id,source_version_id) DO UPDATE SET build_id=excluded.build_id,revision=book_revision_heads.revision+1 WHERE book_revision_heads.build_id<>excluded.build_id",
        (build["book_id"], build["source_version_id"], build["id"]),
    )


def check_revision_identities(db: sqlite3.Connection, build: sqlite3.Row) -> None:
    audit = db.execute(
        "SELECT changes_json,character_map_json FROM book_revisions WHERE build_id=?",
        (build["id"],),
    ).fetchone()
    if not audit:
        return
    mapping = json.loads(audit["character_map_json"])
    for change in json.loads(audit["changes_json"]):
        identifier = (
            mapping[change["target_character_id"]]
            if change["operation"] in ("merge", "correct_owner")
            else mapping[change["character_id"]]
        )
        person = db.execute(
            "SELECT agent_status FROM book_characters WHERE build_id=? AND id=?",
            (build["id"], identifier),
        ).fetchone()
        if not person or person["agent_status"] not in ("ready", "sparse"):
            raise BookWorldError(
                "revision_unresolved",
                "The corrected identity was not independently confirmed; the previous canonical version is retained",
            )
