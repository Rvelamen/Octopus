"""Single-case bridge probe runner for verifying the 588b2be fix at the model layer.

Scope
-----
This script runs exactly **one** T12 case (``boundary-knowable-stone-cave-iron-bridge``)
against the post-588b2be supply layer to verify whether the model can finally
reach the ``铁板桥`` (iron bridge) episode after the compound-anchor fix.

Why a single case
-----------------
The 2026-10-19 long-query real-model run (6 calls) was a *pre-fix* snapshot
where the model's ``approved_excerpt''` was empty for the bridge episode, so
it triggered the ``UNKNOWN_REPLY`` safe-decline. The post-fix 588b2be supply-
layer rebalance keeps ``瀑布`` / ``桥下`` / ``key9`` in the top 32 slots, but
the persona archive still does not carry the bridge passage propositions
(see 2026-10-19-t12-five-remaining-gates.md §2 for the full context).

This script is therefore a *single-case model probe* — the smallest possible
real-model verification of the supply-layer fix. 1 case × 1 model call
roughly = 1 native call, well within the "控制模型调用预算" constraint.

Usage
-----
1. Pre-flight: ``tmp/book-corpus/西游记.txt`` must exist (line 33 carries the
   bridge passage).
2. From the repository root, after the operator has authorised the model
   budget, run::

       python docs/plans/book-character-agents/scripts/run-bridge-probe.py \\
           --workspace tmp/bridge-probe-workspace \\
           --output    tmp/bridge-probe-output.json

3. Inspect the output JSON: look at the single case's
   ``reader_evidence`` / ``approved_excerpt`` / ``published_body``.

The bridge case lives in the ``t12-quality-cases-v1-window-0.json`` slicing
(not the un-windowed ``t12-quality-cases-v1.json``); the script defaults to
the window-0 dataset.

Expected outcomes
-----------------
- **Best case** (supply layer fully fixed, model answers the bridge question):
  ``published_body`` contains ``铁板桥`` / ``桥下之水`` / ``倒挂流出去遮闭桥门``
  or a faithful paraphrase. ``approved_excerpt`` is non-empty.
- **Expected case** (supply fix ok, but persona archive lacks the bridge
  episode as a proposition): ``published_body`` is ``UNKNOWN_REPLY`` or
  refuses the bridge detail; ``approved_excerpt`` empty. This is exactly the
  Gate B-1 remaining gap; the script does not pretend to fix it.
- **Failure case** (supply fix broken): ``published_body`` mentions 关系/trait
  but not the bridge passage. Indicates the 588b2be fix regressed.

It is **deliberately** a single case — the operator is encouraged to run it
once, then decide whether to escalate to a larger pool (Gate C of
2026-10-19-t12-five-remaining-gates.md).

Budget
------
1 case = 1 native call (under the 32-call ceiling; the dataset's slot budget
is 32 but a single case consumes 1 by default). Total model call cost: 1.

Exit codes
----------
- 0: probe completed; output written.
- 2: validation error (workspace missing, dataset missing, etc.).
- 3: real-model call failed; operator should inspect stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
# Default to the v1 window-0 dataset: the bridge case
# ``boundary-knowable-stone-cave-iron-bridge`` is a window-0 case (not in the
# un-windowed ``t12-quality-cases-v1.json`` which is a different slicing).
DEFAULT_DATASET = REPO / "docs/plans/book-character-agents/validation/t12-quality-cases-v1-window-0.json"
DEFAULT_CORPUS_DIR = REPO / "tmp/book-corpus"
BRIDGE_CASE_ID = "boundary-knowable-stone-cave-iron-bridge"


def _validate(workspace: Path, dataset: Path) -> None:
    if not dataset.exists():
        print(f"ERROR: dataset not found: {dataset}", file=sys.stderr)
        sys.exit(2)
    if not DEFAULT_CORPUS_DIR.exists():
        print(
            f"ERROR: book corpus dir missing: {DEFAULT_CORPUS_DIR}. "
            "Required for 铁板桥 line 33 of 西游记.txt.",
            file=sys.stderr,
        )
        sys.exit(2)
    corpus = DEFAULT_CORPUS_DIR / "西游记.txt"
    if not corpus.exists():
        print(f"ERROR: corpus missing: {corpus}", file=sys.stderr)
        sys.exit(2)
    # Sanity: bridge passage must literally be in the corpus.
    text = corpus.read_text(encoding="utf-8")
    if "铁板桥" not in text or "桥下之水" not in text:
        print(
            "ERROR: bridge passage markers missing from 西游记.txt — "
            "the supply layer cannot surface what the corpus does not contain.",
            file=sys.stderr,
        )
        sys.exit(2)
    workspace.mkdir(parents=True, exist_ok=True)
    if not workspace.is_dir():
        print(f"ERROR: workspace path is not a directory: {workspace}", file=sys.stderr)
        sys.exit(2)


async def _run(args: argparse.Namespace) -> int:
    # The runner lives at docs/plans/book-character-agents/t12-quality-runner.py —
    # a hyphen-bearing module name, so we cannot ``import`` it directly. Load
    # the module by file path instead. Lazy-load so --help works without the
    # heavy chain.
    import importlib.util
    runner_path = REPO / "docs/plans/book-character-agents/t12-quality-runner.py"
    if not runner_path.exists():
        print(f"ERROR: runner not found: {runner_path}", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("t12_quality_runner", runner_path)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot import runner spec: {runner_path}", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(REPO))
    spec.loader.exec_module(module)
    runner_run = module.run

    options = argparse.Namespace(
        workspace=args.workspace,
        dataset=args.dataset,
        output=args.output,
        call_budget=args.call_budget,
        provider_id=args.provider_id,
        model_id=args.model_id,
        case_id=[BRIDGE_CASE_ID],
        dry_run=False,
    )
    try:
        await runner_run(options)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Isolated workspace root for the probe (must not be a real book-library workspace).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"Path to t12-quality-cases-v1.json (default: {DEFAULT_DATASET}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON for the single-case probe.",
    )
    parser.add_argument(
        "--call-budget",
        type=int,
        default=32,
        help="Per-case native call budget (default: 32, the dataset ceiling).",
    )
    parser.add_argument(
        "--provider-id",
        type=int,
        default=None,
        help="Override provider id (default: dataset default).",
    )
    parser.add_argument(
        "--model-id",
        type=int,
        default=None,
        help="Override model id (default: dataset default).",
    )
    args = parser.parse_args()
    _validate(args.workspace, args.dataset)
    print(
        f"Probe target: {BRIDGE_CASE_ID} | workspace={args.workspace} "
        f"| output={args.output} | call_budget={args.call_budget}",
        file=sys.stderr,
    )
    print(
        "Reminder: this script makes a real model call. Run it only after the "
        "operator has authorised the model budget. Use --dry-run on the runner "
        "directly to verify the supply layer without consuming budget.",
        file=sys.stderr,
    )
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
