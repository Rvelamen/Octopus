"""Inline wire removes a redundant registry, never source/identity validation."""

import copy
import json

import pytest
from test_book_discovery import story
from test_book_numbered_discovery import input_data

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService
from backend.services.book_world.discovery_inline import assemble_inline
from backend.services.book_world.discovery_models import DiscoveryConfig
from backend.services.book_world.discovery_numbered import prepare_numbered
from backend.services.book_world.storage import connect


def reply():
    return {
        "scenes": [
            {"s": [0], "c": {"a": {"n": "人物甲", "e": 0, "k": 0, "at": "active"}}},
            {
                "s": [1],
                "c": {
                    "a": {"n": "人物甲", "e": 1, "k": 0, "at": "silent"},
                    "b": {"n": "人物乙", "e": 1, "uncertain": True, "at": "active"},
                },
            },
        ]
    }


def validate(value, data=None):
    data = data or input_data()
    expanded = assemble_inline(json.dumps(value, ensure_ascii=False), prepare_numbered(data))
    return BookDiscoveryService._validate_result(json.dumps(expanded, ensure_ascii=False), data)


def test_inline_keeps_one_known_binding_literal_spans_and_uncertain_candidates():
    result = validate(reply())
    assert result.scenes[0].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[1].identity == "uncertain"
    data = input_data()
    for scene in result.scenes:
        for character in scene.characters:
            proof = character.evidence
            source = next(s for s in data["segments"] if s["id"] == proof.segment_id)
            assert proof.quote == source["text"][proof.local_start : proof.local_end]


@pytest.mark.parametrize(
    "defect",
    [
        "foreign_anchor",
        "foreign_known",
        "foreign_segment",
        "wrong_scene",
        "unsupported_name",
        "unsupported_alias",
        "missing_segment",
        "duplicate_segment",
        "duplicate_known",
        "binding_change",
        "known_uncertain",
        "known_anonymous",
        "kind_change",
        "extra_field",
    ],
)
def test_inline_invalid_references_and_identity_changes_fail_closed(defect):
    value = reply()
    person = value["scenes"][0]["c"]["a"]
    if defect == "foreign_anchor":
        person["e"] = 999
    elif defect == "foreign_known":
        person["k"] = 999
    elif defect == "foreign_segment":
        value["scenes"][0]["s"] = [999]
    elif defect == "wrong_scene":
        person["e"] = 1
    elif defect == "unsupported_name":
        person["n"] = "原文没有"
    elif defect == "unsupported_alias":
        person["a"] = [{"n": "原文没有", "e": 0}]
    elif defect == "missing_segment":
        value["scenes"].pop()
    elif defect == "duplicate_segment":
        value["scenes"][1]["s"] = [0, 1]
    elif defect == "duplicate_known":
        value["scenes"][0]["c"]["another"] = copy.deepcopy(person)
    elif defect == "binding_change":
        value["scenes"][1]["c"]["a"].pop("k")
    elif defect == "known_uncertain":
        person["uncertain"] = True
    elif defect == "known_anonymous":
        person["anonymous"] = True
    elif defect == "kind_change":
        value["scenes"][1]["c"]["a"]["kind"] = "group"
    else:
        person["p"] = 0
    with pytest.raises(ValueError):
        validate(value)


@pytest.mark.parametrize(
    "fragment",
    [
        '"a":{"n":"人物甲","e":0,"at":"active"},"a":{"n":"人物乙","e":0,"at":"active"}',
        '"a":{"n":"人物甲","n":"人物乙","e":0,"at":"active"}',
    ],
)
def test_inline_duplicate_json_keys_cannot_silently_discard_candidates(fragment):
    raw = '{"scenes":[{"s":[0],"c":{' + fragment + "}}]}"
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        assemble_inline(raw, prepare_numbered(input_data()))


def test_inline_dense_multiscene_output_preserves_original_capacity_above_256_people():
    data = {"segments": [], "known_characters": []}
    value = {"scenes": []}
    for s in range(4):
        names = [f"候选{i:03d}" for i in range(s * 70, min(257, (s + 1) * 70))]
        data["segments"].append({"id": str(s), "text": "、".join(names), "ordinal": s})
        value["scenes"].append(
            {"s": [s], "c": {n: {"n": n, "e": 0, "at": "referenced"} for n in names}}
        )
    packet = prepare_numbered(data)
    for s, scene in enumerate(value["scenes"]):
        for person in scene["c"].values():
            person["e"] = next(
                a["e"] for a in packet["anchors"] if a["s"] == s and person["n"] in a["t"]
            )
    assert sum(len(s.characters) for s in validate(value, data).scenes) == 257


def test_inline_anonymous_keeps_independent_uncertainty_and_repeated_literal_occurrence():
    data = {
        "segments": [{"id": "s", "ordinal": 0, "text": "他走来，他又走开。"}],
        "known_characters": [],
    }
    value = {
        "scenes": [
            {
                "s": [0],
                "c": {"anon": {"n": "他", "e": 0, "o": 1, "anonymous": True, "at": "uncertain"}},
            }
        ]
    }
    character = validate(value, data).scenes[0].characters[0]
    assert (
        character.anonymous
        and character.identity == "uncertain"
        and character.entity_kind == "unknown"
    )
    assert character.existing_character_id is None
    value["scenes"][0]["c"]["anon"]["o"] = 3
    with pytest.raises(ValueError):
        validate(value, data)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [None, "cancel", "delete"])
async def test_inline_worker_repairs_literal_in_scene_and_fences_late_results(book_library, action):
    import asyncio

    item, source = story(book_library, '人物甲说："这不是秘密"。\n\n人物乙经过，人物甲安坐。')
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v15"
    )
    build = service.create_build(item, source, config)
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                assert data["phase"] == "discovery_inline" and "known" in data
                value = reply()
                for scene in value["scenes"]:
                    scene["c"]["a"].pop("k")
                value["scenes"][1]["c"]["b"]["n"] = "未出现的称呼"
            else:
                assert data["phase"] == "discovery_repair_windows"
                assert len(data["repair_targets"]) == 1
                assert all(a["s"] == 1 for a in data["anchors"])
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
                            "at": "active",
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
            assert not db.execute(
                "SELECT 1 FROM book_build_steps WHERE build_id=? AND status='validated'",
                (build["build_id"],),
            ).fetchone()
    else:
        assert service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
        people = service.list_characters(item, build["build_id"])["characters"]
        assert next(p for p in people if p["name"] == "人物乙")["agent_status"] == "needs_review"
        with connect(service.db_path) as db:
            result = json.loads(
                db.execute(
                    "SELECT result_json FROM book_build_steps WHERE build_id=?",
                    (build["build_id"],),
                ).fetchone()[0]
            )["result"]
            assert (
                "people" not in result
                and result["scenes"][0]["characters"][0]["evidence"]["segment_id"]
            )


@pytest.mark.asyncio
async def test_inline_worker_duplicate_json_never_partially_persists_or_exceeds_two_calls(
    book_library,
):
    item, source = story(book_library, "人物甲走来。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v15"
    )
    build = service.create_build(item, source, config)
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 2:
                assert "Duplicate JSON object key" in data["previous_error"]
            return LLMResponse(
                content='{"scenes":[{"s":[0],"c":{"a":{"n":"人物甲","e":0,"at":"active"},"a":{"n":"乙","e":0,"at":"silent"}}}]}'
            )

    await service.run(build["build_id"], Provider(), config)
    assert len(seen) == 2 and service.get_build(item, build["build_id"])["status"] == "failed"
    with connect(service.db_path) as db:
        assert not db.execute(
            "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
        ).fetchone()
