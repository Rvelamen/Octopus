"""Deterministic slicer: turn the T12 60+24=84 case pool into 8-pilot windows.

The T12 acceptance index mandates a 60 boundary + 24 expression question set
covering both books and multiple characters; the existing 8-pilot runner
(``docs/plans/book-character-agents/t12-quality-runner.py``) consumes an
8-case dataset with a 32-native-call ceiling. This slicer bridges the two
without changing the runner:

* The full set is frozen as
  ``docs/plans/book-character-agents/validation/t12-quality-cases-v2.json``
  (dataset_version ``t12-pilot-eightyfour-v1``).
* The slicer deterministically picks ``--window-size`` cases (default 8)
  from the pool in dataset order, preserving tier/class coverage as evenly
  as possible, and emits a v1-shape 8-pilot JSON that the runner can
  consume via ``--dataset``.
* Slicing is content-free: the script never inspects the case body, only
  the (tier, class, case_id) tuple. Reproducibility is by construction.

Usage::

    python scripts/book_world/slice_t12_pool.py \\
        --pool docs/plans/book-character-agents/validation/t12-quality-cases-v2.json \\
        --output docs/plans/book-character-agents/validation/t12-quality-cases-v1-window-N.json \\
        --window-index 0

Each window carries the v1 dataset schema so the runner's ``--dry-run``
mode accepts it without modification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The frozen v1 8-pilot dataset_version; the runner's expected_count
# checks for this exact string. Windows emitted by this slicer carry
# the v1 version so they remain runner-compatible.
V1_DATASET_VERSION = "t12-pilot-eight-v1"
# The runner's MAX_NATIVE_CALLS is 32; v1 datasets must keep ceiling=32.
V1_CEILING = 32
# v1 tier coverage — windows must preserve these classes in 8 cases.
V1_BOUNDARY_CLASSES = ("knowable", "unknowable", "belief", "emotion")
# v1 expression coverage: the canonical 8-pilot selects these 4 of the
# 6 expression classes defined in chat-quality-protocol.md. The runner
# hard-codes this set, so every runner-compatible window must use it.
V1_EXPRESSION_CLASSES = ("answer", "challenge", "comfort", "cross_book_hearsay")
# v1-extension: the remaining 2 expression classes (disagree,
# unknown_expression) are covered by 4-class slots that swap in the
# missing classes. These windows are NOT runner-compatible (the
# runner rejects expression classes outside the canonical set) but
# they are still deterministic and audit-friendly: the dataset
# version flips to ``t12-pilot-eight-v1-ext`` so a downstream tool
# can detect and skip them when wiring against the runner.
V1_EXPRESSION_CLASSES_EXT_A = ("answer", "disagree", "unknown_expression", "comfort")
V1_EXPRESSION_CLASSES_EXT_B = ("challenge", "disagree", "unknown_expression", "cross_book_hearsay")
# The full 6 expression classes (chat-quality-protocol).
ALL_EXPRESSION_CLASSES = (
    "answer", "challenge", "comfort",
    "disagree", "unknown_expression", "cross_book_hearsay",
)


def _class_buckets(pool_cases):
    """Group pool cases by (tier, class) preserving dataset order within each bucket.

    The v1 8-pilot requires 4 boundary + 4 expression specific classes;
    the v2 pool has 4 boundary + 6 expression classes. We pick a
    rotation per window so all 60+24 cases are exercised across windows
    while each 8-case window covers exactly the v1 contract.
    """
    buckets: dict[tuple[str, str], list[dict]] = {}
    for case in pool_cases:
        buckets.setdefault((case["tier"], case["class"]), []).append(case)
    return buckets


def deterministic_window(pool_cases, window_index, window_size,
                          expression_classes=None):
    """Return ``window_size`` case dicts for the given window index.

    The pool is grouped by (tier, class). Each window pulls cases from
    4 boundary slots + 4 expression slots in a fixed order. Within a
    class bucket, the cursor is ``(window_index + slot_idx) % b``, so
    consecutive windows sample different cases from the same bucket
    while every window still satisfies the 8-pilot contract.

    ``expression_classes`` defaults to the canonical v1 set
    (answer / challenge / comfort / cross_book_hearsay), which is the
    only set the runner accepts. Pass a different 4-tuple to produce
    a v1-extension window that swaps in disagree / unknown_expression
    (these windows are NOT runner-compatible — the runner's
    ``validate_dataset`` rejects them).

    Coverage invariant — given ``N = max(bucket_size) = 15`` windows
    with the v2 pool (boundary b=15, expression b=4), the union of
    case_ids across the 15 v1 windows reaches::

        60 boundary cases (4 classes * 15) +
        16 expression cases (4 canonical classes * 4) = 76 cases

    The remaining 8 expression cases (4 disagree + 4 unknown_expression)
    are reached by running the 15 v1-extension windows with the
    extension expression set.

    The function is pure and side-effect-free.
    """
    if window_index < 0:
        raise ValueError("window_index must be non-negative")
    if window_size != 8:
        raise ValueError(
            f"window_size must be 8 to match the v1 8-pilot contract; got {window_size}"
        )
    if expression_classes is None:
        expression_classes = V1_EXPRESSION_CLASSES
    if len(expression_classes) != 4:
        raise ValueError(
            f"expression_classes must be 4-tuple; got {len(expression_classes)}"
        )
    buckets = _class_buckets(pool_cases)
    selected: list[dict] = []
    # Boundary: per-class cursor = (window_index + slot_idx) % b
    # With b=15, w 0..14 gives 15 distinct samples per class.
    for slot_idx, cls in enumerate(V1_BOUNDARY_CLASSES):
        bucket = buckets.get(("boundary", cls), [])
        if not bucket:
            continue
        idx = (window_index + slot_idx) % len(bucket)
        selected.append(bucket[idx])
    # Expression: per-class cursor = (window_index + slot_idx) % b
    # With b=4, w 0..3 gives all 4 cases per class.
    for slot_idx, cls in enumerate(expression_classes):
        bucket = buckets.get(("expression", cls), [])
        if not bucket:
            continue
        idx = (window_index + slot_idx) % len(bucket)
        selected.append(bucket[idx])
    return selected


def enforce_v1_coverage(window_cases, expression_classes):
    """Return (ok, missing_classes) for the 8-pilot v1 coverage contract.

    The runner's ``validate_dataset`` requires every window to include
    all 4 boundary classes and 4 expression classes (8 total). The
    expression class set cycles per window so all 6 chat-quality-
    protocol expression classes are exercised across 3 windows;
    the caller passes the actual expression classes this window
    used. Boundary class coverage is constant (4 known classes).
    """
    classes = {(c["tier"], c["class"]) for c in window_cases}
    needed = ({(("boundary", c)) for c in V1_BOUNDARY_CLASSES}
              | {("expression", c) for c in expression_classes})
    missing = sorted(needed - classes)
    return (not missing, missing)


def emit_v1_window(pool, window_index, window_size, source_path,
                    expression_classes=None, dataset_version=None):
    """Materialize a v1-shape 8-pilot dataset for the given window.

    The emitted dataset keeps the v1 schema (8 cases, native_call_ceiling=32,
    dataset_version=t12-pilot-eight-v1) so the runner can consume it via
    ``--dataset`` and ``--case-id``. Provenance fields record which pool
    slice produced the window.

    Pass a non-canonical ``expression_classes`` and a custom
    ``dataset_version`` (typically ``"t12-pilot-eight-v1-ext"``) to
    emit a v1-extension window that swaps in disagree /
    unknown_expression. The runner rejects these windows, so they
    are reserved for audit and dataset-level coverage analysis.
    """
    cases = pool["cases"]
    if expression_classes is None:
        expression_classes = list(V1_EXPRESSION_CLASSES)
    if dataset_version is None:
        dataset_version = V1_DATASET_VERSION
    sliced = deterministic_window(
        cases, window_index, window_size, expression_classes
    )
    if not sliced:
        return None
    ok, missing = enforce_v1_coverage(sliced, expression_classes)
    if not ok:
        return {"missing_classes": missing, "cases": sliced}
    tier_breakdown = {
        "boundary_cases": sum(1 for c in sliced if c["tier"] == "boundary"),
        "expression_cases": sum(1 for c in sliced if c["tier"] == "expression"),
        "boundary_classes_covered": list(V1_BOUNDARY_CLASSES),
        "expression_classes_covered": list(expression_classes),
    }
    return {
        "dataset_version": dataset_version,
        "frozen_on": pool.get("frozen_on", ""),
        "scope": (
            f"Window {window_index} of the t12-pilot-eightyfour-v1 pool "
            f"(size={window_size}, expression_classes={list(expression_classes)}). "
            f"pool_sha256={hashlib.sha256(source_path.read_bytes()).hexdigest()}."
        ),
        "actors_from": pool["actors_from"],
        "actor_field": pool["actor_field"],
        "native_call_ceiling": V1_CEILING,
        "manual_continues_per_turn": pool["manual_continues_per_turn"],
        "reviewer_kind": pool["reviewer_kind"],
        "tier_breakdown": tier_breakdown,
        "required_case_fields": pool["required_case_fields"],
        "gold_standard_fields": pool["gold_standard_fields"],
        "verdict_legend": pool["verdict_legend"],
        "cases": sliced,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, required=True,
                        help="Path to t12-quality-cases-v2.json")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output path for the v1-shape window dataset")
    parser.add_argument("--window-index", type=int, required=True,
                        help="0-based window index; cases are sliced in pool order")
    parser.add_argument("--window-size", type=int, default=8,
                        help="Cases per window; default 8 to match runner's 8-pilot")
    parser.add_argument(
        "--extension-set",
        choices=("a", "b"),
        default=None,
        help=(
            "If 'a' or 'b', emit a v1-extension window that swaps in the "
            "disagree / unknown_expression classes. The dataset_version "
            "flips to t12-pilot-eight-v1-ext and the runner will reject it; "
            "use this only for audit and dataset-level coverage analysis."
        ),
    )
    args = parser.parse_args()

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    if pool.get("dataset_version") != "t12-pilot-eightyfour-v1":
        raise ValueError(
            f"pool dataset_version drifted: got {pool.get('dataset_version')!r}, "
            f"expected t12-pilot-eightyfour-v1"
        )
    if args.extension_set is None:
        expression_classes = None
        dataset_version = None
    elif args.extension_set == "a":
        expression_classes = list(V1_EXPRESSION_CLASSES_EXT_A)
        dataset_version = "t12-pilot-eight-v1-ext"
    else:
        expression_classes = list(V1_EXPRESSION_CLASSES_EXT_B)
        dataset_version = "t12-pilot-eight-v1-ext"
    result = emit_v1_window(
        pool, args.window_index, args.window_size, args.pool,
        expression_classes=expression_classes,
        dataset_version=dataset_version,
    )
    if result is None:
        raise ValueError(
            f"window_index {args.window_index} out of range for pool size "
            f"{len(pool['cases'])} with window_size {args.window_size}"
        )
    if "missing_classes" in result:
        raise ValueError(
            f"window {args.window_index} (size={args.window_size}) is missing "
            f"required v1 classes: {result['missing_classes']}. "
            f"Increase --window-size."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(
        f"wrote {args.output} cases={len(result['cases'])} "
        f"window_index={args.window_index} window_size={args.window_size} "
        f"dataset_version={result['dataset_version']} "
        f"classes={Counter((c['tier'], c['class']) for c in result['cases'])}"
    )


if __name__ == "__main__":
    main()
