"""Deterministic tests for the trait-vs-completion proposition linter.

The T17 matrix v2 review (``t17-matrix-v2-agent-review.json``) flagged
two ``warning_source_strength`` cases and listed as remaining work:

  "Disambiguate the approved trait proposition from historical event
  completion, preserve original build and publish a separate
  evidence-backed version if corrected."

The canonical persona baselines are immutable once published, and the
existing revision machinery only patches identity/ownership — there is
no operation to rephrase an over-strong trait proposition in place.
The deterministic lever available without consuming model budget is a
regression gate that detects the failure mode so the next build can be
authored against the warning. These tests pin that gate using the
exact claim / quote pair from the matrix v2 baseline.
"""

from backend.services.book_world.proposition_alignment import (
    TraitOverreach,
    scan_trait_claims,
    trait_completion_overreach,
)

# The exact proposition / evidence quote pair from the matrix v2
# baseline that motivated this linter.
#
# build_id     c2da28c8-cab3-4bc2-9342-b1a60831c99a
# character_id f3335a7e-7dea-4e6d-a34f-457978bb27b7 (石猴)
# claim_id     6742efce-da5c-4892-ac66-0d6c3de1b76f
# evidence_id  36dee9fb-b797-4b23-af33-0414d579b547
# segment_id   0829663f-3552-45e5-8332-999161919caf (chars 67..99)
MATRIX_V2_STONE_MONKEY_PROPOSITION = "石猴勇敢果断，敢于率先跳入瀑布泉中探险。"
MATRIX_V2_STONE_MONKEY_QUOTE = (
    "连呼了三声忽见丛杂中跳出一名石猴应声高叫道:‘我进去!我进去!’"
)


def test_matrix_v2_stone_monkey_trait_is_flagged() -> None:
    """The exact matrix v2 baseline claim must be flagged.

    The proposition asserts the character was the first to *jump into*
    the waterfall and *explore* it; the quote only proves the character
    *volunteered* by shouting "我进去!我进去!" — a speech act, not a
    completed jump. This is the failure mode the T17 review called
    out; the linter must detect it deterministically.
    """
    flag = trait_completion_overreach(
        MATRIX_V2_STONE_MONKEY_PROPOSITION,
        MATRIX_V2_STONE_MONKEY_QUOTE,
    )
    assert flag is not None, "expected over-reach to be detected"
    assert isinstance(flag, TraitOverreach)
    assert flag.asserted_verb == "跳入"
    assert flag.matched_intent_marker in {"我进去", "应声", "高叫", "叫道"}
    assert "率先" in flag.reason or "completed" in flag.reason


def test_aligned_trait_with_completed_action_in_quote_passes() -> None:
    """A trait whose quote literally contains the asserted verb is OK.

    When the evidence quote itself records the completed action (e.g.
    the actual jump passage from segment a0155270), the proposition
    wording is grounded and must not be flagged even if other speech
    markers are present nearby.
    """
    proposition = "石猴勇敢果断,敢于率先跳入瀑布泉中探险。"
    quote = (
        "你看他瞑目蹲身将身一纵径跳入瀑布泉中忽睁睛抬头观看"
        "那里边却无水无波明明朗朗的一架桥梁。"
    )
    flag = trait_completion_overreach(proposition, quote)
    assert flag is None, "quote literally records 跳入; no over-reach"


def test_suggested_correction_passes_lint() -> None:
    """The proposed corrected proposition must not be flagged.

    The diagnosis doc proposes this corrected wording for the next
    persona build:

        石猴勇敢果断,在群猴无人敢应时率先应声表示愿意进入瀑布。

    It keeps the 率先 marker but re-anchors the object to the
    volunteered speech act (应声表示愿意进入) which IS what the quote
    records. The lint must accept this wording against the original
    32-char quote — proving the suggested correction resolves the
    over-reach it diagnosed.
    """
    corrected_proposition = "石猴勇敢果断,在群猴无人敢应时率先应声表示愿意进入瀑布。"
    flag = trait_completion_overreach(
        corrected_proposition,
        MATRIX_V2_STONE_MONKEY_QUOTE,
    )
    assert flag is None, (
        "the suggested correction must clear the lint; if it fires, "
        "the proposed wording still over-reaches the quote"
    )


def test_trait_without_shuaxian_prefix_passes() -> None:
    """Propositions that do not assert primacy are out of scope.

    The linter is intentionally narrow: only 率先 + completion-verb
    constructions are inspected. Other trait wordings are left to
    other layers of validation.
    """
    proposition = "石猴勇敢果断,在群猴不敢应时主动站出来。"
    quote = "连呼了三声忽见丛杂中跳出一名石猴应声高叫道:‘我进去!我进去!’"
    assert trait_completion_overreach(proposition, quote) is None


def test_trait_with_completion_verb_but_no_intent_marker_passes() -> None:
    """If the quote lacks both the verb and any intent marker, do not flag.

    The linter only fires when there is positive evidence that the
    quote records intent rather than completion. Silence is not
    treated as proof of over-reach; that keeps the false-positive
    rate at zero on quotes the linter does not understand.
    """
    proposition = "石猴勇敢果断,敢于率先跳入瀑布泉中探险。"
    quote = "众猴拍手称扬道好水好水原来此处远通山脚之下直接大海之波"
    assert trait_completion_overreach(proposition, quote) is None


def test_non_trait_claims_are_skipped_by_scan() -> None:
    """``scan_trait_claims`` must ignore episodes / facts / beliefs.

    The trait-vs-completion confusion is specific to trait slots;
    episodes legitimately describe completed historical actions and
    must not be flagged.
    """
    claims = [
        {
            "kind": "episode",
            "proposition": "石猴瞑目蹲身纵身跳入瀑布泉中,发现里面无水无波。",
            "quote": "你看他瞑目蹲身将身一纵径跳入瀑布泉中忽睁睛抬头观看",
        },
        {
            "kind": "fact",
            "proposition": "群猴当众约定钻进瀑布寻源而不伤者拜为王。",
            "quote": "那一个有本事的钻进去寻个源头出来不伤身体者我等即拜他为王",
        },
    ]
    findings = scan_trait_claims(claims, lambda c: c["quote"])
    assert findings == []


def test_scan_collects_only_flagged_traits() -> None:
    """End-to-end scan: the matrix v2 trait is the only finding."""
    claims = [
        {
            "kind": "trait",
            "proposition": MATRIX_V2_STONE_MONKEY_PROPOSITION,
            "quote": MATRIX_V2_STONE_MONKEY_QUOTE,
        },
        {
            "kind": "trait",
            "proposition": "石猴善于观察,注意到桥那头似有人家住处。",
            "quote": "却又欠身上桥头再走再看却似有人家住处一般真个好所在",
        },
        {
            "kind": "episode",
            "proposition": "石猴瞑目蹲身纵身跳入瀑布泉中。",
            "quote": "径跳入瀑布泉中忽睁睛抬头观看那里边却无水无波",
        },
    ]
    findings = scan_trait_claims(claims, lambda c: c["quote"])
    assert len(findings) == 1
    assert findings[0].asserted_verb == "跳入"


def test_reason_mentions_both_sides_of_the_mismatch() -> None:
    """The human-readable reason must explain the mismatch.

    Validators and reviewers consume this string when triaging the
    warning; it must name both the asserted completion verb and the
    intent marker found in the quote.
    """
    flag = trait_completion_overreach(
        MATRIX_V2_STONE_MONKEY_PROPOSITION,
        MATRIX_V2_STONE_MONKEY_QUOTE,
    )
    assert flag is not None
    assert flag.asserted_verb in flag.reason
    assert flag.matched_intent_marker in flag.reason
    assert flag.proposition == MATRIX_V2_STONE_MONKEY_PROPOSITION
    assert flag.quote == MATRIX_V2_STONE_MONKEY_QUOTE


def test_matrix_v2_json_yields_expected_flagged_cases() -> None:
    """Integration check: the lint must reproduce the known matrix v2 findings.

    Reads the frozen ``real-model-t17-matrix-v2.json`` baseline and the
    companion ``real-model-persona-evidence-controls-v1.json`` segment
    store, replays the deterministic re-evaluation, and asserts the
    exact set of flagged cases. This locks in both:
      * the lint logic (any regression that stops it firing will fail
        this test), and
      * the diagnosis that exactly four matrix v2 cases rely on the
        over-strong stone-monkey trait — the two cases the agent
        review originally flagged (``free-directed-conditional-action``,
        ``free-all-unshared-private-knowledge``) plus two it missed
        (``topic-natural-retained-topic``, ``topic-directed-rephrased-dilemma``).

    No model calls; both JSON files are read-only.
    """
    import json
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    matrix_path = (
        repo
        / "docs"
        / "plans"
        / "book-character-agents"
        / "validation"
        / "real-model-t17-matrix-v2.json"
    )
    controls_path = (
        repo
        / "docs"
        / "plans"
        / "book-character-agents"
        / "validation"
        / "real-model-persona-evidence-controls-v1.json"
    )
    if not matrix_path.exists() or not controls_path.exists():
        import pytest

        pytest.skip("matrix v2 baselines not present in this checkout")

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    controls = json.loads(controls_path.read_text(encoding="utf-8"))

    segment_text: dict[str, str] = {}

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            seg_id = node.get("id")
            text = node.get("text")
            if isinstance(seg_id, str) and isinstance(text, str):
                segment_text[seg_id] = text
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(controls)

    evidence_lookup: dict[tuple[str, str], dict] = {}
    for entry in matrix.get("reader_evidence", []):
        seg_id = entry.get("segment_id", "")
        text = segment_text.get(seg_id, "")
        if not text:
            continue
        start = entry.get("local_start", 0)
        end = entry.get("local_end", 0)
        quote = text[start:end] if 0 <= start < end <= len(text) else ""
        key = (entry.get("claim_id", ""), entry.get("evidence_id", ""))
        evidence_lookup[key] = {
            "proposition": entry.get("proposition", ""),
            "quote": quote,
            "kind": entry.get("kind", ""),
        }

    flagged_cases: set[str] = set()
    flagged_refs = 0
    for case in matrix.get("cases", []):
        case_id = case.get("case_id", "")
        for turn in case.get("turns", []):
            for message in turn.get("messages", []):
                if message.get("speaker_type") != "character":
                    continue
                for ref in message.get("refs", []):
                    key = (ref.get("claim_id", ""), ref.get("evidence_id", ""))
                    evidence = evidence_lookup.get(key)
                    if not evidence or evidence["kind"] != "trait":
                        continue
                    flag = trait_completion_overreach(
                        evidence["proposition"], evidence["quote"]
                    )
                    if flag is not None:
                        flagged_refs += 1
                        flagged_cases.add(case_id)

    assert flagged_refs == 6, (
        "expected the lint to flag all six trait refs across matrix v2 "
        f"(got {flagged_refs}); if this drops, the lint regressed"
    )
    assert flagged_cases == {
        "free-all-unshared-private-knowledge",
        "free-directed-conditional-action",
        "topic-directed-rephrased-dilemma",
        "topic-natural-retained-topic",
    }, (
        "the lint must catch the two cases the agent review originally "
        "flagged AND the two it missed; if this set changes, update the "
        "diagnosis doc with the new findings"
    )
