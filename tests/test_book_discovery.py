"""Discovery service boundaries: full coverage, candidate-only output and fixed scopes."""

import asyncio
import json

import pytest

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.source import BookSourceService, BookWorldError


def story(library, text):
    path = library.workspace_root / "story.txt"
    path.write_text(text, encoding="utf-8")
    item = library.create_item(pdf_path=path, metadata={"title": "故事", "item_type": "book"})
    library.import_text_attachment(item["id"], path)
    source = BookSourceService(library.workspace_root).prepare_source(item["id"])
    return item["id"], source["source_version_id"]


class RecordedProvider:
    def __init__(self):
        self.inputs = []

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.inputs.append(data)
        rows = data["segments"]
        return LLMResponse(
            content=json.dumps(
                {
                    "scenes": [
                        {
                            "segment_ids": [row["id"] for row in rows],
                            "characters": [
                                {
                                    "name": "人物甲",
                                    "local_character_key": "character-a",
                                    "aliases": [],
                                    "presence": "referenced",
                                    "identity": "new",
                                    "evidence": {
                                        "segment_id": rows[0]["id"],
                                        "local_start": 0,
                                        "local_end": 3,
                                        "quote": "人物甲",
                                    },
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )


@pytest.mark.asyncio
async def test_discovery_covers_tail_is_idempotent_and_keeps_candidates(book_library):
    item_id, version = story(book_library, "人物甲被提起。\n人物甲离开。\n人物甲在全书末尾出现。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=128)
    first = service.create_build(item_id, version, config)
    assert service.create_build(item_id, version, config)["build_id"] == first["build_id"]
    provider = RecordedProvider()
    await service.run(first["build_id"], provider, config)
    result = service.get_build(item_id, first["build_id"])
    assert result["stage"] == "discovery_complete"
    assert result["processed_segments"] == result["total_segments"] == 3
    assert provider.inputs[0]["segments"][-1]["text"] == "人物甲在全书末尾出现。"
    catalog = service.list_characters(item_id, first["build_id"])
    assert [row["name"] for row in catalog["characters"]] == ["人物甲"]
    assert catalog["characters"][0]["agent_status"] == "candidate"
    assert catalog["characters"][0]["appearances"][0]["presence"] == "referenced"
    other_id, _ = story(book_library, "另一部书。")
    with pytest.raises(BookWorldError):
        service.get_build(other_id, first["build_id"])


@pytest.mark.asyncio
async def test_same_names_stay_ambiguous_when_model_does_not_identify_them(book_library):
    item_id, version = story(book_library, "人物甲" + "走" * 100 + "。\n人物甲" + "说" * 100 + "。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=128)
    build = service.create_build(item_id, version, config)
    provider = RecordedProvider()
    await asyncio.gather(
        service.run(build["build_id"], provider, config),
        service.run(build["build_id"], provider, config),
    )
    assert len(provider.inputs) == 2  # Two units, despite concurrent duplicate workers.
    rows = service.list_characters(item_id, build["build_id"])["characters"]
    assert len(rows) == 2
    assert all(row["agent_status"] == "needs_review" for row in rows)
    assert all(row["aliases"][0]["review_state"] == "ambiguous" for row in rows)


@pytest.mark.asyncio
async def test_failed_unit_retries_twice_then_manual_retry_keeps_good_checkpoint(book_library):
    item_id, version = story(book_library, "人物甲" + "走" * 100 + "。\n人物甲" + "说" * 100 + "。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=128)
    build = service.create_build(item_id, version, config)

    class BrokenProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            response = await super().chat(messages, **kwargs)
            return response if len(self.inputs) == 1 else LLMResponse(content='{"not": "valid"}')

    broken = BrokenProvider()
    await service.run(build["build_id"], broken, config)
    failed = service.get_build(item_id, build["build_id"])
    assert failed["status"] == "failed"
    assert failed["completed_units"] == failed["failed_units"] == 1
    assert len(broken.inputs) == 3
    service.retry_build(item_id, build["build_id"])
    good = RecordedProvider()
    await service.run(build["build_id"], good, config)
    assert len(good.inputs) == 1
    assert service.get_build(item_id, build["build_id"])["stage"] == "discovery_complete"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "delete"])
async def test_late_result_cannot_publish_after_cancellation_or_source_deletion(
    book_library, action
):
    item_id, version = story(book_library, "人物甲被提起。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build = service.create_build(item_id, version, config)
    started, release = asyncio.Event(), asyncio.Event()

    class SlowProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            started.set()
            await release.wait()
            return await super().chat(messages, **kwargs)

    task = asyncio.create_task(service.run(build["build_id"], SlowProvider(), config))
    await asyncio.wait_for(started.wait(), 5)
    if action == "cancel":
        service.cancel_build(item_id, build["build_id"])
    else:
        book_library.delete_item(item_id)
    release.set()
    await task
    if action == "cancel":
        assert service.get_build(item_id, build["build_id"])["status"] == "cancelled"
        assert service.list_characters(item_id, build["build_id"])["characters"] == []
    else:
        with pytest.raises(BookWorldError):
            service.get_build(item_id, build["build_id"])


@pytest.mark.asyncio
async def test_fabricated_quotes_never_enter_candidate_catalog(book_library):
    item_id, version = story(book_library, "人物甲被提起。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build = service.create_build(item_id, version, config)

    class FabricatingProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            result = await super().chat(messages, **kwargs)
            return LLMResponse(content=result.content.replace("人物甲", "人物乙"))

    await service.run(build["build_id"], FabricatingProvider(), config)
    assert service.get_build(item_id, build["build_id"])["status"] == "failed"
    assert service.list_characters(item_id, build["build_id"])["characters"] == []


@pytest.mark.asyncio
async def test_same_local_identity_across_scenes_is_one_candidate(book_library):
    item_id, version = story(book_library, "人物甲被提起。\n人物甲走来。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build = service.create_build(item_id, version, config)

    class TwoSceneProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            response = await super().chat(messages, **kwargs)
            result = json.loads(response.content)
            first = result["scenes"][0]
            first["segment_ids"] = [self.inputs[0]["segments"][0]["id"]]
            second = json.loads(json.dumps(first))
            second["segment_ids"] = [self.inputs[0]["segments"][1]["id"]]
            second["characters"][0]["evidence"]["segment_id"] = second["segment_ids"][0]
            second["characters"][0]["presence"] = "active"
            result["scenes"].append(second)
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await service.run(build["build_id"], TwoSceneProvider(), config)
    rows = service.list_characters(item_id, build["build_id"])["characters"]
    assert len(rows) == 1
    assert rows[0]["agent_status"] == "candidate"
    assert sorted(row["presence"] for row in rows[0]["appearances"]) == ["active", "referenced"]


@pytest.mark.asyncio
async def test_cancelled_build_can_resume_without_late_old_result(book_library):
    item_id, version = story(book_library, "人物甲被提起。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build = service.create_build(item_id, version, config)
    service.cancel_build(item_id, build["build_id"])
    service.retry_build(item_id, build["build_id"])
    await service.run(build["build_id"], RecordedProvider(), config)
    assert service.get_build(item_id, build["build_id"])["stage"] == "discovery_complete"


def test_oversized_old_source_segment_is_rejected_before_model_call(book_library):
    item_id, version = story(book_library, "人物甲" + "走" * 200 + "。")
    service = BookDiscoveryService(book_library.workspace_root)
    with pytest.raises(BookWorldError) as error:
        service.create_build(
            item_id, version, DiscoveryConfig(model="fixture", unit_char_limit=128)
        )
    assert error.value.code == "segment_too_large"
    assert service.get_build(item_id, source_version_id=version)["status"] == "not_built"


def test_discovery_migration_keeps_a_pre_migration_backup(book_library):
    import sqlite3

    backup = book_library.workspace_root / "knowledge" / ".knowledge_index.db.pre-discovery-v15.bak"
    assert backup.is_file()
    with sqlite3.connect(backup) as db:
        applied = {row[0] for row in db.execute("SELECT id FROM _schema_migrations")}
        assert 14 in applied
        assert 15 not in applied
        assert db.execute("SELECT COUNT(*) FROM library_items").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_expired_persisted_build_resumes_from_last_validated_checkpoint(book_library):
    from backend.services.book_world.storage import connect

    item_id, version = story(book_library, "人物甲" + "走" * 100 + "。\n人物甲" + "说" * 100 + "。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=128)
    build = service.create_build(item_id, version, config)

    class CrashedProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            if len(self.inputs) == 1:
                raise asyncio.CancelledError
            return await super().chat(messages, **kwargs)

    with pytest.raises(asyncio.CancelledError):
        await service.run(build["build_id"], CrashedProvider(), config)
    assert service.get_build(item_id, build["build_id"])["can_resume"] is False
    # The storage seam models the persisted lease of a crashed process after its expiry.
    with connect(service.db_path) as db:
        db.execute(
            "UPDATE book_builds SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (build["build_id"],),
        )
    resumed = BookDiscoveryService(book_library.workspace_root)
    assert resumed.get_build(item_id, build["build_id"])["can_resume"] is True
    provider = RecordedProvider()
    await resumed.run(build["build_id"], provider, config)
    assert len(provider.inputs) == 1
    assert resumed.get_build(item_id, build["build_id"])["stage"] == "discovery_complete"


@pytest.mark.asyncio
async def test_anthropic_effort_option_is_only_sent_when_requested(monkeypatch):
    from types import SimpleNamespace

    import backend.core.providers.anthropic_provider as module

    requests = []

    async def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"ok":true}')],
            usage=SimpleNamespace(input_tokens=10, output_tokens=4),
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        module,
        "AsyncAnthropic",
        lambda **kwargs: SimpleNamespace(messages=SimpleNamespace(create=create)),
    )
    provider = module.AnthropicProvider(api_key="fixture-key", default_model="k3")
    await provider.chat([{"role": "user", "content": "Fixture"}], reasoning_effort="low")
    await provider.chat([{"role": "user", "content": "Fixture"}])
    assert requests[0]["output_config"] == {"effort": "low"}
    assert "output_config" not in requests[1]
    assert requests[0]["model"] == requests[1]["model"] == "k3"


@pytest.mark.asyncio
async def test_missing_model_is_a_visible_blocked_build(book_library, monkeypatch):
    import backend.channels.desktop.handlers.book_world as module
    from backend.channels.desktop.protocol import MessageType, WSMessage

    item_id, version = story(book_library, "人物甲被提起。")
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)

    def missing_model():
        raise BookWorldError("blocked_config", "Configure extraction model")

    monkeypatch.setattr(module, "resolve_discovery_model", missing_model)
    messages = []

    class Socket:
        async def send_json(self, message):
            messages.append(message)

    await module.BookWorldHandler(object()).handle(
        Socket(),
        WSMessage(
            type=MessageType.BOOK_WORLD,
            request_id="blocked-build",
            data={"action": "start_discovery", "item_id": item_id, "source_version_id": version},
        ),
    )
    assert messages[-1]["type"] == "book_world_result"
    assert messages[-1]["data"]["status"] == "blocked_config"
    assert messages[-1]["data"]["completed_units"] == 0


@pytest.mark.asyncio
async def test_unique_exact_quote_resolves_bad_model_offset_but_ambiguous_quote_is_rejected(
    book_library,
):
    config = DiscoveryConfig(provider_id=1, model="fixture")

    class WrongOffsetProvider(RecordedProvider):
        async def chat(self, messages, **kwargs):
            response = await super().chat(messages, **kwargs)
            result = json.loads(response.content)
            span = result["scenes"][0]["characters"][0]["evidence"]
            span.update(local_start=4, local_end=7)
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    item_id, version = story(book_library, "人物甲被提起。")
    service = BookDiscoveryService(book_library.workspace_root)
    build = service.create_build(item_id, version, config)
    await service.run(build["build_id"], WrongOffsetProvider(), config)
    row = service.list_characters(item_id, build["build_id"])["characters"][0]
    assert row["aliases"][0]["evidence"]["local_start"] == 0
    assert row["aliases"][0]["evidence"]["offset_resolution"] == "unique_quote"
    ambiguous_id, ambiguous_version = story(book_library, "人物甲被提起，人物甲再现。")
    other = service.create_build(ambiguous_id, ambiguous_version, config)
    await service.run(other["build_id"], WrongOffsetProvider(), config)
    assert service.get_build(ambiguous_id, other["build_id"])["status"] == "failed"
    assert service.list_characters(ambiguous_id, other["build_id"])["characters"] == []


@pytest.mark.asyncio
async def test_handler_cancel_during_model_call_then_immediate_retry_finishes(
    book_library, monkeypatch
):
    import backend.channels.desktop.handlers.book_world as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.book_world.discovery_provider import DiscoveryModel

    item_id, version = story(book_library, "人物甲被提起。")
    config = DiscoveryConfig(provider_id=1, model="fixture")
    started = asyncio.Event()

    class SlowFirstProvider(RecordedProvider):
        calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                started.set()
                await asyncio.Event().wait()
            return await super().chat(messages, **kwargs)

    provider = SlowFirstProvider()
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        module, "resolve_discovery_model", lambda: DiscoveryModel(provider=provider, config=config)
    )
    messages = []

    class Socket:
        async def send_json(self, message):
            messages.append(message)

    handler = module.BookWorldHandler(object())

    async def request(action, **kwargs):
        await handler.handle(
            Socket(),
            WSMessage(
                type=MessageType.BOOK_WORLD,
                data={
                    "action": action,
                    "item_id": item_id,
                    "source_version_id": version,
                    **kwargs,
                },
            ),
        )
        assert messages[-1]["type"] == "book_world_result"
        return messages[-1]["data"]

    build = await request("start_discovery")
    await asyncio.wait_for(started.wait(), 5)
    await request("cancel_build", build_id=build["build_id"])
    await request("retry_build", build_id=build["build_id"])
    deadline = asyncio.get_running_loop().time() + 5
    while asyncio.get_running_loop().time() < deadline:
        current = await request("get_build", build_id=build["build_id"])
        if current["stage"] == "discovery_complete":
            break
        await asyncio.sleep(0.01)
    assert current["stage"] == "discovery_complete"
    assert provider.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [("person", "failed"), ("group", "discovery_complete")])
async def test_combined_people_cannot_be_a_single_person_agent_candidate(
    book_library, kind, expected
):
    item_id, version = story(book_library, "千里眼、顺风耳出门。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture")
    build = service.create_build(item_id, version, config)

    class CombinedProvider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            segment_id = data["segments"][0]["id"]
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [
                            {
                                "segment_ids": [segment_id],
                                "characters": [
                                    {
                                        "name": "千里眼、顺风耳",
                                        "entity_kind": kind,
                                        "local_character_key": "pair",
                                        "presence": "active",
                                        "evidence": {
                                            "segment_id": segment_id,
                                            "local_start": 0,
                                            "local_end": 7,
                                            "quote": "千里眼、顺风耳",
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )

    await service.run(build["build_id"], CombinedProvider(), config)
    outcome = service.get_build(item_id, build["build_id"])
    assert (outcome["status"] if expected == "failed" else outcome["stage"]) == expected
    characters = service.list_characters(item_id, build["build_id"])["characters"]
    if kind == "group":
        assert characters[0]["agent_status"] == "needs_review"
    else:
        assert characters == []
