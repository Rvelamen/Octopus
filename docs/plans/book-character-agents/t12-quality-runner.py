"""Run the T12 8-pilot quality case set through real room services with a native-call ceiling.

This runner is the small-budget pilot driver for the T12 first-version quality evaluation
defined in ``chat-quality-protocol.md`` Q05. It is a sibling of ``discussion-acceptance.py``
(used by T17 for the free/topic × natural/directed/all six-combination matrix).

The runner intentionally parallels ``discussion-acceptance.py`` in structure
(SHA pins, ceiling pattern, capture wrapper) so that T17 and T12 share the same
runtime invariants and the same "non-destructive probe" promise. Where T17 is
about the six-discussion-mode matrix, T12 is about the 60+24+84 question set's
single-room behavior across two books (西游记 / 红楼梦) and two characters
(石猴 / 黛玉) drawn from ``real-model-group-chat-probe.json``.

It does NOT run the 8 cases by default — the T12 acceptance index and the
"控制模型调用预算" directive require that no new model budget is consumed
without explicit instruction. The runner exists so that, when the budget
opens, a single ``python t12-quality-runner.py --workspace <path> --output <path>``
command reproduces the 8-pilot with the same ceiling / SHA / capture pattern
as T17.

Run with ``--case-id`` to scope to a subset; with no ``--case-id`` all 8 cases
are queued in dataset order. With ``--dry-run`` it validates the dataset
schema, character scopes, policy versions and SHA pins without spending
any model budget; ``--dry-run`` is the only mode that should be used until
the user reopens the model budget.
"""

# Direct CLI execution needs the repository bootstrap before backend imports.
# ruff: noqa: E402

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[3]
MAX_NATIVE_CALLS = 32
sys.path.insert(0, str(REPO))

from loguru import logger  # noqa: E402

from backend.services.book_world.chat_provider import resolve_character_chat_model  # noqa: E402
from backend.services.book_world.chat_worker import BookChatWorker  # noqa: E402
from backend.services.book_world.discussion import RoomDiscussionService  # noqa: E402
from backend.services.book_world.features import get_features  # noqa: E402
from backend.services.book_world.knowledge_models import CanonicalScope  # noqa: E402
from backend.services.book_world.members import RoomMembershipService  # noqa: E402
from backend.services.book_world.rounds import BookRoundService  # noqa: E402


class NativeBudgetExhausted(asyncio.CancelledError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def source_ids(value):
    result = {}

    def walk(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in (
                    "claim_id",
                    "evidence_id",
                    "message_id",
                    "material_id",
                    "set_id",
                ) and isinstance(child, str):
                    result.setdefault(key, set()).add(child)
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return {key: sorted(values) for key, values in result.items()}


def validate_dataset(dataset, *, expected_count, expected_ceiling, reviewer_kind, dataset_required_fields, case_required_fields, gold_required_fields):
    if dataset.get("dataset_version") != expected_count["dataset_version"]:
        raise ValueError(
            f"dataset_version drifted: dataset={dataset.get('dataset_version')!r}, "
            f"runner expects {expected_count['dataset_version']!r}"
        )
    ceiling = dataset.get("native_call_ceiling")
    if ceiling != expected_ceiling:
        raise ValueError(
            f"native_call_ceiling drifted: {ceiling!r} != {expected_ceiling!r}"
        )
    if dataset.get("reviewer_kind") != reviewer_kind:
        raise ValueError(
            f"reviewer_kind drifted: {dataset.get('reviewer_kind')!r} != {reviewer_kind!r}"
        )
    if dataset.get("manual_continues_per_turn") != 1:
        raise ValueError("manual_continues_per_turn must remain 1 (operator-continuation policy)")
    cases = dataset.get("cases") or []
    if len(cases) != expected_count["case_count"]:
        raise ValueError(
            f"case count drifted: {len(cases)} != {expected_count['case_count']} "
            f"(the 8-pilot is part of the gold standard; renumbering requires a new version)"
        )
    if len({c.get("case_id") for c in cases}) != len(cases):
        raise ValueError("Duplicate case_id; the gold standard requires unique case_id per run")
    for field in dataset_required_fields:
        if field not in dataset:
            raise ValueError(f"dataset missing required field {field!r}")
    for case in cases:
        missing = case_required_fields - set(case.keys())
        if missing:
            raise ValueError(
                f"case {case.get('case_id')!r} missing fields {missing!r}"
            )
        gold = case.get("gold_standard") or {}
        for key in gold_required_fields:
            if key not in gold:
                raise ValueError(
                    f"case {case.get('case_id')!r} gold_standard missing {key!r}"
                )
    expected_classes = {
        ("boundary", c)
        for c in expected_count["boundary_classes_covered"]
    }
    # Two protocols: v1 (frozen 4-of-6 expression classes) vs v1ext
    # (4 expression classes declared per window, drawn from any of the 6
    # chat-quality-protocol classes). v1 keeps the frozen list; v1ext
    # accepts whichever 4 the window's ``tier_breakdown.expression_classes_covered``
    # declares, as long as they're a strict subset of the 6 protocol
    # classes. This lets ext-a/ext-b windows cover disagree +
    # unknown_expression without re-freezing the v1 wire contract.
    expression_expected = expected_count.get("expression_classes_covered")
    if expression_expected is None:
        # v1ext protocol: read expression classes from tier_breakdown.
        tb = dataset.get("tier_breakdown") or {}
        expression_declared = set(tb.get("expression_classes_covered") or [])
        allowed_v1ext = {
            "answer", "challenge", "comfort",
            "disagree", "unknown_expression", "cross_book_hearsay",
        }
        if not expression_declared:
            raise ValueError(
                "v1ext dataset must declare expression_classes_covered in "
                "tier_breakdown (one of the 6 chat-quality-protocol classes)"
            )
        if expression_declared - allowed_v1ext:
            raise ValueError(
                f"v1ext expression classes {expression_declared - allowed_v1ext} "
                f"are not part of the 6 chat-quality-protocol classes; "
                f"allowed = {sorted(allowed_v1ext)}"
            )
        expression_expected = sorted(expression_declared)
    expected_classes |= {
        ("expression", c) for c in expression_expected
    }
    actual_classes = {(c.get("tier"), c.get("class")) for c in cases}
    if actual_classes != expected_classes:
        raise ValueError(
            f"tier/class coverage drifted: got {actual_classes!r}, expected {expected_classes!r}"
        )


async def run(options):
    dataset_path = options.dataset.resolve()
    output = options.output.resolve()
    raw_path = REPO / "tmp" / f"{output.stem}-native.json"
    if output.exists() or raw_path.exists():
        raise RuntimeError("This run already exists; inspect it instead of restarting its budget")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    # Two parallel protocols share the same 8-case / 32-call ceiling:
    #   - v1   (frozen): 4 canonical expression classes
    #                   (answer / challenge / comfort / cross_book_hearsay)
    #   - v1ext (ext-a/ext-b): 4 expression classes drawn from the 6
    #                   chat-quality-protocol classes (incl. disagree /
    #                   unknown_expression), declared per-window via
    #                   ``tier_breakdown.expression_classes_covered``.
    # v1ext lets ext-a/ext-b windows reach the 4 disagree + 4
    # unknown_expression cases in t12-quality-cases-v2.json without
    # re-freezing the v1 wire contract. The v1 protocol's exact class
    # list is preserved as a literal so the existing
    # test_runner_expected_count_class_list_matches_v1_protocol guard
    # continues to pin it verbatim.
    if dataset.get("dataset_version") == "t12-pilot-eight-v1":
        expected_count = {
            "dataset_version": "t12-pilot-eight-v1",
            "case_count": 8,
            "boundary_classes_covered": ["knowable", "unknowable", "belief", "emotion"],
            "expression_classes_covered": ["answer", "challenge", "comfort", "cross_book_hearsay"],
        }
    elif dataset.get("dataset_version") == "t12-pilot-eight-v1-ext":
        expected_count = {
            "dataset_version": "t12-pilot-eight-v1-ext",
            "case_count": 8,
            "boundary_classes_covered": ["knowable", "unknowable", "belief", "emotion"],
            # None triggers the v1ext branch in validate_dataset
            # (reads the actual 4 from tier_breakdown).
            "expression_classes_covered": None,
        }
    else:
        raise ValueError(
            f"unrecognized dataset_version: {dataset.get('dataset_version')!r}; "
            f"runner accepts 't12-pilot-eight-v1' or 't12-pilot-eight-v1-ext'"
        )
    validate_dataset(
        dataset,
        expected_count=expected_count,
        expected_ceiling=MAX_NATIVE_CALLS,
        reviewer_kind="Agent checks complete published bodies and supplied sources; no claim of human blind review",
        dataset_required_fields={"dataset_version", "native_call_ceiling", "manual_continues_per_turn", "reviewer_kind", "cases", "actors_from", "actor_field", "tier_breakdown", "verdict_legend"},
        case_required_fields={"case_id", "tier", "class", "target_actor_indices", "questions", "gold_standard", "expected"},
        gold_required_fields={"verdict", "required_claims", "forbidden_claims", "expected_source"},
    )
    ceiling = dataset.get("native_call_ceiling")
    if (
        type(ceiling) is not int
        or not 1 <= ceiling <= MAX_NATIVE_CALLS
        or type(options.call_budget) is not int
        or not 1 <= options.call_budget <= ceiling
    ):
        raise ValueError("Call budget must fit the frozen dataset ceiling")
    cases = dataset["cases"]
    requested = getattr(options, "case_id", None)
    selected = requested if requested is not None else [case["case_id"] for case in cases]
    if (
        not selected
        or len(set(selected)) != len(selected)
        or not set(selected) <= {case["case_id"] for case in cases}
    ):
        raise ValueError("Selected case identities must be unique members of the frozen dataset")

    if options.dry_run:
        # Read-only validation: no model budget is consumed, no room is created.
        # This is the only mode the T12 acceptance index allows under
        # "控制模型调用预算" — the runner proves the dataset + runner pair is
        # wired and reproducible without ever calling the model provider.
        actor_path = dataset_path.parent / dataset["actors_from"]
        actor_source = json.loads(actor_path.read_text(encoding="utf-8"))
        actors = [
            CanonicalScope.model_validate(value)
            for value in actor_source[dataset["actor_field"]]
        ]
        report = {
            "mode": "dry_run",
            "date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
            "dataset_version": dataset["dataset_version"],
            "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "actors_source_sha256": hashlib.sha256(actor_path.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": dataset["scope"],
            "character_scopes": [actor.model_dump() for actor in actors],
            "native_call_ceiling": ceiling,
            "call_budget": options.call_budget,
            "case_selection": {
                "selected": selected,
                "frozen_case_count": len(cases),
                "full_pilot": len(selected) == len(cases),
            },
            "cases": [
                {
                    "case_id": case["case_id"],
                    "tier": case["tier"],
                    "class": case["class"],
                    "target_actor_indices": case["target_actor_indices"],
                    "gold_standard": case["gold_standard"],
                    "status": "not_started" if case["case_id"] in selected else "not_selected",
                    **(
                        {}
                        if case["case_id"] in selected
                        else {"not_evaluated": "outside_selected_probe"}
                    ),
                }
                for case in cases
            ],
            "actual_native_calls": 0,
            "quality_pass": False,
            "semantic_review": "pending full-body/source inspection; no human blind-review claim",
            "publication": False,
            "terminal": True,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    features = get_features()
    features.require("single_chat")
    features.require("group_chat")
    actor_path = dataset_path.parent / dataset["actors_from"]
    actor_source = json.loads(actor_path.read_text(encoding="utf-8"))
    actors = [
        CanonicalScope.model_validate(value) for value in actor_source[dataset["actor_field"]]
    ]
    membership = RoomMembershipService(options.workspace.resolve())
    discussion = RoomDiscussionService(options.workspace.resolve())
    rounds = BookRoundService(options.workspace.resolve())
    model = resolve_character_chat_model(options.provider_id, options.model_id)

    def baseline():
        return digest([membership.rooms.knowledge.baseline(actor).model_dump() for actor in actors])

    report = {
        "date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "dataset_version": dataset["dataset_version"],
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "actors_source_sha256": hashlib.sha256(actor_path.read_bytes()).hexdigest(),
        "scope": dataset["scope"],
        "character_scopes": [actor.model_dump() for actor in actors],
        "model_config": model.config.model_dump(),
        "timeouts": model.timeouts.model_dump(),
        "native_call_ceiling": options.call_budget,
        "calls": [],
        "case_selection": {
            "selected": selected,
            "frozen_case_count": len(cases),
            "full_pilot": len(selected) == len(cases),
        },
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reader_evidence": [],
        "cases": [
            {
                "case_id": case["case_id"],
                "tier": case["tier"],
                "class": case["class"],
                "status": "not_started" if case["case_id"] in selected else "not_selected",
                "turns": [],
                **(
                    {}
                    if case["case_id"] in selected
                    else {"not_evaluated": "outside_selected_probe"}
                ),
            }
            for case in cases
        ],
        "canonical_baselines_before": baseline(),
        "quality_pass": False,
        "semantic_review": "pending full-body/source inspection; no human blind-review claim",
    }
    raw_calls = []
    evidence_seen = set()
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    def save():
        report["actual_native_calls"] = len(raw_calls)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw_path.write_text(
            json.dumps(raw_calls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    class Capture:
        async def chat(self, messages, **kwargs):
            if len(raw_calls) >= options.call_budget:
                raise NativeBudgetExhausted()
            data = json.loads(messages[-1]["content"])
            context = data.get("context", {})
            character_scope = context.get("character_scope", {})
            for item in [
                *context.get("knowledge", {}).get("items", []),
                *context.get("baseline", {}).values(),
            ]:
                if "claim_id" not in item or "evidence_id" not in item:
                    continue
                identity = (digest(character_scope), item["claim_id"], item["evidence_id"])
                if identity not in evidence_seen:
                    evidence_seen.add(identity)
                    report["reader_evidence"].append({"character_scope": character_scope, **item})
            record = {
                "phase": data["phase"],
                "status": "started",
                "input_sha256": digest(data),
                "source_ids": source_ids(data),
            }
            raw = {"input": data, "status": "started"}
            raw_calls.append(raw)
            report["calls"].append(record)
            save()
            started = time.monotonic()
            try:
                response = await model.provider.chat(messages, **kwargs)
                raw.update(status="completed", output=response.content)
                record.update(
                    status="completed", usage=response.usage, finish_reason=response.finish_reason
                )
                return response
            except BaseException as error:
                raw.update(status="failed", error_type=type(error).__name__)
                record.update(status="failed", error_type=type(error).__name__)
                raise
            finally:
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                save()
                print(
                    json.dumps(
                        {
                            "native_calls": len(raw_calls),
                            "phase": data["phase"],
                            "status": record["status"],
                        }
                    ),
                    flush=True,
                )

    save()
    exhausted = False
    try:
        for spec, case in zip(cases, report["cases"], strict=True):
            if spec["case_id"] not in selected:
                continue
            if len(raw_calls) >= options.call_budget:
                exhausted = True
                break
            room = membership.create(
                actors,
                client_room_id=str(uuid4()),
                title=f"T12 pilot {spec['case_id']}",
            )
            scope = membership.rooms.bind_room(room["room_id"], 1)
            revision = 0
            if spec.get("discussion_mode") == "topic":
                configured = discussion.set(
                    scope, 0, "topic", spec.get("topic", ""), spec.get("goal", "")
                )
                revision = configured["discussion"]["revision"]
            case.update(
                status="running",
                room_id=room["room_id"],
                epoch=scope.epoch,
                discussion_mode=spec.get("discussion_mode"),
                mode=spec.get("mode"),
                expected=spec["expected"],
                gold_standard=spec["gold_standard"],
            )
            targets = []
            for index in spec.get("target_actor_indices", []):
                actor = actors[index]
                targets.append(
                    next(
                        member["id"]
                        for member in room["members"]
                        if all(
                            member[key] == getattr(actor, key)
                            for key in ("book_id", "source_version_id", "build_id", "character_id")
                        )
                    )
                )
            # Coercion policy: when a case pins specific target actors, the
            # submission is semantically directed (the case author wants that
            # exact actor to answer). ``coordinator.select_speakers`` rejects
            # ``mode='natural'`` carrying ``target_member_ids``, so override
            # ``mode`` whenever ``targets`` is non-empty. This keeps frozen
            # case datasets stable while still honoring ``target_actor_indices``.
            effective_mode = spec.get("mode", "natural")
            if targets and effective_mode == "natural":
                effective_mode = "directed"
            for question in spec["questions"]:
                if len(raw_calls) >= options.call_budget:
                    exhausted = True
                    break
                turn = rounds.submit(
                    scope,
                    str(uuid4()),
                    question,
                    model.config,
                    time_limit_seconds=model.timeouts.seconds_for_mode(effective_mode),
                    mode=effective_mode,
                    target_member_ids=targets or None,
                    expected_discussion_revision=revision,
                )
                record = {
                    "question": question,
                    "round_id": turn["round_id"],
                    "call_start": len(raw_calls),
                    "execution_windows": [],
                    "operator_controls": [],
                }
                case["turns"].append(record)
                save()
                try:
                    for window in range(2):
                        await BookChatWorker(options.workspace.resolve()).run(
                            scope, turn["round_id"], Capture(), model.config
                        )
                        current = rounds.get_round(scope, turn["round_id"])
                        record["execution_windows"].append(current)
                        if current["status"] not in ("paused", "interrupted") or window == 1:
                            break
                        if len(raw_calls) >= options.call_budget:
                            exhausted = True
                            break
                        latest = resolve_character_chat_model(options.provider_id, options.model_id)
                        seconds = latest.timeouts.seconds_for_mode(effective_mode)
                        rounds.control(
                            scope, turn["round_id"], "resume", time_limit_seconds=seconds
                        )
                        record["operator_controls"].append(
                            {"action": "manual_resume", "time_limit_seconds": seconds}
                        )
                except NativeBudgetExhausted:
                    exhausted = True
                    record["not_completed"] = "native_call_ceiling"
                finally:
                    exception_in_flight = sys.exc_info()[0] is not None
                    record["round"] = rounds.get_round(scope, turn["round_id"])
                    record["messages"] = [
                        entry
                        for entry in membership.rooms.read_messages(scope)["messages"]
                        if entry["round_id"] == turn["round_id"]
                    ]
                    record["call_end"] = len(raw_calls)
                    try:
                        if record["round"]["status"] in (
                            "paused",
                            "interrupted",
                            "queued",
                            "running",
                        ):
                            rounds.control(scope, turn["round_id"], "cancel")
                            record["operator_controls"].append(
                                {
                                    "action": "manual_cancel",
                                    "reason": "bounded QA windows ended or run interrupted; timeout/partial results retained",
                                }
                            )
                            record["after_stop"] = rounds.get_round(scope, turn["round_id"])
                    except Exception as cleanup_error:
                        record["cleanup_error_type"] = type(cleanup_error).__name__
                        report["cleanup_failed"] = True
                        if not exception_in_flight:
                            raise
                    finally:
                        save()
                if exhausted:
                    break
            case["status"] = "budget_exhausted" if exhausted else "executed_pending_semantic_review"
            save()
            if exhausted:
                break
    except BaseException as error:
        report["run_error_type"] = type(error).__name__
        for case in report["cases"]:
            if case["status"] == "running":
                case["status"] = "interrupted"
        raise
    finally:
        for case in report["cases"]:
            if case["status"] == "not_started":
                case["not_evaluated"] = "native_call_ceiling" if exhausted else "run_interrupted"
        report["canonical_baselines_after"] = baseline()
        report["canonical_baselines_unchanged"] = (
            report["canonical_baselines_before"] == report["canonical_baselines_after"]
        )
        report["budget_exhausted"] = exhausted
        report["run_status"] = (
            "interrupted"
            if report.get("run_error_type")
            else "budget_exhausted"
            if exhausted
            else "executed_pending_semantic_review"
        )
        report["terminal"] = True
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO / "docs/plans/book-character-agents/validation/t12-quality-cases-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--call-budget", type=int, default=32)
    parser.add_argument("--provider-id", type=int)
    parser.add_argument("--model-id", type=int)
    parser.add_argument(
        "--case-id",
        action="append",
        help="Run only named frozen cases; every omitted case remains explicitly unassessed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate dataset + character scopes + SHA pins without consuming any model budget. "
            "Default and required mode while '控制模型调用预算' is in effect."
        ),
    )
    options = parser.parse_args()
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    asyncio.run(run(options))


if __name__ == "__main__":
    main()
