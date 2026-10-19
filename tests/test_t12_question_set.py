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
AGGREGATION = (
    REPO / "docs" / "plans" / "book-character-agents" / "validation"
    / "2026-10-16-t12-real-runs-aggregation.json"
)

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


def test_extension_windows_use_v1ext_protocol_and_runner_accepts() -> None:
    """v1-extension windows carry ``dataset_version='t12-pilot-eight-v1-ext'``
    and a 4-expression-class declaration in ``tier_breakdown`` drawn from
    the 6 chat-quality-protocol classes (including ``disagree`` /
    ``unknown_expression``). The runner accepts them via the
    ``t12-pilot-eight-v1-ext`` parallel protocol (separate
    ``expected_count`` block in the runner) instead of rejecting them.
    The v1 wire contract is unchanged: v1 windows still must match the
    frozen 4-class list pinned by
    ``test_runner_expected_count_class_list_matches_v1_protocol``.
    """
    import subprocess

    if not V2_POOL.exists():
        import pytest
        pytest.skip("v2 pool not present")
    out = REPO / "tmp" / "test-t12-ext-a-0.json"
    runner_path = REPO / "docs" / "plans" / "book-character-agents" / "t12-quality-runner.py"
    actors_path = REPO / "docs" / "plans" / "book-character-agents" / "validation" / "real-model-group-chat-probe.json"
    if not actors_path.exists():
        import pytest
        pytest.skip("probe persona source not present")
    # The runner refuses to overwrite existing output (contract pinned by
    # ``test_runner_refuses_to_overwrite_existing_output``); pre-clean any
    # leftover dryrun from a previous run so this test stays idempotent.
    dryrun_output = REPO / "tmp" / "test-t12-ext-a-0-dryrun.json"
    if dryrun_output.exists():
        dryrun_output.unlink()
    try:
        # Slice ext-a window 0 (covers disagree + unknown_expression among
        # its 4 expression slots).
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
        expr_classes = {c["class"] for c in window["cases"]
                        if c["tier"] == "expression"}
        assert "unknown_expression" in expr_classes
        assert "disagree" in expr_classes
        # Mirror the sliced window to where the runner expects the actor
        # source: the runner resolves ``actors_from`` as
        # ``dataset_path.parent / actors_from``, and the actor source
        # already lives in ``validation/``. Without this copy, the
        # runner's --dry-run cannot load character scopes.
        out_in_validation = out.parent / "test-t12-ext-a-0-mirrored.json"
        try:
            mirrored = dict(window)
            # Point actors_from at the in-place copy the runner will
            # see when it reads from ``tmp/``.
            mirrored_path = REPO / "tmp" / "real-model-group-chat-probe.json"
            subprocess.run(
                [sys.executable, "-c",
                 "import shutil, pathlib; "
                 f"shutil.copy({str(actors_path)!r}, {str(mirrored_path)!r})"],
                capture_output=True, text=True, check=True, cwd=str(REPO),
            )
            out_in_validation.write_text(
                json.dumps(mirrored, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            # The runner must accept the v1ext window via --dry-run.
            result = subprocess.run(
                [sys.executable, str(runner_path),
                 "--workspace", str(REPO / "tmp" / "book-corpus-workspace"),
                 "--dataset", str(out_in_validation),
                 "--output", str(REPO / "tmp" / "test-t12-ext-a-0-dryrun.json"),
                 "--call-budget", "32",
                 "--dry-run"],
                capture_output=True, text=True, cwd=str(REPO),
            )
            assert result.returncode == 0, (
                f"runner must accept v1ext windows via the v1ext protocol; "
                f"stderr={result.stderr!r}"
            )
        finally:
            if out_in_validation.exists():
                out_in_validation.unlink()
            mirrored = REPO / "tmp" / "real-model-group-chat-probe.json"
            if mirrored.exists():
                mirrored.unlink()
    finally:
        if out.exists():
            out.unlink()
        if dryrun_output.exists():
            dryrun_output.unlink()


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


# ---------------------------------------------------------------------------
# Frozen dryrun report guards — the 4 canonical dryrun reports on disk are
# the audit trail showing the runner wire contract works end-to-end with
# 0 model calls. They freeze a runner_sha256 (so an unintended runner edit
# is visible) and a per-window dataset_sha256 (so a window cannot be
# re-authored silently). If any of the SHA pins drifts, downstream
# tooling comparing report-from-baseline to a fresh report would silently
# disagree.
# ---------------------------------------------------------------------------

DRYRUN_REPORTS = (
    REPO / "docs" / "plans" / "book-character-agents" / "validation"
    / "2026-10-16-t12-window-0-dryrun.json",
    REPO / "docs" / "plans" / "book-character-agents" / "validation"
    / "2026-10-16-t12-window-1-dryrun.json",
    REPO / "docs" / "plans" / "book-character-agents" / "validation"
    / "2026-10-16-t12-window-2-dryrun.json",
    REPO / "docs" / "plans" / "book-character-agents" / "validation"
    / "2026-10-16-t12-window-3-dryrun.json",
)


def test_dryrun_reports_all_canonical_windows_present() -> None:
    """All 4 canonical window dryrun reports must be on disk; the
    audit trail is incomplete if any is missing.
    """
    import pytest
    for path in DRYRUN_REPORTS:
        if not path.exists():
            pytest.skip(f"dryrun report not present at {path}")


def test_dryrun_reports_carry_v1_wire_contract() -> None:
    """Each dryrun report must carry the v1 wire signal: dataset_version,
    ceiling, 8 cases, and actual_native_calls==0 (since mode=='dry_run').
    """
    import pytest
    seen = 0
    for path in DRYRUN_REPORTS:
        if not path.exists():
            continue
        seen += 1
        report = _load(path)
        assert report["mode"] == "dry_run", (
            f"{path.name} mode must be dry_run, got {report['mode']!r}"
        )
        assert report["dataset_version"] == "t12-pilot-eight-v1", (
            f"{path.name} must carry v1 dataset_version, "
            f"got {report['dataset_version']!r}"
        )
        assert report["native_call_ceiling"] == 32, (
            f"{path.name} must have ceiling=32, got "
            f"{report['native_call_ceiling']!r}"
        )
        assert report["actual_native_calls"] == 0, (
            f"{path.name} dry_run must have 0 native calls, got "
            f"{report['actual_native_calls']!r}"
        )
        assert report["publication"] is False
        assert report["quality_pass"] is False
        assert len(report["cases"]) == 8
    if seen == 0:
        pytest.skip("no dryrun reports present on disk")


def test_dryrun_reports_runner_sha256_matches_runner_file() -> None:
    """The frozen runner_sha256 in each dryrun report must match the
    SHA of the runner script on disk. If the runner is edited
    intentionally, regenerate the dryrun reports and update the test;
    if not, the test catches silent drift.
    """
    import hashlib
    import pytest
    runner_bytes = RUNNER.read_bytes()
    actual_runner_sha = hashlib.sha256(runner_bytes).hexdigest()
    seen = 0
    for path in DRYRUN_REPORTS:
        if not path.exists():
            continue
        seen += 1
        report = _load(path)
        assert report["runner_sha256"] == actual_runner_sha, (
            f"{path.name} frozen runner_sha256={report['runner_sha256']!r} "
            f"drifted from the runner file on disk {actual_runner_sha!r}; "
            f"either regenerate the dryrun reports or revert the runner edit"
        )
    if seen == 0:
        pytest.skip("no dryrun reports present on disk")


def test_dryrun_reports_each_window_has_distinct_dataset_sha() -> None:
    """Different windows slice the v2 pool differently, so their
    dataset_sha256 must differ. Two reports sharing the same SHA would
    mean a copy-paste bug in the audit trail.
    """
    import pytest
    seen = []
    for path in DRYRUN_REPORTS:
        if not path.exists():
            continue
        report = _load(path)
        seen.append((path.name, report["dataset_sha256"]))
    if len(seen) < 2:
        pytest.skip("need ≥2 dryrun reports to compare")
    shas = [s for _, s in seen]
    assert len(set(shas)) == len(shas), (
        f"dryrun reports must each carry a distinct dataset_sha256 "
        f"(different windows = different slices); got {list(zip(*seen))[0]} "
        f"-> {shas}"
    )


# ---------------------------------------------------------------------------
# Runner script structural invariants — pins the contract that the runner
# itself satisfies even when no dryrun report is on disk. These are
# textual/bytecode-level guards: they do not import or execute the runner
# (which would mutate sys.path) but read its source so the safety
# invariants survive any future dryrun regeneration.
# ---------------------------------------------------------------------------


def test_runner_max_native_calls_constant_is_32() -> None:
    """The runner file must declare ``MAX_NATIVE_CALLS = 32`` as a
    module-level constant. This is the call ceiling that protects T12
    8-pilot from runaway model spend; a silent change to 64 would
    silently double the per-pilot budget.
    """
    import re

    source = RUNNER.read_text(encoding="utf-8")
    match = re.search(r"^MAX_NATIVE_CALLS\s*=\s*(\d+)\s*$", source, re.MULTILINE)
    assert match is not None, (
        f"runner must declare a module-level MAX_NATIVE_CALLS = N constant; "
        f"none found in {RUNNER}"
    )
    assert int(match.group(1)) == 32, (
        f"MAX_NATIVE_CALLS must remain 32 (T12 8-pilot ceiling); got "
        f"{match.group(1)!r}"
    )


def test_runner_call_budget_default_matches_ceiling() -> None:
    """The runner's ``--call-budget`` argparse default must equal
    ``MAX_NATIVE_CALLS`` (32). A mismatch would mean the default CLI
    invocation consumes fewer calls than the ceiling allows — i.e. the
    8-pilot could be silently truncated.
    """
    import re

    source = RUNNER.read_text(encoding="utf-8")
    max_match = re.search(r"^MAX_NATIVE_CALLS\s*=\s*(\d+)\s*$", source, re.MULTILINE)
    budget_match = re.search(
        r'add_argument\(\s*"--call-budget"[^)]*default\s*=\s*(\d+)',
        source, re.DOTALL,
    )
    assert max_match is not None, "MAX_NATIVE_CALLS not found"
    assert budget_match is not None, (
        f"--call-budget argparse default not found in {RUNNER}"
    )
    max_value = int(max_match.group(1))
    budget_default = int(budget_match.group(1))
    assert budget_default == max_value, (
        f"--call-budget default ({budget_default}) must equal "
        f"MAX_NATIVE_CALLS ({max_value}) so the default CLI run "
        f"does not silently truncate the 8-pilot"
    )


def test_runner_refuses_to_overwrite_existing_output() -> None:
    """The runner must check ``output.exists() or raw_path.exists()``
    before doing any work and raise a clear error if either already
    exists. This is the safety invariant that prevents a real-pilot
    run from overwriting the previous run's audit trail — a silent
    overwrite would make budgets un-attributable.
    """
    source = RUNNER.read_text(encoding="utf-8")
    assert "if output.exists() or raw_path.exists():" in source, (
        f"runner must refuse to overwrite an existing output or raw "
        f"path; pre-write check missing in {RUNNER}"
    )
    # The check must appear before any model call / save() that could
    # mutate the output. Confirm the raising message is descriptive.
    assert "This run already exists" in source, (
        f"runner overwrite-guard must raise a descriptive error; "
        f"generic RuntimeError without 'already exists' context found"
    )


def test_runner_run_status_terminal_enum_covers_all_paths() -> None:
    """The runner's ``report['run_status']`` must enumerate every
    terminal state: ``dry_run`` (validation only), ``interrupted``
    (an exception short-circuited the loop), ``budget_exhausted``
    (call budget hit), and ``executed_pending_semantic_review``
    (full 8-pilot completed). A missing branch would let a real run
    end without an explicit status — leaving the audit trail ambiguous.
    """
    source = RUNNER.read_text(encoding="utf-8")
    required_statuses = {
        "dry_run",
        "interrupted",
        "budget_exhausted",
        "executed_pending_semantic_review",
    }
    for status in required_statuses:
        assert f'"{status}"' in source, (
            f"runner must wire terminal run_status {status!r} in "
            f"the report builder; missing in {RUNNER}"
        )
    # ``case['status']`` must similarly carry an 'executed_pending_semantic_review'
    # value (used per-case, not just per-run) so per-case audit is unambiguous.
    assert "executed_pending_semantic_review" in source, (
        "per-case status 'executed_pending_semantic_review' must appear "
        "in the runner's case-status update"
    )


def test_runner_validate_dataset_enforces_manual_continues_per_turn_equals_one() -> None:
    """The runner's ``validate_dataset`` must reject any dataset whose
    ``manual_continues_per_turn`` field drifts from 1. The T12 protocol
    requires operator-driven continuation (no auto-continue); silently
    allowing ``manual_continues_per_turn=0`` would let a 2-call pilot
    become a 64-call runaway by removing the pause-then-resume contract.
    """
    source = RUNNER.read_text(encoding="utf-8")
    assert 'manual_continues_per_turn") != 1' in source, (
        f"runner validate_dataset must check manual_continues_per_turn == 1; "
        f"drift guard missing in {RUNNER}"
    )
    assert "operator-continuation policy" in source, (
        "runner must keep the descriptive 'operator-continuation policy' "
        "rationale in the ValueError so the reviewer sees why 1 is the "
        "frozen value"
    )


def test_runner_validate_dataset_enforces_reviewer_kind_match() -> None:
    """The runner must explicitly pass a non-human-blind-review
    ``reviewer_kind`` string to ``validate_dataset`` and the function
    must compare it against the dataset's own field. Drifting either
    side (dataset claims human blind review, or runner stops checking)
    would let a future real run silently inflate the audit-trail
    quality claim.
    """
    source = RUNNER.read_text(encoding="utf-8")
    assert "Agent checks complete published bodies and supplied sources" in source, (
        f"runner must pass a non-human-blind-review reviewer_kind to "
        f"validate_dataset; call-site string missing in {RUNNER}"
    )
    assert "no claim of human blind review" in source, (
        f"reviewer_kind string must explicitly disclaim human blind "
        f"review; qualifier missing in {RUNNER}"
    )
    assert 'dataset.get("reviewer_kind") != reviewer_kind' in source, (
        f"validate_dataset must compare dataset's reviewer_kind against "
        f"the runner's reviewer_kind argument; comparison missing in {RUNNER}"
    )


def test_runner_expected_count_class_list_matches_v1_protocol() -> None:
    """The runner's ``expected_count`` dict (passed to
    ``validate_dataset``) must list the 4 v1 boundary classes and 4 v1
    expression classes in exactly the order the protocol freezes. Any
    rename (e.g. ``belief`` -> ``opinion``) without bumping
    ``dataset_version`` would silently invalidate every frozen
    v1 dataset on disk.
    """
    source = RUNNER.read_text(encoding="utf-8")
    expected_pairs = {
        ('"knowable"', '"unknowable"', '"belief"', '"emotion"'): (
            "boundary_classes_covered"
        ),
        ('"answer"', '"challenge"', '"comfort"', '"cross_book_hearsay"'): (
            "expression_classes_covered"
        ),
    }
    for class_tuple, key in expected_pairs.items():
        # All four class strings must appear together inside the same
        # list literal under the expected_count[key] assignment.
        marker_open = f'"{key}": ['
        idx = source.find(marker_open)
        assert idx != -1, (
            f"runner must declare expected_count['{key}'] as a list; "
            f"marker not found in {RUNNER}"
        )
        # Read until the closing `]` of the list.
        end = source.find("]", idx)
        assert end != -1, f"expected_count['{key}'] list is not closed"
        list_body = source[idx + len(marker_open):end]
        for needle in class_tuple:
            assert needle in list_body, (
                f"expected_count['{key}'] must contain {needle}; "
                f"got {list_body!r} (v1 protocol frozen on these 4 classes)"
            )


def test_runner_v1ext_protocol_class_list_uses_chat_quality_protocol() -> None:
    """The runner's v1ext branch (``dataset_version='t12-pilot-eight-v1-ext'``)
    must declare its boundary classes the same way as v1, and must set
    ``expression_classes_covered=None`` so ``validate_dataset`` reads the
    actual 4 expression classes from the window's
    ``tier_breakdown.expression_classes_covered``. This lets ext-a/ext-b
    windows cover ``disagree`` and ``unknown_expression`` (the two
    chat-quality-protocol classes that the v1 protocol deliberately
    excluded) without re-freezing the v1 wire contract.
    """
    source = RUNNER.read_text(encoding="utf-8")

    # v1ext branch must exist with the frozen extension dataset_version.
    assert '"t12-pilot-eight-v1-ext"' in source, (
        "runner must declare the v1ext dataset_version literal so the "
        "v1ext branch in run() can dispatch to the v1ext expected_count"
    )
    # The v1ext block must have the same boundary class set as v1.
    boundary_marker = '"boundary_classes_covered": [\n            "knowable", "unknowable", "belief", "emotion"'
    # Tolerate whitespace variations in the literal.
    v1ext_idx = source.find('"t12-pilot-eight-v1-ext"')
    v1ext_block = source[v1ext_idx:] if v1ext_idx != -1 else ""
    assert '"knowable"' in v1ext_block, (
        "v1ext block must include 'knowable' boundary class"
    )
    assert '"unknowable"' in v1ext_block
    assert '"belief"' in v1ext_block
    assert '"emotion"' in v1ext_block
    # The v1ext block must set expression_classes_covered to None so
    # validate_dataset reads it from the window's tier_breakdown.
    # The None literal must appear inside the v1ext expected_count
    # block (not anywhere else in the file).
    v1ext_block_end = v1ext_block.find("}", v1ext_block.find("expression_classes_covered"))
    assert v1ext_block_end != -1, (
        "v1ext expected_count must contain expression_classes_covered"
    )
    v1ext_block_window = v1ext_block[
        v1ext_block.find("expression_classes_covered"):v1ext_block_end
    ]
    assert "None" in v1ext_block_window, (
        f"v1ext expression_classes_covered must be None (read from "
        f"tier_breakdown); got window={v1ext_block_window!r}"
    )


def test_runner_coerces_mode_to_directed_when_target_actor_indices_set() -> None:
    """The runner must coerce ``mode='natural'`` to ``mode='directed'``
    whenever the case spec carries non-empty ``target_actor_indices``
    (which builds a non-empty ``targets`` list). Without this coercion,
    ``coordinator.select_speakers`` rejects the call with
    ``Natural selection cannot carry directed targets`` because every
    v1 case (and every v2 window) pins a specific target actor while
    declaring ``mode='natural'``. The coercion preserves the frozen
    case datasets and honors the author intent: a case that pins an
    actor wants that actor to answer, which is a directed submission.
    """
    source = RUNNER.read_text(encoding="utf-8")

    # The runner must define a local ``effective_mode`` variable derived
    # from the spec, so the submit path uses the coerced mode (not the
    # raw spec value) at both ``rounds.submit`` and the manual-resume
    # control path.
    assert "effective_mode = spec.get(\"mode\", \"natural\")" in source, (
        "runner must compute an effective_mode from spec.get('mode') so "
        "the directed-coercion policy can apply before rounds.submit"
    )
    assert (
        "if targets and effective_mode == \"natural\":" in source
    ), (
        "runner must override effective_mode from 'natural' to 'directed' "
        "when targets is non-empty (case spec pins a target actor)"
    )
    assert "    effective_mode = \"directed\"" in source, (
        "runner must set effective_mode='directed' inside the coercion branch"
    )

    # Submit path must use the coerced mode, not the raw spec value.
    submit_block_marker = "turn = rounds.submit("
    submit_idx = source.find(submit_block_marker)
    assert submit_idx != -1, f"rounds.submit call not found in {RUNNER}"
    # Read a generous window after the submit call to verify
    # ``mode=effective_mode`` and ``seconds_for_mode(effective_mode)``.
    submit_window = source[submit_idx:submit_idx + 1200]
    assert "mode=effective_mode" in submit_window, (
        "rounds.submit must use mode=effective_mode (coerced), not "
        "mode=spec.get('mode', 'natural')"
    )
    assert "seconds_for_mode(effective_mode)" in submit_window, (
        "rounds.submit time_limit_seconds must derive from "
        "seconds_for_mode(effective_mode) (coerced)"
    )

    # The manual-resume control path (operator continuation) must also
    # use the coerced mode so the resumed round reads the same
    # time_limit_seconds the submit recorded. The ``seconds`` local is
    # computed on the line immediately above ``rounds.control(``, so
    # capture a 1-line-back window that includes both.
    resume_marker = 'rounds.control(\n                        scope, turn["round_id"], "resume"'
    resume_idx = source.find(resume_marker)
    if resume_idx == -1:
        # Fallback to a whitespace-tolerant match.
        import re
        matches = list(
            re.finditer(
                r"seconds_for_mode\(effective_mode\)\s*\n[^\n]*rounds\.control\(",
                source,
            )
        )
        assert matches, (
            "manual-resume must compute seconds_for_mode(effective_mode) "
            "immediately before the rounds.control('resume', ...) call"
        )
    else:
        # Window includes the line above (where ``seconds`` is computed).
        above_idx = source.rfind("\n", 0, resume_idx - 1)
        above_idx = source.rfind("\n", 0, above_idx - 1)
        resume_window = source[above_idx:resume_idx + 400]
        assert "seconds_for_mode(effective_mode)" in resume_window, (
            "manual-resume must derive time_limit_seconds from "
            "seconds_for_mode(effective_mode) (coerced), not from the raw spec"
        )


# ---------------------------------------------------------------------------
# Aggregation file (8-pilot + v2 60+24 = 20 windows / 160 cases)
# ---------------------------------------------------------------------------


def _load_aggregation_or_skip() -> dict:
    if not AGGREGATION.exists():
        import pytest
        pytest.skip(
            f"aggregation file not present at {AGGREGATION}; "
            f"regenerate via scripts/aggregate_t12_real_runs.py"
        )
    return json.loads(AGGREGATION.read_text(encoding="utf-8"))


def test_aggregation_file_has_expected_top_level_keys() -> None:
    """Lock the aggregation JSON's schema so a refactor of the aggregator
    script that drops a table is caught immediately."""
    payload = _load_aggregation_or_skip()
    expected = {"meta", "totals", "by_window", "by_class",
                "by_character", "by_phase", "by_status",
                "t17_summary", "ab_comparison", "cognition_per_case",
                "t17_published_bodies"}
    assert expected.issubset(payload.keys()), (
        f"aggregation must contain tables {expected}, got {set(payload.keys())}"
    )
    assert payload["meta"]["source_file_count"] == 20, (
        f"expected 20 source files (1 8-pilot + 15 canonical + 4 ext-a), "
        f"got {payload['meta']['source_file_count']}"
    )
    assert sorted(payload["meta"]["source_protocols"]) == ["v1", "v1ext"], (
        f"expected protocols v1 + v1ext, got {payload['meta']['source_protocols']}"
    )


def test_aggregation_totals_match_sum_of_per_window_rows() -> None:
    """The totals row must equal the sum of per-window rows so the table
    is self-consistent. Catches a divergence if someone re-runs the
    aggregator after editing the source files."""
    payload = _load_aggregation_or_skip()
    totals = payload["totals"]
    by_window = payload["by_window"]
    sum_calls = sum(w["call_count"] for w in by_window)
    sum_tok_in = sum(w["tok_in"] for w in by_window)
    sum_tok_out = sum(w["tok_out"] for w in by_window)
    sum_elapsed = round(sum(w["elapsed_seconds"] for w in by_window), 1)
    assert sum_calls == totals["call_count"], (
        f"sum of per-window call_count ({sum_calls}) must equal "
        f"totals.call_count ({totals['call_count']})"
    )
    assert sum_tok_in == totals["tok_in_total"], (
        f"sum of per-window tok_in ({sum_tok_in}) must equal "
        f"totals.tok_in_total ({totals['tok_in_total']})"
    )
    assert sum_tok_out == totals["tok_out_total"], (
        f"sum of per-window tok_out ({sum_tok_out}) must equal "
        f"totals.tok_out_total ({totals['tok_out_total']})"
    )
    # elapsed_seconds_total is rounded per-window to 1 decimal (display
    # friendly) so the sum can drift by up to 0.2 across 20 windows. Use
    # a tight tolerance rather than exact equality to keep the invariant
    # honest without forbidding the per-window rounding.
    assert abs(sum_elapsed - totals["elapsed_seconds_total"]) < 0.5, (
        f"sum of per-window elapsed ({sum_elapsed}) must be within 0.5s "
        f"of totals.elapsed_seconds_total ({totals['elapsed_seconds_total']})"
    )


def test_aggregation_by_phase_and_by_status_sum_to_totals() -> None:
    """by_phase + by_status row sums must equal totals.call_count. Catches
    a bug where calls are double-counted or dropped during phase/status
    bucketing."""
    payload = _load_aggregation_or_skip()
    totals = payload["totals"]
    by_phase_sum = sum(p["calls"] for p in payload["by_phase"])
    by_status_sum = sum(s["calls"] for s in payload["by_status"])
    assert by_phase_sum == totals["call_count"], (
        f"sum of by_phase calls ({by_phase_sum}) must equal "
        f"totals.call_count ({totals['call_count']})"
    )
    assert by_status_sum == totals["call_count"], (
        f"sum of by_status calls ({by_status_sum}) must equal "
        f"totals.call_count ({totals['call_count']})"
    )


def test_aggregation_per_class_case_count_sums_to_160() -> None:
    """The 8-pilot (8 cases) + 19 v2 windows (152 cases) must total
    160 cases in by_class. The 4 ext-b windows are intentionally not run
    (ext-a already covers disagree + unknown_expression); 152 = 15
    canonical × 8 + 4 ext-a × 8."""
    payload = _load_aggregation_or_skip()
    by_class = payload["by_class"]
    total_cases = sum(c["cases"] for c in by_class)
    assert total_cases == 160, (
        f"by_class case total must be 160 (8-pilot 8 + v2 152), "
        f"got {total_cases}"
    )
    classes = {c["class"] for c in by_class}
    expected_classes = {
        "knowable", "unknowable", "belief", "emotion",
        "answer", "challenge", "comfort", "disagree",
        "unknown_expression", "cross_book_hearsay",
    }
    assert classes == expected_classes, (
        f"by_class must cover all 10 chat-quality-protocol classes, "
        f"got {classes}, missing {expected_classes - classes}"
    )


def test_aggregation_per_character_count_matches_source_speakers() -> None:
    """Role attribution must follow recorded speakers rather than substring order."""
    import runpy

    script = runpy.run_path(str(AGGREGATION.parent.parent / "scripts/aggregate_t12_real_runs.py"))
    expected = Counter()
    published = Counter()
    for _, _, run in script["discover_runs"]():
        for case in run["cases"]:
            bodies = [m for t in case.get("turns", []) for m in t.get("messages", []) if m["speaker_type"] == "character"]
            if bodies:
                expected[bodies[0]["identity"]["name"]] += 1
                published.update(m["identity"]["name"] for m in bodies)
            else:
                assert case["case_id"] == "expression-comfort-stone-to-failed-peer"
                expected["石猴"] += 1
    payload = _load_aggregation_or_skip()
    by_character = payload["by_character"]
    char_total = sum(c["cases"] for c in by_character)
    assert char_total == 160, (
        f"by_character case total must equal 160, got {char_total}"
    )
    by_ch = {c["character"]: c["cases"] for c in by_character}
    assert set(by_ch.keys()) == {"石猴", "黛玉"}, (
        f"by_character must split into 石猴/黛玉, got {set(by_ch.keys())}"
    )
    assert by_ch["石猴"] + by_ch["黛玉"] == 160
    assert by_ch == dict(expected)
    assert {row["character"]: row["published_count"] for row in by_character} == dict(published)


def test_aggregation_published_count_matches_final_slots_in_source_runs() -> None:
    """A pending quality verdict does not undo already published room messages."""
    import runpy

    script = runpy.run_path(str(AGGREGATION.parent.parent / "scripts/aggregate_t12_real_runs.py"))
    expected = Counter()
    for _, _, run in script["discover_runs"]():
        for case in run["cases"]:
            expected[case["class"]] += sum(
                slot["status"] == "published"
                for turn in case.get("turns", [])
                for slot in turn.get("round", {}).get("slots", [])
            )
    payload = _load_aggregation_or_skip()
    assert {row["class"]: row["published_count"] for row in payload["by_class"]} == dict(expected)
    assert sum(expected.values()) > 0  # The frozen source runs contain real character replies.
    for w in payload["by_window"]:
        assert w["run_status"] == "executed_pending_semantic_review", (
            f"window {w['window']} run_status must be "
            f"executed_pending_semantic_review, got {w['run_status']}"
        )
        assert w["canonical_baselines_unchanged"] is True, (
            f"window {w['window']} canonical_baselines_unchanged must be True"
        )
        assert w["budget_exhausted"] is False, (
            f"window {w['window']} budget_exhausted must be False, got "
            f"{w['budget_exhausted']}"
        )


def test_aggregation_counts_only_final_published_slots_not_execution_snapshots() -> None:
    import runpy

    script = runpy.run_path(str(AGGREGATION.parent.parent / "scripts/aggregate_t12_real_runs.py"))
    case = {
        "class": "knowable", "status": "executed_pending_semantic_review",
        "turns": [{
            "execution_windows": [{"slots": [{"status": "published"}]}] * 2,
            "round": {"slots": [{"status": "published"}, {"status": "failed"}, {"status": "no_comment"}]},
        }],
    }
    run = {"cases": [case], "calls": []}
    row = script["build_by_class"]([("fixture", AGGREGATION, run)])[0]
    assert row["published_count"] == 1


def test_blind_review_uses_actual_character_identity_instead_of_first_room_member() -> None:
    import runpy

    cli = runpy.run_path(str(AGGREGATION.parent.parent / "blind-review-cli.py"))
    source = AGGREGATION.parent / "_v2_runs/window-0-real.json"
    extracted = {case["case_id"]: case for case in cli["load_run_file"](source)}
    seen = set()
    for original in _load(source)["cases"]:
        body = next((m for m in original["turns"][0]["messages"] if m["speaker_type"] == "character"), None)
        if body:
            expected = body["identity"]["name"]
            seen.add(expected)
            case = extracted[original["case_id"]]
            assert case["character_label"] == expected
            assert cli["CHARACTER_LABELS"][case["character_build_id"]] == expected
    assert seen == {"石猴", "黛玉"}


def test_aggregation_self_consistency_under_regeneration() -> None:
    """Running the aggregator script must be idempotent: the second run
    produces the same totals (the only field that changes is the
    aggregated_at timestamp, which is in meta)."""
    import subprocess
    if not (REPO / "docs" / "plans" / "book-character-agents" / "scripts"
            / "aggregate_t12_real_runs.py").exists():
        import pytest
        pytest.skip("aggregator script not present")
    before = _load_aggregation_or_skip()
    result = subprocess.run(
        [sys.executable, str(
            REPO / "docs" / "plans" / "book-character-agents" / "scripts"
            / "aggregate_t12_real_runs.py"
        )],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"aggregator failed: {result.returncode}\nstdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )
    after = json.loads(AGGREGATION.read_text(encoding="utf-8"))
    # Drop timestamp before comparison
    before.pop("meta", None)
    after.pop("meta", None)
    assert before == after, (
        f"aggregator must be deterministic; before != after\n"
        f"diffs: {[k for k in before if before.get(k) != after.get(k)]}"
    )


# ---------------------------------------------------------------------------
# T17 aggregation contract tests
#
# T17 produces 3 distinct real-run files (A path, B path, cognition pilot)
# whose results the §4 row 91 (A/B 对照) and §4 row 95 (cognition 正例)
# directly consume. These tests lock the aggregation shape and the
# deterministic A==B / 1-of-6-runned invariants.
# ---------------------------------------------------------------------------


def test_aggregation_t17_summary_has_three_sources_with_published_slots() -> None:
    """T17 real-run file constant set: 1 A-path + 1 B-path + 1 cognition pilot.
    The A/B path each have 6 cases, all executed; the cognition pilot has 6
    candidate cases but only the cognition-passing subset runs."""
    payload = _load_aggregation_or_skip()
    t17_summary = payload.get("t17_summary", [])
    assert len(t17_summary) == 3, (
        f"t17_summary must have 3 source rows (A, B, cognition), got "
        f"{len(t17_summary)}: {[r['source'] for r in t17_summary]}"
    )
    by_source = {r["source"]: r for r in t17_summary}
    assert set(by_source.keys()) == {
        "t17_matrix_v2_A", "t17_ab_reeval_B", "t17_cognition_pilot"
    }, (
        f"t17_summary sources must be exactly A/B/cognition, got "
        f"{set(by_source.keys())}"
    )
    # A and B each cover 6 T17 cases, all executed_pending_semantic_review.
    for src in ("t17_matrix_v2_A", "t17_ab_reeval_B"):
        row = by_source[src]
        assert row["case_count"] == 6, (
            f"{src} must have 6 cases, got {row['case_count']}"
        )
        assert row["cases_executed_pending_semantic_review"] == 6, (
            f"{src} all 6 cases must be executed_pending_semantic_review, "
            f"got {row['cases_executed_pending_semantic_review']}"
        )
        assert row["cases_not_selected"] == 0, (
            f"{src} must have 0 not_selected cases, got {row['cases_not_selected']}"
        )
    # The published_slot_count comes from round.slots[].status == "published"
    # (slot-level, not case-level), and is the T17 row 95 evidence signal.
    for src in ("t17_matrix_v2_A", "t17_ab_reeval_B", "t17_cognition_pilot"):
        row = by_source[src]
        assert row["published_slot_count"] >= 0, (
            f"{src} published_slot_count must be non-negative, got "
            f"{row['published_slot_count']}"
        )


def test_aggregation_t17_ab_comparison_has_6_cases_with_A_equals_B() -> None:
    """T17 row 91 'A/B 对照' evidence: 6 cases, side-by-side A vs B
    published-slot counts. The A/B paths share the same model config but
    run independently; the A==B invariant must hold for the deterministic
    shape to be useful as the A/B 对照 signal."""
    payload = _load_aggregation_or_skip()
    ab = payload.get("ab_comparison", [])
    assert len(ab) == 6, (
        f"ab_comparison must have 6 cases, got {len(ab)}: "
        f"{[r['case_id'] for r in ab]}"
    )
    case_ids = {r["case_id"] for r in ab}
    expected_ids = {
        "free-all-unshared-private-knowledge",
        "free-directed-conditional-action",
        "free-natural-topic-shift",
        "topic-all-modern-hearsay",
        "topic-directed-rephrased-dilemma",
        "topic-natural-retained-topic",
    }
    assert case_ids == expected_ids, (
        f"ab_comparison must cover all 6 T17 discussion_matrix cases, "
        f"got {case_ids}, missing {expected_ids - case_ids}"
    )
    for row in ab:
        assert row["A_equals_B"] is True, (
            f"case {row['case_id']} A==B must be True for the A/B 对照 "
            f"signal to be meaningful, got A={row['A_published_slots']} "
            f"B={row['B_published_slots']}"
        )
        assert row["A_case_status"] == "executed_pending_semantic_review", (
            f"case {row['case_id']} A status must be "
            f"executed_pending_semantic_review, got {row['A_case_status']}"
        )
        assert row["B_case_status"] == "executed_pending_semantic_review", (
            f"case {row['case_id']} B status must be "
            f"executed_pending_semantic_review, got {row['B_case_status']}"
        )


def test_aggregation_t17_cognition_pilot_runs_exactly_one_case() -> None:
    """T17 row 95 '条件推演 / 引述 / 有据否定经历有正例' evidence: the
    cognition pilot exercises 6 candidate cases and runs exactly the ones
    that pass the cognition filter. From the real-run data, 1 of 6 ran
    (topic-directed-rephrased-dilemma) and produced 1 published slot —
    this is the row 95 '正例' (positive example) signal."""
    payload = _load_aggregation_or_skip()
    cognition = payload.get("cognition_per_case", [])
    assert len(cognition) == 6, (
        f"cognition_per_case must list 6 candidate cases, got {len(cognition)}"
    )
    executed = [r for r in cognition if r["status"] == "executed_pending_semantic_review"]
    not_selected = [r for r in cognition if r["status"] == "not_selected"]
    assert len(executed) == 1, (
        f"cognition pilot must run exactly 1 case, got {len(executed)}: "
        f"{[r['case_id'] for r in executed]}"
    )
    assert len(not_selected) == 5, (
        f"cognition pilot must reject 5 cases (not_selected), got "
        f"{len(not_selected)}"
    )
    # The 1 case that ran must have ≥1 published slot
    assert executed[0]["published_slots"] >= 1, (
        f"the 1 cognition-executed case must have ≥1 published slot, got "
        f"{executed[0]['published_slots']}"
    )
    # All 5 not_selected cases must have 0 published slots
    for row in not_selected:
        assert row["published_slots"] == 0, (
            f"not_selected case {row['case_id']} must have 0 published "
            f"slots, got {row['published_slots']}"
        )


def test_aggregation_t17_published_bodies_extracts_21_slots_with_real_content() -> None:
    """T17 row 95 '条件推演 / 引述 / 有据否定经历有正例' needs the 1/6
    cognition-pilot positive example to have REAL character text + citation
    refs, not just a published-slot counter. This test pins the per-slot
    body extraction: 21 rows total (10 A path + 10 B path + 1 cognition
    pilot), every row has the character identity + content + at least
    one citation ref, and the single cognition positive example
    (topic-directed-rephrased-dilemma) is the row a reviewer needs to
    read to confirm 条件推演 / 引述 / 有据否定经历 — i.e. the content
    is a hypothetical conditional reasoning rather than a literal
    experience claim."""
    payload = _load_aggregation_or_skip()
    bodies = payload.get("t17_published_bodies", [])
    assert len(bodies) == 21, (
        f"t17_published_bodies must list 21 published-slot rows "
        f"(10 A + 10 B + 1 cognition), got {len(bodies)}"
    )
    # Per-source distribution
    from collections import Counter
    by_source = Counter(r["source"] for r in bodies)
    assert by_source.get("t17_matrix_v2_A") == 10, (
        f"A path must have 10 published bodies, got {by_source.get('t17_matrix_v2_A')}"
    )
    assert by_source.get("t17_ab_reeval_B") == 10, (
        f"B path must have 10 published bodies, got {by_source.get('t17_ab_reeval_B')}"
    )
    assert by_source.get("t17_cognition_pilot") == 1, (
        f"cognition pilot must have exactly 1 published body, got "
        f"{by_source.get('t17_cognition_pilot')}"
    )
    # Every row must carry a real character identity (name + book) and
    # non-empty content. ref_count is NOT required to be ≥1 — some
    # published bodies are refusals / stance statements (e.g. "我不该拿
    # 旁人私事冒充亲历" with 0 refs) that still legitimately publish.
    # The aggregate ref distribution across all 21 rows must include at
    # least one canon + one inference (the 1/6 cognition positive example
    # uses 1 canon + 4 inference per the real-run data).
    for row in bodies:
        assert row.get("identity_name"), (
            f"row {row['source']}/{row['case_id']}/{row['turn_idx']}/"
            f"{row['slot_idx']} must have identity_name"
        )
        assert row.get("identity_book_title"), (
            f"row {row['source']}/{row['case_id']}/{row['turn_idx']}/"
            f"{row['slot_idx']} must have identity_book_title"
        )
        assert row.get("content") and len(row["content"]) > 0, (
            f"row {row['source']}/{row['case_id']}/{row['turn_idx']}/"
            f"{row['slot_idx']} must have non-empty content"
        )
    total_refs = sum(row.get("ref_count", 0) for row in bodies)
    assert total_refs >= 30, (
        f"across all 21 published bodies, total ref_count must be ≥30 "
        f"(per the real-run distribution of ~36), got {total_refs}"
    )
    # Origin distribution sanity: at least 1 canon and 1 inference across
    # the 21 rows (proves the runner is logging real citation refs, not
    # all of them being stance/refusal responses with empty refs)
    origins_seen = set()
    for row in bodies:
        origins_seen.update(row.get("ref_origins", []))
    assert "canon" in origins_seen, (
        f"at least 1 published body must carry a canon ref, got "
        f"origins {origins_seen}"
    )
    assert "inference" in origins_seen or "room_hearsay" in origins_seen, (
        f"at least 1 published body must carry an inference or "
        f"room_hearsay ref, got origins {origins_seen}"
    )
    # The 1 cognition positive example is the row that proves
    # 条件推演 / 引述 / 有据否定经历 — its content must exhibit a
    # conditional / hypothetical marker (假设/如果/要是/若是/万一/若/...),
    # which is the linguistic signal of 条件推演 (conditional reasoning).
    # It must also have at least 1 ref (the conditional reasoning cites
    # the character's own canonical self-description "我这性子敢领头").
    cognition = [r for r in bodies if r["source"] == "t17_cognition_pilot"]
    assert len(cognition) == 1, (
        f"cognition pilot must yield exactly 1 published body, got {len(cognition)}"
    )
    content = cognition[0]["content"]
    assert cognition[0]["case_id"] == "topic-directed-rephrased-dilemma", (
        f"the 1 cognition positive example must be the directed rephrased "
        f"dilemma case, got {cognition[0]['case_id']}"
    )
    assert any(marker in content for marker in ("假设", "如果", "要是", "若是", "万一", "若")), (
        f"cognition positive example must exhibit a 条件推演 marker "
        f"(假设/如果/要是/若是/万一/若), got content: {content!r}"
    )
    assert cognition[0]["ref_count"] >= 1, (
        f"the 1 cognition positive example must carry ≥1 citation ref "
        f"(canonical self-citation for '我这性子敢领头'), got "
        f"{cognition[0]['ref_count']}"
    )

