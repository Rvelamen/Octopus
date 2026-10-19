"""Character-scoped retrieval returns only reviewed perspective materials."""

import pytest
from test_book_persona import ScriptedPersonaProvider, discovered, quote, review_all

from backend.services.book_world.knowledge import CharacterKnowledgeService
from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.source import BookWorldError
from backend.services.book_world.storage import connect

LONG_BRIDGE_QUESTION = (
    "请讲一讲你第一次从瀑布外面看到的那座桥：它是用什么搭的、"
    "桥下水流走向如何。请只说你亲眼看到的。"
)


def test_long_query_retains_compound_anchor_and_identifier_within_term_budget():
    from backend.services.book_world.search_terms import query_terms

    selected = query_terms(LONG_BRIDGE_QUESTION + "记录号 KEY9。", ["人物甲"])
    assert "瀑布" in selected
    assert "key9" in selected
    assert len(selected) <= 32


@pytest.mark.asyncio
async def test_long_question_recalls_owned_episode_without_granting_it_to_another_person(book_library):
    text = "人物甲进入瀑布，发现铁板桥。\n\n人物乙在山外歇息。"
    item, parent = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "active"))
    )
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = next(person["id"] for person in data["characters"] if person["name"] == "人物甲")
        row = next(row for row in data["segments"] if "铁板桥" in row["text"])
        evidence = quote(row, "人物甲进入瀑布，发现铁板桥。")
        return {"claims": [{
            "local_key": "bridge", "kind": "episode", "owner_character_id": actor,
            "proposition": "人物甲进入瀑布，发现铁板桥。", "evidence": [evidence],
            "access": [{"character_id": actor, "route": "firsthand", "acquisition": evidence,
                        "approved_excerpt": evidence["quote"]}],
        }]}

    await service.run(build, ScriptedPersonaProvider(extract, review_all), config)
    people = {person["name"]: person["id"] for person in service.discovery.list_characters(item, build)["characters"]}
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    owner = knowledge.bind_character(item, build, people["人物甲"])
    other = knowledge.bind_character(item, build, people["人物乙"])
    brief = knowledge.retrieve(owner, "瀑布")
    full = knowledge.retrieve(owner, LONG_BRIDGE_QUESTION)
    assert full.status == "known"
    assert {item.claim_id for item in full.items} == {item.claim_id for item in brief.items}
    assert any("铁板桥" in item.proposition for item in full.items)
    assert knowledge.retrieve(other, LONG_BRIDGE_QUESTION).status == "unknown"
    assert knowledge.retrieve(other, "瀑布").items == ()


async def style_character(library, *, with_excerpt=True):
    text = "人物甲说：“慢慢说，我听着。”旁白：人物乙暗藏秘密。"
    item, parent = await discovered(library, text)
    service = BookPersonaService(library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "style",
                    "kind": "style",
                    "owner_character_id": actor,
                    "proposition": "人物甲用语平和简短",
                    "slot_key": "style:语气",
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": "人物甲说：“慢慢说，我听着。”"
                            if with_excerpt
                            else "",
                        }
                    ],
                }
            ]
        }

    await service.run(build, ScriptedPersonaProvider(extract, review_all), config)
    actor = service.discovery.list_characters(item, build)["characters"][0]["id"]
    scope = CharacterKnowledgeService(library.workspace_root).bind_character(item, build, actor)
    return item, build, actor, scope


@pytest.mark.asyncio
async def test_proposition_only_authority_retains_baseline_without_dialogue_or_raw_quote(
    book_library,
):
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, scope = await style_character(book_library, with_excerpt=False)
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    matched = knowledge.retrieve(scope, "平和")
    assert matched.status == "known"
    assert matched.items[0].proposition == "人物甲用语平和简短"
    assert matched.items[0].approved_excerpt == ""
    baseline = knowledge.baseline(scope)
    assert baseline.slots["style:语气"].proposition == "人物甲用语平和简短"
    assert "暗藏秘密" not in matched.model_dump_json() + baseline.model_dump_json()

    expressions = CharacterExpressionService(book_library.workspace_root)
    job = expressions.create_set(scope, ExpressionConfig(provider_id=1, model="fixture"))
    assert job["status"] == "ready" and job["total_units"] == 0 and job["total_calls"] == 0
    result = expressions.retrieve(scope, "平和")
    assert [rule.text for rule in result.rules] == ["人物甲用语平和简短"]
    assert result.examples == ()


@pytest.mark.asyncio
async def test_queued_expression_can_be_resumed_by_a_new_service_after_restart(book_library):
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, scope = await style_character(book_library)
    config = ExpressionConfig(provider_id=1, model="fixture")
    first = CharacterExpressionService(book_library.workspace_root)
    job = first.create_set(scope, config)
    restarted = CharacterExpressionService(book_library.workspace_root)
    assert restarted.get_set(scope, job["set_id"])["can_resume"] is True
    resumed = restarted.control(scope, job["set_id"], "resume")
    assert resumed["status"] == "queued" and resumed["total_calls"] == 0

    class Empty:
        async def chat(self, *args, **kwargs):
            return LLMResponse(content='{"materials":[]}')

    await restarted.run(job["set_id"], Empty(), config)
    assert restarted.get_set(scope, job["set_id"])["status"] == "ready"


@pytest.mark.asyncio
async def test_cancelled_late_invalid_response_cannot_replace_resumed_checkpoint(book_library):
    import asyncio

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    config = ExpressionConfig(provider_id=1, model="fixture")
    job = service.create_set(scope, config)
    started, release = asyncio.Event(), asyncio.Event()

    class Late:
        async def chat(self, *args, **kwargs):
            started.set()
            await release.wait()
            return LLMResponse(content="invalid-json")

    class Empty:
        async def chat(self, *args, **kwargs):
            return LLMResponse(content='{"materials":[]}')

    old = asyncio.create_task(service.run(job["set_id"], Late(), config))
    try:
        await asyncio.wait_for(started.wait(), 5)
        service.control(scope, job["set_id"], "cancel")
        service.control(scope, job["set_id"], "retry")
        await service.run(job["set_id"], Empty(), config)
        checkpoint = service.get_set(scope, job["set_id"])
        release.set()
        await asyncio.wait_for(old, 5)
        assert service.get_set(scope, job["set_id"]) == checkpoint
        assert checkpoint["status"] == "ready" and checkpoint["completed_units"] == 1
    finally:
        release.set()
        if not old.done():
            old.cancel()
            await asyncio.gather(old, return_exceptions=True)


@pytest.mark.asyncio
async def test_expression_sets_and_caches_are_isolated_across_books_and_workspaces(
    book_library, tmp_path
):
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, first_scope = await style_character(book_library)
    _, _, _, second_scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    job = service.create_set(first_scope, ExpressionConfig(provider_id=1, model="fixture"))
    assert service.knowledge.retrieve(first_scope, "平和").status == "known"
    assert service.knowledge.retrieve(second_scope, "平和").status == "known"
    for operation in (
        lambda: service.get_set(second_scope, job["set_id"]),
        lambda: service.list_materials(second_scope, job["set_id"]),
        lambda: service.control(second_scope, job["set_id"], "cancel"),
        lambda: service.retrieve(second_scope, "平和", set_id=job["set_id"]),
    ):
        with pytest.raises(BookWorldError):
            operation()
    foreign = CharacterExpressionService(tmp_path / "other-workspace")
    with pytest.raises(BookWorldError):
        foreign.knowledge.retrieve(first_scope, "平和")
    with pytest.raises(BookWorldError):
        foreign.get_set(first_scope, job["set_id"])


@pytest.mark.asyncio
async def test_source_removal_fences_cached_knowledge_and_derivatives_without_disabling_other_book(
    book_library,
):
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    item, _, _, removed_scope = await style_character(book_library)
    _, _, _, surviving_scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    job = service.create_set(removed_scope, ExpressionConfig(provider_id=1, model="fixture"))
    assert service.knowledge.retrieve(removed_scope, "平和").status == "known"
    assert book_library.delete_item(item)
    for operation in (
        lambda: service.knowledge.retrieve(removed_scope, "平和"),
        lambda: service.knowledge.baseline(removed_scope),
        lambda: service.get_set(removed_scope, job["set_id"]),
        lambda: service.retrieve(removed_scope, "平和"),
    ):
        with pytest.raises(BookWorldError):
            operation()
    assert service.knowledge.retrieve(surviving_scope, "平和").status == "known"


@pytest.mark.asyncio
async def test_dialogue_fact_reference_requires_current_query_facts_or_baseline(book_library):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    text = "人物甲说：“我见过石桥。”"
    item, parent = await discovered(book_library, text)
    persona = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": key,
                    "kind": kind,
                    "owner_character_id": actor if kind == "style" else None,
                    "proposition": proposition,
                    **({"slot_key": "style:语气"} if kind == "style" else {}),
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": text,
                        }
                    ],
                }
                for key, kind, proposition in (
                    ("style", "style", "人物甲用短句表达见闻"),
                    ("bridge", "fact", "人物甲见过石桥"),
                )
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), config)
    actor = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    service = CharacterExpressionService(book_library.workspace_root)
    scope = service.knowledge.bind_character(item, build, actor)
    expression_config = ExpressionConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    job = service.create_set(scope, expression_config)

    class Example:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            style = next(entry for entry in data["items"] if entry["kind"] == "style")
            fact = next(entry for entry in data["items"] if entry["kind"] == "fact")
            if data["phase"] == "extract":
                result = {
                    "materials": [
                        {
                            "local_key": "bridge",
                            "kind": "dialogue_example",
                            "text": "我见过石桥。",
                            "dialogue_action": "answer",
                            "refs": [
                                {
                                    "claim_id": style["claim_id"],
                                    "evidence_id": style["evidence_id"],
                                    "purpose": "speaker",
                                }
                            ],
                        }
                    ]
                }
            else:
                result = {
                    "materials": [
                        {
                            "local_key": "bridge",
                            "supported": True,
                            "speaker_confirmed": True,
                            "safe": True,
                            "baseline_compatible": True,
                            "purpose_supported": True,
                            "facts_complete": True,
                            "fact_claim_ids": [fact["claim_id"]],
                            "reason": "本人原话中的桥有独立允许事实",
                        }
                    ]
                }
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await service.run(job["set_id"], Example(), expression_config)
    assert service.get_set(scope, job["set_id"])["status"] == "ready"
    assert service.retrieve(scope, "", "answer").examples == ()
    selected = service.retrieve(scope, "石桥", "answer")
    assert [entry.text for entry in selected.examples] == ["我见过石桥。"]


@pytest.mark.asyncio
async def test_desktop_expression_work_leaves_preview_responsive_and_supports_cancel_resume(
    book_library, monkeypatch
):
    import asyncio
    import json

    import backend.channels.desktop.handlers.book_world as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.discovery_models import DiscoveryConfig
    from backend.services.book_world.discovery_provider import DiscoveryModel

    item, build, actor, _ = await style_character(book_library)
    started, release = asyncio.Event(), asyncio.Event()

    class Slow:
        async def chat(self, messages, **kwargs):
            assert "暗藏秘密" not in json.dumps(messages, ensure_ascii=False)
            started.set()
            await release.wait()
            return LLMResponse(content='{"materials":[]}')

    model = DiscoveryModel(Slow(), DiscoveryConfig(provider_id=1, model="fixture"))
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(module, "resolve_discovery_model", lambda: model)

    class Socket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            json.dumps(message)
            self.messages.append(message)

    socket, handler = Socket(), module.BookWorldHandler(object())

    async def request(action, **extra):
        await asyncio.wait_for(
            handler.handle(
                socket,
                WSMessage(
                    type=MessageType.BOOK_WORLD,
                    request_id=action,
                    data={
                        "action": action,
                        "item_id": item,
                        "build_id": build,
                        "character_id": actor,
                        **extra,
                    },
                ),
            ),
            5,
        )
        response = socket.messages[-1]
        assert response["request_id"] == action
        return response

    created = await request("start_expression_set")
    set_id = created["data"]["set_id"]
    try:
        await asyncio.wait_for(started.wait(), 5)
        preview = await request("preview_knowledge", query="平和")
        assert preview["data"]["knowledge"]["status"] == "known"
        assert "暗藏秘密" not in json.dumps(preview, ensure_ascii=False)
        rejected = await request("preview_knowledge", query="平和", workspace_root="foreign")
        assert rejected["data"]["code"] == "invalid_request"
        cancelled = await request("cancel_expression_set", expression_set_id=set_id)
        assert cancelled["data"]["status"] == "cancelled"
        release.set()
        resumed = await request("retry_expression_set", expression_set_id=set_id)
        assert resumed["data"]["set_id"] == set_id
        for _ in range(100):
            current = await request("get_expression_set", expression_set_id=set_id)
            if current["data"]["status"] == "ready":
                break
            await asyncio.sleep(0.01)
        assert current["data"]["status"] == "ready"
        catalog = await request("list_expression_materials", expression_set_id=set_id)
        assert catalog["data"]["materials"][0]["text"] == "人物甲用语平和简短"
    finally:
        release.set()
        await handler._stop_worker(book_library.workspace_root, f"expression:{set_id}")


@pytest.mark.asyncio
async def test_two_desktop_clients_cannot_cancel_each_others_replacement_worker(
    book_library, monkeypatch
):
    import asyncio
    import threading

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_world as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.discovery_models import DiscoveryConfig
    from backend.services.book_world.discovery_provider import DiscoveryModel

    item, build, actor, _ = await style_character(book_library)
    started, cancel_committed, finish_provider = asyncio.Event(), asyncio.Event(), asyncio.Event()
    release_cancel = threading.Event()
    event_loop = asyncio.get_running_loop()
    original_control = module.CharacterExpressionService.control

    def delayed_cancel(service, scope, set_id, action):
        result = original_control(service, scope, set_id, action)
        if action == "cancel":
            event_loop.call_soon_threadsafe(cancel_committed.set)
            assert release_cancel.wait(5)
        return result

    class Slow:
        async def chat(self, *args, **kwargs):
            started.set()
            await finish_provider.wait()
            return LLMResponse(content='{"materials":[]}')

    monkeypatch.setattr(module.CharacterExpressionService, "control", delayed_cancel)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        module,
        "resolve_discovery_model",
        lambda: DiscoveryModel(Slow(), DiscoveryConfig(provider_id=1, model="fixture")),
    )
    handler = module.BookWorldHandler(object())

    async def request(action, **extra):
        socket = Socket()
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_WORLD,
                request_id=action,
                data={
                    "action": action,
                    "item_id": item,
                    "build_id": build,
                    "character_id": actor,
                    **extra,
                },
            ),
        )
        return socket.messages[-1]

    created = await request("start_expression_set")
    set_id = created["data"]["set_id"]
    controls = []
    try:
        await asyncio.wait_for(started.wait(), 5)
        controls.append(
            asyncio.create_task(request("cancel_expression_set", expression_set_id=set_id))
        )
        await asyncio.wait_for(cancel_committed.wait(), 5)
        controls.append(
            asyncio.create_task(request("retry_expression_set", expression_set_id=set_id))
        )
        await asyncio.sleep(0.3)
        assert not controls[1].done(), "Replacement must wait for the earlier cancel to finish"
        release_cancel.set()
        await asyncio.wait_for(asyncio.gather(*controls), 5)
        finish_provider.set()
        for _ in range(100):
            result = await request("get_expression_set", expression_set_id=set_id)
            if result["data"]["status"] == "ready":
                break
            await asyncio.sleep(0.01)
        assert result["data"]["status"] == "ready"
    finally:
        release_cancel.set()
        finish_provider.set()
        await asyncio.gather(*controls, return_exceptions=True)
        await handler._stop_worker(book_library.workspace_root, f"expression:{set_id}")


@pytest.mark.asyncio
async def test_expression_set_preserves_canon_and_returns_reviewed_own_dialogue(book_library):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    item, build, actor, scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    persona = BookPersonaService(book_library.workspace_root)
    before = persona.get_agent_definition(item, build, actor)
    config = ExpressionConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    result = service.create_set(scope, config)

    class ExpressionProvider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "extract":
                proof = data["items"][0]
                answer = {
                    "materials": [
                        {
                            "local_key": "comfort",
                            "kind": "dialogue_example",
                            "text": "慢慢说，我听着。",
                            "dialogue_action": "comfort",
                            "topic_terms": ["慢慢"],
                            "refs": [
                                {
                                    "claim_id": proof["claim_id"],
                                    "evidence_id": proof["evidence_id"],
                                    "purpose": "speaker",
                                }
                            ],
                        }
                    ]
                }
            else:
                answer = {
                    "materials": [
                        {
                            "local_key": "comfort",
                            "supported": True,
                            "speaker_confirmed": True,
                            "safe": True,
                            "baseline_compatible": True,
                            "purpose_supported": True,
                            "facts_complete": True,
                            "fact_claim_ids": [],
                            "reason": "本人原文的温和回应",
                        }
                    ]
                }
            return LLMResponse(content=json.dumps(answer, ensure_ascii=False))

    assert service.create_set(scope, config)["set_id"] == result["set_id"]
    await service.run(result["set_id"], ExpressionProvider(), config)
    saved = service.get_set(scope, result["set_id"])
    assert saved["status"] == "ready"
    selected = service.retrieve(scope, "慢慢说", "comfort")
    assert selected.examples[0].text == "慢慢说，我听着。"
    assert selected.rules[0].text == "人物甲用语平和简短"
    assert persona.get_agent_definition(item, build, actor) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unsupported_speaker", "outside_source", "foreign_reference"])
async def test_expression_review_or_verbatim_failure_never_enters_actor_context(
    book_library, failure
):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    config = ExpressionConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    job = service.create_set(scope, config)

    class Rejected:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "extract":
                proof = data["items"][0]
                answer = {
                    "materials": [
                        {
                            "local_key": "x",
                            "kind": "dialogue_example",
                            "text": "这是原文之外的秘密"
                            if failure == "outside_source"
                            else "慢慢说，我听着。",
                            "dialogue_action": "comfort",
                            "refs": [
                                {
                                    "claim_id": "foreign-claim"
                                    if failure == "foreign_reference"
                                    else proof["claim_id"],
                                    "evidence_id": proof["evidence_id"],
                                    "purpose": "speaker",
                                }
                            ],
                        }
                    ]
                }
            else:
                answer = {
                    "materials": [
                        {
                            "local_key": "x",
                            "supported": True,
                            "speaker_confirmed": False,
                            "safe": True,
                            "baseline_compatible": True,
                            "purpose_supported": True,
                            "facts_complete": True,
                            "fact_claim_ids": [],
                            "reason": "不能确认是本人发言",
                        }
                    ]
                }
            return LLMResponse(content=json.dumps(answer, ensure_ascii=False))

    await service.run(job["set_id"], Rejected(), config)
    assert service.get_set(scope, job["set_id"])["status"] == "partial"
    assert service.retrieve(scope, "慢慢说", "comfort").examples == ()


@pytest.mark.asyncio
async def test_expression_call_budget_pauses_and_manual_resume_preserves_canon(book_library):
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.expressions import CharacterExpressionService, ExpressionConfig

    _, _, _, scope = await style_character(book_library)
    service = CharacterExpressionService(book_library.workspace_root)
    config = ExpressionConfig(
        provider_id=1, model="fixture", unit_char_limit=4000, max_calls_per_window=2
    )
    job = service.create_set(scope, config)

    class Invalid:
        async def chat(self, *args, **kwargs):
            return LLMResponse(content="not-json")

    await service.run(job["set_id"], Invalid(), config)
    paused = service.get_set(scope, job["set_id"])
    assert paused["status"] == "paused"
    assert paused["error_code"] == "expression_budget" and paused["window_calls"] == 1
    restarted = service.control(scope, job["set_id"], "resume")
    assert restarted["status"] == "queued" and restarted["window_calls"] == 0
    assert restarted["total_calls"] == 1


@pytest.mark.asyncio
async def test_search_filters_person_permissions_and_returns_only_safe_excerpt(book_library):
    text = "人物甲说：我最看重诚信。旁白：人物乙暗中藏起钥匙，人物甲并不知道。"
    item, parent = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "active"))
    )
    persona = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, config)["build_id"]

    def extract(data):
        actors = {person["name"]: person["id"] for person in data["characters"]}
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "value",
                    "kind": "trait",
                    "owner_character_id": actors["人物甲"],
                    "proposition": "人物甲重视诚信",
                    "slot_key": "value:诚信",
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actors["人物甲"],
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": "人物甲说：我最看重诚信。",
                        }
                    ],
                },
                {
                    "local_key": "secret",
                    "kind": "episode",
                    "owner_character_id": actors["人物乙"],
                    "proposition": "人物乙暗中藏起钥匙",
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actors["人物乙"],
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": "人物乙暗中藏起钥匙",
                        }
                    ],
                },
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), config)
    people = {
        person["name"]: person
        for person in persona.discovery.list_characters(item, build)["characters"]
    }
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    scope = knowledge.bind_character(item, build, people["人物甲"]["id"])
    allowed = knowledge.retrieve(scope, "诚信", limit=1)
    assert allowed.status == "known"
    assert allowed.items[0].proposition == "人物甲重视诚信"
    assert allowed.items[0].approved_excerpt == "人物甲说：我最看重诚信。"
    assert "钥匙" not in allowed.model_dump_json()
    assert knowledge.retrieve(scope, "钥匙", limit=1).status == "unknown"
    assert knowledge.retrieve(scope, "人物乙藏起钥匙了吗", limit=1).status == "unknown"
    assert knowledge.catalog(scope).items[0].approved_excerpt == "人物甲说：我最看重诚信。"
    baseline = knowledge.baseline(scope)
    assert baseline.slots["value:诚信"].proposition == "人物甲重视诚信"
    assert "钥匙" not in baseline.model_dump_json()
    for changes in (
        {"workspace_id": "another-workspace"},
        {"book_id": "another-book"},
        {"source_version_id": "another-source"},
        {"build_id": parent},
        {"character_id": people["人物乙"]["id"], "book_id": "another-book"},
        {"canonical_policy_version": "another-policy"},
    ):
        with pytest.raises(BookWorldError):
            knowledge.retrieve(scope.model_copy(update=changes), "诚信")
    with connect(knowledge.db_path) as db:
        db.execute("DROP TABLE book_claims_fts")
    fallback = knowledge.retrieve(scope, "诚信", limit=1)
    assert fallback.retrieval_strategy == "allowlist_scan"
    assert fallback.items[0].approved_excerpt == "人物甲说：我最看重诚信。"
    assert knowledge.retrieve(scope, "钥匙", limit=1).items == ()


@pytest.mark.asyncio
async def test_current_belief_excludes_superseded_belief_and_reader_truth_labels(book_library):
    text = "人物甲说：我相信钥匙在柜子里。人物甲后来发现：钥匙其实在盒子里。"
    item, parent = await discovered(book_library, text)
    persona = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        original = quote(data["segments"][0], "人物甲说：我相信钥匙在柜子里。")
        corrected = quote(data["segments"][0], "人物甲后来发现：钥匙其实在盒子里。")
        return {
            "claims": [
                {
                    "local_key": "old",
                    "kind": "belief",
                    "owner_character_id": actor,
                    "proposition": "人物甲相信钥匙在柜子里",
                    "truth_state": "false",
                    "slot_key": "belief:钥匙",
                    "evidence": [original],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": original,
                            "approved_excerpt": original["quote"],
                        }
                    ],
                },
                {
                    "local_key": "new",
                    "kind": "belief",
                    "owner_character_id": actor,
                    "proposition": "人物甲相信钥匙在盒子里",
                    "truth_state": "true",
                    "slot_key": "belief:钥匙",
                    "supersedes_local_key": "old",
                    "evidence": [corrected],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": corrected,
                            "approved_excerpt": corrected["quote"],
                        }
                    ],
                },
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), config)
    actor = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    scope = knowledge.bind_character(item, build, actor)
    current = knowledge.retrieve(scope, "钥匙")
    assert [item.proposition for item in current.items] == ["人物甲相信钥匙在盒子里"]
    assert current.items[0].temporal_state == "current"
    assert "truth_state" not in current.model_dump_json()
    assert knowledge.retrieve(scope, "柜子").status == "unknown"
    earlier = knowledge.retrieve(scope, "柜子", retrospective=True)
    assert earlier.items[0].proposition == "人物甲相信钥匙在柜子里"
    assert earlier.items[0].temporal_state == "historical"


@pytest.mark.asyncio
async def test_empty_or_ambiguous_projection_never_returns_raw_source(book_library):
    text = "人物甲说：我最看重诚信。人物甲又说：我最看重诚信。旁白有隐藏秘密。"
    item, parent = await discovered(book_library, text)
    persona = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "value",
                    "kind": "trait",
                    "owner_character_id": actor,
                    "proposition": "人物甲重视诚信",
                    "slot_key": "value:诚信",
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": "我最看重诚信。",
                        }
                    ],
                }
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), config)
    actor = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    scope = knowledge.bind_character(item, build, actor)
    result = knowledge.retrieve(scope, "诚信")
    assert result.status == "unknown"
    assert knowledge.catalog(scope).items == ()
    assert "隐藏秘密" not in result.model_dump_json()
