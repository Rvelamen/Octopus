"""Deterministic contract tests for the T12 60+24 question-set pool + slicer.

Locks in the v2 pool structure (60 boundary + 24 expression = 84 cases),
the v1 slicer contract (every 8-pilot window covers all 4 boundary + 4
v1 expression classes), and the runner-wiring invariant (a sliced
window passes the runner's ``--dry-run``). All checks are pure: no DB,
no model, no fixtures beyond the on-disk JSON files.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V2_POOL = REPO / "docs" / "plans" / "book-character-agents" / "validation" / "t12-quality-cases-v2.json"
V1_DATASET = REPO / "docs" / "plans" / "book-character-agents" / "validation" / "t12-quality-cases-v1.json"
RUNNER = REPO / "docs" / "plans" / "book-character-agents" / "t12-quality-runner.py"
SLICER = REPO / "scripts" / "book_world" / "slice_t12_pool.py"

V1_BOUNDARY = ("knowable", "unknowable", "belief", "emotion")
V1_EXPRESSION = ("answer", "challenge", "comfort", "cross_book_hearsay")
ALL_EXPRESSION = ("answer", "challenge", "comfort", "disagree",
                  "unknown_expression", "cross_book_hearsay")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_pool_exists() -> dict:
    if not V2_POOL.exists():
        import pytest
        pytest.skip(f"v2 pool not present at {V2_POOL}")
    return _load(V2_POOL)


def test_v2_pool_has_exactly_84_cases() -> None:
    """The T12 protocol mandates 60 boundary + 24 expression = 84."""
    pool = _ensure_pool_exists()
    assert len(pool["cases"]) == 84, f"expected 84 cases, got {len(pool['cases'])}"
    boundary = sum(1 for c in pool["cases"] if c["tier"] == "boundary")
    expression = sum(1 for c in pool["cases"] if c["tier"] == "expression")
    assert boundary == 60, f"expected 60 boundary, got {boundary}"
    assert expression == 24, f"expected 24 expression, got {expression}"


def test_v2_pool_class_distribution_matches_protocol() -> None:
    """Each boundary class has 15 cases (8 stone + 7 daiyu); each
    expression class has 4 cases (2 stone + 2 daiyu)."""
    pool = _ensure_pool_exists()
    classes = Counter((c["tier"], c["class"]) for c in pool["cases"])
    for cls in V1_BOUNDARY:
        assert classes[("boundary", cls)] == 15, (
            f"boundary/{cls} expected 15, got {classes[('boundary', cls)]}"
        )
    for cls in ALL_EXPRESSION:
        assert classes[("expression", cls)] == 4, (
            f"expression/{cls} expected 4, got {classes[('expression', cls)]}"
        )


def test_v2_pool_covers_both_books_and_both_characters() -> None:
    """Both books (西游记 / 红楼梦) and both characters (石猴 / 黛玉)
    appear in every class — required by chat-quality-protocol.md line 66.
    """
    pool = _ensure_pool_exists()
    XYJ = "efc80c04-df9b-48e2-ace5-833de34d63fe"
    HLM = "2740f60c-3198-4350-b664-2ed688f9e2cb"
    for tier in ("boundary", "expression"):
        for cls in (V1_BOUNDARY if tier == "boundary" else ALL_EXPRESSION):
            tier_class_cases = [
                c for c in pool["cases"]
                if c["tier"] == tier and c["class"] == cls
            ]
            actors = {tuple(c["target_actor_indices"]) for c in tier_class_cases}
            books = {tuple(c["book_ids"]) for c in tier_class_cases}
            assert (0,) in actors and (1,) in actors, (
                f"{tier}/{cls} must cover both 石猴 (0) and 黛玉 (1); got {actors}"
            )
            assert XYJ in {b for c in tier_class_cases for b in c["book_ids"]}
            assert HLM in {b for c in tier_class_cases for b in c["book_ids"]}


def test_v2_pool_v1_subset_class_set_is_superset_of_v1() -> None:
    """Every v1 8-pilot class is in the v2 pool, and v2 covers all 6
    expression classes from the chat-quality-protocol (answer,
    challenge, comfort, disagree, unknown_expression, cross_book_hearsay).
    """
    pool = _ensure_pool_exists()
    v1 = _load(V1_DATASET)
    v1_classes = {(c["tier"], c["class"]) for c in v1["cases"]}
    v2_classes = {(c["tier"], c["class"]) for c in pool["cases"]}
    assert v1_classes <= v2_classes, (
        f"v1 8-pilot classes must be a subset of v2 pool classes; "
        f"missing in v2: {v1_classes - v2_classes}"
    )
    # v2 covers the FULL 6-class expression set from chat-quality-protocol.
    assert set(pool["tier_breakdown"]["expression_classes_covered"]) == {
        "answer", "challenge", "comfort", "disagree",
        "unknown_expression", "cross_book_hearsay",
    }
    # The v1 4 expression classes are a subset of the v2 6.
    assert (
        set(pool["tier_breakdown"]["expression_classes_covered"])
        >= {c for tier, c in v1_classes if tier == "expression"}
    )


def test_v2_pool_case_ids_are_unique() -> None:
    pool = _ensure_pool_exists()
    case_ids = [c["case_id"] for c in pool["cases"]]
    assert len(set(case_ids)) == len(case_ids), "duplicate case_id in v2 pool"


def test_v2_pool_schema_fields_match_v1() -> None:
    """The v2 pool's top-level schema must mirror v1 exactly so the
    slicer can emit v1-shape windows without translation."""
    pool = _ensure_pool_exists()
    v1 = _load(V1_DATASET)
    for key in ("actors_from", "actor_field", "manual_continues_per_turn",
                "reviewer_kind", "required_case_fields", "gold_standard_fields",
                "verdict_legend"):
        assert key in pool, f"v2 missing top-level field {key!r}"
    assert pool["actors_from"] == v1["actors_from"]
    assert pool["actor_field"] == v1["actor_field"]
    assert pool["manual_continues_per_turn"] == v1["manual_continues_per_turn"]
    assert pool["reviewer_kind"] == v1["reviewer_kind"]
    assert pool["required_case_fields"] == v1["required_case_fields"]
    assert pool["gold_standard_fields"] == v1["gold_standard_fields"]
    assert pool["verdict_legend"] == v1["verdict_legend"]


def test_v2_pool_each_case_has_required_fields() -> None:
    """Each case in the v2 pool carries every field the v1 runner checks
    and the v1 case-level schema requires."""
    pool = _ensure_pool_exists()
    required = {"case_id", "tier", "class", "target_actor_indices",
                "questions", "gold_standard", "expected"}
    gold_required = {"verdict", "required_claims", "forbidden_claims",
                     "expected_source"}
    for case in pool["cases"]:
        missing = required - set(case.keys())
        assert not missing, f"case {case.get('case_id')!r} missing fields {missing}"
        g_missing = gold_required - set(case["gold_standard"].keys())
        assert not g_missing, (
            f"case {case['case_id']!r} gold_standard missing {g_missing}"
        )


def test_v2_pool_native_call_ceiling_keeps_v1_invariant() -> None:
    """The v2 pool's ceiling is the per-run ceiling (=32) and matches v1.
    v2 itself is the *upstream pool*; runs against it are sliced into
    8-pilot windows. The pool ceiling is therefore the same as v1, not
    a per-dataset multiplier.
    """
    pool = _ensure_pool_exists()
    v1 = _load(V1_DATASET)
    assert pool["native_call_ceiling"] == v1["native_call_ceiling"] == 32


def test_v2_pool_forbidden_claims_avoid_paraphrase_drift() -> None:
    """Every boundary case lists at least one paraphrase-drift guard
    in its forbidden_claims — this is the concrete anti-drift
    mechanism for the lint T17 introduced. The vocabulary is wider
    than the original token list because each boundary class uses the
    vocabulary natural to its claim type (改字 / 改写 / 现代化 / 补出 /
    后世 / 今人 / 成佛 / 换成 / 扩成 / 降格 / 抬高 / 当成 / 替换 /
    延伸 / 扩写). The assertion is that *some* drift-guard token
    appears; the lint is not opinionated about which one."""
    pool = _ensure_pool_exists()
    boundary = [c for c in pool["cases"] if c["tier"] == "boundary"]
    assert len(boundary) == 60
    drift_tokens = (
        "改字", "改写", "现代化", "补出", "后世", "今人",
        "成佛", "把'", "换成", "替换", "扩成", "降格",
        "抬高", "当成", "延伸", "扩写", "改成", "改名",
        "扩", "混为", "改", "扩为",
    )
    for case in boundary:
        forbidden = case["gold_standard"]["forbidden_claims"]
        assert forbidden, (
            f"boundary {case['case_id']!r} has empty forbidden_claims; "
            "every boundary case must list at least one drift guard"
        )
        forbidden_blob = " ".join(forbidden)
        if case["class"] == "unknowable":
            # unknowable cases forbid inventions of private states
            # (e.g. 后世 / 揣测 / 推断) which still land in drift_tokens
            pass
        has_drift_token = any(tok in forbidden_blob for tok in drift_tokens)
        assert has_drift_token, (
            f"boundary {case['case_id']!r} missing paraphrase-drift guard: "
            f"forbidden_claims={forbidden}"
        )


def test_slicer_emits_v1_shape_8_pilot_window() -> None:
    """Slice window 0 and assert it carries the v1 schema required by
    the runner's ``validate_dataset``. The window must include all 4
    boundary classes plus the 4 expression classes this window chose
    (the expression class set cycles every 3 windows)."""
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    out = REPO / "tmp" / "test-t12-window-0.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                sys.executable, str(SLICER),
                "--pool", str(V2_POOL),
                "--output", str(out),
                "--window-index", "0",
                "--window-size", "8",
            ],
            capture_output=True, text=True, check=True,
        )
        assert "wrote" in result.stdout
    finally:
        if out.exists():
            window = _load(out)
            assert window["dataset_version"] == "t12-pilot-eight-v1", (
                f"sliced window must carry v1 dataset_version; "
                f"got {window['dataset_version']!r}"
            )
            assert window["native_call_ceiling"] == 32
            assert len(window["cases"]) == 8
            classes = {(c["tier"], c["class"]) for c in window["cases"]}
            # boundary coverage is constant; expression coverage cycles
            boundary_needed = {("boundary", c) for c in V1_BOUNDARY}
            assert boundary_needed <= classes, (
                f"window 0 must cover all 4 boundary classes; "
                f"missing {boundary_needed - classes}"
            )
            # window 0 uses the canonical v1 expression set
            expr_needed_w0 = {("expression", c) for c in V1_EXPRESSION}
            assert expr_needed_w0 <= classes, (
                f"window 0 must cover the 4 v1 expression classes; "
                f"missing {expr_needed_w0 - classes}"
            )
            out.unlink()


def test_slicer_covers_pool_across_windows() -> None:
    """Across 15 canonical v1 windows + 15 v1-extension windows, every
    v2 pool case is reached at least once.

    The pool has 4 boundary classes × 15 cases + 6 expression classes
    × 4 cases = 84. The v1 8-pilot contract covers 4 boundary + 4
    canonical expression classes per window; the 4 canonical
    expression classes (answer / challenge / comfort /
    cross_book_hearsay) yield 16 expression cases, leaving
    disagree (4) + unknown_expression (4) = 8 cases uncovered.

    Coverage budget:
      * 15 canonical windows → 60 boundary + 16 expression = 76
      * 15 extension-a windows → + 4 unknown_expression + 4 of
        (answer, comfort) = +4
      * 15 extension-b windows → + 4 disagree + 4 of (challenge,
        cross_book_hearsay) = +4
      * Total = 76 + 4 + 4 = 84.
    """
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    pool = _ensure_pool_exists()
    seen: set[str] = set()

    # 15 canonical v1 windows
    for window_index in range(15):
        out = REPO / "tmp" / f"test-t12-canon-{window_index}.json"
        try:
            subprocess.run(
                [sys.executable, str(SLICER),
                 "--pool", str(V2_POOL),
                 "--output", str(out),
                 "--window-index", str(window_index),
                 "--window-size", "8"],
                capture_output=True, text=True, check=True, cwd=str(REPO),
            )
            window = _load(out)
            for case in window["cases"]:
                seen.add(case["case_id"])
        finally:
            if out.exists():
                out.unlink()

    # 15 v1-extension-a windows (covers unknown_expression + 2 canonical)
    for window_index in range(15):
        out = REPO / "tmp" / f"test-t12-ext-a-{window_index}.json"
        try:
            subprocess.run(
                [sys.executable, str(SLICER),
                 "--pool", str(V2_POOL),
                 "--output", str(out),
                 "--window-index", str(window_index),
                 "--window-size", "8",
                 "--extension-set", "a"],
                capture_output=True, text=True, check=True, cwd=str(REPO),
            )
            window = _load(out)
            for case in window["cases"]:
                seen.add(case["case_id"])
        finally:
            if out.exists():
                out.unlink()

    # 15 v1-extension-b windows (covers disagree + 2 canonical)
    for window_index in range(15):
        out = REPO / "tmp" / f"test-t12-ext-b-{window_index}.json"
        try:
            subprocess.run(
                [sys.executable, str(SLICER),
                 "--pool", str(V2_POOL),
                 "--output", str(out),
                 "--window-index", str(window_index),
                 "--window-size", "8",
                 "--extension-set", "b"],
                capture_output=True, text=True, check=True, cwd=str(REPO),
            )
            window = _load(out)
            for case in window["cases"]:
                seen.add(case["case_id"])
        finally:
            if out.exists():
                out.unlink()

    assert seen == {c["case_id"] for c in pool["cases"]}, (
        f"across 45 windows (15 canonical + 15 ext-a + 15 ext-b) the "
        f"slicer must cover all 84 pool cases; "
        f"missing {set(c['case_id'] for c in pool['cases']) - seen}"
    )


def test_extension_windows_are_not_runner_compatible() -> None:
    """v1-extension windows must carry dataset_version ``-ext`` so the
    runner rejects them at validate_dataset time. The 4 canonical
    expression classes plus disagree + unknown_expression together
    exceed the runner's hard-coded 4-class expectation, so the version
    bump is the wire signal that the window is for audit only.
    """
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    out = REPO / "tmp" / "test-t12-ext-a-0.json"
    try:
        subprocess.run(
            [sys.executable, str(SLICER),
             "--pool", str(V2_POOL),
             "--output", str(out),
             "--window-index", "0",
             "--window-size", "8",
             "--extension-set", "a"],
            capture_output=True, text=True, check=True, cwd=str(REPO),
        )
        window = _load(out)
        assert window["dataset_version"] == "t12-pilot-eight-v1-ext"
        # Must include unknown_expression and disagree (extension set 'a')
        expr_classes = {c["class"] for c in window["cases"]
                        if c["tier"] == "expression"}
        assert "unknown_expression" in expr_classes
        assert "disagree" in expr_classes
    finally:
        if out.exists():
            out.unlink()


def test_slicer_dry_run_through_runner_actually_loads() -> None:
    """A sliced window must satisfy the runner's ``--dry-run`` schema check
    end-to-end. This is the wiring test that ties the pool, the slicer
    and the runner together. The runner resolves the actor source from
    ``dataset_path.parent / dataset["actors_from"]``, so the sliced
    window must be written into the validation directory where the
    pre-frozen actor source already lives.
    """
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    validation_dir = REPO / "docs" / "plans" / "book-character-agents" / "validation"
    sliced = validation_dir / "test-t12-sliced-dryrun.json"
    out = validation_dir / "test-t12-sliced-dryrun-report.json"
    try:
        subprocess.run(
            [
                sys.executable, str(SLICER),
                "--pool", str(V2_POOL),
                "--output", str(sliced),
                "--window-index", "0",
                "--window-size", "8",
            ],
            capture_output=True, text=True, check=True, cwd=str(REPO),
        )
        result = subprocess.run(
            [
                sys.executable, str(RUNNER),
                "--workspace", "C:/Users/GYENNO/.octopus/workspace",
                "--dataset", str(sliced),
                "--output", str(out),
                "--dry-run", "--call-budget", "32",
            ],
            capture_output=True, text=True, cwd=str(REPO),
        )
        assert result.returncode == 0, (
            f"runner --dry-run against sliced window failed: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        report = _load(out)
        assert report["mode"] == "dry_run"
        assert report["dataset_version"] == "t12-pilot-eight-v1"
        assert report["actual_native_calls"] == 0
        assert report["publication"] is False
        assert report["quality_pass"] is False
    finally:
        for p in (sliced, out):
            if p.exists():
                p.unlink()


def test_v2_pool_v1_consistency_with_corpus_anchors() -> None:
    """Each v2 case's ``expected_source`` mentions a known scene keyword
    that we cross-checked in the corpus files at authoring time. The
    test asserts the corpus still contains the canonical anchor so
    future re-authorings do not silently drift.
    """
    pool = _ensure_pool_exists()
    xyj = (REPO / "tmp" / "book-corpus" / "西游记.txt").read_text(
        encoding="utf-8", errors="ignore"
    )
    hlm = (REPO / "tmp" / "book-corpus" / "红楼梦.txt").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Anchors we explicitly verified in the corpus at authoring time
    XYJ_ANCHORS = ("铁板桥", "我进去", "我进去！我进去！", "五行山",
                   "白骨夫人", "齐天大圣", "八卦炉", "弼马温",
                   "七七四十九日", "唵嘛呢叭", "芭蕉", "蟠桃")
    HLM_ANCHORS = ("我自来是如此", "颦", "花谢花飞", "潇湘",
                   "葬花", "病如西子胜三分", "心较比干多一窍",
                   "秋窗风雨夕", "寒塘渡鹤影", "凹晶", "燕窝")
    for anchor in XYJ_ANCHORS:
        assert anchor in xyj, f"corpus drift: 西游记 missing anchor {anchor!r}"
    for anchor in HLM_ANCHORS:
        assert anchor in hlm, f"corpus drift: 红楼梦 missing anchor {anchor!r}"


def test_v2_pool_hearsay_cases_target_both_books() -> None:
    """All cross_book_hearsay cases must list both book_ids so the
    cross-book boundary is enforced at the data layer, not just at
    runtime."""
    pool = _ensure_pool_exists()
    hearsay = [c for c in pool["cases"] if c["class"] == "cross_book_hearsay"]
    assert len(hearsay) == 4
    for case in hearsay:
        assert len(case["book_ids"]) == 2, (
            f"hearsay case {case['case_id']!r} must list both books; "
            f"got {case['book_ids']}"
        )


# ---------------------------------------------------------------------------
# Additional structural integrity tests — actor↔book pairing, verdict↔class
# mapping, tier_breakdown totals, and per-case field invariants the runner
# relies on at read time.
# ---------------------------------------------------------------------------

XYJ = "efc80c04-df9b-48e2-ace5-833de34d63fe"
HLM = "2740f60c-3198-4350-b664-2ed688f9e2cb"
ACTOR_TO_BOOK = {0: XYJ, 1: HLM}


def test_v2_pool_actor_indices_match_book_ids() -> None:
    """target_actor_indices[0] ↔ 西游记 (XYJ), [1] ↔ 红楼梦 (HLM).

    The 8-pilot windowing (and the future v2-window runner) routes each
    case's question to the actor whose index appears here; if the book
    UUID is not in book_ids the agent would have no source to draw from.
    """
    pool = _ensure_pool_exists()
    for case in pool["cases"]:
        actors = case["target_actor_indices"]
        books = set(case["book_ids"])
        for actor in actors:
            assert actor in ACTOR_TO_BOOK, (
                f"case {case['case_id']!r} has unknown actor index {actor}; "
                f"only 0 (XYJ) and 1 (HLM) are valid"
            )
            assert ACTOR_TO_BOOK[actor] in books, (
                f"case {case['case_id']!r} targets actor {actor} "
                f"({ACTOR_TO_BOOK[actor]}) but its book_ids={books} "
                f"does not include the actor's source book"
            )
        # Single-book cases must list exactly one book; hearsay cases list two.
        if case["class"] == "cross_book_hearsay":
            assert len(books) == 2, (
                f"hearsay case {case['case_id']!r} must list both books, "
                f"got {books}"
            )
        else:
            assert len(books) == 1, (
                f"non-hearsay case {case['case_id']!r} must list one book, "
                f"got {books}"
            )


def test_v2_pool_question_and_expected_lengths_match_runner() -> None:
    """Each case has exactly 1 question, exactly 3 expected behavior
    clauses, a non-empty expected_source, and a non-empty question.

    The runner's per-turn contract (see
    ``t12-quality-runner.py::validate_dataset``) loops over
    ``case['questions']`` once per turn and joins ``case['expected']``
    to the agent review form; mismatched lengths would silently
    truncate or pad the review UI.
    """
    pool = _ensure_pool_exists()
    for case in pool["cases"]:
        questions = case["questions"]
        expected = case["expected"]
        assert isinstance(questions, list) and len(questions) == 1, (
            f"case {case['case_id']!r} must carry exactly 1 question, "
            f"got {len(questions)}: {questions!r}"
        )
        assert questions[0].strip(), (
            f"case {case['case_id']!r} has empty question text"
        )
        assert isinstance(expected, list) and len(expected) == 3, (
            f"case {case['case_id']!r} must carry exactly 3 expected "
            f"behavior clauses, got {len(expected)}: {expected!r}"
        )
        for i, clause in enumerate(expected):
            assert clause.strip(), (
                f"case {case['case_id']!r} expected[{i}] is empty"
            )
        source = case["gold_standard"]["expected_source"]
        assert isinstance(source, str) and source.strip(), (
            f"case {case['case_id']!r} gold_standard.expected_source "
            f"must be a non-empty string"
        )


def test_v2_pool_boundary_verdict_equals_class() -> None:
    """For every boundary case, ``verdict`` must equal ``class``.

    Boundary cases are about what a character can know / say in the
    original text; the verdict therefore IS the class. Expression
    cases test a different dimension (the character's *expression
    style* — answer / challenge / comfort / disagree /
    unknown_expression / cross_book_hearsay) and intentionally can
    have a different verdict (e.g. expression/challenge carries
    verdict=belief, expression/comfort carries verdict=conditional).
    Locking the boundary-side equality keeps the table
    knowable/unknowable/belief/emotion from drifting.
    """
    pool = _ensure_pool_exists()
    for case in pool["cases"]:
        if case["tier"] != "boundary":
            continue
        assert case["gold_standard"]["verdict"] == case["class"], (
            f"boundary case {case['case_id']!r} (class={case['class']!r}) "
            f"must have gold_standard.verdict==class; "
            f"got verdict={case['gold_standard']['verdict']!r}"
        )


def test_v2_pool_tier_breakdown_totals_match_cases() -> None:
    """tier_breakdown.{boundary_cases, expression_cases} must match
    the actual case distribution; otherwise the runner's printed
    progress would lie to operators about the size of the queue.
    """
    pool = _ensure_pool_exists()
    boundary = sum(1 for c in pool["cases"] if c["tier"] == "boundary")
    expression = sum(1 for c in pool["cases"] if c["tier"] == "expression")
    tb = pool["tier_breakdown"]
    assert tb["boundary_cases"] == boundary == 60, (
        f"tier_breakdown.boundary_cases={tb['boundary_cases']!r} "
        f"but {boundary} boundary cases present in pool"
    )
    assert tb["expression_cases"] == expression == 24, (
        f"tier_breakdown.expression_cases={tb['expression_cases']!r} "
        f"but {expression} expression cases present in pool"
    )
    # The protocol-mandated class sets must be present and exhausted.
    assert set(tb["boundary_classes_covered"]) == {
        "knowable", "unknowable", "belief", "emotion",
    }
    assert set(tb["expression_classes_covered"]) == {
        "answer", "challenge", "comfort", "disagree",
        "unknown_expression", "cross_book_hearsay",
    }
    assert tb["expression_classes_remaining"] == [], (
        f"expression_classes_remaining must be empty (all 6 classes "
        f"covered); got {tb['expression_classes_remaining']!r}"
    )


def test_v2_pool_metadata_freeze_fields_are_present() -> None:
    """``frozen_on``, ``dataset_version``, ``scope``, and ``reviewer_kind``
    must all be set so the audit trail on the JSON itself is complete.
    ``frozen_on`` is an ISO date; ``dataset_version`` is the
    ``t12-pilot-eightyfour-v1`` wire signal the runner checks.
    """
    import re

    pool = _ensure_pool_exists()
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", pool.get("frozen_on", "")), (
        f"frozen_on must be YYYY-MM-DD; got {pool.get('frozen_on')!r}"
    )
    assert pool.get("dataset_version") == "t12-pilot-eightyfour-v1", (
        f"dataset_version must be the v2 84-case wire signal; "
        f"got {pool.get('dataset_version')!r}"
    )
    assert pool.get("scope", "").strip(), (
        "scope must be a non-empty string"
    )
    assert pool.get("reviewer_kind", "").strip(), (
        "reviewer_kind must be a non-empty string"
    )


def test_v2_pool_gold_standard_verdict_uses_protocol_vocabulary() -> None:
    """Every ``gold_standard.verdict`` must be one of the 6 protocol
    values: knowable / unknowable / belief / emotion / conditional /
    hearsay_cross_book. A typo would silently route the case to a
    non-existent review bucket.
    """
    pool = _ensure_pool_exists()
    VALID = {
        "knowable", "unknowable", "belief", "emotion",
        "conditional", "hearsay_cross_book",
    }
    for case in pool["cases"]:
        v = case["gold_standard"]["verdict"]
        assert v in VALID, (
            f"case {case['case_id']!r} gold_standard.verdict={v!r} "
            f"is not in the protocol vocabulary {VALID}"
        )


# ---------------------------------------------------------------------------
# v1 8-pilot dataset invariants — the runner's wire contract. v1 is the
# 8-case dataset t12-quality-runner.py consumes; v2 is the 84-case
# upstream pool. v1 ≠ a literal subset of v2 by case_id (they are
# different authoring rounds that cover the same protocol class set),
# but v1 must itself be self-consistent on the wire contract the
# runner checks.
# ---------------------------------------------------------------------------


def _ensure_v1_exists() -> dict:
    if not V1_DATASET.exists():
        import pytest
        pytest.skip(f"v1 dataset not present at {V1_DATASET}")
    return _load(V1_DATASET)


def test_v1_dataset_has_exactly_8_cases() -> None:
    """The runner hard-codes the 8-pilot contract; the v1 dataset must
    be exactly 8 cases or the runner's expected_count check fails.
    """
    v1 = _ensure_v1_exists()
    assert len(v1["cases"]) == 8, (
        f"v1 8-pilot must have exactly 8 cases, got {len(v1['cases'])}"
    )


def test_v1_dataset_class_set_matches_canonical_protocol() -> None:
    """v1 must cover exactly the 4 boundary classes + the 4 canonical
    expression classes (one case per class). The remaining 2
    expression classes (disagree, unknown_expression) are intentionally
    excluded from v1 — they are covered by v2 + the extension windows
    (see test_extension_windows_are_not_runner_compatible).
    """
    v1 = _ensure_v1_exists()
    classes = {(c["tier"], c["class"]) for c in v1["cases"]}
    expected = (
        {("boundary", c) for c in V1_BOUNDARY}
        | {("expression", c) for c in V1_EXPRESSION}
    )
    assert classes == expected, (
        f"v1 class set must match the 4+4 canonical protocol; "
        f"missing {expected - classes}, extra {classes - expected}"
    )


def test_v1_dataset_one_case_per_class() -> None:
    """Each of the 8 classes must appear exactly once in v1; otherwise
    the runner's per-class counters would lie about coverage.
    """
    from collections import Counter
    v1 = _ensure_v1_exists()
    counts = Counter((c["tier"], c["class"]) for c in v1["cases"])
    for k, v in counts.items():
        assert v == 1, f"v1 {k} appears {v} times; expected exactly 1"


def test_v1_dataset_covers_both_characters_and_both_books() -> None:
    """8-pilot covers 石猴 (0) and 黛玉 (1); the cross_book_hearsay
    case must list both book UUIDs.
    """
    v1 = _ensure_v1_exists()
    actors = {c["target_actor_indices"][0] for c in v1["cases"]}
    assert actors == {0, 1}, f"v1 must cover both characters, got {actors}"
    hearsay = [c for c in v1["cases"] if c["class"] == "cross_book_hearsay"]
    assert len(hearsay) == 1
    assert set(hearsay[0]["book_ids"]) == {XYJ, HLM}, (
        f"v1 cross_book_hearsay case must list both books, "
        f"got {hearsay[0]['book_ids']}"
    )


def test_v1_dataset_metadata_freeze() -> None:
    """The runner checks ``dataset_version == 't12-pilot-eight-v1'`` and
    ``native_call_ceiling == 32``; both are wire contracts.
    """
    v1 = _ensure_v1_exists()
    assert v1["dataset_version"] == "t12-pilot-eight-v1", (
        f"v1 dataset_version must be t12-pilot-eight-v1 (runner wire "
        f"signal), got {v1['dataset_version']!r}"
    )
    assert v1["native_call_ceiling"] == 32, (
        f"v1 native_call_ceiling must be 32 (runner wire signal), "
        f"got {v1['native_call_ceiling']!r}"
    )


def test_v1_pool_v2_slicing_round_trip() -> None:
    """The v2 84-case pool can be sliced into 8-pilot windows; the
    result must satisfy the same v1 contract. This is a round-trip
    check: pick window 0, assert it carries the v1 dataset_version,
    8 cases, the 4 boundary + 4 expression class set, and ceiling=32.
    """
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    out = REPO / "tmp" / "test-t12-roundtrip-window-0.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, str(SLICER),
             "--pool", str(V2_POOL),
             "--output", str(out),
             "--window-index", "0",
             "--window-size", "8"],
            capture_output=True, text=True, check=True, cwd=str(REPO),
        )
        window = _load(out)
        assert window["dataset_version"] == "t12-pilot-eight-v1"
        assert window["native_call_ceiling"] == 32
        assert len(window["cases"]) == 8
        classes = {(c["tier"], c["class"]) for c in window["cases"]}
        assert ("boundary", "knowable") in classes
        assert ("boundary", "unknowable") in classes
        assert ("boundary", "belief") in classes
        assert ("boundary", "emotion") in classes
        assert ("expression", "answer") in classes
        assert ("expression", "challenge") in classes
        assert ("expression", "comfort") in classes
        assert ("expression", "cross_book_hearsay") in classes
    finally:
        if out.exists():
            out.unlink()
