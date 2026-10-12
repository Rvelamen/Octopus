"""Rooms bind persistent public conversation to one workspace and canonical sources."""

import pytest
from test_book_knowledge import style_character

from backend.services.book_world.source import BookWorldError


async def pending_turn(library, *, seconds=60):
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, character = await style_character(library)
    rooms = BookRoomService(library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="pending-room")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    rounds = BookRoundService(library.workspace_root)
    turn = rounds.submit(scope, "pending-turn", "你好", config, time_limit_seconds=seconds)
    return rooms, scope, rounds, turn, config


def empty_review(*, supported=True):
    return {
        "supported": supported,
        "facts_complete": supported,
        "persona_consistent": True,
        "action_supported": True,
        "emotion_supported": True,
        "attribution_correct": True,
        "unlisted_assertions": [] if supported else ["未标注的原著秘密"],
        "claims": [],
        "reason": "完整正文复核",
    }


@pytest.mark.asyncio
async def test_single_room_creation_is_idempotent_and_keeps_reader_material_out_of_snapshot(
    book_library,
):
    from backend.services.book_world.rooms import BookRoomService

    _, _, _, character = await style_character(book_library)
    service = BookRoomService(book_library.workspace_root)
    created = service.create_single_room(character, client_room_id="first-room")
    repeated = service.create_single_room(character, client_room_id="first-room")
    assert repeated["room_id"] == created["room_id"]
    assert created["epoch"] == 1 and created["next_seq"] == 1
    member = created["members"][0]
    assert member["character_id"] == character.character_id and member["seat_index"] == 0
    assert member["identity"]["name"] == "人物甲"
    assert "暗藏秘密" not in str(created) and "approved_excerpt" not in str(created)
    room_scope = service.bind_room(created["room_id"], expected_epoch=1)
    assert service.get_room(room_scope)["members"][0]["id"] == member["id"]
    assert service.list_rooms()["total"] == 1
    with pytest.raises(BookWorldError):
        service.bind_room(created["room_id"], expected_epoch=2)


@pytest.mark.asyncio
async def test_turn_submission_commits_one_user_message_and_one_fenced_slot_only_once(book_library):
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    first = rounds.submit(scope, "turn-1", "你重视什么？", config, time_limit_seconds=75)
    repeated = rounds.submit(scope, "turn-1", "你重视什么？", config, time_limit_seconds=120)
    assert repeated["round_id"] == first["round_id"]
    assert first["status"] == "queued" and repeated["time_limit_seconds"] == 75
    assert first["slots"][0]["member_generation"] == 0
    messages = rooms.read_messages(scope)["messages"]
    assert [
        (message["speaker_type"], message["content"], message["seq"]) for message in messages
    ] == [("user", "你重视什么？", 1)]
    assert rooms.get_room(scope)["next_seq"] == 2
    with pytest.raises(BookWorldError) as conflicting:
        rounds.submit(scope, "turn-1", "不同问题", config, time_limit_seconds=75)
    assert conflicting.value.code == "idempotency_conflict"
    with pytest.raises(BookWorldError) as busy:
        rounds.submit(scope, "turn-2", "第二轮", config, time_limit_seconds=75)
    assert busy.value.code == "room_busy"
    assert len(rooms.read_messages(scope)["messages"]) == 1


@pytest.mark.asyncio
async def test_room_and_turn_bindings_reject_other_workspace_and_removed_sources(
    book_library, tmp_path
):
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    item, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="scoped-room")
    scope = rooms.bind_room(room["room_id"], 1)
    foreign = BookRoomService(tmp_path / "other-workspace")
    with pytest.raises(BookWorldError):
        foreign.get_room(scope)
    with pytest.raises(BookWorldError):
        rooms.create_single_room(
            character.model_copy(update={"workspace_id": "foreign"}), client_room_id="forged"
        )
    assert book_library.delete_item(item)
    assert rooms.get_room(scope)["members"][0]["available"] is False
    with pytest.raises(BookWorldError):
        BookRoundService(book_library.workspace_root).submit(
            scope,
            "removed",
            "你好",
            CharacterChatConfig(provider_id=1, model="fixture"),
            time_limit_seconds=60,
        )
    assert rooms.get_room(scope)["next_seq"] == 1
    assert rooms.read_messages(scope)["messages"] == []


@pytest.mark.asyncio
async def test_character_context_uses_safe_baseline_and_keeps_current_question(book_library):
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="context-room")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = BookRoundService(book_library.workspace_root).submit(
        scope, "context-turn", "你说话的语气如何？", config, time_limit_seconds=60
    )
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    assert context.payload["current_message"]["content"] == "你说话的语气如何？"
    assert context.payload["identity"]["name"] == "人物甲"
    assert context.payload["baseline"]["style:语气"]["proposition"] == "人物甲用语平和简短"
    assert context.payload["expressions"]["examples"] == []
    assert "暗藏秘密" not in context.serialized and "quote_text" not in context.serialized
    assert "truth_state" not in context.serialized
    assert context.diagnostics["input_bytes"] <= context.diagnostics["input_budget"]
    with pytest.raises(BookWorldError):
        CharacterContextBuilder(book_library.workspace_root).compose(
            scope, turn["round_id"], "foreign-member"
        )


@pytest.mark.asyncio
async def test_worker_publishes_only_reviewed_reply_with_original_references(book_library):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="reply-room")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "reply-turn", "你说话的语气如何？", config, time_limit_seconds=60)
    calls = []

    class Reviewed:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data["phase"])
            assert "暗藏秘密" not in json.dumps(data, ensure_ascii=False)
            if data["phase"] == "generate":
                proof = data["context"]["baseline"]["style:语气"]
                result = {
                    "content": "我的语气平和简短。",
                    "dialogue_action": "answer",
                    "action_basis_claim_ids": [proof["claim_id"]],
                    "claims": [
                        {
                            "text": "我的语气平和简短",
                            "origin": "canon",
                            "refs": [
                                {"claim_id": proof["claim_id"], "evidence_id": proof["evidence_id"]}
                            ],
                        }
                    ],
                }
            else:
                result = {
                    "supported": True,
                    "facts_complete": True,
                    "persona_consistent": True,
                    "action_supported": True,
                    "emotion_supported": True,
                    "attribution_correct": True,
                    "unlisted_assertions": [],
                    "claims": [
                        {
                            "ordinal": 0,
                            "supported": True,
                            "origin_correct": True,
                            "references_complete": True,
                        }
                    ],
                    "reason": "本人当前表达基线支持",
                }
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Reviewed(), config
    )
    history = rooms.read_messages(scope)["messages"]
    assert [message["content"] for message in history] == [
        "你说话的语气如何？",
        "我的语气平和简短。",
    ]
    assert history[1]["refs"][0]["character_id"] == character.character_id
    assert history[1]["seq"] == 2 and calls == ["generate", "review"]
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
    from backend.services.book_world.storage import connect

    with connect(rooms.db_path) as db:
        diagnostic = json.loads(
            db.execute(
                "SELECT display_snapshot_json FROM book_room_messages WHERE id=?",
                (history[1]["id"],),
            ).fetchone()[0]
        )
    assert diagnostic["dialogue_action"] == "answer" and diagnostic["action_basis_claim_ids"]
    assert diagnostic["action_basis_scope"]["character_id"] == character.character_id
    assert "action_basis_claim_ids" not in str(rooms.read_messages(scope))
    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Reviewed(), config
    )
    assert len(rooms.read_messages(scope)["messages"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["unlisted_fact", "foreign_reference", "incomplete_response", "unfounded_autobiography"],
)
async def test_rejected_candidates_get_one_rewrite_then_safe_unknown_without_raw_publication(
    book_library, failure
):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_models import UNKNOWN_REPLY
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)
    calls = []

    class Rejected:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data["phase"])
            if data["phase"] == "generate":
                result = {
                    "content": "我知道人物乙暗藏秘密。",
                    "dialogue_action": "answer",
                    "claims": [],
                }
                if failure == "unfounded_autobiography":
                    result = {
                        "content": "我还没细看。",
                        "dialogue_action": "answer",
                        "claims": [{"text": "我还没细看", "origin": "conversation"}],
                    }
                if failure == "foreign_reference":
                    result["claims"] = [
                        {
                            "text": "人物乙暗藏秘密",
                            "origin": "canon",
                            "refs": [
                                {"claim_id": "foreign-claim", "evidence_id": "foreign-evidence"}
                            ],
                        }
                    ]
            else:
                result = empty_review(supported=data["candidate"]["content"] == UNKNOWN_REPLY)
            return LLMResponse(
                content=json.dumps(result, ensure_ascii=False),
                finish_reason="length"
                if failure == "incomplete_response" and data["phase"] == "generate"
                else "stop",
            )

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Rejected(), config
    )
    history = rooms.read_messages(scope)["messages"]
    assert [entry["content"] for entry in history] == ["你好", UNKNOWN_REPLY]
    assert history[1]["refs"] == []
    assert calls.count("generate") == 2 and len(calls) <= 5
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["cancel", "remove_source"])
async def test_late_generation_after_cancellation_or_source_removal_never_publishes(
    book_library, control
):
    import asyncio
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Late:
        async def chat(self, messages, **kwargs):
            calls.append(json.loads(messages[-1]["content"])["phase"])
            started.set()
            await release.wait()
            return LLMResponse(content='{"content":"你好。","dialogue_action":"greet","claims":[]}')

    task = asyncio.create_task(
        BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], Late(), config)
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        if control == "cancel":
            rounds.control(scope, turn["round_id"], "cancel")
        else:
            items, _ = book_library.list_items()
            assert book_library.delete_item(items[0]["id"])
        release.set()
        await asyncio.wait_for(task, 5)
        assert [entry["content"] for entry in rooms.read_messages(scope)["messages"]] == ["你好"]
        assert rooms.get_room(scope)["next_seq"] == 2 and calls == ["generate"]
        assert rounds.get_round(scope, turn["round_id"])["status"] in ("cancelled", "failed")
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_monotonic_publication_deadline_pauses_and_manual_continue_uses_new_seconds(
    book_library,
):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library, seconds=1)
    now = [0.0]

    class AtBoundary:
        advanced = False

        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                result = {"content": "你好。", "dialogue_action": "greet", "claims": []}
            else:
                if not self.advanced:
                    now[0] += 2
                    self.advanced = True
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    provider = AtBoundary()
    worker = BookChatWorker(book_library.workspace_root, monotonic=lambda: now[0])
    await worker.run(scope, turn["round_id"], provider, config)
    paused = rounds.get_round(scope, turn["round_id"])
    assert paused["status"] == "paused" and paused["error_code"] == "round_timeout"
    assert len(rooms.read_messages(scope)["messages"]) == 1
    resumed = rounds.control(scope, turn["round_id"], "resume", time_limit_seconds=3)
    assert resumed["time_limit_seconds"] == 3 and resumed["execution_window"] == 2
    assert resumed["window_elapsed_ms"] == 0 and resumed["total_elapsed_ms"] == 2000
    await worker.run(scope, turn["round_id"], provider, config)
    completed = rounds.get_round(scope, turn["round_id"])
    assert completed["status"] == "completed" and completed["total_elapsed_ms"] == 2000
    assert [message["seq"] for message in rooms.read_messages(scope)["messages"]] == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("review_error", [False, True])
async def test_unknown_fallback_rejection_or_unavailable_review_leaves_only_user_message(
    book_library, review_error
):
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)

    class Unreviewable:
        async def chat(self, messages, **kwargs):
            import json

            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                return LLMResponse(content="invalid-json")
            return LLMResponse(
                content=json.dumps(empty_review(supported=False)),
                finish_reason="error" if review_error else "stop",
            )

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Unreviewable(), config
    )
    assert len(rooms.read_messages(scope)["messages"]) == 1
    result = rounds.get_round(scope, turn["round_id"])
    assert result["status"] == "failed"
    assert result["error_code"] == (
        "model_unavailable" if review_error else "fallback_validation_failed"
    )


@pytest.mark.asyncio
async def test_provider_execution_error_is_not_published_as_character_unknown(book_library):
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)

    class Broken:
        async def chat(self, *args, **kwargs):
            return LLMResponse(content="provider connection failed", finish_reason="error")

    await BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], Broken(), config)
    result = rounds.get_round(scope, turn["round_id"])
    assert result["status"] == "failed" and result["error_code"] == "model_unavailable"
    assert [message["content"] for message in rooms.read_messages(scope)["messages"]] == ["你好"]


@pytest.mark.asyncio
async def test_resume_preserves_generation_parameters_when_latest_preferences_change(
    book_library, monkeypatch
):
    import json

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_provider import CharacterChatModel

    rooms, scope, rounds, turn, config = await pending_turn(book_library)
    # The submission is persisted but has not obtained a worker lease (restart seam).
    seen = []

    class Recording:
        async def chat(self, messages, **kwargs):
            seen.append(kwargs["max_tokens"])
            phase = json.loads(messages[-1]["content"])["phase"]
            return LLMResponse(
                content=json.dumps(
                    {"content": "你好。", "dialogue_action": "greet", "claims": []}
                    if phase == "generate"
                    else empty_review()
                )
            )

    model = CharacterChatModel(
        Recording(),
        config.model_copy(update={"max_tokens": 2048}),
        BookRoomTimeoutSettings(book_room_round_timeout_seconds=120),
    )
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(module, "resolve_character_chat_model", lambda *args, **kwargs: model)
    socket, handler = Socket(), module.BookRoomHandler(object())
    await handler.handle(
        socket,
        WSMessage(
            type=MessageType.BOOK_ROOM,
            request_id="resume-prefs",
            data={
                "action": "resume_round",
                "workspace_id": scope.workspace_id,
                "room_id": scope.room_id,
                "expected_epoch": scope.epoch,
                "round_id": turn["round_id"],
            },
        ),
    )
    assert socket.messages[-1]["type"] == "book_room_result"
    assert socket.messages[-1]["data"]["time_limit_seconds"] == 120
    try:
        for _ in range(100):
            if rounds.get_round(scope, turn["round_id"])["status"] == "completed":
                break
            import asyncio

            await asyncio.sleep(0.01)
        assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
        assert seen == [4096, 4096]
    finally:
        await handler._stop(book_library.workspace_root, turn["round_id"])


@pytest.mark.asyncio
async def test_repeated_queued_submission_resolves_original_model_not_new_choice(
    book_library, monkeypatch
):
    import json

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_provider import CharacterChatModel

    rooms, scope, rounds, turn, config = await pending_turn(book_library)
    seen = []

    class Recording:
        async def chat(self, messages, **kwargs):
            seen.append(kwargs["model"])
            phase = json.loads(messages[-1]["content"])["phase"]
            return LLMResponse(
                content=json.dumps(
                    {"content": "你好。", "dialogue_action": "greet", "claims": []}
                    if phase == "generate"
                    else empty_review()
                )
            )

    original = CharacterChatModel(Recording(), config, BookRoomTimeoutSettings())
    changed = CharacterChatModel(
        Recording(),
        config.model_copy(update={"model": "new-model", "provider_id": 2, "model_record_id": 2}),
        BookRoomTimeoutSettings(),
    )
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        module,
        "resolve_character_chat_model",
        lambda *args, **kwargs: changed if args else original,
    )
    socket, handler = Socket(), module.BookRoomHandler(object())
    await handler.handle(
        socket,
        WSMessage(
            type=MessageType.BOOK_ROOM,
            request_id="repeat-model",
            data={
                "action": "submit_turn",
                "workspace_id": scope.workspace_id,
                "room_id": scope.room_id,
                "expected_epoch": scope.epoch,
                "client_turn_id": "pending-turn",
                "content": "你好",
                "provider_id": 2,
                "model_record_id": 2,
            },
        ),
    )
    assert socket.messages[-1]["data"]["round_id"] == turn["round_id"]
    try:
        for _ in range(100):
            if rounds.get_round(scope, turn["round_id"])["status"] == "completed":
                break
            import asyncio

            await asyncio.sleep(0.01)
        assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
        assert seen == ["fixture", "fixture"]
        assert len(rooms.read_messages(scope)["messages"]) == 2
    finally:
        await handler._stop(book_library.workspace_root, turn["round_id"])


@pytest.mark.parametrize("capability", ["embedding", "image", "audio", "tts"])
def test_nonchat_model_records_are_not_offered_or_resolved(monkeypatch, capability):
    from types import SimpleNamespace

    import backend.services.book_world.chat_provider as module

    provider = SimpleNamespace(id=1, name="fixture", enabled=True, api_key="fixture-key")
    model = SimpleNamespace(
        id=1,
        provider_id=1,
        model_id="fixture",
        display_name="fixture",
        enabled=True,
        model_types=[capability],
        context_window=None,
        max_tokens=None,
    )
    defaults = SimpleNamespace(default_provider_id=1, default_model_id=1)
    monkeypatch.setattr(module, "Database", lambda: None)
    monkeypatch.setattr(
        module,
        "AgentDefaultsRepository",
        lambda db: SimpleNamespace(get_or_create_defaults=lambda: defaults),
    )
    monkeypatch.setattr(
        module,
        "ProviderRepository",
        lambda db: SimpleNamespace(
            get_enabled_providers=lambda: [provider], get_provider_by_id=lambda id: provider
        ),
    )
    monkeypatch.setattr(
        module,
        "ModelRepository",
        lambda db: SimpleNamespace(
            get_enabled_models_by_provider=lambda id: [model], get_model_by_id=lambda id: model
        ),
    )
    assert module.list_character_chat_models() == []
    with pytest.raises(BookWorldError) as rejected:
        module.resolve_character_chat_model(1, 1)
    assert rejected.value.code == "blocked_config"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "utterance", ["如果我没见过这件事，我就先问你。", "“我没见过”这句话是在表达没有遇到过。"]
)
async def test_conditional_and_quoted_negative_are_not_treated_as_actual_autobiography(
    book_library, utterance
):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)

    class Conversational:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                result = {
                    "content": utterance,
                    "dialogue_action": "answer",
                    "claims": [{"text": utterance, "origin": "conversation"}],
                }
            else:
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": index,
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                    for index, _ in enumerate(data["candidate"]["claims"])
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Conversational(), config
    )
    assert rooms.read_messages(scope)["messages"][-1]["content"] == utterance


@pytest.mark.asyncio
async def test_desktop_room_protocol_is_responsive_and_rejects_workspace_forgery(
    book_library, monkeypatch
):
    import asyncio
    import json

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_provider import CharacterChatModel
    from backend.services.book_world.room_models import CharacterChatConfig

    item, build, actor, character = await style_character(book_library)
    started, release = asyncio.Event(), asyncio.Event()

    class Slow:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                started.set()
                await release.wait()
                result = {"content": "你好。", "dialogue_action": "greet", "claims": []}
            else:
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        module,
        "resolve_character_chat_model",
        lambda: CharacterChatModel(
            Slow(),
            CharacterChatConfig(provider_id=1, model="fixture"),
            BookRoomTimeoutSettings(book_room_round_timeout_seconds=75),
        ),
    )
    handler = module.BookRoomHandler(object())
    socket = Socket()

    async def request(action, **data):
        await asyncio.wait_for(
            handler.handle(
                socket,
                WSMessage(
                    type=MessageType.BOOK_ROOM,
                    request_id=action,
                    data={"action": action, "workspace_id": character.workspace_id, **data},
                ),
            ),
            5,
        )
        assert socket.messages[-1]["request_id"] == action
        return socket.messages[-1]

    created = await request(
        "create_single_room",
        item_id=item,
        build_id=build,
        character_id=actor,
        client_room_id="ws-room",
    )
    identity = {"room_id": created["data"]["room_id"], "expected_epoch": 1}
    turn = await request("submit_turn", **identity, client_turn_id="ws-turn", content="你好")
    round_id = turn["data"]["round_id"]
    try:
        await asyncio.wait_for(started.wait(), 5)
        current = await request("get_round", **identity, round_id=round_id)
        assert current["data"]["timeLimitSeconds"] == 75
        history = await request("read_messages", **identity)
        assert len(history["data"]["messages"]) == 1
        forged = await request("get_room", **identity, workspace_id="foreign")
        assert forged["data"]["code"] == "invalid_scope"
        extra = await request("get_room", **identity, workspace_root="foreign-path")
        assert extra["data"]["code"] == "invalid_request"
        cancelled = await request("cancel_round", **identity, round_id=round_id)
        assert cancelled["data"]["status"] == "cancelled"
        release.set()
        history = await request("read_messages", **identity)
        assert [row["content"] for row in history["data"]["messages"]] == ["你好"]
    finally:
        release.set()
        await handler._stop(book_library.workspace_root, round_id)


@pytest.mark.asyncio
async def test_negative_autobiography_with_original_evidence_can_be_published(book_library):
    import json

    from test_book_persona import ScriptedPersonaProvider, discovered, quote, review_all

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.persona import BookPersonaService, PersonaConfig
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    original = "人物甲从未去过北山。"
    item, parent = await discovered(book_library, original)
    persona = BookPersonaService(book_library.workspace_root)
    persona_config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, persona_config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        proof = quote(data["segments"][0], original)
        return {
            "claims": [
                {
                    "local_key": "not_visited",
                    "kind": "fact",
                    "proposition": original,
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": original,
                        }
                    ],
                }
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), persona_config)
    actor = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    rooms = BookRoomService(book_library.workspace_root)
    character = rooms.knowledge.bind_character(item, build, actor)
    room = rooms.create_single_room(character, client_room_id="supported-negative-room")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = BookRoundService(book_library.workspace_root).submit(
        scope, "supported-negative-turn", "你去过北山吗？", config, time_limit_seconds=60
    )

    class SupportedNegative:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                proof = next(
                    entry
                    for entry in data["context"]["knowledge"]["items"]
                    if entry["proposition"] == original
                )
                result = {
                    "content": "我从未去过北山。",
                    "dialogue_action": "answer",
                    "claims": [
                        {
                            "text": "我从未去过北山",
                            "origin": "canon",
                            "refs": [
                                {"claim_id": proof["claim_id"], "evidence_id": proof["evidence_id"]}
                            ],
                        }
                    ],
                }
            else:
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": 0,
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], SupportedNegative(), config
    )
    reply = rooms.read_messages(scope)["messages"][-1]
    assert reply["content"] == "我从未去过北山。"
    assert reply["refs"][0]["character_id"] == actor
    assert reply["refs"][0]["origin"] == "canon"


@pytest.mark.asyncio
async def test_long_question_keeps_short_related_dialogue_in_actor_context(book_library):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.expression_models import ExpressionConfig
    from backend.services.book_world.expressions import CharacterExpressionService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, character = await style_character(book_library)
    expressions = CharacterExpressionService(book_library.workspace_root)
    expression_config = ExpressionConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    job = expressions.create_set(character, expression_config)

    class RelatedDialogue:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "extract":
                proof = data["items"][0]
                result = {
                    "materials": [
                        {
                            "local_key": "listen",
                            "kind": "dialogue_example",
                            "text": "我听着。",
                            "topic_terms": ["听着"],
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
                result = {
                    "materials": [
                        {
                            "local_key": "listen",
                            "supported": True,
                            "speaker_confirmed": True,
                            "safe": True,
                            "baseline_compatible": True,
                            "purpose_supported": True,
                            "facts_complete": True,
                            "fact_claim_ids": [],
                            "reason": "本人平和短句的原文表达",
                        }
                    ]
                }
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await expressions.run(job["set_id"], RelatedDialogue(), expression_config)
    assert expressions.get_set(character, job["set_id"])["status"] == "ready"
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="related-short-dialogue")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        expression_enabled=True,
        expression_selection_version="expression-selection-v2",
    )
    question = "你当时是怎样主动提出继续听着别人说话的？请根据已有资料回答。"
    turn = BookRoundService(book_library.workspace_root).submit(
        scope, "long-related-question", question, config, time_limit_seconds=60
    )
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    assert context.payload["current_message"]["content"] == question
    assert [entry["text"] for entry in context.payload["expressions"]["examples"]] == ["我听着。"]
    assert context.diagnostics["expression_selection_version"] == "expression-selection-v2"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["resume_round", "submit_turn"])
async def test_resume_uses_saved_budget_when_latest_global_budget_is_below_chat_minimum(
    book_library, tmp_path, monkeypatch, operation
):
    import asyncio
    import json

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    import backend.services.book_world.chat_provider as provider_module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.providers.base import LLMResponse
    from backend.data.database import Database
    from backend.data.provider_store import (
        AgentDefaultsRepository,
        ModelRepository,
        ProviderRepository,
    )
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService

    db = Database(tmp_path / "resume-config.db")
    provider = ProviderRepository(db).add_provider(
        name="t06-budget-fixture",
        display_name="Budget fixture",
        provider_type="openai",
        api_key="qa-placeholder",
        api_host="https://fixture.invalid",
        enabled=True,
    )
    record = ModelRepository(db).add_model(
        provider_id=provider.id,
        model_id="fixture",
        display_name="Fixture",
        max_tokens=4096,
        context_window=32768,
        enabled=True,
    )
    defaults = AgentDefaultsRepository(db)
    defaults.update_agent_defaults(
        default_provider_id=provider.id, default_model_id=record.id, max_tokens=4096
    )
    seen, factory_budgets = [], []

    class Recording:
        async def chat(self, messages, **kwargs):
            seen.append(kwargs["max_tokens"])
            phase = json.loads(messages[-1]["content"])["phase"]
            result = (
                {"content": "你好。", "dialogue_action": "greet", "claims": []}
                if phase == "generate"
                else empty_review()
            )
            return LLMResponse(content=json.dumps(result))

    def factory(providers, config):
        factory_budgets.append(config.max_tokens)
        return Recording()

    monkeypatch.setattr(provider_module, "Database", lambda: db)
    monkeypatch.setattr(provider_module, "create_provider", factory)
    original = provider_module.resolve_character_chat_model(provider.id, record.id)
    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="saved-budget-room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "saved-budget-turn", "你好", original.config, time_limit_seconds=60)
    defaults.update_agent_defaults(max_tokens=128, book_room_round_timeout_seconds=120)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    socket, handler = Socket(), module.BookRoomHandler(object())
    try:
        values = (
            {"round_id": turn["round_id"]}
            if operation == "resume_round"
            else {"client_turn_id": "saved-budget-turn", "content": "你好"}
        )
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_ROOM,
                request_id="saved-budget-resume",
                data={
                    "action": operation,
                    "workspace_id": scope.workspace_id,
                    "room_id": scope.room_id,
                    "expected_epoch": 1,
                    **values,
                },
            ),
        )
        assert socket.messages[-1]["type"] == "book_room_result"
        assert socket.messages[-1]["data"]["timeLimitSeconds"] == (
            120 if operation == "resume_round" else 60
        )
        for _ in range(200):
            if rounds.get_round(scope, turn["round_id"])["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
        assert seen == [4096, 4096] and factory_budgets == [4096, 4096]
        assert defaults.get_or_create_defaults().max_tokens == 128
        with pytest.raises(BookWorldError) as blocked_new:
            provider_module.resolve_character_chat_model(provider.id, record.id)
        assert blocked_new.value.code == "blocked_config"
    finally:
        await handler._stop(book_library.workspace_root, turn["round_id"])


@pytest.mark.asyncio
async def test_style_evidence_cannot_be_used_as_an_emotion_pattern(book_library):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_models import UNKNOWN_REPLY
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, scope, rounds, turn, config = await pending_turn(book_library)

    class MisattributedEmotion:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                style = data["context"]["baseline"]["style:语气"]
                result = {
                    "content": "我很生气。",
                    "dialogue_action": "answer",
                    "claims": [],
                    "ephemeral_emotion": {
                        "label": "愤怒",
                        "trigger_message_ids": [data["context"]["current_message"]["id"]],
                        "pattern_claim_ids": [style["claim_id"]],
                    },
                }
            else:
                # Deliberately permissive semantic reviewer cannot grant the wrong claim kind.
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], MisattributedEmotion(), config
    )
    assert [entry["content"] for entry in rooms.read_messages(scope)["messages"]] == [
        "你好",
        UNKNOWN_REPLY,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("resume_older", [False, True])
async def test_reviewed_emotion_uses_current_room_trigger_and_original_emotion_pattern(
    book_library,
    resume_older,
):
    import json

    from test_book_persona import ScriptedPersonaProvider, discovered, quote, review_all

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.persona import BookPersonaService, PersonaConfig
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.rounds import BookRoundService
    from backend.services.book_world.storage import connect

    original = "人物甲遭到欺骗会生气。"
    item, parent = await discovered(book_library, original)
    persona = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, config)["build_id"]

    def extract(data):
        actor = data["characters"][0]["id"]
        span = quote(data["segments"][0], original)
        return {
            "claims": [
                {
                    "local_key": "anger",
                    "kind": "emotion",
                    "owner_character_id": actor,
                    "slot_key": "emotion:受骗",
                    "proposition": original,
                    "evidence": [span],
                    "access": [
                        {
                            "character_id": actor,
                            "route": "firsthand",
                            "acquisition": span,
                            "approved_excerpt": original,
                        }
                    ],
                }
            ]
        }

    await persona.run(build, ScriptedPersonaProvider(extract, review_all), config)
    actor = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    rooms = BookRoomService(book_library.workspace_root)
    character = rooms.knowledge.bind_character(item, build, actor)
    room = rooms.create_single_room(character, client_room_id="emotion-room")
    scope = rooms.bind_room(room["room_id"], 1)
    chat_config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        memory_policy_version="typed-room-memory-v1" if resume_older else "legacy-history-v1",
    )
    rounds = BookRoundService(book_library.workspace_root)
    if resume_older:
        old_turn = rounds.submit(
            scope, "earlier-failed", "旧问题", chat_config, time_limit_seconds=60
        )

        class Unavailable:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("fixture provider failure")

        await BookChatWorker(book_library.workspace_root).run(
            scope, old_turn["round_id"], Unavailable(), chat_config
        )
        assert rounds.get_round(scope, old_turn["round_id"])["status"] == "failed"
    turn = rounds.submit(scope, "emotion-turn", "我骗了你", chat_config, time_limit_seconds=60)

    class SupportedEmotion:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                source = data["context"]["current_message"]["id"]
                pattern = data["context"]["baseline"]["emotion:受骗"]["claim_id"]
                result = {
                    "content": "听到你说骗了我，我生气。",
                    "dialogue_action": "answer",
                    "claims": [
                        {"text": "你说骗了我", "origin": "room_hearsay", "message_ids": [source]}
                    ],
                    "ephemeral_emotion": {
                        "label": "生气",
                        "trigger_message_ids": [source],
                        "pattern_claim_ids": [pattern],
                    },
                }
            else:
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": 0,
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], SupportedEmotion(), chat_config
    )
    history = rooms.read_messages(scope)["messages"]
    assert history[-1]["content"] == "听到你说骗了我，我生气。"
    trigger = next(
        message
        for message in history
        if message["round_id"] == turn["round_id"] and message["speaker_type"] == "user"
    )
    assert history[-1]["refs"][0]["heard_message_id"] == trigger["id"]
    assert "ephemeral_emotion" not in str(history)
    with connect(rooms.db_path) as db:
        state = db.execute(
            "SELECT ephemeral_state_json FROM book_room_members WHERE id=?",
            (room["members"][0]["id"],),
        ).fetchone()[0]
    assert "生气" in state and trigger["id"] in state
    if resume_older:
        rounds.control(scope, old_turn["round_id"], "resume", time_limit_seconds=60)

        class Resumed:
            async def chat(self, messages, **kwargs):
                data = json.loads(messages[-1]["content"])
                if data["phase"] == "generate":
                    assert data["context"]["current_message"]["content"] == "旧问题"
                    assert data["context"]["room_state"]["trigger_message_ids"] == [trigger["id"]]
                    assert trigger["id"] in {
                        message["id"] for message in data["context"]["room_history"]
                    }
                    result = {
                        "content": "我们继续谈刚才的问题。",
                        "dialogue_action": "answer",
                        "claims": [],
                    }
                else:
                    result = empty_review()
                return LLMResponse(content=json.dumps(result, ensure_ascii=False))

        await BookChatWorker(book_library.workspace_root).run(
            scope, old_turn["round_id"], Resumed(), chat_config
        )
        assert rounds.get_round(scope, old_turn["round_id"])["status"] == "completed"
        assert rooms.read_messages(scope)["messages"][-1]["content"] == "我们继续谈刚才的问题。"
