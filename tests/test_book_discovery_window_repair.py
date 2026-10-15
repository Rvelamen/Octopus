"""Development reproducer for a failed full-source label, before integration."""

import copy
import json

import pytest
from test_book_discovery import story

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService
from backend.services.book_world.discovery_models import DiscoveryConfig, DiscoveryResult
from backend.services.book_world.discovery_numbered import assemble_numbered, prepare_numbered
from backend.services.book_world.discovery_repair import prepare_repair
from backend.services.book_world.discovery_selection import prepare_selection
from backend.services.book_world.discovery_window_repair import (
    apply_window_repair,
    prepare_window_repair,
    window_repair_input,
)
from backend.services.book_world.storage import connect


def failure():
    text = "石兄，你这一去可有什么消息？那僧答道：且待分明。"
    data = {
        "unit_key": "2",
        "segments": [
            {"id": "s0", "ordinal": 0, "text": text},
            {"id": "s1", "ordinal": 1, "text": "甲坐在门外。"},
        ],
        "known_characters": [
            {
                "id": "known",
                "name": "石头",
                "aliases": [{"alias": "石头", "review_state": "candidate"}],
            }
        ],
    }

    def person(key, name, segment, quote, **extra):
        return {
            "local_character_key": key,
            "name": name,
            "presence": "active",
            "evidence": {
                "segment_id": segment,
                "local_start": 0,
                "local_end": len(quote),
                "quote": quote,
            },
            **extra,
        }

    raw = json.dumps(
        {
            "scenes": [
                {
                    "segment_ids": ["s0"],
                    "characters": [
                        person(
                            "stone",
                            "石头",
                            "s0",
                            text,
                            identity="existing",
                            existing_character_id="known",
                        )
                    ],
                },
                {"segment_ids": ["s1"], "characters": [person("a", "甲", "s1", "甲坐在门外。")]},
            ]
        },
        ensure_ascii=False,
    )
    packet = prepare_repair(
        raw,
        data,
        BookDiscoveryService._validate_result,
        allow_uncertain_split=True,
        allow_binding_split=True,
    )
    assert packet is not None and prepare_selection(packet, data) is None
    return data, packet


def response(**changes):
    return json.dumps(
        {
            "repairs": [
                {
                    "scene_index": 0,
                    "character_index": 0,
                    "identity": "uncertain",
                    "n": "石兄",
                    "e": 0,
                    "at": "active",
                    **changes,
                }
            ]
        },
        ensure_ascii=False,
    )


def test_window_repair_fixes_literal_without_guessing_identity_or_changing_valid_entries():
    data, packet = failure()
    original = copy.deepcopy(packet)
    windows = prepare_window_repair(packet, data)
    assert windows is not None
    wire = window_repair_input(windows)
    assert wire["phase"] == "discovery_repair_windows"
    assert all(anchor["s"] == 0 for anchor in wire["anchors"])
    assert "known" not in json.dumps(wire)
    result = apply_window_repair(response(), windows, data, BookDiscoveryService._validate_result)
    corrected = result.scenes[0].characters[0]
    assert corrected.name == "石兄" and corrected.identity == "uncertain"
    assert corrected.existing_character_id is None
    assert corrected.local_character_key == packet["targets"][0]["independent_local_key"]
    assert (
        corrected.evidence.quote
        == data["segments"][0]["text"][
            corrected.evidence.local_start : corrected.evidence.local_end
        ]
    )
    assert result.scenes[1] == DiscoveryResult.model_validate(packet["candidate"]).scenes[1]
    assert packet == original


@pytest.mark.parametrize(
    "changes",
    [
        {"e": 1},
        {"e": 999},
        {"n": "孙悟空"},
        {"identity": "preserve"},
        {"o": 99},
        {"anonymous": True, "n": "石兄", "identity": "preserve"},
        {"scene_index": 1},
        {"n": "不存在", "anonymous": True},
    ],
)
def test_window_repair_cannot_borrow_scene_identity_or_invent_sources(changes):
    data, packet = failure()
    windows = prepare_window_repair(packet, data)
    with pytest.raises(ValueError):
        apply_window_repair(
            response(**changes), windows, data, BookDiscoveryService._validate_result
        )


def test_window_repair_requires_all_targets_exactly_once_and_has_finite_input():
    data, packet = failure()
    windows = prepare_window_repair(packet, data)
    one = json.loads(response())["repairs"][0]
    for entries in [[], [one, one]]:
        with pytest.raises(ValueError):
            apply_window_repair(
                json.dumps({"repairs": entries}),
                windows,
                data,
                BookDiscoveryService._validate_result,
            )
    data["segments"][0]["text"] *= 1000
    assert prepare_window_repair(packet, data) is None


@pytest.mark.parametrize("kind", ["unique", "absent", "ambiguous", "foreign_scene"])
def test_implicit_existing_label_requires_one_offered_literal_in_the_selected_window(kind):
    data = {
        "segments": [
            {"id": "a", "ordinal": 0, "text": "石头说话。"},
            {"id": "b", "ordinal": 1, "text": "甲坐在门外。"},
        ],
        "known_characters": [
            {
                "id": "existing",
                "name": "石头",
                "aliases": [{"alias": "石头", "review_state": "candidate"}],
            }
        ],
    }
    if kind == "absent":
        data["segments"][0]["text"] = "甲说话。"
    elif kind == "ambiguous":
        data["known_characters"][0]["aliases"].append(
            {"alias": "石兄", "review_state": "candidate"}
        )
        data["segments"][0]["text"] += "石兄走来。"
    packet = prepare_numbered(data)
    raw = json.dumps(
        {
            "people": [{"i": 0, "k": 0, "state": "existing"}],
            "scenes": [
                {
                    "s": [0],
                    "c": [{"p": 0, "e": 1 if kind == "foreign_scene" else 0, "at": "active"}],
                },
                {"s": [1], "c": []},
            ],
        }
    )
    if kind == "unique":
        with pytest.raises(ValueError, match="literal label"):
            assemble_numbered(raw, packet)
        result = assemble_numbered(raw, packet, allow_implicit_name=True)
        assert (
            BookDiscoveryService._validate_result(json.dumps(result), data)
            .scenes[0]
            .characters[0]
            .name
            == "石头"
        )
    else:
        with pytest.raises(ValueError):
            result = assemble_numbered(raw, packet, allow_implicit_name=True)
            BookDiscoveryService._validate_result(json.dumps(result), data)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [None, "cancel", "delete"])
async def test_v14_worker_repairs_unoffered_literal_once_and_rejects_revoked_publication(
    book_library, action
):
    import asyncio

    item, source = story(
        book_library, "石兄，你这一去可有什么消息？那僧答道：且待分明。\n\n甲坐在门外。"
    )
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v14"
    )
    build = service.create_build(item, source, config)
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                assert data["phase"] == "discovery_numbered"
                reply = {
                    "people": [{"i": 0}, {"i": 1}],
                    "scenes": [
                        {"s": [0], "c": [{"p": 0, "n": "孙悟空", "e": 0, "at": "active"}]},
                        {"s": [1], "c": [{"p": 1, "n": "甲", "e": 1, "at": "silent"}]},
                    ],
                }
                return LLMResponse(content=json.dumps(reply))
            assert data["phase"] == "discovery_repair_windows"
            assert len(data["repair_targets"]) == 1
            assert data["repair_targets"][0]["original_name"] == "孙悟空"
            entered.set()
            if action is not None:
                await release.wait()
            return LLMResponse(content=response())

    worker = asyncio.create_task(service.run(build["build_id"], Provider(), config))
    try:
        if action is not None:
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
        if action is None:
            assert service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
            candidates = service.list_characters(item, build["build_id"])["characters"]
            assert (
                next(person for person in candidates if person["name"] == "石兄")["agent_status"]
                == "needs_review"
            )
            assert {row["name"] for row in candidates} == {"石兄", "甲"}
        else:
            assert not db.execute(
                "SELECT 1 FROM book_build_steps WHERE build_id=? AND status='validated'",
                (build["build_id"],),
            ).fetchone()
            assert not db.execute(
                "SELECT 1 FROM book_characters WHERE build_id=?", (build["build_id"],)
            ).fetchone()
