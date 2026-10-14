"""A single targeted correction retains valid entries and remains behind the build lease."""

import asyncio
import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_book_discovery import RecordedProvider, story

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.discovery_models import DiscoveryResult
from backend.services.book_world.discovery_repair import apply_repair, prepare_repair
from backend.services.book_world.storage import connect


class RepairProvider:
    def __init__(self, *, corrupt=False, hold=False):
        self.inputs = []
        self.initial = None
        self.corrupt = corrupt
        self.hold = hold
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.inputs.append(data)
        segment = data["segments"][0]

        def span(quote):
            start = segment["text"].index(quote)
            return {
                "segment_id": segment["id"],
                "quote": quote,
                "local_start": start,
                "local_end": start + len(quote),
            }

        if len(self.inputs) == 1:
            self.initial = {
                "scenes": [
                    {
                        "segment_ids": [row["id"] for row in data["segments"]],
                        "characters": [
                            {
                                "name": "人物甲",
                                "local_character_key": "a",
                                "presence": "active",
                                "evidence": span("他离开。"),
                            },
                            {
                                "name": "人物乙",
                                "local_character_key": "b",
                                "presence": "silent",
                                "evidence": span("人物乙安坐。"),
                            },
                        ],
                    }
                ]
            }
            result = self.initial
        else:
            assert data["phase"] == "discovery_repair"
            assert "repair_packet" not in data and "candidate" not in data
            assert len(data["repair_targets"]) == 1
            target = data["repair_targets"][0]
            assert (target["scene_index"], target["character_index"]) == (0, 0)
            fixed = copy.deepcopy(target["character"])
            fixed["evidence"] = span("人物甲开口")
            self.entered.set()
            if self.hold:
                await self.release.wait()
            result = {
                "repairs": [
                    {
                        "scene_index": 0,
                        "character_index": 1 if self.corrupt else 0,
                        "replacement": fixed,
                    }
                ]
            }
        return LLMResponse(content=json.dumps(result, ensure_ascii=False))


class ChoiceProvider(RepairProvider):
    async def chat(self, messages, **kwargs):
        if not self.inputs:
            return await super().chat(messages, **kwargs)
        data = json.loads(messages[-1]["content"])
        self.inputs.append(data)
        assert data["phase"] == "discovery_repair_choices"
        assert "segments" not in data and "known_characters" not in data
        target = data["repair_targets"][0]
        assert "character" not in target and "candidate" not in data
        choice = next(option for option in target["choices"] if option["name"] == "人物甲")
        self.entered.set()
        if self.hold:
            await self.release.wait()
        return LLMResponse(
            content=json.dumps(
                {
                    "repairs": [
                        {
                            "scene_index": 0,
                            "character_index": 0,
                            "identity": "preserve",
                            "presence": "active",
                            "evidence_choice": 999 if self.corrupt else choice["id"],
                        }
                    ]
                }
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", [False, True])
async def test_choice_repair_uses_exact_server_source_and_preserves_other_entries(
    book_library, corrupt
):
    item, source = story(book_library, "人物甲开口，他离开。人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v12"
    )
    build = service.create_build(item, source, config)
    provider = ChoiceProvider(corrupt=corrupt)
    await service.run(build["build_id"], provider, config)
    outcome = service.get_build(item, build["build_id"])
    assert len(provider.inputs) == 2
    if corrupt:
        assert outcome["status"] == "failed"
        assert not service.list_characters(item, build["build_id"])["characters"]
    else:
        assert outcome["stage"] == "discovery_complete"
        with connect(service.db_path) as db:
            saved = json.loads(
                db.execute(
                    "SELECT result_json FROM book_build_steps WHERE build_id=?",
                    (build["build_id"],),
                ).fetchone()[0]
            )["result"]
        untouched = DiscoveryResult.model_validate(provider.initial).model_dump()["scenes"][0][
            "characters"
        ][1]
        assert saved["scenes"][0]["characters"][1] == untouched
        evidence = saved["scenes"][0]["characters"][0]["evidence"]
        assert "人物甲" in evidence["quote"]
        assert evidence["local_end"] > evidence["local_start"]


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", [False, True])
async def test_targeted_retry_retains_valid_characters_and_cannot_patch_other_entries(
    book_library, corrupt
):
    item, source = story(book_library, "人物甲开口，他离开。人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v8"
    )
    build = service.create_build(item, source, config)
    provider = RepairProvider(corrupt=corrupt)
    await service.run(build["build_id"], provider, config)
    outcome = service.get_build(item, build["build_id"])
    assert len(provider.inputs) == 2
    if corrupt:
        assert outcome["status"] == "failed"
        assert service.list_characters(item, build["build_id"])["characters"] == []
    else:
        assert outcome["stage"] == "discovery_complete"
        with connect(service.db_path) as db:
            saved = json.loads(
                db.execute(
                    "SELECT result_json FROM book_build_steps WHERE build_id=?",
                    (build["build_id"],),
                ).fetchone()[0]
            )["result"]
        expected = DiscoveryResult.model_validate(provider.initial).model_dump()
        assert saved["scenes"][0]["characters"][1] == expected["scenes"][0]["characters"][1]
        assert [person["name"] for person in saved["scenes"][0]["characters"]] == [
            "人物甲",
            "人物乙",
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "delete"])
@pytest.mark.parametrize("version", ["character-discovery-v8", "character-discovery-v12"])
async def test_late_targeted_repair_cannot_publish_after_cancellation_or_delete(
    book_library, action, version
):
    item, source = story(book_library, "人物甲开口，他离开。人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", prompt_version=version)
    build = service.create_build(item, source, config)
    provider = ChoiceProvider(hold=True) if version.endswith("v12") else RepairProvider(hold=True)
    task = asyncio.create_task(service.run(build["build_id"], provider, config))
    try:
        await asyncio.wait_for(provider.entered.wait(), 5)
        if action == "cancel":
            service.cancel_build(item, build["build_id"])
        else:
            assert book_library.delete_item(item)
        provider.release.set()
        await task
        with connect(service.db_path) as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM book_characters WHERE build_id=?", (build["build_id"],)
                ).fetchone()[0]
                == 0
            )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def choice_fixture():
    from backend.services.book_world.discovery_selection import prepare_selection

    data = {
        "segments": [
            {"id": "s1", "text": "士隐说话。他离开。"},
            {"id": "s2", "text": "人物乙安坐。另一场景的秘密。"},
        ],
        "known_characters": [
            {
                "id": "known",
                "name": "甄士隐",
                "aliases": [{"alias": "甄士隐", "review_state": "candidate"}],
            }
        ],
    }
    first = {
        "local_character_key": "same",
        "name": "甄士隐",
        "presence": "active",
        "identity": "existing",
        "existing_character_id": "known",
        "evidence": {"segment_id": "s1", "local_start": 0, "local_end": 0, "quote": "他离开。"},
    }
    second = {
        "local_character_key": "other",
        "name": "人物乙",
        "presence": "silent",
        "evidence": {"segment_id": "s2", "local_start": 0, "local_end": 6, "quote": "人物乙安坐。"},
    }
    raw = json.dumps(
        {
            "scenes": [
                {"segment_ids": ["s1"], "characters": [first]},
                {"segment_ids": ["s2"], "characters": [second]},
            ]
        }
    )
    packet = prepare_repair(
        raw, data, BookDiscoveryService._validate_result, allow_uncertain_split=True
    )
    return data, prepare_selection(packet, data)


@pytest.mark.parametrize(
    "mutation", ["valid", "preserve", "alias", "foreign", "duplicate", "other_target"]
)
def test_source_choices_are_scoped_and_cannot_claim_an_unconfirmed_alias(mutation):
    from backend.services.book_world.discovery_selection import apply_selection, selection_input

    data, packet = choice_fixture()
    frozen = copy.deepcopy(packet)
    offered = selection_input(packet)
    assert "另一场景的秘密" not in json.dumps(offered, ensure_ascii=False)
    assert all(c["evidence"]["segment_id"] == "s1" for c in packet["targets"][0]["choices"])
    choice = next(c for c in packet["targets"][0]["choices"] if c["name"] == "士隐")
    assert not choice["can_preserve"]
    repair = {
        "scene_index": 0,
        "character_index": 0,
        "identity": "uncertain",
        "presence": "active",
        "evidence_choice": choice["id"],
    }
    if mutation == "preserve":
        repair["identity"] = "preserve"
    if mutation == "alias":
        repair["alias_choices"] = [choice["id"]]
    if mutation == "foreign":
        choice["evidence"].update(segment_id="s2", quote="人物乙安坐。", local_start=0, local_end=6)
    if mutation == "other_target":
        repair["scene_index"] = 1
    raw = json.dumps({"repairs": [repair, repair] if mutation == "duplicate" else [repair]})
    if mutation == "valid":
        result = apply_selection(raw, packet, data, BookDiscoveryService._validate_result)
        person = result.scenes[0].characters[0]
        assert person.name == "士隐" and person.identity == "uncertain"
        assert person.existing_character_id is None
        assert person.local_character_key == packet["targets"][0]["independent_local_key"]
        assert not person.aliases
        assert result.scenes[1].characters[0].name == "人物乙"
        assert packet == frozen
    else:
        with pytest.raises(ValueError):
            apply_selection(raw, packet, data, BookDiscoveryService._validate_result)


def test_choice_input_is_bounded_and_only_offered_ids_remain_in_packet():
    from backend.services.book_world.discovery_selection import (
        MAX_INPUT_BYTES,
        SELECTION_PROMPT,
        SelectedRepairs,
        apply_selection,
        prepare_selection,
        selection_input,
    )

    data, packet = choice_fixture()
    data["segments"][0]["text"] = "士隐说话。他离开。" * 12
    # Many independently scoped targets exercise the optional-choice trimming.
    template = packet["targets"][0]
    packet["targets"] = [{**copy.deepcopy(template), "scene_index": i} for i in range(8)]
    prepared = prepare_selection(packet, data)
    assert prepared is not None
    assert (
        len(json.dumps(selection_input(prepared), ensure_ascii=False).encode()) <= MAX_INPUT_BYTES
    )
    assert all(target["choices"] for target in prepared["targets"])
    assert sum(len(t["choices"]) for t in prepared["targets"]) < 8 * 4
    # A pruned option must not remain selectable from an internal superset.
    for target in prepared["targets"]:
        missing = {0, 1, 2, 3} - {choice["id"] for choice in target["choices"]}
        if missing:
            with pytest.raises(ValueError, match="not offered"):
                apply_selection(
                    json.dumps(
                        {
                            "repairs": [
                                {
                                    "scene_index": target["scene_index"],
                                    "character_index": 0,
                                    "identity": "uncertain",
                                    "presence": "active",
                                    "evidence_choice": min(missing),
                                }
                            ]
                        }
                    ),
                    prepared,
                    data,
                    BookDiscoveryService._validate_result,
                )
            break
    assert (
        len(
            (
                SELECTION_PROMPT
                + json.dumps(SelectedRepairs.model_json_schema(), ensure_ascii=False)
            ).encode()
        )
        < 5000
    )
    packet["targets"] = [{**copy.deepcopy(template), "scene_index": i} for i in range(128)]
    assert prepare_selection(packet, data) is None


def test_registered_literal_alias_can_preserve_existing_identity():
    from backend.services.book_world.discovery_selection import apply_selection, prepare_selection

    data, packet = choice_fixture()
    data["known_characters"][0]["aliases"].append({"alias": "士隐", "review_state": "candidate"})
    packet = prepare_selection(packet, data)
    choice = next(c for c in packet["targets"][0]["choices"] if c["name"] == "士隐")
    assert choice["can_preserve"]
    result = apply_selection(
        json.dumps(
            {
                "repairs": [
                    {
                        "scene_index": 0,
                        "character_index": 0,
                        "identity": "preserve",
                        "presence": "active",
                        "evidence_choice": choice["id"],
                    }
                ]
            }
        ),
        packet,
        data,
        BookDiscoveryService._validate_result,
    )
    assert result.scenes[0].characters[0].existing_character_id == "known"
    assert result.scenes[0].characters[0].local_character_key == "same"


@pytest.mark.asyncio
async def test_no_source_choices_falls_back_to_one_complete_regeneration(book_library):
    item, source = story(book_library, "人物甲开口。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v12"
    )
    build = service.create_build(item, source, config)

    class NoChoice(RecordedProvider):
        async def chat(self, messages, **kwargs):
            response = await super().chat(messages, **kwargs)
            assert self.inputs[-1].get("phase") != "discovery_repair_choices"
            if len(self.inputs) == 1:
                value = json.loads(response.content)
                value["scenes"][0]["characters"][0]["name"] = "无此姓名"
                return LLMResponse(content=json.dumps(value))
            return response

    provider = NoChoice()
    await service.run(build["build_id"], provider, config)
    assert len(provider.inputs) == 2
    assert service.get_build(item, build["build_id"])["stage"] == "discovery_complete"


def test_failed_repair_checkpoint_cannot_restore_deleted_source(book_library, monkeypatch):
    item, source = story(book_library, "人物甲开口，他离开。人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build_id = service.create_build(item, source, config)["build_id"]
    owner, generation = service._lease(build_id, config)
    data = service._input(build_id, owner, generation, config)
    entered, release = threading.Event(), threading.Event()
    original_fence = service._fence

    def pause_after_fence(*args):
        result = original_fence(*args)
        entered.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(service, "_fence", pause_after_fence)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            service._failed_attempt,
            build_id,
            owner,
            generation,
            data["unit_key"],
            "invalid repair",
            repair_packet={"candidate": "人物甲开口，他离开。"},
            record_repair=True,
        )
        try:
            assert entered.wait(10)
            # Coordinate the race without sleeps. A writer holding the fence must
            # finish before deletion; an unfenced writer resumes after deletion.
            probe = sqlite3.connect(str(service.db_path), timeout=0)
            try:
                try:
                    probe.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    assert "locked" in str(error)
                    release.set()
                else:
                    probe.rollback()
            finally:
                probe.close()
            assert book_library.delete_item(item)
        finally:
            release.set()
            pending.result(timeout=10)
    with connect(service.db_path) as db:
        rows = db.execute(
            "SELECT result_json FROM book_build_steps WHERE build_id=?", (build_id,)
        ).fetchall()
        assert rows and all(json.loads(row[0]) == {} for row in rows)


@pytest.mark.parametrize(
    "structural_error", ["duplicate", "conflicting_binding", "duplicate_existing"]
)
def test_mixed_character_and_structure_errors_require_full_retry(structural_error):
    data = {
        "segments": [
            {"id": "s1", "text": "人物甲开口，他离开。"},
            {"id": "s2", "text": "人物乙安坐。"},
        ],
        "known_characters": [
            {
                "id": "known-a",
                "name": "人物甲",
                "aliases": [{"alias": "人物甲", "review_state": "candidate"}],
            }
        ],
    }
    first = {
        "name": "人物甲",
        "local_character_key": "same",
        "presence": "active",
        "evidence": {"segment_id": "s1", "local_start": 6, "local_end": 10, "quote": "他离开。"},
    }
    second = {
        "name": "人物乙",
        "local_character_key": "same",
        "presence": "active",
        "evidence": {"segment_id": "s2", "local_start": 0, "local_end": 6, "quote": "人物乙安坐。"},
    }
    if structural_error == "duplicate":
        scenes = [{"segment_ids": ["s1", "s2"], "characters": [first, second]}]
    elif structural_error == "duplicate_existing":
        first.update(identity="existing", existing_character_id="known-a")
        second.update(
            identity="existing", existing_character_id="known-a", local_character_key="other"
        )
        data["known_characters"][0]["aliases"].append(
            {"alias": "人物乙", "review_state": "candidate"}
        )
        scenes = [{"segment_ids": ["s1", "s2"], "characters": [first, second]}]
    else:
        first.update(identity="existing", existing_character_id="known-a")
        scenes = [
            {"segment_ids": ["s1"], "characters": [first]},
            {"segment_ids": ["s2"], "characters": [second]},
        ]
    assert (
        prepare_repair(json.dumps({"scenes": scenes}), data, BookDiscoveryService._validate_result)
        is None
    )


@pytest.mark.parametrize("replacement_key", ["fresh-anonymous", "same", "reserved"])
@pytest.mark.parametrize("original_identity", ["new", "existing"])
@pytest.mark.parametrize("split_kind", ["anonymous", "named"])
def test_anonymous_repair_can_only_split_into_a_fresh_local_identity(
    replacement_key, original_identity, split_kind
):
    data = {
        "segments": [
            {"id": "s1", "text": "人物甲走来。人物乙安坐。"},
            {"id": "s2", "text": "他离开。"},
        ],
        "known_characters": [
            {
                "id": "known-a",
                "name": "人物甲",
                "aliases": [{"alias": "人物甲", "review_state": "candidate"}],
            }
        ],
    }
    first = {
        "name": "人物甲",
        "local_character_key": "same",
        "presence": "active",
        "identity": "existing",
        "existing_character_id": "known-a",
        "evidence": {"segment_id": "s1", "local_start": 0, "local_end": 6, "quote": "人物甲走来。"},
    }
    if original_identity == "new":
        first.update(identity="new", existing_character_id=None)
    second = {
        **first,
        "evidence": {"segment_id": "s2", "local_start": 0, "local_end": 4, "quote": "他离开。"},
    }
    reserved = {
        **first,
        "local_character_key": "reserved",
        "identity": "new",
        "existing_character_id": None,
        "name": "人物乙",
        "evidence": {
            "segment_id": "s1",
            "local_start": 6,
            "local_end": 12,
            "quote": "人物乙安坐。",
        },
    }
    original = {
        "scenes": [
            {"segment_ids": ["s1"], "characters": [first, reserved]},
            {"segment_ids": ["s2"], "characters": [second]},
        ]
    }
    packet = prepare_repair(
        json.dumps(original),
        data,
        BookDiscoveryService._validate_result,
        allow_anonymous_split=split_kind == "anonymous",
        allow_uncertain_split=split_kind == "named",
    )
    replacement = {
        **second,
        "local_character_key": packet["targets"][0][
            "anonymous_local_key" if split_kind == "anonymous" else "independent_local_key"
        ]
        if replacement_key == "fresh-anonymous"
        else replacement_key,
        "name": "他",
        "anonymous": split_kind == "anonymous",
        "entity_kind": "unknown" if split_kind == "anonymous" else "person",
        "identity": "uncertain",
        "existing_character_id": None,
    }
    raw = json.dumps(
        {"repairs": [{"scene_index": 1, "character_index": 0, "replacement": replacement}]}
    )
    if replacement_key == "fresh-anonymous":
        result = apply_repair(raw, packet, data, BookDiscoveryService._validate_result)
        assert result.scenes[1].characters[0].existing_character_id is None
        assert (
            result.scenes[0].characters[0].model_dump()
            == DiscoveryResult.model_validate(original).scenes[0].characters[0].model_dump()
        )
    else:
        with pytest.raises(ValueError):
            apply_repair(raw, packet, data, BookDiscoveryService._validate_result)
