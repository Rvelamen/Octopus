"""One identity binding per person still requires every original source guard."""

import copy
import json
from pathlib import Path

import pytest
from test_book_discovery import story
from test_book_numbered_discovery import input_data

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService
from backend.services.book_world.discovery_grouped import assemble_grouped
from backend.services.book_world.discovery_models import DiscoveryConfig
from backend.services.book_world.discovery_numbered import WINDOW_OVERLAP, prepare_numbered
from backend.services.book_world.discovery_repair import prepare_repair
from backend.services.book_world.discovery_selection import apply_selection, prepare_selection
from backend.services.book_world.discovery_window_repair import (
    apply_window_repair,
    prepare_window_repair,
)
from backend.services.book_world.storage import connect


def reply():
    return {
        "scenes": [{"s": [0]}, {"s": [1]}],
        "people": [
            {
                "identity": 0,
                "appearances": [
                    {"scene": 0, "n": "人物甲", "e": 0, "at": "active"},
                    {"scene": 1, "n": "人物甲", "e": 1, "at": "silent"},
                ],
            },
            {
                "identity": "uncertain",
                "appearances": [{"scene": 1, "n": "人物乙", "e": 1, "at": "referenced"}],
            },
        ],
    }


def validate(value, data=None):
    data = data or input_data()
    expanded = assemble_grouped(json.dumps(value, ensure_ascii=False), prepare_numbered(data))
    return BookDiscoveryService._validate_result(json.dumps(expanded, ensure_ascii=False), data)


def test_grouped_one_binding_keeps_all_appearances_and_literal_source_spans():
    data = input_data()
    result = validate(reply(), data)
    assert result.scenes[0].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[1].identity == "uncertain"
    for scene in result.scenes:
        for person in scene.characters:
            proof = person.evidence
            source = next(s for s in data["segments"] if s["id"] == proof.segment_id)
            assert proof.quote == source["text"][proof.local_start : proof.local_end]


@pytest.mark.parametrize(
    "defect",
    [
        "foreign_anchor",
        "foreign_scene",
        "foreign_known",
        "negative_known",
        "bool_known",
        "string_known",
        "foreign_segment",
        "negative_segment",
        "wrong_scene",
        "unsupported_name",
        "unsupported_alias",
        "missing_segment",
        "duplicate_segment",
        "duplicate_known",
        "duplicate_scene",
        "unused_person",
        "identity_flag",
        "malformed_presence",
        "extra_scene_field",
    ],
)
def test_grouped_fails_closed_for_invalid_references_bindings_and_extra_fields(defect):
    value = reply()
    person = value["people"][0]
    appearance = person["appearances"][0]
    if defect == "foreign_anchor":
        appearance["e"] = 999
    elif defect == "foreign_scene":
        appearance["scene"] = 999
    elif defect == "foreign_known":
        person["identity"] = 999
    elif defect == "negative_known":
        person["identity"] = -1
    elif defect == "bool_known":
        person["identity"] = True
    elif defect == "string_known":
        person["identity"] = "0"
    elif defect == "foreign_segment":
        value["scenes"][0]["s"] = [999]
    elif defect == "negative_segment":
        value["scenes"][0]["s"] = [-1]
    elif defect == "wrong_scene":
        appearance["e"] = 1
    elif defect == "unsupported_name":
        appearance["n"] = "别处人名"
    elif defect == "unsupported_alias":
        appearance["a"] = [{"n": "别处人名", "e": 0}]
    elif defect == "missing_segment":
        value["scenes"].pop()
    elif defect == "duplicate_segment":
        value["scenes"][1]["s"] = [0, 1]
    elif defect == "duplicate_known":
        value["people"].append(copy.deepcopy(person))
    elif defect == "duplicate_scene":
        person["appearances"].append(copy.deepcopy(appearance))
    elif defect == "unused_person":
        person["appearances"] = []
    elif defect == "identity_flag":
        person["uncertain"] = True
    elif defect == "malformed_presence":
        appearance["at"] = "present"
    else:
        value["scenes"][0]["c"] = []
    with pytest.raises(ValueError):
        validate(value)


def test_grouped_missing_presence_is_uncertain_and_anonymous_never_gets_a_known_identity():
    value = reply()
    value["people"][0]["appearances"][0].pop("at")
    assert validate(value).scenes[0].characters[0].presence == "uncertain"
    data = {
        "segments": [{"id": "s", "ordinal": 0, "text": "他走来，他又走开。"}],
        "known_characters": [],
    }
    value = {
        "scenes": [{"s": [0]}],
        "people": [
            {"identity": "anonymous", "appearances": [{"scene": 0, "n": "他", "e": 0, "o": 1}]}
        ],
    }
    person = validate(value, data).scenes[0].characters[0]
    assert person.anonymous and person.entity_kind == "unknown" and person.identity == "uncertain"
    assert person.existing_character_id is None
    value["people"][0]["appearances"][0]["e"] = 999
    with pytest.raises(ValueError):
        validate(value, data)


def test_grouped_duplicate_json_keys_never_silently_drop_an_appearance():
    raw = '{"scenes":[{"s":[0]}],"people":[{"identity":"new","appearances":[{"scene":0,"n":"人物甲","n":"人物乙","e":0}]}]}'
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        assemble_grouped(raw, prepare_numbered(input_data()))


def test_grouped_dense_output_keeps_original_multiscene_capacity_above_256_people():
    data = {"segments": [], "known_characters": []}
    value = {"scenes": [], "people": []}
    for scene in range(4):
        names = [f"人物{i:03d}" for i in range(scene * 70, min(257, (scene + 1) * 70))]
        data["segments"].append({"id": str(scene), "ordinal": scene, "text": "、".join(names)})
        value["scenes"].append({"s": [scene]})
        for name in names:
            value["people"].append(
                {
                    "identity": "new",
                    "appearances": [{"scene": scene, "n": name, "e": 0, "at": "referenced"}],
                }
            )
    packet = prepare_numbered(data)
    for person in value["people"]:
        a = person["appearances"][0]
        a["e"] = next(
            x["e"] for x in packet["anchors"] if x["s"] == a["scene"] and a["n"] in x["t"]
        )
    assert sum(len(s.characters) for s in validate(value, data).scenes) == 257


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [None, "cancel", "delete"])
async def test_grouped_worker_locally_repairs_then_fences_persistence(book_library, action):
    import asyncio

    item, source = story(book_library, '人物甲说："这不是秘密"。\n\n人物乙经过，人物甲安坐。')
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
                assert data["phase"] == "discovery_grouped" and "known" in data
                value = reply()
                value["people"][0]["identity"] = "new"
                value["people"][1]["appearances"][0]["n"] = "没有的名字"
            else:
                assert data["phase"] == "discovery_repair_windows"
                assert len(data["repair_targets"]) == 1 and all(
                    a["s"] == 1 for a in data["anchors"]
                )
                entered.set()
                if action:
                    await release.wait()
                value = {
                    "repairs": [
                        {
                            "scene_index": 1,
                            "character_index": 1,
                            "identity": "uncertain",
                            "n": "人物乙",
                            "e": data["anchors"][0]["e"],
                            "at": "referenced",
                        }
                    ]
                }
            return LLMResponse(content=json.dumps(value))

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
    if action:
        with connect(service.db_path) as db:
            assert not db.execute(
                "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
            ).fetchone()
    else:
        assert service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
        people = service.list_characters(item, build["build_id"])["characters"]
        assert next(p for p in people if p["name"] == "人物乙")["agent_status"] == "needs_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("always_invalid", [False, True])
async def test_grouped_worker_structure_retry_is_precise_bounded_and_atomic(
    book_library, always_invalid
):
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
            if len(seen) == 2:
                assert "repeated scene 0" in data["previous_error"]
                assert data["phase"] == "discovery_unit_mentions"
                mention = {"n": "人物甲", "e": 0, "at": "active"}
                if always_invalid:
                    mention["o"] = 999
                return LLMResponse(
                    content=json.dumps({"people": [{"identity": "new", "mentions": [mention]}]})
                )
            a = {"scene": 0, "n": "人物甲", "e": 0, "at": "active"}
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [{"s": [0]}],
                        "people": [
                            {
                                "identity": "new",
                                "appearances": [a, a] if always_invalid or len(seen) == 1 else [a],
                            }
                        ],
                    }
                )
            )

    await service.run(build["build_id"], Provider(), config)
    assert len(seen) == 2
    result = service.get_build(item, build["build_id"])
    assert (
        result["status"] == "failed" if always_invalid else result["stage"] == "discovery_complete"
    )
    if always_invalid:
        with connect(service.db_path) as db:
            assert not db.execute(
                "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
            ).fetchone()


@pytest.mark.parametrize("book", ["西游记", "红楼梦"])
def test_production_grouped_codec_replays_frozen_native_failure_and_local_repair(book):
    # Replay only: these native calls already happened; no model or quality claim.
    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    source = next(
        c
        for c in json.loads(
            (base / "real-model-grouped-discovery-v1.json").read_text(encoding="utf8")
        )["cases"]
        if c["book"] == book
    )
    repair = next(
        c
        for c in json.loads(
            (base / "real-model-grouped-repair-v1.json").read_text(encoding="utf8")
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
        "unit_key": "3",
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
    numbered = prepare_numbered(data)
    assert numbered["input"]["anchors"] == wire["anchors"]
    assert numbered["input"]["known"] == wire["known"]
    expanded = json.dumps(assemble_grouped(source["output"], numbered), ensure_ascii=False)
    with pytest.raises(ValueError, match="unambiguous matching alias"):
        BookDiscoveryService._validate_result(expanded, data)
    packet = prepare_repair(
        expanded,
        data,
        BookDiscoveryService._validate_result,
        allow_uncertain_split=True,
        allow_binding_split=True,
    )
    selected = prepare_selection(packet, data)
    if selected is not None:
        result = apply_selection(
            repair["output"], selected, data, BookDiscoveryService._validate_result
        )
    else:
        windowed = prepare_window_repair(packet, data)
        result = apply_window_repair(
            repair["output"], windowed, data, BookDiscoveryService._validate_result
        )
    assert sum(len(s.characters) for s in result.scenes) == repair["appearances"]
    assert (
        sum(c.identity == "uncertain" for s in result.scenes for c in s.characters)
        == repair["uncertain"]
    )
