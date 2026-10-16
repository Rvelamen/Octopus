"""Deterministic re-evaluation of T17 matrix v2 character refs.

Scans every character message ref in
``docs/plans/book-character-agents/validation/real-model-t17-matrix-v2.json``
and flags any whose underlying claim is a trait proposition that
over-reaches its evidence quote, using
``backend.services.book_world.proposition_alignment.trait_completion_overreach``.

This script is the executable form of the matrix v2 ``remaining_work``
item 2 ("Re-evaluate matrix v2 replies against corrected source gold")
run against the deterministic lint rather than against a corrected
baseline (which does not yet exist). It consumes no model budget and
mutates nothing.

Usage::

    python scripts/book_world/reevaluate_matrix_v2_refs.py \\
        --matrix docs/plans/book-character-agents/validation/real-model-t17-matrix-v2.json \\
        --controls docs/plans/book-character-agents/validation/real-model-persona-evidence-controls-v1.json \\
        --report docs/plans/book-character-agents/validation/2026-10-16-t17-matrix-v2-lint-reeval.json

The report JSON records, per case, the flagged refs with the asserted
verb, the intent marker found in the quote, and the assertion text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from the repository root without installing
# the package.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.book_world.proposition_alignment import (  # noqa: E402
    trait_completion_overreach,
)


def _collect_segment_text(payload: object, sink: dict[str, str]) -> None:
    """Walk ``payload`` and collect every ``{id, text}`` pair as a segment."""
    if isinstance(payload, dict):
        segment_id = payload.get("id")
        text = payload.get("text")
        if isinstance(segment_id, str) and isinstance(text, str):
            sink[segment_id] = text
        for value in payload.values():
            _collect_segment_text(value, sink)
    elif isinstance(payload, list):
        for value in payload:
            _collect_segment_text(value, sink)


def _build_evidence_lookup(
    matrix: dict,
    segment_text: dict[str, str],
) -> dict[tuple[str, str], dict]:
    """Map ``(claim_id, evidence_id)`` to proposition / quote / kind metadata."""
    lookup: dict[tuple[str, str], dict] = {}
    for entry in matrix.get("reader_evidence", []):
        segment_id = entry.get("segment_id", "")
        text = segment_text.get(segment_id, "")
        if not text:
            continue
        start = entry.get("local_start", 0)
        end = entry.get("local_end", 0)
        quote = text[start:end] if 0 <= start < end <= len(text) else ""
        scope = entry.get("character_scope", {}) or {}
        key = (entry.get("claim_id", ""), entry.get("evidence_id", ""))
        lookup[key] = {
            "proposition": entry.get("proposition", ""),
            "quote": quote,
            "kind": entry.get("kind", ""),
            "route": entry.get("route", ""),
            "build_id": scope.get("build_id", ""),
            "character_id": scope.get("character_id", ""),
            "segment_id": segment_id,
        }
    return lookup


def reevaluate(matrix_path: Path, controls_path: Path) -> dict:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    controls = json.loads(controls_path.read_text(encoding="utf-8"))

    segment_text: dict[str, str] = {}
    _collect_segment_text(controls, segment_text)
    evidence_lookup = _build_evidence_lookup(matrix, segment_text)

    findings: list[dict] = []
    total_refs = 0
    trait_refs = 0
    for case in matrix.get("cases", []):
        case_id = case.get("case_id", "")
        for turn in case.get("turns", []):
            for message in turn.get("messages", []):
                if message.get("speaker_type") != "character":
                    continue
                for ref in message.get("refs", []):
                    total_refs += 1
                    key = (ref.get("claim_id", ""), ref.get("evidence_id", ""))
                    evidence = evidence_lookup.get(key)
                    if not evidence or evidence["kind"] != "trait":
                        continue
                    trait_refs += 1
                    flag = trait_completion_overreach(
                        evidence["proposition"], evidence["quote"]
                    )
                    if flag is None:
                        continue
                    findings.append(
                        {
                            "case_id": case_id,
                            "message_id": message.get("id", ""),
                            "round_id": turn.get("round_id", ""),
                            "assertion_text": ref.get("assertion_text", ""),
                            "assertion_ordinal": ref.get("assertion_ordinal"),
                            "claim_id": key[0],
                            "evidence_id": key[1],
                            "build_id": evidence["build_id"],
                            "character_id": evidence["character_id"],
                            "segment_id": evidence["segment_id"],
                            "proposition": evidence["proposition"],
                            "quote": evidence["quote"],
                            "asserted_verb": flag.asserted_verb,
                            "intent_marker": flag.matched_intent_marker,
                            "reason": flag.reason,
                        }
                    )

    cases_flagged = sorted({f["case_id"] for f in findings})
    return {
        "matrix_path": str(matrix_path),
        "controls_path": str(controls_path),
        "matrix_dataset_sha256": matrix.get("dataset_sha256", ""),
        "matrix_runner_sha256": matrix.get("runner_sha256", ""),
        "total_character_refs": total_refs,
        "trait_refs_examined": trait_refs,
        "flagged_refs": len(findings),
        "flagged_cases": cases_flagged,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--controls", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    report = reevaluate(args.matrix, args.controls)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "refs={total} trait_refs={trait} flagged={flagged} cases={cases}".format(
            total=report["total_character_refs"],
            trait=report["trait_refs_examined"],
            flagged=report["flagged_refs"],
            cases=",".join(report["flagged_cases"]) or "<none>",
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
