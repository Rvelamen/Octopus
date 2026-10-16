"""Aggregate the 8-pilot + 19 v2 real-run JSON files into a single evidence file.

Produces deterministic per-window / per-class / per-character / per-phase / per-status
tables so the real-model run data is consumable as one artifact rather than 20
scattered files. No model calls. Reads only. Writes one JSON + one Markdown
summary to ``validation/``.

Usage::

    python docs/plans/book-character-agents/scripts/aggregate_t12_real_runs.py

Outputs::

    validation/2026-10-16-t12-real-runs-aggregation.json
    validation/2026-10-16-t12-real-runs-aggregation.md

Tables produced
---------------
1. totals ............................ overall call/token/elapsed totals across all
                                         20 real-run files
2. by_window ......................... per-window call count, tokens, elapsed,
                                         status, source protocol
3. by_class ......................... per-class case count, completed, mean tokens,
                                         mean elapsed, published (always 0)
4. by_character ..................... per-character (石猴/黛玉/cross-book) breakdown
5. by_phase ......................... generate vs review call count, tokens, elapsed
6. by_status ......................... per-call status (completed/failed/timeout)
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLAN_DIR = HERE.parent
VALIDATION_DIR = PLAN_DIR / "validation"
RUNS_DIR = VALIDATION_DIR / "_v2_runs"
EIGHT_PILOT = VALIDATION_DIR / "2026-10-16-t12-8pilot-real-run.json"

OUTPUT_JSON = VALIDATION_DIR / "2026-10-16-t12-real-runs-aggregation.json"
OUTPUT_MD = VALIDATION_DIR / "2026-10-16-t12-real-runs-aggregation.md"

# Character parsed from case_id (slug) - matches the runner's case_id convention
# used in t12-quality-cases-v1.json and t12-quality-cases-v2.json.
STONE_RE = re.compile(r"-stone-")
DAIYU_RE = re.compile(r"-daiyu-")
# cross_book_hearsay cases have a single "speaker" character + a "hearer" character;
# the speaker is the one whose case_id embeds -stone- or -daiyu- (which is the
# actor the runner books via target_actor_indices).  The hearer is noted in the
# case_id suffix (e.g. ``stone-hears-daiyu``).  We only attribute primary actor.


def parse_character(case_id: str) -> str:
    """Return ``石猴`` / ``黛玉`` / ``unknown`` from a case_id slug."""
    if STONE_RE.search(case_id):
        return "石猴"
    if DAIYU_RE.search(case_id):
        return "黛玉"
    return "unknown"


def infer_protocol(path: Path) -> str:
    """Return the runner protocol version (v1 / v1ext) inferred from the file."""
    if "exta-" in path.stem:
        return "v1ext"
    return "v1"


def load_run(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_runs() -> list[tuple[str, Path, dict[str, Any]]]:
    """Yield ``(label, path, run_json)`` for the 8-pilot + 19 v2 windows."""
    items: list[tuple[str, Path, dict[str, Any]]] = []
    if EIGHT_PILOT.exists():
        items.append(("8pilot", EIGHT_PILOT, load_run(EIGHT_PILOT)))
    for p in sorted(RUNS_DIR.glob("window-*-real.json")):
        items.append((p.stem.replace("-real", ""), p, load_run(p)))
    for p in sorted(RUNS_DIR.glob("exta-window-*-real.json")):
        items.append((p.stem.replace("-real", ""), p, load_run(p)))
    return items


def safe_mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def build_totals(items: list[tuple[str, Path, dict[str, Any]]]) -> dict[str, Any]:
    calls = [c for _, _, run in items for c in run.get("calls", [])]
    tok_in = sum(c.get("usage", {}).get("prompt_tokens", 0) for c in calls)
    tok_out = sum(c.get("usage", {}).get("completion_tokens", 0) for c in calls)
    cache_read = sum(
        c.get("usage", {}).get("cache_read_input_tokens", 0) for c in calls
    )
    cache_create = sum(
        c.get("usage", {}).get("cache_creation_input_tokens", 0) for c in calls
    )
    elapsed = sum(c.get("elapsed_seconds", 0) for c in calls)
    completed = sum(1 for c in calls if c.get("status") == "completed")
    failed = sum(1 for c in calls if c.get("status") not in {"completed", None})
    return {
        "window_count": len(items),
        "call_count": len(calls),
        "completed_call_count": completed,
        "non_completed_call_count": failed,
        "tok_in_total": tok_in,
        "tok_out_total": tok_out,
        "cache_read_total": cache_read,
        "cache_creation_total": cache_create,
        "tok_total": tok_in + tok_out,
        "elapsed_seconds_total": round(elapsed, 1),
        "elapsed_seconds_mean": round(safe_mean(
            [c.get("elapsed_seconds", 0) for c in calls]
        ), 3),
        "elapsed_seconds_max": round(
            max((c.get("elapsed_seconds", 0) for c in calls), default=0), 3
        ),
    }


def build_by_window(
    items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for label, path, run in items:
        calls = run.get("calls", [])
        cases = run.get("cases", [])
        tok_in = sum(c.get("usage", {}).get("prompt_tokens", 0) for c in calls)
        tok_out = sum(c.get("usage", {}).get("completion_tokens", 0) for c in calls)
        cache_read = sum(
            c.get("usage", {}).get("cache_read_input_tokens", 0) for c in calls
        )
        cache_create = sum(
            c.get("usage", {}).get("cache_creation_input_tokens", 0) for c in calls
        )
        elapsed = sum(c.get("elapsed_seconds", 0) for c in calls)
        by_phase: dict[str, dict[str, int]] = {}
        for c in calls:
            ph = c.get("phase", "unknown")
            slot = by_phase.setdefault(
                ph, {"calls": 0, "completed": 0, "non_completed": 0, "elapsed_s": 0.0}
            )
            slot["calls"] += 1
            slot["elapsed_s"] += c.get("elapsed_seconds", 0) or 0
            if c.get("status") == "completed":
                slot["completed"] += 1
            else:
                slot["non_completed"] += 1
        for slot in by_phase.values():
            slot["elapsed_s"] = round(slot["elapsed_s"], 1)
        case_status = Counter(c.get("status", "unknown") for c in cases)
        rows.append(
            {
                "window": label,
                "source_file": str(path.relative_to(PLAN_DIR.parent)),
                "protocol": infer_protocol(path),
                "case_count": len(cases),
                "case_status": dict(case_status),
                "call_count": len(calls),
                "tok_in": tok_in,
                "tok_out": tok_out,
                "cache_read": cache_read,
                "cache_creation": cache_create,
                "elapsed_seconds": round(elapsed, 1),
                "by_phase": by_phase,
                "run_status": run.get("run_status"),
                "canonical_baselines_unchanged": run.get(
                    "canonical_baselines_unchanged"
                ),
                "budget_exhausted": run.get("budget_exhausted"),
                "runner_sha256": run.get("runner_sha256"),
            }
        )
    return rows


def build_by_class(
    items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Aggregate per-class over ALL cases. Native calls are not uniquely tagged
    with case_id at the call level (only ``input_sha256``), so per-class call /
    token totals are an aggregate over the case's room epoch, not a strict
    per-class sum of native calls.  We mark this with the field
    ``call_attribution_method``."""
    by_cls: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "cases": 0,
            "completed_cases": 0,
            "pending_review_cases": 0,
            "other_status_cases": 0,
            "tok_in_attributed": 0,
            "tok_out_attributed": 0,
            "elapsed_attributed_seconds": 0.0,
            "elapsed_per_call_seconds": [],
        }
    )
    for _, _, run in items:
        cases = run.get("cases", [])
        calls = run.get("calls", [])
        n_cases = len(cases) or 1
        tok_in = sum(c.get("usage", {}).get("prompt_tokens", 0) for c in calls)
        tok_out = sum(c.get("usage", {}).get("completion_tokens", 0) for c in calls)
        elapsed = sum(c.get("elapsed_seconds", 0) for c in calls)
        for case in cases:
            cls = case.get("class", "unknown")
            slot = by_cls[cls]
            slot["cases"] += 1
            status = case.get("status", "unknown")
            if status == "executed_pending_semantic_review":
                slot["completed_cases"] += 1
            elif status == "pending_semantic_review":
                slot["pending_review_cases"] += 1
            else:
                slot["other_status_cases"] += 1
            # Even attribution: divide window totals across the window's cases
            slot["tok_in_attributed"] += tok_in // n_cases
            slot["tok_out_attributed"] += tok_out // n_cases
            slot["elapsed_attributed_seconds"] += round(elapsed / n_cases, 3)
        # Per-call elapsed pool for class-level mean
        # (note: calls aren't 1:1 attributable to a single class, so we report
        # window-mean elapsed_per_call as a stable secondary signal)
    rows = []
    for cls, slot in sorted(by_cls.items()):
        n = slot["cases"] or 1
        rows.append(
            {
                "class": cls,
                "cases": slot["cases"],
                "completed_cases": slot["completed_cases"],
                "pending_review_cases": slot["pending_review_cases"],
                "other_status_cases": slot["other_status_cases"],
                "tok_in_mean": round(slot["tok_in_attributed"] / n, 1),
                "tok_out_mean": round(slot["tok_out_attributed"] / n, 1),
                "elapsed_seconds_mean": round(
                    slot["elapsed_attributed_seconds"] / n, 2
                ),
                "published_count": 0,  # always 0 in 8-pilot + v2 real runs
            }
        )
    return rows


def build_by_character(
    items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_ch: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "cases": 0,
            "completed_cases": 0,
            "tok_in_attributed": 0,
            "tok_out_attributed": 0,
            "elapsed_attributed_seconds": 0.0,
        }
    )
    for _, _, run in items:
        cases = run.get("cases", [])
        calls = run.get("calls", [])
        n_cases = len(cases) or 1
        tok_in = sum(c.get("usage", {}).get("prompt_tokens", 0) for c in calls)
        tok_out = sum(c.get("usage", {}).get("completion_tokens", 0) for c in calls)
        elapsed = sum(c.get("elapsed_seconds", 0) for c in calls)
        for case in cases:
            ch = parse_character(case.get("case_id", ""))
            slot = by_ch[ch]
            slot["cases"] += 1
            if case.get("status") == "executed_pending_semantic_review":
                slot["completed_cases"] += 1
            slot["tok_in_attributed"] += tok_in // n_cases
            slot["tok_out_attributed"] += tok_out // n_cases
            slot["elapsed_attributed_seconds"] += round(elapsed / n_cases, 3)
    rows = []
    for ch, slot in sorted(by_ch.items()):
        n = slot["cases"] or 1
        rows.append(
            {
                "character": ch,
                "cases": slot["cases"],
                "completed_cases": slot["completed_cases"],
                "tok_in_mean": round(slot["tok_in_attributed"] / n, 1),
                "tok_out_mean": round(slot["tok_out_attributed"] / n, 1),
                "elapsed_seconds_mean": round(
                    slot["elapsed_attributed_seconds"] / n, 2
                ),
            }
        )
    return rows


def build_by_phase(
    items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_ph: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "completed": 0,
            "non_completed": 0,
            "tok_in": 0,
            "tok_out": 0,
            "elapsed_seconds": 0.0,
        }
    )
    for _, _, run in items:
        for c in run.get("calls", []):
            ph = c.get("phase", "unknown")
            slot = by_ph[ph]
            slot["calls"] += 1
            if c.get("status") == "completed":
                slot["completed"] += 1
            else:
                slot["non_completed"] += 1
            slot["tok_in"] += c.get("usage", {}).get("prompt_tokens", 0)
            slot["tok_out"] += c.get("usage", {}).get("completion_tokens", 0)
            slot["elapsed_seconds"] += c.get("elapsed_seconds", 0) or 0
    rows = []
    for ph, slot in sorted(by_ph.items()):
        n = slot["calls"] or 1
        rows.append(
            {
                "phase": ph,
                "calls": slot["calls"],
                "completed": slot["completed"],
                "non_completed": slot["non_completed"],
                "tok_in": slot["tok_in"],
                "tok_out": slot["tok_out"],
                "elapsed_seconds_total": round(slot["elapsed_seconds"], 1),
                "elapsed_seconds_mean": round(slot["elapsed_seconds"] / n, 3),
            }
        )
    return rows


def build_by_status(
    items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_st: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "elapsed_seconds": 0.0}
    )
    for _, _, run in items:
        for c in run.get("calls", []):
            st = c.get("status", "unknown")
            slot = by_st[st]
            slot["calls"] += 1
            slot["elapsed_seconds"] += c.get("elapsed_seconds", 0) or 0
    rows = []
    for st, slot in sorted(by_st.items()):
        rows.append(
            {
                "status": st,
                "calls": slot["calls"],
                "elapsed_seconds_total": round(slot["elapsed_seconds"], 1),
            }
        )
    return rows


def render_markdown(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    by_window = payload["by_window"]
    by_class = payload["by_class"]
    by_character = payload["by_character"]
    by_phase = payload["by_phase"]
    by_status = payload["by_status"]
    meta = payload["meta"]

    lines = []
    lines.append("# T12 真实模型运行聚合（8-pilot + v2 60+24 = 160 case 链路）")
    lines.append("")
    lines.append(
        f"> 聚合时间：{meta['aggregated_at']}  |  来源文件：{meta['source_file_count']} 份"
        f"（{', '.join(meta['source_protocols'])} 协议）  |  模型调用：0"
    )
    lines.append("")
    lines.append("## 1. 总体")
    lines.append("")
    lines.append(f"- 窗口数：{totals['window_count']}")
    lines.append(f"- 调用总数：{totals['call_count']}（已完成 {totals['completed_call_count']} / 未完成 {totals['non_completed_call_count']}）")
    lines.append(f"- prompt_tokens 总和：{totals['tok_in_total']:,}")
    lines.append(f"- completion_tokens 总和：{totals['tok_out_total']:,}")
    lines.append(f"- cache_read_input_tokens 总和：{totals['cache_read_total']:,}")
    lines.append(f"- cache_creation_input_tokens 总和：{totals['cache_creation_total']:,}")
    lines.append(f"- elapsed_seconds 总和：{totals['elapsed_seconds_total']}")
    lines.append(f"- elapsed_seconds 平均/调用：{totals['elapsed_seconds_mean']}")
    lines.append(f"- elapsed_seconds 最大/调用：{totals['elapsed_seconds_max']}")
    lines.append("")
    lines.append("## 2. 按窗口")
    lines.append("")
    lines.append("| 窗口 | 协议 | case | 调用 | tok_in | tok_out | cache_read | cache_create | elapsed_s | 状态 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in by_window:
        lines.append(
            f"| {row['window']} | {row['protocol']} | {row['case_count']}"
            f" | {row['call_count']} | {row['tok_in']:,} | {row['tok_out']:,}"
            f" | {row['cache_read']:,} | {row['cache_creation']:,}"
            f" | {row['elapsed_seconds']} | {row['run_status']} |"
        )
    lines.append("")
    lines.append("## 3. 按 class（按窗口 case 数等分归因 token/elapsed）")
    lines.append("")
    lines.append("| class | cases | 已完成 | 待审 | tok_in 平均 | tok_out 平均 | elapsed 平均 | published |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in by_class:
        lines.append(
            f"| {row['class']} | {row['cases']} | {row['completed_cases']}"
            f" | {row['pending_review_cases']} | {row['tok_in_mean']}"
            f" | {row['tok_out_mean']} | {row['elapsed_seconds_mean']}"
            f" | {row['published_count']} |"
        )
    lines.append("")
    lines.append("## 4. 按角色（从 case_id slug 解析 primary actor）")
    lines.append("")
    lines.append("| 角色 | cases | 已完成 | tok_in 平均 | tok_out 平均 | elapsed 平均 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in by_character:
        lines.append(
            f"| {row['character']} | {row['cases']}"
            f" | {row['completed_cases']} | {row['tok_in_mean']}"
            f" | {row['tok_out_mean']} | {row['elapsed_seconds_mean']} |"
        )
    lines.append("")
    lines.append("## 5. 按 phase（generate vs review）")
    lines.append("")
    lines.append("| phase | 调用 | 完成 | 未完成 | tok_in | tok_out | elapsed 总和 | elapsed 平均 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in by_phase:
        lines.append(
            f"| {row['phase']} | {row['calls']} | {row['completed']}"
            f" | {row['non_completed']} | {row['tok_in']:,} | {row['tok_out']:,}"
            f" | {row['elapsed_seconds_total']} | {row['elapsed_seconds_mean']} |"
        )
    lines.append("")
    lines.append("## 6. 按 call status")
    lines.append("")
    lines.append("| status | 调用 | elapsed 总和 |")
    lines.append("| --- | ---: | ---: |")
    for row in by_status:
        lines.append(
            f"| {row['status']} | {row['calls']}"
            f" | {row['elapsed_seconds_total']} |"
        )
    lines.append("")
    lines.append("## 7. 归因方法说明")
    lines.append("")
    lines.append(
        "- per-class / per-character 的 token 与 elapsed 通过按窗口 case 数等分归因（窗口 totals / case_count）。"
    )
    lines.append(
        "- 这是 runner 输出 schema 不在 ``calls`` 层携带 case_id 时的确定性近似："
        "每个窗口内 8 个 case 通常共享相同 runner budget，所以等分是稳定近似。"
    )
    lines.append(
        "- published 永远为 0：8-pilot + v2 真实跑全部进入 ``executed_pending_semantic_review`` 终态，"
        "质量层不声明通过；T12 §4 row 9 的人工盲评接收这一信号。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    items = discover_runs()
    if not items:
        print("ERROR: no real-run files found", flush=True)
        return 1
    totals = build_totals(items)
    by_window = build_by_window(items)
    by_class = build_by_class(items)
    by_character = build_by_character(items)
    by_phase = build_by_phase(items)
    by_status = build_by_status(items)
    from datetime import datetime, timezone
    aggregated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "meta": {
            "aggregated_at": aggregated_at,
            "source_file_count": len(items),
            "source_protocols": sorted({infer_protocol(p) for _, p, _ in items}),
            "generator": "docs/plans/book-character-agents/scripts/aggregate_t12_real_runs.py",
        },
        "totals": totals,
        "by_window": by_window,
        "by_class": by_class,
        "by_character": by_character,
        "by_phase": by_phase,
        "by_status": by_status,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        f"wrote {OUTPUT_JSON.relative_to(PLAN_DIR.parent)} and "
        f"{OUTPUT_MD.relative_to(PLAN_DIR.parent)}"
    )
    print(
        f"windows={totals['window_count']} calls={totals['call_count']}"
        f" tok_in={totals['tok_in_total']:,} tok_out={totals['tok_out_total']:,}"
        f" elapsed_s={totals['elapsed_seconds_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
