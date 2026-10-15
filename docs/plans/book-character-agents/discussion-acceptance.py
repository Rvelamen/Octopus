"""Run a frozen discussion matrix through real room services with a native-call ceiling."""

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

from loguru import logger

from backend.services.book_world.chat_provider import resolve_character_chat_model
from backend.services.book_world.chat_worker import BookChatWorker
from backend.services.book_world.discussion import RoomDiscussionService
from backend.services.book_world.features import get_features
from backend.services.book_world.knowledge_models import CanonicalScope
from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.rounds import BookRoundService


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


async def run(options):
    dataset_path = options.dataset.resolve()
    output = options.output.resolve()
    raw_path = REPO / "tmp" / f"{output.stem}-native.json"
    if output.exists() or raw_path.exists():
        raise RuntimeError("This run already exists; inspect it instead of restarting its budget")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    ceiling = dataset.get("native_call_ceiling")
    if (
        type(ceiling) is not int
        or not 1 <= ceiling <= MAX_NATIVE_CALLS
        or type(options.call_budget) is not int
        or not 1 <= options.call_budget <= ceiling
    ):
        raise ValueError("Call budget must fit the frozen dataset ceiling")
    if dataset["manual_continues_per_turn"] != 1:
        raise ValueError("Unsupported operator continuation policy")
    cases = dataset["cases"]
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case identity")
    if {(case["discussion_mode"], case["mode"]) for case in cases} != {
        (discussion, mode)
        for discussion in ("free", "topic")
        for mode in ("natural", "directed", "all")
    }:
        raise ValueError("Dataset must cover all six independent mode combinations")
    requested = getattr(options, "case_id", None)
    selected = requested if requested is not None else [case["case_id"] for case in cases]
    if (
        not selected
        or len(set(selected)) != len(selected)
        or not set(selected) <= {case["case_id"] for case in cases}
    ):
        raise ValueError("Selected case identities must be unique members of the frozen dataset")
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
            "full_matrix": len(selected) == len(cases),
        },
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime_sha256": {
            name: hashlib.sha256(
                (
                    Path(__file__).resolve().parents[3] / "backend/services/book_world" / name
                ).read_bytes()
            ).hexdigest()
            for name in (
                "chat_worker.py",
                "chat_models.py",
                "chat_validation.py",
                "context.py",
                "knowledge.py",
            )
        },
        "reader_evidence": [],
        "cases": [
            {
                "case_id": case["case_id"],
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
                title=f"T17 matrix {spec['case_id']} (excerpts)",
            )
            scope = membership.rooms.bind_room(room["room_id"], 1)
            revision = 0
            if spec["discussion_mode"] == "topic":
                configured = discussion.set(scope, 0, "topic", spec["topic"], spec["goal"])
                revision = configured["discussion"]["revision"]
            case.update(
                status="running",
                room_id=room["room_id"],
                epoch=scope.epoch,
                discussion_mode=spec["discussion_mode"],
                mode=spec["mode"],
                expected=spec["expected"],
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
            for question in spec["questions"]:
                if len(raw_calls) >= options.call_budget:
                    exhausted = True
                    break
                turn = rounds.submit(
                    scope,
                    str(uuid4()),
                    question,
                    model.config,
                    time_limit_seconds=model.timeouts.seconds_for_mode(spec["mode"]),
                    mode=spec["mode"],
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
                        seconds = latest.timeouts.seconds_for_mode(spec["mode"])
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
        default=REPO / "docs/plans/book-character-agents/validation/t17-discussion-cases-v1.json",
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
    options = parser.parse_args()
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    asyncio.run(run(options))


if __name__ == "__main__":
    main()
