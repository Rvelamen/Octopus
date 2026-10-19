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
                                         mean elapsed, actual published slots
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

# T17 real-run files (separate from T12 v1/v1ext windows; the T17 protocol
# exercises 6 free/topic x natural/directed/all combinations, not the
# chat-quality-protocol class set)
T17_MATRIX_V2 = VALIDATION_DIR / "real-model-t17-matrix-v2.json"  # A path
T17_AB_REEVAL = VALIDATION_DIR / "real-model-t17-matrix-v2-ab.json"  # B path
T17_COGNITION_PILOT = VALIDATION_DIR / "real-model-t17-cognition-pilot-v2.json"

OUTPUT_JSON = VALIDATION_DIR / "2026-10-16-t12-real-runs-aggregation.json"
OUTPUT_MD = VALIDATION_DIR / "2026-10-16-t12-real-runs-aggregation.md"

# Character parsed from case_id (slug) - matches the runner's case_id convention
# used in t12-quality-cases-v1.json and t12-quality-cases-v2.json.
STONE_RE = re.compile(r"-stone(?:-|$)")
DAIYU_RE = re.compile(r"-daiyu(?:-|$)")
# cross_book_hearsay cases have a single "speaker" character + a "hearer" character;
# the speaker is the one whose case_id embeds -stone- or -daiyu- (which is the
# actor the runner books via target_actor_indices).  The hearer is noted in the
# case_id suffix (e.g. ``stone-hears-daiyu``).  We only attribute primary actor.


def parse_character(case_id: str) -> str:
    """Return ``石猴`` / ``黛玉`` / ``unknown`` from a case_id slug."""
    stone = STONE_RE.search(case_id)
    daiyu = DAIYU_RE.search(case_id)
    if stone and (not daiyu or stone.start() < daiyu.start()):
        return "石猴"
    if daiyu:
        return "黛玉"
    return "unknown"


def case_character(case: dict[str, Any]) -> str:
    """Use the published speaker; the first named case actor is only a fallback."""
    for turn in case.get("turns", []):
        for message in turn.get("messages", []):
            if message.get("speaker_type") == "character":
                name = message.get("identity", {}).get("name")
                if isinstance(name, str) and name:
                    return name
    return parse_character(case.get("case_id", ""))


def infer_protocol(path: Path) -> str:
    """Return the runner protocol version (v1 / v1ext) inferred from the file."""
    if "exta-" in path.stem:
        return "v1ext"
    return "v1"


def load_run(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return report


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
    cases = [case for _, _, run in items for case in run.get("cases", [])]
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
        "case_count": len(cases),
        "published_count": sum(count_published_slots(case) for case in cases),
        "published_case_count": sum(count_published_slots(case) > 0 for case in cases),
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
        by_phase: dict[str, dict[str, Any]] = {}
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
                "published_count": sum(count_published_slots(case) for case in cases),
                "published_case_count": sum(count_published_slots(case) > 0 for case in cases),
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
            "published_count": 0,
            "published_case_count": 0,
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
            published = count_published_slots(case)
            slot["published_count"] += published
            slot["published_case_count"] += published > 0
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
                "published_count": slot["published_count"],
                "published_case_count": slot["published_case_count"],
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
            "published_count": 0,
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
            ch = case_character(case)
            slot = by_ch[ch]
            slot["cases"] += 1
            slot["published_count"] += count_published_slots(case)
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
                "published_count": slot["published_count"],
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
    t17_summary = payload.get("t17_summary", [])
    ab_comparison = payload.get("ab_comparison", [])
    cognition_per_case = payload.get("cognition_per_case", [])
    t17_published_bodies = payload.get("t17_published_bodies", [])
    meta = payload["meta"]

    lines = []
    lines.append("# T12 + T17 真实模型运行聚合")
    lines.append("")
    lines.append(
        f"> 聚合时间：{meta['aggregated_at']}  |  T12 来源文件：{meta['source_file_count']} 份"
        f"（{', '.join(meta['source_protocols'])} 协议）"
        f"  |  T17 来源文件：{meta.get('t17_source_file_count', 0)} 份"
        f"  |  模型调用：0"
    )
    lines.append("")

    # --- Part I — T12 ---
    lines.append("## Part I — T12 真实模型运行（8-pilot + v2 60+24）")
    lines.append("")
    lines.append("### 1. 总体")
    lines.append("")
    lines.append(f"- 窗口数：{totals['window_count']}")
    lines.append(f"- 样本数：{totals['case_count']}；实际发布槽位：{totals['published_count']}；有发布的样本：{totals['published_case_count']}")
    lines.append("- 发布仅表示正文通过当次运行校验，不代表原著语义、人物质量或人工盲评通过。")
    lines.append(f"- 调用总数：{totals['call_count']}（已完成 {totals['completed_call_count']} / 未完成 {totals['non_completed_call_count']}）")
    lines.append(f"- prompt_tokens 总和：{totals['tok_in_total']:,}")
    lines.append(f"- completion_tokens 总和：{totals['tok_out_total']:,}")
    lines.append(f"- cache_read_input_tokens 总和：{totals['cache_read_total']:,}")
    lines.append(f"- cache_creation_input_tokens 总和：{totals['cache_creation_total']:,}")
    lines.append(f"- elapsed_seconds 总和：{totals['elapsed_seconds_total']}")
    lines.append(f"- elapsed_seconds 平均/调用：{totals['elapsed_seconds_mean']}")
    lines.append(f"- elapsed_seconds 最大/调用：{totals['elapsed_seconds_max']}")
    lines.append("")
    lines.append("### 2. 按窗口")
    lines.append("")
    lines.append("| 窗口 | 协议 | case | 发布槽位 | 调用 | tok_in | tok_out | cache_read | cache_create | elapsed_s | 状态 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in by_window:
        lines.append(
            f"| {row['window']} | {row['protocol']} | {row['case_count']}"
            f" | {row['published_count']}"
            f" | {row['call_count']} | {row['tok_in']:,} | {row['tok_out']:,}"
            f" | {row['cache_read']:,} | {row['cache_creation']:,}"
            f" | {row['elapsed_seconds']} | {row['run_status']} |"
        )
    lines.append("")
    lines.append("### 3. 按 class（按窗口 case 数等分归因 token/elapsed）")
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
    lines.append("### 4. 按样本首条人物发言身份（无正文时按 case_id 首个人名归因）")
    lines.append("")
    lines.append("| 角色 | cases | 已完成 | 发布槽位 | tok_in 平均 | tok_out 平均 | elapsed 平均 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in by_character:
        lines.append(
            f"| {row['character']} | {row['cases']}"
            f" | {row['completed_cases']} | {row['published_count']} | {row['tok_in_mean']}"
            f" | {row['tok_out_mean']} | {row['elapsed_seconds_mean']} |"
        )
    lines.append("")
    lines.append("### 5. 按 phase（generate vs review）")
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
    lines.append("### 6. 按 call status")
    lines.append("")
    lines.append("| status | 调用 | elapsed 总和 |")
    lines.append("| --- | ---: | ---: |")
    for row in by_status:
        lines.append(
            f"| {row['status']} | {row['calls']}"
            f" | {row['elapsed_seconds_total']} |"
        )
    lines.append("")

    # --- Part II — T17 ---
    lines.append("## Part II — T17 真实模型运行（6 组合 + A/B + cognition）")
    lines.append("")
    lines.append("### 7. T17 来源总览")
    lines.append("")
    if t17_summary:
        lines.append("| 来源 | case | executed | not_selected | other | native_call | published_slots | tok_in | tok_out | elapsed_s |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in t17_summary:
            lines.append(
                f"| {row['source']} | {row['case_count']}"
                f" | {row['cases_executed_pending_semantic_review']}"
                f" | {row['cases_not_selected']}"
                f" | {row['cases_other_status']}"
                f" | {row['native_call_count']}"
                f" | {row['published_slot_count']}"
                f" | {row['tok_in']:,}"
                f" | {row['tok_out']:,}"
                f" | {row['elapsed_seconds']} |"
            )
    else:
        lines.append("（无 T17 真实跑文件）")
    lines.append("")
    lines.append("### 8. T17 A/B 对照（matrix_v2 A 路径 vs ab_reeval B 路径）")
    lines.append("")
    if ab_comparison:
        lines.append("| case_id | discussion_mode | mode | A published | B published | A==B | A status | B status |")
        lines.append("| --- | --- | --- | ---: | ---: | :---: | --- | --- |")
        for row in ab_comparison:
            eq_mark = "✓" if row["A_equals_B"] else "✗"
            lines.append(
                f"| {row['case_id']} | {row['discussion_mode']} | {row['mode']}"
                f" | {row['A_published_slots']} | {row['B_published_slots']}"
                f" | {eq_mark}"
                f" | {row['A_case_status']} | {row['B_case_status']} |"
            )
    else:
        lines.append("（A 路径或 B 路径文件缺失）")
    lines.append("")
    lines.append("### 9. T17 cognition pilot（6 case 选 1）")
    lines.append("")
    if cognition_per_case:
        lines.append("| case_id | discussion_mode | mode | status | turns | published_slots |")
        lines.append("| --- | --- | --- | --- | ---: | ---: |")
        for row in cognition_per_case:
            lines.append(
                f"| {row['case_id']} | {row['discussion_mode']} | {row['mode']}"
                f" | {row['status']} | {row['turns']}"
                f" | {row['published_slots']} |"
            )
    else:
        lines.append("（cognition pilot 文件缺失）")
    lines.append("")
    lines.append("### 10. T17 published body 抽样（A/B + cognition 共 21 slot）")
    lines.append("")
    if t17_published_bodies:
        # Per-source + per-case + per-slot table. The 1/6 cognition-pilot
        # case ``topic-directed-rephrased-dilemma`` is the only "cognition
        # 正例" in T17 row 95; showing its content + ref breakdown makes
        # the signal concrete. Identity / content_len / ref_count / origin
        # distribution are what a reviewer needs to judge true positive.
        lines.append("| source | case_id | turn/slot | identity | content_len | ref_count | ref_origins | has_canon |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | --- | :---: |")
        for row in t17_published_bodies:
            ident = f"{row.get('identity_name') or '?'}·{row.get('identity_book_title') or '?'}"
            origins = ",".join(row.get("ref_origins", [])) or "—"
            has_canon = (
                "✓"
                if "canon" in (row.get("ref_count_by_origin") or {})
                else "—"
            )
            lines.append(
                f"| {row['source']} | {row['case_id']}"
                f" | {row['turn_idx']}/{row['slot_idx']}"
                f" | {ident}"
                f" | {row['content_len']}"
                f" | {row['ref_count']}"
                f" | {origins}"
                f" | {has_canon} |"
            )
        lines.append("")
        # First cognition-pilot published body (the 1/6 正例) printed in full
        # so a reviewer can see the 条件推演 / 引述 / 有据否定经历 pattern
        # directly, not just an aggregated counter.
        for row in t17_published_bodies:
            if (
                row["source"] == "t17_cognition_pilot"
                and row.get("content")
            ):
                lines.append("**T17 cognition 正例 body（topic-directed-rephrased-dilemma / directed mode / published slot 0/0）**：")
                lines.append("")
                lines.append(f"> {row['content']}")
                lines.append("")
                if row.get("first_ref_text"):
                    lines.append(f"首条 citation：{row['first_ref_text']}")
                    lines.append("")
                break
    else:
        lines.append("（无 T17 published body 抽样）")
    lines.append("")

    # --- Part III — 归因方法说明 ---
    lines.append("## Part III — 归因方法说明")
    lines.append("")
    lines.append(
        "- T12 per-class / per-character 的 token 与 elapsed 通过按窗口 case 数等分归因（窗口 totals / case_count）。"
    )
    lines.append(
        "- T12 published 来自各 turn 最终 ``round.slots[].status == 'published'``，不重复累计 execution_windows 快照。"
        "``executed_pending_semantic_review`` 是质量复核状态，与是否已经发布正文是两件事；不能据它把发布数记成零。"
    )
    lines.append(
        "- T17 published 来自 ``round.slots[].status == 'published'``（slot-level，不是 case-level 的 status 字段）。"
        "case.status = ``executed_pending_semantic_review`` 只代表流程走完，slot 仍可能 publish；"
        "T17 row 95 cognition 正例 = cognition pilot 中 1 case 取得 ≥1 published slot，"
        "T17 row 91 A/B 对照 = A 路径 6 case / B 路径 6 case 的 published-slot 数逐 case 比较（A==B 列）。"
    )
    lines.append("")
    return "\n".join(lines)


def count_published_slots(case: dict[str, Any]) -> int:
    """Return total published slot count across all turns of a case.

    A ``round.slots[].status == "published"`` is the actual publish marker
    in T12 and T17 runner output (the case-level ``status`` may say
    ``executed_pending_semantic_review`` even when individual slots publish,
    because the runner does not auto-claim full quality pass)."""
    n = 0
    for turn in case.get("turns", []):
        for slot in turn.get("round", {}).get("slots", []):
            if slot.get("status") == "published":
                n += 1
    return n


def load_t17_runs() -> list[tuple[str, Path, dict[str, Any]]]:
    """Yield ``(label, path, run_json)`` for the 3 T17 real-run files."""
    out: list[tuple[str, Path, dict[str, Any]]] = []
    if T17_MATRIX_V2.exists():
        out.append(("t17_matrix_v2_A", T17_MATRIX_V2, load_run(T17_MATRIX_V2)))
    if T17_AB_REEVAL.exists():
        out.append(("t17_ab_reeval_B", T17_AB_REEVAL, load_run(T17_AB_REEVAL)))
    if T17_COGNITION_PILOT.exists():
        out.append(
            ("t17_cognition_pilot", T17_COGNITION_PILOT, load_run(T17_COGNITION_PILOT))
        )
    return out


def build_t17_summary(
    t17_items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Per-source T17 totals: cases / native calls / published slots.

    The T17 protocol is discussion_matrix × natural/directed/all = 6 cases;
    each case typically produces 1-2 turns × 1-2 slots. ``published_slots``
    is the actual publish count (slot-level, not case-level) and is the
    signal T17 row 91 + row 95 need."""
    rows = []
    for label, path, run in t17_items:
        cases = run.get("cases", [])
        calls = run.get("calls", [])
        published = sum(count_published_slots(c) for c in cases)
        cases_executed = sum(
            1 for c in cases if c.get("status") == "executed_pending_semantic_review"
        )
        cases_not_selected = sum(
            1 for c in cases if c.get("status") == "not_selected"
        )
        cases_other = len(cases) - cases_executed - cases_not_selected
        tok_in = sum(c.get("usage", {}).get("prompt_tokens", 0) for c in calls)
        tok_out = sum(c.get("usage", {}).get("completion_tokens", 0) for c in calls)
        elapsed = sum(c.get("elapsed_seconds", 0) or 0 for c in calls)
        rows.append(
            {
                "source": label,
                "source_file": str(path.relative_to(PLAN_DIR.parent)),
                "case_count": len(cases),
                "cases_executed_pending_semantic_review": cases_executed,
                "cases_not_selected": cases_not_selected,
                "cases_other_status": cases_other,
                "native_call_count": len(calls),
                "published_slot_count": published,
                "tok_in": tok_in,
                "tok_out": tok_out,
                "elapsed_seconds": round(elapsed, 1),
                "run_status": run.get("run_status"),
                "canonical_baselines_unchanged": run.get(
                    "canonical_baselines_unchanged"
                ),
            }
        )
    return rows


def build_ab_comparison(
    t17_items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Side-by-side comparison of A (matrix_v2) vs B (ab_reeval) on the 6
    T17 discussion_matrix cases. T17 row 91 'A/B 对照' wants this exact
    shape: same case_id, same model config, two independent runner runs,
    per-case A vs B published-slot count."""
    by_label: dict[str, dict[str, Any]] = {label: run for label, _, run in t17_items}
    a_run = by_label.get("t17_matrix_v2_A")
    b_run = by_label.get("t17_ab_reeval_B")
    if a_run is None or b_run is None:
        return []
    a_cases = {c["case_id"]: c for c in a_run.get("cases", [])}
    b_cases = {c["case_id"]: c for c in b_run.get("cases", [])}
    rows = []
    for cid in sorted(a_cases.keys() & b_cases.keys()):
        a = a_cases[cid]
        b = b_cases[cid]
        a_pub = count_published_slots(a)
        b_pub = count_published_slots(b)
        rows.append(
            {
                "case_id": cid,
                "discussion_mode": a.get("discussion_mode"),
                "mode": a.get("mode"),
                "A_published_slots": a_pub,
                "B_published_slots": b_pub,
                "A_equals_B": a_pub == b_pub,
                "A_case_status": a.get("status"),
                "B_case_status": b.get("status"),
            }
        )
    return rows


def build_cognition_per_case(
    t17_items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Per-case cognition selection status. T17 row 95 '条件推演 / 引述 /
    有据否定经历有正例' wants a per-case breakdown: which of the 6 T17
    cognition cases actually ran (``executed_pending_semantic_review``) and
    which got ``not_selected`` (cognition filter rejected them)."""
    for label, _, run in t17_items:
        if label == "t17_cognition_pilot":
            return [
                {
                    "case_id": c.get("case_id"),
                    "discussion_mode": c.get("discussion_mode"),
                    "mode": c.get("mode"),
                    "status": c.get("status"),
                    "turns": len(c.get("turns", [])),
                    "published_slots": count_published_slots(c),
                }
                for c in run.get("cases", [])
            ]
    return []


def _extract_published_body_for_slot(
    turn: dict[str, Any], slot: dict[str, Any]
) -> dict[str, Any] | None:
    """Return the character message that produced this published slot.

    Walks the turn's ``messages`` to find the ``character``-speaker message
    whose ``speaker_member_id`` matches the slot's ``member_id``. Returns
    the body, ref breakdown, and identity so a reviewer can judge whether
    the published text is a true positive (e.g. for the 1/6 cognition-pilot
    case). Returns ``None`` if no matching character message is found
    (defensive — should not happen in normal T17 output)."""
    slot_member = slot.get("member_id")
    for m in turn.get("messages", []):
        if (
            m.get("speaker_type") == "character"
            and m.get("speaker_member_id") == slot_member
        ):
            content = m.get("content", "")
            refs = m.get("refs", []) or []
            ref_origins = sorted({r.get("origin", "unknown") for r in refs})
            ref_count_by_origin: dict[str, int] = {}
            for r in refs:
                o = r.get("origin", "unknown")
                ref_count_by_origin[o] = ref_count_by_origin.get(o, 0) + 1
            first_ref = refs[0] if refs else None
            return {
                "content": content,
                "content_len": len(content),
                "ref_count": len(refs),
                "ref_origins": ref_origins,
                "ref_count_by_origin": ref_count_by_origin,
                "first_ref_text": (
                    (first_ref.get("assertion_text") or "")[:120]
                    if first_ref and first_ref.get("assertion_text")
                    else None
                ),
                "identity": m.get("identity", {}),
            }
    return None


def extract_t17_published_bodies(
    t17_items: list[tuple[str, Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Per-source per-case per-slot published body extraction.

    For every published slot across the 3 T17 real-run files, extract
    the actual character text + citation metadata so a reviewer can
    judge whether each ``published`` is a true positive. This is the
    concrete evidence T17 row 95 ("条件推演 / 引述 / 有据否定经历有
    正例") needs — the 1/6 cognition-pilot case is only meaningful if
    the published body actually exhibits one of those 3 patterns.

    Deterministic, read-only, no model calls."""
    rows = []
    for label, _, run in t17_items:
        for case in run.get("cases", []):
            if case.get("status") != "executed_pending_semantic_review":
                continue
            cid = case.get("case_id")
            for ti, turn in enumerate(case.get("turns", [])):
                for si, slot in enumerate(turn.get("round", {}).get("slots", [])):
                    if slot.get("status") != "published":
                        continue
                    body = _extract_published_body_for_slot(turn, slot)
                    if body is None:
                        # published slot with no character message — record
                        # the slot metadata only, so the gap is visible
                        rows.append(
                            {
                                "source": label,
                                "case_id": cid,
                                "turn_idx": ti,
                                "slot_idx": si,
                                "member_id": slot.get("member_id"),
                                "content": None,
                                "content_len": 0,
                                "ref_count": 0,
                                "ref_origins": [],
                                "ref_count_by_origin": {},
                                "first_ref_text": None,
                                "identity": {},
                                "note": "published slot has no matching character message",
                            }
                        )
                        continue
                    identity = body["identity"] or {}
                    rows.append(
                        {
                            "source": label,
                            "case_id": cid,
                            "turn_idx": ti,
                            "slot_idx": si,
                            "member_id": slot.get("member_id"),
                            "content": body["content"],
                            "content_len": body["content_len"],
                            "ref_count": body["ref_count"],
                            "ref_origins": body["ref_origins"],
                            "ref_count_by_origin": body["ref_count_by_origin"],
                            "first_ref_text": body["first_ref_text"],
                            "identity_name": identity.get("name"),
                            "identity_book_title": identity.get("book_title"),
                        }
                    )
    return rows


def main() -> int:
    items = discover_runs()
    t17_items = load_t17_runs()
    if not items:
        print("ERROR: no T12 real-run files found", flush=True)
        return 1
    totals = build_totals(items)
    by_window = build_by_window(items)
    by_class = build_by_class(items)
    by_character = build_by_character(items)
    by_phase = build_by_phase(items)
    by_status = build_by_status(items)
    t17_summary = build_t17_summary(t17_items)
    ab_comparison = build_ab_comparison(t17_items)
    cognition_per_case = build_cognition_per_case(t17_items)
    t17_published_bodies = extract_t17_published_bodies(t17_items)
    from datetime import datetime, timezone
    aggregated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "meta": {
            "aggregated_at": aggregated_at,
            "source_file_count": len(items),
            "source_protocols": sorted({infer_protocol(p) for _, p, _ in items}),
            "t17_source_file_count": len(t17_items),
            "generator": "docs/plans/book-character-agents/scripts/aggregate_t12_real_runs.py",
        },
        "totals": totals,
        "by_window": by_window,
        "by_class": by_class,
        "by_character": by_character,
        "by_phase": by_phase,
        "by_status": by_status,
        "t17_summary": t17_summary,
        "ab_comparison": ab_comparison,
        "cognition_per_case": cognition_per_case,
        "t17_published_bodies": t17_published_bodies,
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
        f"t12_windows={totals['window_count']} calls={totals['call_count']}"
        f" tok_in={totals['tok_in_total']:,} tok_out={totals['tok_out_total']:,}"
        f" elapsed_s={totals['elapsed_seconds_total']}"
    )
    print(
        f"t17_sources={len(t17_items)}"
        f" ab_rows={len(ab_comparison)}"
        f" cognition_rows={len(cognition_per_case)}"
        f" published_body_rows={len(t17_published_bodies)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
