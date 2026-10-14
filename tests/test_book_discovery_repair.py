"""A single targeted correction retains valid entries and remains behind the build lease."""

import asyncio
import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_book_discovery import story

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
async def test_late_targeted_repair_cannot_publish_after_cancellation_or_delete(
    book_library, action
):
    item, source = story(book_library, "人物甲开口，他离开。人物乙安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", prompt_version="character-discovery-v8"
    )
    build = service.create_build(item, source, config)
    provider = RepairProvider(hold=True)
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
