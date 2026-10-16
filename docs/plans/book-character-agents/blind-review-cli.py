#!/usr/bin/env python3
"""
T12/T17 人工盲评 CLI（manual blind review）

按"只增不改"原则实现：
- 不修改任何 canonical baseline
- 不消耗任何模型调用
- 不修改既有的 8-pilot / 60+24 / A/B 真实模型运行结果
- 仅为 160 case 的人工盲评提供审阅界面 + 审计 trail

用法：
    python blind-review-cli.py start [--reviewer NAME] [--out PATH]
    python blind-review-cli.py resume [--out PATH]
    python blind-review-cli.py stats [--out PATH]
    python blind-review-cli.py worksheet [--out PATH]  # 导出为 CSV
    python blind-review-cli.py regrade CASE_ID  # 重审单条

审阅键（单字符）：
    p  pass            角色回答与金标准一致
    f  fail            角色回答与金标准不一致
    o  over-decline    应答却拒答（verdict=knowable/answer 等，但模型沉默了）
    u  under-decline   不应答却回答（verdict=unknowable，但模型给出了具体事实）
    s  skip            审阅者无法判定
    c  comment-only    跳过判定但附加评论
    ?  help            显示帮助
    q  quit-and-save   保存并退出
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
VALIDATION_DIR = REPO_ROOT / "validation"
V2_RUNS_DIR = VALIDATION_DIR / "_v2_runs"

EIGHT_PILOT_PATH = VALIDATION_DIR / "2026-10-16-t12-8pilot-real-run.json"

# v2 真实跑窗口（按 evidence 文档顺序 0-14 + exta 0-3）
V2_WINDOWS = [V2_RUNS_DIR / f"window-{i}-real.json" for i in range(15)]
V2_EXT_WINDOWS = [V2_RUNS_DIR / f"exta-window-{i}-real.json" for i in range(4)]

# 全部 20 份结果文件
ALL_RUN_FILES = [EIGHT_PILOT_PATH, *V2_WINDOWS, *V2_EXT_WINDOWS]

# 判定键 → 中文标签 + 含义
VERDICT_KEYS = {
    "p": ("pass", "角色回答与金标准一致"),
    "f": ("fail", "角色回答与金标准不一致"),
    "o": ("over_decline", "应答却拒答（verdict 应答但模型沉默）"),
    "u": ("under_decline", "不应答却回答（verdict 应沉默但模型给了具体事实）"),
    "s": ("skip", "审阅者无法判定"),
    "c": ("comment", "跳过判定但附加评论"),
}

# 角色 build_id → 显示名（来自真实跑 character_scopes）
CHARACTER_LABELS = {
    "c2da28c8-cab3-4bc2-9342-b1a60831c99a": "石猴",
    "58609a52-4ba4-4c8e-83c0-46c8bca65c1b": "黛玉",
}


def load_run_file(path: Path) -> list[dict[str, Any]]:
    """从单份 runner 输出中抽取结构化 case 审阅单元。"""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        report = json.load(fh)
    run_id = path.stem  # e.g. window-0-real / exta-window-0-real / 2026-10-16-t12-8pilot-real-run
    run_label = _shorten_run_label(run_id)
    char_scopes = report.get("character_scopes") or []
    char_label = _resolve_character_label(char_scopes)

    cases = []
    for case in report.get("cases") or []:
        turns = case.get("turns") or []
        if not turns:
            continue
        messages = turns[0].get("messages") or []
        user_msg = next((m for m in messages if m.get("speaker_type") == "user"), None)
        char_msg = next((m for m in messages if m.get("speaker_type") == "character"), None)
        round_summary = turns[0].get("round") or {}
        execution_windows = turns[0].get("execution_windows") or []
        cases.append(
            {
                "run_id": run_id,
                "run_label": run_label,
                "case_id": case.get("case_id"),
                "tier": case.get("tier"),
                "class": case.get("class"),
                "mode": case.get("mode"),
                "discussion_mode": case.get("discussion_mode"),
                "status": case.get("status"),
                "character_label": char_label,
                "character_build_id": _first_build_id(char_scopes),
                "question": (user_msg.get("content") or "").strip() if user_msg else "",
                "character_response": (char_msg.get("content") or "").strip() if char_msg else "",
                "has_character_response": bool(char_msg),
                "round_status": round_summary.get("status"),
                "round_error_code": round_summary.get("error_code"),
                "execution_windows_count": len(execution_windows),
                "expected": case.get("expected") or [],
                "gold_standard": case.get("gold_standard") or {},
                "reviewer_kind": report.get("scope", {}).get("reviewer_kind")
                if isinstance(report.get("scope"), dict)
                else None,
            }
        )
    return cases


def _resolve_character_label(char_scopes: list[dict]) -> str:
    if not char_scopes:
        return "?"
    build_id = char_scopes[0].get("build_id", "")
    return CHARACTER_LABELS.get(build_id, build_id[:8] or "?")


def _first_build_id(char_scopes: list[dict]) -> str:
    if not char_scopes:
        return ""
    return char_scopes[0].get("build_id", "")


def _shorten_run_label(run_id: str) -> str:
    if run_id.startswith("2026-10-16-t12-8pilot"):
        return "8pilot"
    if run_id.startswith("exta-window"):
        m = re.match(r"exta-window-(\d+)-real", run_id)
        if m:
            return f"exta-{m.group(1)}"
    if run_id.startswith("window"):
        m = re.match(r"window-(\d+)-real", run_id)
        if m:
            return f"v2-{m.group(1)}"
    return run_id


def collect_all_cases() -> list[dict[str, Any]]:
    """按固定顺序收集全部真实跑 case：8pilot → v2-0..14 → exta-0..3"""
    cases = []
    for path in ALL_RUN_FILES:
        cases.extend(load_run_file(path))
    return cases


def load_existing_review(out_path: Path) -> dict[str, dict[str, Any]]:
    """从 JSON 文件加载已有审阅结果，按 (run_id, case_id) 索引"""
    if not out_path.exists():
        return {}
    with out_path.open(encoding="utf-8") as fh:
        report = json.load(fh)
    by_key = {}
    for review in report.get("reviews") or []:
        key = f"{review['run_id']}::{review['case_id']}"
        by_key[key] = review
    return by_key


def save_review(out_path: Path, header: dict[str, Any], reviews: list[dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **header,
        "reviews": reviews,
        "stats": compute_stats(reviews),
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def compute_stats(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {label: 0 for label, _ in VERDICT_KEYS.values()}
    counts["total"] = len(reviews)
    counts["with_comment"] = sum(1 for r in reviews if r.get("comment"))
    verdict_set = {label: 0 for label, _ in VERDICT_KEYS.values()}
    by_class: dict[str, dict[str, int]] = {}
    by_character: dict[str, dict[str, int]] = {}
    for r in reviews:
        verdict = r.get("verdict")
        if verdict:
            counts[verdict] = counts.get(verdict, 0) + 1
        cls = r.get("class") or "?"
        if cls not in by_class:
            by_class[cls] = {**verdict_set, "total": 0}
        by_class[cls]["total"] += 1
        if verdict:
            by_class[cls][verdict] = by_class[cls].get(verdict, 0) + 1
        char_label = r.get("character_label") or "?"
        if char_label not in by_character:
            by_character[char_label] = {**verdict_set, "total": 0}
        by_character[char_label]["total"] += 1
        if verdict:
            by_character[char_label][verdict] = by_character[char_label].get(verdict, 0) + 1
    return {
        "verdict_counts": counts,
        "by_class": by_class,
        "by_character": by_character,
    }


def render_case(case: dict[str, Any], show_blind: bool = False) -> str:
    """渲染单个 case 给审阅者看。

    show_blind=True 时隐藏 expected/gold_standard（盲评）；
    默认 open 模式显示所有信息以辅助审阅。
    """
    gs = case.get("gold_standard") or {}
    expected = case.get("expected") or []
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(
        f"[{case['run_label']}] case_id={case['case_id']}  "
        f"class={case['class']}  tier={case['tier']}"
    )
    lines.append(
        f"character={case['character_label']}  "
        f"mode={case['mode']}  discussion={case['discussion_mode']}  "
        f"status={case['status']}"
    )
    lines.append("-" * 72)
    lines.append("【用户问】")
    lines.append(case["question"])
    lines.append("-" * 72)
    lines.append("【角色答】")
    if case.get("has_character_response"):
        lines.append(case["character_response"] or "（空回答）")
    else:
        lines.append(
            "[MODEL 未产出角色回答] round_status="
            f"{case.get('round_status')!r}  error_code={case.get('round_error_code')!r}  "
            f"execution_windows={case.get('execution_windows_count')}"
        )
    if not show_blind:
        lines.append("-" * 72)
        lines.append("【金标准 verdict】")
        lines.append(f"  verdict: {gs.get('verdict')}")
        if gs.get("expected_source"):
            lines.append(f"  expected_source: {gs['expected_source']}")
        if gs.get("required_claims"):
            lines.append(f"  required_claims: {gs['required_claims']}")
        if gs.get("forbidden_claims"):
            lines.append(f"  forbidden_claims: {gs['forbidden_claims']}")
        lines.append("【expected（runner 内置）】")
        for i, e in enumerate(expected, 1):
            lines.append(f"  {i}. {e}")
    lines.append("=" * 72)
    return "\n".join(lines)


def render_help() -> str:
    lines = ["审阅键（单字符）:"]
    for k, (label, desc) in VERDICT_KEYS.items():
        lines.append(f"  {k}  {label:<16}  {desc}")
    lines.append("  ?  help            显示本帮助")
    lines.append("  q  quit-and-save   保存并退出（可 resume 续审）")
    return "\n".join(lines)


def prompt_with_default(prompt: str, default: str = "") -> str:
    if default:
        sys.stdout.write(f"{prompt} [{default}]: ")
    else:
        sys.stdout.write(f"{prompt}: ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        return default
    val = line.strip()
    return val or default


def cmd_start(args: argparse.Namespace) -> int:
    out_path = Path(args.out).resolve()
    cases = collect_all_cases()
    print(f"已加载 {len(cases)} case（来自 8-pilot + 15 canonical + 4 ext-a 共 20 份结果文件）")
    if not cases:
        print("ERROR: 未找到任何 case，请检查 validation/_v2_runs/ 与 8-pilot 文件路径")
        return 1
    existing = load_existing_review(out_path)
    print(f"已加载 {len(existing)} 条既有审阅（来自 {out_path}）")
    reviewer_name = getattr(args, "reviewer", None) or os.environ.get("USER", "reviewer")
    show_blind = bool(getattr(args, "blind", False))
    header = {
        "reviewer": reviewer_name,
        "review_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "review_protocol_version": "v1",
        "reviewer_kind": "Agent checks complete published bodies and supplied sources; no claim of human blind review",
        "case_count": len(cases),
        "show_blind": show_blind,
    }
    reviews: list[dict[str, Any]] = []
    for existing_review in existing.values():
        reviews.append(existing_review)
    reviewed_keys = {f"{r['run_id']}::{r['case_id']}" for r in reviews}

    pending = [c for c in cases if f"{c['run_id']}::{c['case_id']}" not in reviewed_keys]
    print(f"待审 {len(pending)} case / 已审 {len(reviews)} case\n")
    if not pending:
        print("无待审 case，审阅已完成。可执行 stats 子命令查看统计。")
        save_review(out_path, header, reviews)
        return 0

    print(render_help())
    print()

    for idx, case in enumerate(pending, 1):
        print(f"\n>>> Case {idx}/{len(pending)} <<<")
        print(render_case(case, show_blind=show_blind))
        while True:
            verdict_input = prompt_with_default("判定 (p/f/o/u/s/c/?/q)").lower()
            if not verdict_input:
                continue
            ch = verdict_input[0]
            if ch == "?":
                print(render_help())
                continue
            if ch == "q":
                save_review(out_path, header, reviews)
                print(f"\n已保存 {len(reviews)} 条审阅到 {out_path}")
                return 0
            if ch not in VERDICT_KEYS:
                print(f"未识别键 '{verdict_input}'，请重试（输入 ? 查看帮助）")
                continue
            verdict_label, _ = VERDICT_KEYS[ch]
            comment = ""
            if ch in ("f", "o", "u", "c"):
                comment = prompt_with_default("评论（可空）")
            review = {
                "run_id": case["run_id"],
                "run_label": case["run_label"],
                "case_id": case["case_id"],
                "tier": case["tier"],
                "class": case["class"],
                "mode": case["mode"],
                "discussion_mode": case["discussion_mode"],
                "character_label": case["character_label"],
                "character_build_id": case["character_build_id"],
                "verdict_key": ch,
                "verdict": verdict_label,
                "comment": comment,
                "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            reviews.append(review)
            save_review(out_path, header, reviews)
            print(f"  → 记录 {verdict_label}{('：' + comment) if comment else ''}")
            break

    save_review(out_path, header, reviews)
    print(f"\n全部 {len(pending)} case 审阅完成，结果保存到 {out_path}")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    out_path = Path(args.out).resolve()
    if not out_path.exists():
        print(f"未找到审阅文件 {out_path}，请先执行 start 子命令")
        return 1
    # 复用 start 逻辑：start 会自动加载已有审阅并跳过
    return cmd_start(args)


def cmd_stats(args: argparse.Namespace) -> int:
    out_path = Path(args.out).resolve()
    if not out_path.exists():
        print(f"未找到审阅文件 {out_path}，请先执行 start 子命令")
        return 1
    with out_path.open(encoding="utf-8") as fh:
        report = json.load(fh)
    stats = report.get("stats") or compute_stats(report.get("reviews") or [])
    print(f"审阅者: {report.get('reviewer')}")
    print(f"case 总数: {stats['verdict_counts'].get('total', 0)}")
    print(f"  pass:        {stats['verdict_counts'].get('pass', 0)}")
    print(f"  fail:        {stats['verdict_counts'].get('fail', 0)}")
    print(f"  over_decline: {stats['verdict_counts'].get('over_decline', 0)}")
    print(f"  under_decline: {stats['verdict_counts'].get('under_decline', 0)}")
    print(f"  skip:        {stats['verdict_counts'].get('skip', 0)}")
    print(f"  comment:     {stats['verdict_counts'].get('comment', 0)}")
    print(f"  带评论:       {stats['verdict_counts'].get('with_comment', 0)}")
    print()
    print("按 class:")
    for cls, c in sorted(stats.get("by_class", {}).items()):
        print(
            f"  {cls:<22}  total={c.get('total',0):>3}  pass={c.get('pass',0):>3}  "
            f"fail={c.get('fail',0):>3}  over={c.get('over_decline',0):>3}  "
            f"under={c.get('under_decline',0):>3}  skip={c.get('skip',0):>3}"
        )
    print()
    print("按 character:")
    for ch, c in sorted(stats.get("by_character", {}).items()):
        print(
            f"  {ch:<6}  total={c.get('total',0):>3}  pass={c.get('pass',0):>3}  "
            f"fail={c.get('fail',0):>3}  over={c.get('over_decline',0):>3}  "
            f"under={c.get('under_decline',0):>3}  skip={c.get('skip',0):>3}"
        )
    return 0


def cmd_worksheet(args: argparse.Namespace) -> int:
    """导出 CSV 供离线审阅（不依赖交互式 CLI）"""
    out_csv = Path(args.worksheet).resolve()
    cases = collect_all_cases()
    if not cases:
        print("ERROR: 未找到任何 case")
        return 1
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "case_id",
                "run_label",
                "tier",
                "class",
                "character",
                "mode",
                "question",
                "character_response",
                "round_status",
                "round_error_code",
                "has_response",
                "gold_verdict",
                "required_claims",
                "forbidden_claims",
                "expected_source",
                "reviewer_verdict",
                "reviewer_comment",
            ]
        )
        for case in cases:
            gs = case.get("gold_standard") or {}
            response = case.get("character_response") or ""
            if not case.get("has_character_response"):
                response = (
                    f"[NO_RESPONSE round_status={case.get('round_status')!r} "
                    f"error={case.get('round_error_code')!r} "
                    f"windows={case.get('execution_windows_count')}]"
                )
            writer.writerow(
                [
                    case["case_id"],
                    case["run_label"],
                    case["tier"],
                    case["class"],
                    case["character_label"],
                    case["mode"],
                    case["question"],
                    response,
                    case.get("round_status") or "",
                    case.get("round_error_code") or "",
                    "yes" if case.get("has_character_response") else "no",
                    gs.get("verdict", ""),
                    " | ".join(gs.get("required_claims") or []),
                    " | ".join(gs.get("forbidden_claims") or []),
                    gs.get("expected_source", ""),
                    "",
                    "",
                ]
            )
    no_response_count = sum(1 for c in cases if not c.get("has_character_response"))
    print(
        f"已导出 {len(cases)} case 到 {out_csv}"
        f"（{no_response_count} 条无角色回答，建议按 over_decline 处理）"
    )
    return 0


def cmd_regrade(args: argparse.Namespace) -> int:
    out_path = Path(args.out).resolve()
    cases = collect_all_cases()
    target = [c for c in cases if c["case_id"] == args.case_id]
    if not target:
        print(f"ERROR: 找不到 case_id={args.case_id}")
        return 1
    if len(target) > 1:
        print(f"WARNING: case_id={args.case_id} 在 {len(target)} 处出现，全部展示")
    for case in target:
        print(render_case(case, show_blind=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="T12/T17 人工盲评 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="开始/继续审阅")
    p_start.add_argument("--reviewer", help="审阅者名（默认读 $USER）")
    p_start.add_argument("--out", default=str(VALIDATION_DIR / "blind-review-2026-10-16.json"))
    p_start.add_argument("--blind", action="store_true", help="盲评模式（隐藏 expected/gold_standard）")

    p_resume = sub.add_parser("resume", help="从既有审阅文件继续")
    p_resume.add_argument("--out", default=str(VALIDATION_DIR / "blind-review-2026-10-16.json"))

    p_stats = sub.add_parser("stats", help="查看审阅统计")
    p_stats.add_argument("--out", default=str(VALIDATION_DIR / "blind-review-2026-10-16.json"))

    p_sheet = sub.add_parser("worksheet", help="导出为 CSV 供离线审阅")
    p_sheet.add_argument(
        "--worksheet", default=str(VALIDATION_DIR / "blind-review-2026-10-16-worksheet.csv")
    )

    p_regrade = sub.add_parser("regrade", help="重审单条 case")
    p_regrade.add_argument("case_id")
    p_regrade.add_argument("--out", default=str(VALIDATION_DIR / "blind-review-2026-10-16.json"))

    args = parser.parse_args()
    return {
        "start": cmd_start,
        "resume": cmd_resume,
        "stats": cmd_stats,
        "worksheet": cmd_worksheet,
        "regrade": cmd_regrade,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
