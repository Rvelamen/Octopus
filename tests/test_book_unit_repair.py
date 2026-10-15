"""Whole-unit structural repair retains source, scope and the two-call ceiling."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_book_discovery import story
from test_book_numbered_discovery import input_data

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.discovery_numbered import WINDOW_OVERLAP
from backend.services.book_world.discovery_unit_repair import (
    apply_unit_repair,
    prepare_unit_repair,
    unit_repair_input,
)
from backend.services.book_world.storage import connect


def scope(data):
    encoded = json.dumps(
        data["segments"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "workspace_id": "a" * 64,
        "book_id": "book",
        "source_version_id": "source",
        "build_id": "build",
        "unit_key": data.get("unit_key", "0"),
        "input_hash": hashlib.sha256(encoded.encode()).hexdigest(),
    }


def mentions():
    return {
        "people": [
            {
                "identity": 0,
                "mentions": [
                    {"n": "人物甲", "e": 0, "at": "active"},
                    {"n": "人物甲", "e": 1, "at": "silent"},
                ],
            },
            {"identity": "uncertain", "mentions": [{"n": "人物乙", "e": 1}]},
        ]
    }


def packet(data):
    return prepare_unit_repair(data, scope(data), "Invalid structure", "b" * 64)


def apply(value, data=None):
    data = data or input_data()
    return apply_unit_repair(
        json.dumps(value, ensure_ascii=False),
        packet(data),
        data,
        scope(data),
        BookDiscoveryService._validate_result,
    )


def test_unit_mentions_preserve_known_identity_source_and_unknown_presence():
    data = input_data()
    result = apply(mentions(), data)
    assert result.scenes[0].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[1].identity == "uncertain"
    assert result.scenes[1].characters[1].presence == "uncertain"
    assert [s.segment_ids for s in result.scenes] == [["segment-a"], ["segment-b"]]
    wire = unit_repair_input(packet(data), data, scope(data))
    assert wire["phase"] == "discovery_unit_mentions"
    assert "segment-a" not in json.dumps(wire) and "known-a" not in json.dumps(wire)


@pytest.mark.parametrize("defect", ["occurrence", "literal", "anchor", "blank"])
def test_every_duplicate_raw_mention_is_validated_before_deduplication(defect):
    data = {
        "unit_key": "0",
        "segments": [{"id": "s", "text": "人物甲走来，人物甲安坐。", "ordinal": 0}],
        "known_characters": [],
    }
    bad = {"n": "人物甲", "e": 0, "o": 999}
    if defect == "literal":
        bad["n"] = "未出现的名字"
    elif defect == "anchor":
        bad["e"] = 999
    elif defect == "blank":
        bad["n"] = " "
    with pytest.raises(ValueError):
        apply(
            {"people": [{"identity": "new", "mentions": [{"n": "人物甲", "e": 0, "o": 0}, bad]}]},
            data,
        )


def test_coalescing_preserves_distinct_names_and_conservatively_handles_presence_conflicts():
    data = {
        "unit_key": "0",
        "segments": [{"id": "s", "text": "人物甲又称阿甲，人物甲走来。", "ordinal": 0}],
        "known_characters": [],
    }
    result = apply(
        {
            "people": [
                {
                    "identity": "new",
                    "mentions": [
                        {"n": "人物甲", "e": 0, "at": "active"},
                        {"n": "阿甲", "e": 0, "at": "referenced"},
                        {"n": "人物甲", "e": 0, "at": "active"},
                    ],
                }
            ]
        },
        data,
    )
    person = result.scenes[0].characters[0]
    assert person.name == "人物甲" and person.presence == "uncertain"
    assert [a.alias for a in person.aliases] == ["阿甲"]


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "book_id",
        "source_version_id",
        "build_id",
        "unit_key",
        "input_hash",
        "catalog_hash",
        "anchors_hash",
    ],
)
def test_saved_unit_packet_cannot_borrow_any_other_scope_or_number_table(field):
    data = input_data()
    saved = packet(data)
    if field in saved["scope"]:
        saved["scope"][field] = (
            "c" * 64 if field.endswith("hash") or field == "workspace_id" else "foreign"
        )
    else:
        saved[field] = "c" * 64
    with pytest.raises(ValueError):
        unit_repair_input(saved, data, scope(data))


@pytest.mark.parametrize(
    "defect", ["known", "bool_known", "duplicate_known", "extra", "anonymous_occurrence"]
)
def test_unit_protocol_retains_strict_identity_and_anonymous_reference_checks(defect):
    value = mentions()
    if defect == "known":
        value["people"][0]["identity"] = 999
    elif defect == "bool_known":
        value["people"][0]["identity"] = True
    elif defect == "duplicate_known":
        value["people"].append(copy.deepcopy(value["people"][0]))
    elif defect == "extra":
        value["people"][0]["scene"] = 0
    else:
        value["people"][0] = {
            "identity": "anonymous",
            "mentions": [{"n": "未具名", "e": 0, "o": 0}],
        }
    with pytest.raises(ValueError):
        apply(value)


def test_capacity_and_duplicate_keys_fail_instead_of_dropping_names():
    data = {
        "unit_key": "0",
        "segments": [{"id": "s", "text": "、".join(f"别名{i}" for i in range(14)), "ordinal": 0}],
        "known_characters": [],
    }
    with pytest.raises(ValueError):
        apply(
            {
                "people": [
                    {"identity": "new", "mentions": [{"n": f"别名{i}", "e": 0} for i in range(14)]}
                ]
            },
            data,
        )
    original = input_data()
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        apply_unit_repair(
            '{"people":[],"people":[]}',
            packet(original),
            original,
            scope(original),
            BookDiscoveryService._validate_result,
        )
    with pytest.raises(ValueError):
        apply_unit_repair(
            " " * 100001,
            packet(original),
            original,
            scope(original),
            BookDiscoveryService._validate_result,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [None, "cancel", "delete"])
async def test_wire_failure_uses_second_unit_protocol_and_late_results_remain_fenced(
    book_library, action
):
    import asyncio

    item, source = story(book_library, "人物甲经过。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v16"
    )
    build = service.create_build(item, source, config)
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                assert data["phase"] == "discovery_grouped"
                return LLMResponse(content="{")
            assert data["phase"] == "discovery_unit_mentions"
            entered.set()
            if action:
                await release.wait()
            return LLMResponse(
                content=json.dumps(
                    {
                        "people": [
                            {
                                "identity": "new",
                                "mentions": [{"n": "人物甲", "e": 0, "at": "active"}],
                            }
                        ]
                    }
                )
            )

    worker = asyncio.create_task(service.run(build["build_id"], Provider(), config))
    try:
        if action:
            await asyncio.wait_for(entered.wait(), 10)
            if action == "cancel":
                service.cancel_build(item, build["build_id"])
            else:
                assert book_library.delete_item(item)
            release.set()
        await worker
    finally:
        release.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
    assert len(seen) == 2
    with connect(service.db_path) as db:
        valid = db.execute(
            "SELECT 1 FROM book_build_steps WHERE build_id=? AND status='validated'",
            (build["build_id"],),
        ).fetchone()
        people = db.execute(
            "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
        ).fetchone()
    assert bool(valid) == (action is None) and bool(people) == (action is None)
    if action is None:
        with connect(service.db_path) as db:
            saved = json.loads(
                db.execute(
                    "SELECT result_json FROM book_build_steps WHERE build_id=? AND status='validated'",
                    (build["build_id"],),
                ).fetchone()[0]
            )
        assert saved["repair_provenance"]["selection_protocol"] == "source-unit-mentions-v1"


@pytest.mark.asyncio
async def test_failed_unit_repair_stops_after_two_calls_and_never_persists_a_prefix(book_library):
    item, source = story(book_library, "人物甲经过。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v16"
    )
    build = service.create_build(item, source, config)
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                return LLMResponse(content="{")
            assert data["phase"] == "discovery_unit_mentions"
            return LLMResponse(
                content=json.dumps(
                    {
                        "people": [
                            {
                                "identity": "new",
                                "mentions": [
                                    {"n": "人物甲", "e": 0},
                                    {"n": "人物甲", "e": 0, "o": 999},
                                ],
                            }
                        ]
                    }
                )
            )

    await service.run(build["build_id"], Provider(), config)
    assert len(seen) == 2 and service.get_build(item, build["build_id"])["status"] == "failed"
    with connect(service.db_path) as db:
        assert not db.execute(
            "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
        ).fetchone()


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", [False, True])
async def test_process_restart_reuses_scoped_second_attempt_or_rejects_corrupted_packet(
    book_library, monkeypatch, tamper
):
    import asyncio
    from datetime import datetime, timedelta, timezone

    import backend.services.book_world.discovery as module

    clock = [datetime(2026, 10, 15, tzinfo=timezone.utc)]
    monkeypatch.setattr(
        module,
        "_now",
        lambda seconds=0: (clock[0] + timedelta(seconds=seconds)).isoformat(
            timespec="milliseconds"
        ),
    )
    item, source = story(book_library, "人物甲经过。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v16"
    )
    build = service.create_build(item, source, config)
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                return LLMResponse(content="{")
            assert data["phase"] == "discovery_unit_mentions"
            return LLMResponse(
                content=json.dumps(
                    {
                        "people": [
                            {
                                "identity": "new",
                                "mentions": [{"n": "人物甲", "e": 0, "at": "active"}],
                            }
                        ]
                    }
                )
            )

    original_input = service._input

    def interrupted(*args, **kwargs):
        if len(seen) == 1:
            raise asyncio.CancelledError()
        return original_input(*args, **kwargs)

    monkeypatch.setattr(service, "_input", interrupted)
    with pytest.raises(asyncio.CancelledError):
        await service.run(build["build_id"], Provider(), config)
    with connect(service.db_path) as db:
        saved = json.loads(
            db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=?", (build["build_id"],)
            ).fetchone()[0]
        )
        assert saved["repair_packet"]["selection_protocol"] == "source-unit-mentions-v1"
        if tamper:
            saved["repair_packet"]["scope"]["build_id"] = "another-build"
            db.execute(
                "UPDATE book_build_steps SET result_json=? WHERE build_id=?",
                (json.dumps(saved), build["build_id"]),
            )
    clock[0] += timedelta(seconds=1000)
    monkeypatch.setattr(service, "_input", original_input)
    assert service.get_build(item, build["build_id"])["can_resume"]
    await service.run(build["build_id"], Provider(), config)
    result = service.get_build(item, build["build_id"])
    if tamper:
        assert len(seen) == 1 and result["error_code"] == "repair_scope_changed"
    else:
        assert len(seen) == 2 and result["stage"] == "discovery_complete"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["truncated", "timeout", "literal_no_local_repair", "name_capacity", "location_capacity"]
)
async def test_non_structure_errors_do_not_trigger_whole_unit_repair(
    book_library, monkeypatch, reason
):
    import backend.services.book_world.discovery as module

    item, source = story(book_library, "人物甲经过。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v16"
    )
    build = service.create_build(item, source, config)
    seen = []
    if reason == "literal_no_local_repair":
        monkeypatch.setattr(module, "prepare_repair", lambda *args, **kwargs: None)

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            assert data["phase"] == "discovery_grouped"
            if len(seen) == 1:
                if reason == "timeout":
                    raise TimeoutError()
                if reason == "truncated":
                    return LLMResponse(content="{", finish_reason="length")
            name = "不存在的称呼" if len(seen) == 1 else "人物甲"
            scene = {"s": [0]}
            if len(seen) == 1 and reason == "name_capacity":
                name = "甲" * 81
            if len(seen) == 1 and reason == "location_capacity":
                scene["l"] = "山" * 121
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [scene],
                        "people": [
                            {
                                "identity": "new",
                                "appearances": [{"scene": 0, "n": name, "e": 0, "at": "active"}],
                            }
                        ],
                    }
                )
            )

    await service.run(build["build_id"], Provider(), config)
    assert (
        len(seen) == 2
        and service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
    )


@pytest.mark.asyncio
async def test_explicit_coverage_failure_can_recover_without_dropping_source_segments(book_library):
    item, source = story(book_library, "人物甲经过。\n\n人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v16"
    )
    build = service.create_build(item, source, config)
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                return LLMResponse(content=json.dumps({"scenes": [{"s": [0]}], "people": []}))
            assert data["phase"] == "discovery_unit_mentions" and len(data["segments"]) == 2
            return LLMResponse(
                content=json.dumps(
                    {
                        "people": [
                            {
                                "identity": "new",
                                "mentions": [{"n": "人物甲", "e": 0, "at": "active"}],
                            },
                            {
                                "identity": "new",
                                "mentions": [{"n": "人物乙", "e": 1, "at": "silent"}],
                            },
                        ]
                    }
                )
            )

    await service.run(build["build_id"], Provider(), config)
    result = service.get_build(item, build["build_id"])
    assert (
        len(seen) == 2
        and result["processed_segments"] == 2
        and result["stage"] == "discovery_complete"
    )


@pytest.mark.asyncio
async def test_legacy_numbered_strategy_keeps_its_original_retry_protocol(book_library):
    item, source = story(book_library, "人物甲经过。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v14"
    )
    build = service.create_build(item, source, config)
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            assert data["phase"] == "discovery_numbered"
            if len(seen) == 1:
                return LLMResponse(content="{")
            return LLMResponse(
                content=json.dumps(
                    {
                        "people": [{"i": 0}],
                        "scenes": [
                            {"s": [0], "c": [{"p": 0, "n": "人物甲", "e": 0, "at": "active"}]}
                        ],
                    }
                )
            )

    await service.run(build["build_id"], Provider(), config)
    assert (
        len(seen) == 2
        and service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
    )


def test_unit_repair_preserves_original_multiscene_capacity_without_truncating():
    data = {"unit_key": "0", "segments": [], "known_characters": []}
    value = {"people": []}
    for s in range(4):
        names = [f"人物{i:03d}" for i in range(s * 70, min(257, (s + 1) * 70))]
        data["segments"].append({"id": str(s), "text": "、".join(names), "ordinal": s})
        value["people"].extend(
            {"identity": "new", "mentions": [{"n": n, "e": 0, "at": "referenced"}]} for n in names
        )
    wire = unit_repair_input(packet(data), data, scope(data))
    for person in value["people"]:
        m = person["mentions"][0]
        m["e"] = next(a["e"] for a in wire["anchors"] if m["n"] in a["t"])
    assert sum(len(s.characters) for s in apply(value, data).scenes) == 257
    names = [f"人物{i:03d}" for i in range(81)]
    data = {
        "unit_key": "0",
        "segments": [{"id": "one", "text": "、".join(names), "ordinal": 0}],
        "known_characters": [],
    }
    wire = unit_repair_input(packet(data), data, scope(data))
    value = {
        "people": [
            {
                "identity": "new",
                "mentions": [{"n": n, "e": next(a["e"] for a in wire["anchors"] if n in a["t"])}],
            }
            for n in names
        ]
    }
    with pytest.raises(ValueError):
        apply(value, data)


@pytest.mark.parametrize("book", ["西游记", "红楼梦"])
def test_all_frozen_native_mentions_pass_the_production_guard_before_coalescing(book):
    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    source = next(
        c
        for c in json.loads(
            (base / "real-model-mentions-discovery-v1.json").read_text(encoding="utf8")
        )["cases"]
        if c["book"] == book
    )
    wire = source["input"]
    segments = []
    for s in wire["segments"]:
        anchors = [wire["anchors"][i] for i in s["e"]]
        segments.append(
            {
                "id": f"segment-{s['s']}",
                "ordinal": s["s"],
                "text": anchors[0]["t"] + "".join(a["t"][WINDOW_OVERLAP:] for a in anchors[1:]),
            }
        )
    data = {
        "unit_key": wire["unit_key"],
        "segments": segments,
        "known_characters": [
            {
                "id": f"known-{k['k']}",
                "name": k["names"][0],
                "aliases": [{"alias": n, "review_state": "candidate"} for n in k["names"]],
            }
            for k in wire["known"]
        ],
    }
    result = apply_unit_repair(
        source["output"], packet(data), data, scope(data), BookDiscoveryService._validate_result
    )
    assert sum(len(s.characters) for s in result.scenes) == source["appearances"]
    assert [s.segment_ids[0] for s in result.scenes] == [s["id"] for s in data["segments"]]
