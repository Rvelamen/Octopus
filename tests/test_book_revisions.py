"""Revision requests preserve published canon and require supported changes."""

import asyncio
import json

import pytest
from test_book_persona import (
    PersonaProvider,
    ScriptedPersonaProvider,
    discovered,
    quote,
    review_all,
)

from backend.core.providers.base import LLMResponse
from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.revisions import BookRevisionService, RevisionPatch
from backend.services.book_world.source import BookWorldError


async def published(library):
    item, parent = await discovered(library, "人物甲说：我最看重诚信。人物甲又名阿甲。")
    service = BookPersonaService(library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    await service.run(build["build_id"], PersonaProvider(), config)
    return item, build["build_id"], config


class RevisionReviewer:
    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        return LLMResponse(
            content=json.dumps(
                {
                    "changes": [
                        {"index": i, "supported": True, "reason": "原文明确别名关系"}
                        for i, _ in enumerate(data["changes"])
                    ]
                }
            )
        )


@pytest.mark.asyncio
async def test_supported_alias_creates_revision_without_mutating_published_parent(book_library):
    item, parent, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, parent)
    person = context["characters"][0]
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=person["id"],
        value="阿甲",
        evidence={
            "segment_id": segment["id"],
            "quote": "人物甲又名阿甲。",
            "local_start": 0,
            "local_end": 8,
        },
    )
    result = await service.create_revision(
        item, parent, context["revision"], [patch], "request-1", RevisionReviewer(), config
    )
    assert result["build_id"] != parent
    new = service.persona.discovery.list_characters(item, result["build_id"])["characters"][0]
    assert any(alias["alias"] == "阿甲" for alias in new["aliases"])
    old = service.persona.discovery.list_characters(item, parent)["characters"][0]
    assert not any(alias["alias"] == "阿甲" for alias in old["aliases"])
    assert (
        service.persona.get_agent_definition(item, parent, old["id"])["baseline"]["value:诚信"][
            "proposition"
        ]
        == "人物甲重视诚信"
    )
    repeated = await service.create_revision(
        item, parent, context["revision"], [patch], "request-1", RevisionReviewer(), config
    )
    assert repeated["build_id"] == result["build_id"]
    with pytest.raises(BookWorldError):
        await service.create_revision(
            item, parent, context["revision"], [patch], "request-2", RevisionReviewer(), config
        )
    await service.persona.run(result["build_id"], PersonaProvider(), config)
    assert service.persona.discovery.get_build(item, result["build_id"])["status"] == "published"
    assert service.get_context(item, result["build_id"])["head_build_id"] == result["build_id"]
    assert (
        service.persona.get_character(item, parent, old["id"])["reader"]["baseline"]["value:诚信"][
            "claim_id"
        ]
        != service.persona.get_character(item, result["build_id"], new["id"])["reader"]["baseline"][
            "value:诚信"
        ]["claim_id"]
    )
    assert (
        service.get_context(item, result["build_id"])["characters"][0]["lineage_id"]
        == person["lineage_id"]
    )


@pytest.mark.asyncio
async def test_supported_merge_reextracts_only_surviving_identity(book_library):
    text = "人物甲说：我最看重诚信。人物甲又名阿甲。"
    item, discovery = await discovered(
        book_library, text, (("人物甲", "active"), ("阿甲", "active"))
    )
    service = BookRevisionService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    base = service.persona.request_build(item, discovery, config)["build_id"]
    await service.persona.run(base, PersonaProvider(), config)
    context = service.get_context(item, base)
    people = {person["name"]: person for person in context["characters"]}
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="merge",
        character_id=people["阿甲"]["id"],
        target_character_id=people["人物甲"]["id"],
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    result = await service.create_revision(
        item, base, context["revision"], [patch], "merge", RevisionReviewer(), config
    )
    assert service.persona.discovery.list_characters(item, result["build_id"])["total"] == 1
    assert service.persona.discovery.list_characters(item, base)["total"] == 2
    provider = PersonaProvider()
    await service.persona.run(result["build_id"], provider, config)
    new = service.get_context(item, result["build_id"])
    assert new["characters"][0]["lineage_id"] == people["人物甲"]["lineage_id"]
    assert all(len(data["characters"]) == 1 for data in provider.inputs)
    assert (
        service.persona.get_agent_definition(item, result["build_id"], new["characters"][0]["id"])[
            "baseline"
        ]["value:诚信"]["proposition"]
        == "人物甲重视诚信"
    )


@pytest.mark.asyncio
async def test_semantic_rejection_and_absent_quote_preserve_head(book_library):
    item, base, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, base)
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=context["characters"][0]["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )

    class Reject:
        async def chat(self, *args, **kwargs):
            return LLMResponse(
                content=json.dumps(
                    {"changes": [{"index": 0, "supported": False, "reason": "身份归属不确定"}]}
                )
            )

    with pytest.raises(BookWorldError) as error:
        await service.create_revision(
            item, base, context["revision"], [patch], "reject", Reject(), config
        )
    assert error.value.code == "unsupported_revision"
    assert service.get_context(item, base)["revision"] == context["revision"]
    invalid = patch.model_copy(
        update={"evidence": patch.evidence.model_copy(update={"quote": "人物甲又名宇航员。"})}
    )
    with pytest.raises(BookWorldError) as error:
        await service.create_revision(
            item, base, context["revision"], [invalid], "absent", RevisionReviewer(), config
        )
    assert error.value.code == "unsupported_revision"


@pytest.mark.asyncio
async def test_superseded_revision_cannot_publish_and_old_version_is_usable(book_library):
    item, base, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, base)
    person = context["characters"][0]
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=person["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    old = await service.create_revision(
        item, base, context["revision"], [patch], "old-edit", RevisionReviewer(), config
    )
    current = service.get_context(item, base)
    new = await service.create_revision(
        item, base, current["revision"], [patch], "new-edit", RevisionReviewer(), config
    )
    await service.persona.run(old["build_id"], PersonaProvider(), config)
    stale = service.persona.discovery.get_build(item, old["build_id"])
    assert stale["status"] == "failed" and stale["error_code"] == "revision_conflict"
    assert (
        service.persona.get_agent_definition(item, base, person["id"])["baseline"]["value:诚信"][
            "proposition"
        ]
        == "人物甲重视诚信"
    )
    await service.persona.run(new["build_id"], PersonaProvider(), config)
    assert service.get_context(item, new["build_id"])["head_build_id"] == new["build_id"]


@pytest.mark.asyncio
async def test_reader_extension_is_visible_but_never_part_of_agent(book_library):
    item, parent, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    person = service.get_context(item, parent)["characters"][0]
    before = service.persona.get_agent_definition(item, parent, person["id"])
    saved = service.save_extension(item, parent, person["id"], "人物甲会驾驶宇宙飞船")
    assert saved["canonical"] is False
    archive = service.persona.get_character(item, parent, person["id"])
    assert archive["reader"]["extensions"][0]["text"] == "人物甲会驾驶宇宙飞船"
    assert service.persona.get_agent_definition(item, parent, person["id"]) == before


@pytest.mark.asyncio
async def test_identity_revision_cannot_replace_head_when_affected_person_is_unverified(
    book_library,
):
    text = "人物甲说：我最看重诚信。人物甲又名阿甲。人物乙说：我最看重勇气。"
    item, discovery = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "active"))
    )
    service = BookRevisionService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    base = service.persona.request_build(item, discovery, config)["build_id"]

    def extract(data):
        actor = next(person["id"] for person in data["characters"] if person["name"] == "人物乙")
        proof = quote(data["segments"][0], "人物乙说：我最看重勇气。")
        return {
            "claims": [
                {
                    "local_key": "value",
                    "kind": "trait",
                    "owner_character_id": actor,
                    "proposition": "人物乙重视勇气",
                    "slot_key": "value:勇气",
                    "evidence": [proof],
                    "access": [{"character_id": actor, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    await service.persona.run(base, ScriptedPersonaProvider(extract, review_all), config)
    context = service.get_context(item, base)
    person = next(person for person in context["characters"] if person["name"] == "人物甲")
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=person["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    child = await service.create_revision(
        item, base, context["revision"], [patch], "unverified-identity", RevisionReviewer(), config
    )

    def reject_alpha(data):
        result = review_all(data)
        result["identities"] = [
            {"character_id": person["id"], "confirmed": person["name"] == "人物乙"}
            for person in data["characters"]
        ]
        return result

    await service.persona.run(
        child["build_id"], ScriptedPersonaProvider(extract, reject_alpha), config
    )
    result = service.persona.discovery.get_build(item, child["build_id"])
    assert result["status"] == "failed" and result["error_code"] == "revision_unresolved"
    assert service.get_context(item, base)["head_build_id"] == base


@pytest.mark.asyncio
async def test_simultaneous_edits_have_one_winner_after_review(book_library):
    item, base, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, base)
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=context["characters"][0]["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )

    class BarrierReviewer(RevisionReviewer):
        def __init__(self):
            self.arrivals = 0
            self.both_arrived = asyncio.Event()

        async def chat(self, messages, **kwargs):
            self.arrivals += 1
            if self.arrivals == 2:
                self.both_arrived.set()
            await asyncio.wait_for(self.both_arrived.wait(), 3)
            return await super().chat(messages, **kwargs)

    reviewer = BarrierReviewer()
    results = await asyncio.gather(
        *(
            service.create_revision(item, base, context["revision"], [patch], key, reviewer, config)
            for key in ("race-1", "race-2")
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert [result.code for result in results if isinstance(result, BookWorldError)] == [
        "revision_conflict"
    ]
    assert service.get_context(item, base)["head_build_id"] == base


@pytest.mark.asyncio
async def test_revision_rejects_another_books_identity_or_evidence(book_library):
    item, base, config = await published(book_library)
    other_item, other_base, _ = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, base)
    other = service.get_context(other_item, other_base)
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    proof = quote(segment, "人物甲又名阿甲。")
    patch = RevisionPatch(
        operation="merge",
        character_id=context["characters"][0]["id"],
        target_character_id=other["characters"][0]["id"],
        evidence=proof,
    )
    with pytest.raises(BookWorldError) as error:
        await service.create_revision(
            item, base, context["revision"], [patch], "foreign-person", RevisionReviewer(), config
        )
    assert error.value.code == "invalid_revision"
    foreign_segment = service.persona.source.list_segments(other_item, other["source_version_id"])[
        "segments"
    ][0]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=context["characters"][0]["id"],
        value="阿甲",
        evidence=quote(foreign_segment, "人物甲又名阿甲。"),
    )
    with pytest.raises(BookWorldError) as error:
        await service.create_revision(
            item, base, context["revision"], [patch], "foreign-proof", RevisionReviewer(), config
        )
    assert error.value.code == "unsupported_revision"


@pytest.mark.asyncio
async def test_desktop_revision_actions_use_fixed_scope_and_return_conflicts(
    book_library, monkeypatch
):
    from test_book_world_handler import Socket

    from backend.channels.desktop.handlers.book_world import BookWorldHandler
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.book_world.discovery_provider import DiscoveryModel

    item, base, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.book_world.get_workspace_path",
        lambda: book_library.workspace_root,
    )
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.book_world.resolve_discovery_model",
        lambda: DiscoveryModel(RevisionReviewer(), config),
    )
    socket = Socket()
    handler = BookWorldHandler(object())

    async def request(action, **data):
        count = len(socket.messages)
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_WORLD,
                request_id="revision-protocol",
                data={"action": action, "item_id": item, "build_id": base, **data},
            ),
        )
        for _ in range(100):
            if len(socket.messages) > count:
                break
            await asyncio.sleep(0.01)
        assert socket.messages[-1]["request_id"] == "revision-protocol"
        return socket.messages[-1]

    context = (await request("get_revision_context"))["data"]
    person = context["characters"][0]
    saved = await request("save_extension", character_id=person["id"], extension_text="无依据设定")
    assert saved["type"] == "book_world_result" and saved["data"]["canonical"] is False
    assert saved["data"]["workspace_id"] == context["workspace_id"]
    invalid = await request("create_revision", expected_revision=True)
    assert invalid["data"]["code"] == "invalid_request"
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=person["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    await service.create_revision(
        item, base, context["revision"], [patch], "reserve", RevisionReviewer(), config
    )
    stale = await request(
        "create_revision",
        expected_revision=context["revision"],
        revision_request_id="stale",
        patches=[patch.model_dump()],
    )
    assert stale["type"] == "error" and stale["data"]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_slow_revision_review_leaves_same_connection_responsive(book_library, monkeypatch):
    from test_book_world_handler import Socket

    from backend.channels.desktop.handlers.book_world import BookWorldHandler
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.book_world.discovery_provider import DiscoveryModel

    item, base, config = await published(book_library)
    service = BookRevisionService(book_library.workspace_root)
    context = service.get_context(item, base)
    segment = service.persona.source.list_segments(item, context["source_version_id"])["segments"][
        0
    ]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=context["characters"][0]["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowReviewer:
        async def chat(self, *args, **kwargs):
            entered.set()
            await release.wait()
            return LLMResponse(
                content=json.dumps(
                    {"changes": [{"index": 0, "supported": False, "reason": "固定拒绝样本"}]}
                )
            )

    monkeypatch.setattr(
        "backend.channels.desktop.handlers.book_world.get_workspace_path",
        lambda: book_library.workspace_root,
    )
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.book_world.resolve_discovery_model",
        lambda: DiscoveryModel(SlowReviewer(), config),
    )
    socket, handler = Socket(), BookWorldHandler(object())
    await asyncio.wait_for(
        handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_WORLD,
                request_id="slow-review",
                data={
                    "action": "create_revision",
                    "item_id": item,
                    "build_id": base,
                    "expected_revision": context["revision"],
                    "revision_request_id": "slow",
                    "patches": [patch.model_dump()],
                },
            ),
        ),
        3,
    )
    await asyncio.wait_for(entered.wait(), 3)
    try:
        await asyncio.wait_for(
            handler.handle(
                socket,
                WSMessage(
                    type=MessageType.BOOK_WORLD,
                    request_id="refresh-during-review",
                    data={"action": "get_build", "item_id": item, "build_id": base},
                ),
            ),
            3,
        )
        assert socket.messages[-1]["request_id"] == "refresh-during-review"
        assert socket.messages[-1]["data"]["build_id"] == base
    finally:
        release.set()
    for _ in range(100):
        if any(message["request_id"] == "slow-review" for message in socket.messages):
            break
        await asyncio.sleep(0.01)
    final = next(message for message in socket.messages if message["request_id"] == "slow-review")
    assert final["data"]["code"] == "unsupported_revision"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["ignored", "correct", "unrelated_trait", "paraphrased_error"])
async def test_ownership_revision_requires_verified_reextraction(book_library, mode):
    text = "人物甲问人物乙：你最看重什么？人物乙说：我最看重诚信。我也喜欢音乐。"
    item, discovery = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "active"))
    )
    service = BookRevisionService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)

    def extract(data):
        alpha = next(person["id"] for person in data["characters"] if person["name"] == "人物甲")
        hint = next(iter(data.get("correction_hints", [])), None) if mode != "ignored" else None
        actor = hint["target_character_id"] if hint else alpha
        proof = quote(data["segments"][0], text)
        result = {
            "claims": [
                {
                    "local_key": hint["local_key"] if hint else "value",
                    "kind": "trait",
                    "owner_character_id": actor,
                    "proposition": (
                        "人物乙喜欢音乐" if mode == "unrelated_trait" else "人物乙重视诚信"
                    )
                    if hint
                    else "人物甲重视诚信",
                    "slot_key": "value:诚信",
                    "evidence": [proof],
                    "access": [{"character_id": actor, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }
        if hint and mode == "paraphrased_error":
            result["claims"].append(
                {
                    **result["claims"][0],
                    "local_key": "old-paraphrase",
                    "owner_character_id": alpha,
                    "proposition": "诚信对人物甲很重要",
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            )
        return result

    def review(data):
        result = review_all(data)
        if data.get("correction_hints"):
            result["revision_checks"] = [
                {
                    "local_key": hint["local_key"],
                    "same_claim_repaired": mode != "unrelated_trait" and mode != "ignored",
                    "original_assignment_removed": mode != "paraphrased_error"
                    and mode != "ignored",
                    "reason": "固定样本校验同一价值观与原错误归属，音乐是另一特征",
                }
                for hint in data["correction_hints"]
            ]
        return result

    # An intentionally mistaken model result exercises correction of a published attribution.
    base = service.persona.request_build(item, discovery, config)["build_id"]
    await service.persona.run(base, ScriptedPersonaProvider(extract, review), config)
    context = service.get_context(item, base)
    people = {person["name"]: person for person in context["characters"]}
    claim = service.persona.get_character(item, base, people["人物甲"]["id"])["reader"]["claims"][0]
    proof = {**claim["evidence"][0], "quote": text}
    proof = {key: proof[key] for key in ("segment_id", "local_start", "local_end", "quote")}
    patch = RevisionPatch(
        operation="correct_owner",
        character_id=people["人物甲"]["id"],
        target_character_id=people["人物乙"]["id"],
        claim_id=claim["id"],
        evidence=proof,
    )
    revised = await service.create_revision(
        item, base, context["revision"], [patch], "owner-failure", RevisionReviewer(), config
    )
    provider = ScriptedPersonaProvider(extract, review)
    await service.persona.run(revised["build_id"], provider, config)
    result = service.persona.discovery.get_build(item, revised["build_id"])
    assert (
        provider.inputs[0]["correction_hints"][0]["target_character_id"]
        != patch.target_character_id
    )
    if mode == "correct":
        assert result["status"] == "published"
        people = {
            person["name"]: person
            for person in service.get_context(item, revised["build_id"])["characters"]
        }
        target = service.persona.get_agent_definition(
            item, revised["build_id"], people["人物乙"]["id"]
        )
        assert target["baseline"]["value:诚信"]["proposition"] == "人物乙重视诚信"
        assert (
            service.persona.get_character(item, revised["build_id"], people["人物甲"]["id"])[
                "reader"
            ]["claims"]
            == []
        )
    else:
        assert result["status"] == "failed"
        assert result["error_code"] == "revision_unresolved"
        assert service.get_context(item, base)["head_build_id"] == base


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["queued", "failed", "cancelled"])
async def test_unpublished_rebuild_keeps_published_history_without_hiding_current_state(
    book_library, state
):
    item, base, config = await published(book_library)
    service = BookPersonaService(book_library.workspace_root)
    old = service.discovery.get_build(item, base)
    new_config = config.model_copy(
        update={
            "prompt_version": "persona-extract-v4",
            "review_prompt_version": "persona-review-v4",
        }
    )
    child = service.request_build(item, old["parent_build_id"], new_config)
    if state == "cancelled":
        service.control(item, child["build_id"], "cancel")
    elif state == "failed":

        class Invalid:
            async def chat(self, messages, **kwargs):
                return LLMResponse(content="{")

        await service.run(child["build_id"], Invalid(), new_config)
    selected = service.discovery.get_build(item, source_version_id=old["source_version_id"])
    assert selected["build_id"] == child["build_id"] and selected["status"] == state
    assert selected["history_build_id"] == base
    context = BookRevisionService(book_library.workspace_root).get_context(
        item, selected["history_build_id"]
    )
    assert context["head_build_id"] == base
    assert child["build_id"] in {version["id"] for version in context["versions"]}
    assert service.discovery.get_build(item, base)["status"] == "published"


@pytest.mark.asyncio
async def test_published_history_lookup_never_crosses_book_or_source(book_library):
    from backend.services.book_world.discovery import DiscoveryConfig

    item, base, config = await published(book_library)
    service = BookPersonaService(book_library.workspace_root)
    old = service.discovery.get_build(item, base)
    other, discovery = await discovered(book_library)
    assert other != item
    assert service.discovery.get_build(other, discovery)["history_build_id"] is None
    with pytest.raises(BookWorldError):
        service.discovery.get_build(other, base)
    path = book_library.workspace_root / "replacement-version.txt"
    path.write_bytes("人物甲说：这是独立的新来源。".encode())
    book_library.import_text_attachment(item, path)
    source = service.source.prepare_source(item)
    assert source["source_version_id"] != old["source_version_id"]
    new = service.discovery.create_build(
        item, source["source_version_id"], DiscoveryConfig(provider_id=1, model="fixture")
    )
    assert new["history_build_id"] is None
