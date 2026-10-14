"""Cross-book members use public room identity and independent original scopes."""

import pytest
from test_book_knowledge import style_character


@pytest.mark.asyncio
async def test_natural_selection_uses_evidence_reviewed_alias_without_private_projection(
    book_library,
):
    from test_book_persona import PersonaProvider
    from test_book_revisions import RevisionReviewer, published

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.revisions import BookRevisionService, RevisionPatch
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    first = (await style_character(book_library))[3]
    item, parent, config = await published(book_library)
    revisions = BookRevisionService(book_library.workspace_root)
    context = revisions.get_context(item, parent)
    segment = revisions.persona.source.list_segments(item, context["source_version_id"])[
        "segments"
    ][0]
    updated = await revisions.create_revision(
        item,
        parent,
        context["revision"],
        [
            RevisionPatch(
                operation="add_alias",
                character_id=context["characters"][0]["id"],
                value="阿甲",
                evidence={
                    "segment_id": segment["id"],
                    "quote": "人物甲又名阿甲。",
                    "local_start": 0,
                    "local_end": 8,
                },
            )
        ],
        "alias-for-room",
        RevisionReviewer(),
        config,
    )
    await revisions.persona.run(updated["build_id"], PersonaProvider(), config)
    person = revisions.persona.discovery.list_characters(item, updated["build_id"])["characters"][0]
    membership = RoomMembershipService(book_library.workspace_root)
    second = membership.rooms.knowledge.bind_character(item, updated["build_id"], person["id"])
    room = membership.create([first, second], client_room_id="alias-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    turn = BookRoundService(book_library.workspace_root).submit(
        scope,
        "alias-question",
        "阿甲怎么看？",
        CharacterChatConfig(provider_id=1, model="fixture"),
        time_limit_seconds=60,
        mode="natural",
    )
    assert [slot["member_id"] for slot in turn["slots"]] == [room["members"][1]["id"]]
    assert "原文" not in str(turn["discussion"]["speaker_request"])


@pytest.mark.asyncio
@pytest.mark.parametrize("other_client_resume", [False, True])
async def test_member_control_handoff_cannot_cancel_the_next_speaker(
    book_library, monkeypatch, other_client_resume
):
    import asyncio
    import json
    import threading

    from test_book_rooms import empty_review
    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_provider import CharacterChatModel
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="handoff-race-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    ids = [member["id"] for member in room["members"]]
    started_a, started_b, release_a, release_b, controlled = [asyncio.Event() for _ in range(5)]
    return_control = threading.Event()
    loop = asyncio.get_running_loop()
    config = CharacterChatConfig(provider_id=1, model="fixture")

    class Replies:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                if data["context"]["character_scope"]["character_id"] == actors[0].character_id:
                    started_a.set()
                    await release_a.wait()
                else:
                    started_b.set()
                    await release_b.wait()
                result = {"content": "你好。", "dialogue_action": "greet", "claims": []}
            else:
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    provider = Replies()
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        module,
        "resolve_character_chat_model",
        lambda *args, **kwargs: CharacterChatModel(
            provider, kwargs.get("original_config", config), BookRoomTimeoutSettings()
        ),
    )
    original_control = RoomMembershipService.control

    def delayed_control(self, *args, **kwargs):
        result = original_control(self, *args, **kwargs)
        loop.call_soon_threadsafe(controlled.set)
        loop.call_soon_threadsafe(release_a.set)
        if not return_control.wait(5):
            raise TimeoutError("test control barrier")
        return result

    monkeypatch.setattr(RoomMembershipService, "control", delayed_control)
    first_handler, second_handler = (
        module.BookRoomHandler(object()),
        module.BookRoomHandler(object()),
    )
    first_socket, second_socket = Socket(), Socket()

    async def request(handler, socket, action, **values):
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_ROOM,
                request_id=action,
                data={
                    "action": action,
                    "workspace_id": scope.workspace_id,
                    "room_id": scope.room_id,
                    "expected_epoch": 1,
                    **values,
                },
            ),
        )
        return socket.messages[-1]

    change = resume = None
    try:
        submission = await request(
            first_handler,
            first_socket,
            "submit_turn",
            client_turn_id="race-turn",
            content="你好",
            mode="directed",
            target_member_ids=ids,
        )
        assert submission["type"] == "book_room_result"
        round_id = submission["data"]["round_id"]
        await asyncio.wait_for(started_a.wait(), 5)
        change = asyncio.create_task(
            request(
                first_handler, first_socket, "set_member", member_id=ids[0], speaking_mode="muted"
            )
        )
        await asyncio.wait_for(controlled.wait(), 5)
        if other_client_resume:
            resume = asyncio.create_task(
                request(second_handler, second_socket, "resume_round", round_id=round_id)
            )
        await asyncio.sleep(0.1)
        assert not started_b.is_set(), (
            "The revoked runner or another client took the queue before control finished"
        )
        return_control.set()
        assert (await asyncio.wait_for(change, 5))["type"] == "book_room_result"
        if resume:
            assert (await asyncio.wait_for(resume, 5))["type"] == "book_room_result"
        await asyncio.wait_for(started_b.wait(), 5)
        release_b.set()
        rounds = BookRoundService(book_library.workspace_root)
        for _ in range(200):
            final = rounds.get_round(scope, round_id)
            if final["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        assert final["status"] == "completed"
        assert [slot["status"] for slot in final["slots"]] == ["no_comment", "published"]
        replies = [
            message
            for message in membership.rooms.read_messages(scope)["messages"]
            if message["speaker_type"] == "character"
        ]
        assert len(replies) == 1 and replies[0]["speaker_member_id"] == ids[1]
    finally:
        return_control.set()
        release_a.set()
        release_b.set()
        await asyncio.gather(*(task for task in (change, resume) if task), return_exceptions=True)


@pytest.mark.asyncio
async def test_natural_selection_rotates_after_reviewed_silence(book_library):
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="silence-fairness-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v4")
    rounds = BookRoundService(book_library.workspace_root)
    first = rounds.submit(
        scope, "silent-first", "你好", config, time_limit_seconds=60, mode="natural"
    )

    class Silent:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            result = (
                {"content": "", "dialogue_action": "no_comment", "claims": []}
                if data["phase"] == "generate"
                else empty_review()
            )
            return LLMResponse(content=json.dumps(result))

    await BookChatWorker(book_library.workspace_root).run(
        scope, first["round_id"], Silent(), config
    )
    second = rounds.submit(
        scope, "next-opportunity", "你好", config, time_limit_seconds=60, mode="natural"
    )
    assert second["slots"][0]["member_id"] == room["members"][1]["id"]


@pytest.mark.asyncio
async def test_reviewed_silence_advances_the_fixed_queue_without_publishing_a_body(book_library):
    import json

    from test_book_persona import ScriptedPersonaProvider, discovered, review_all
    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.persona import BookPersonaService, PersonaConfig
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    item, parent = await discovered(book_library, "人物甲站在那里。")
    persona = BookPersonaService(book_library.workspace_root)
    persona_config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = persona.request_build(item, parent, persona_config)["build_id"]
    await persona.run(
        build, ScriptedPersonaProvider(lambda _: {"claims": []}, review_all), persona_config
    )
    sparse_id = persona.discovery.list_characters(item, build)["characters"][0]["id"]
    membership = RoomMembershipService(book_library.workspace_root)
    sparse = membership.rooms.knowledge.bind_character(item, build, sparse_id)
    _, _, _, other = await style_character(book_library)
    room = membership.create([sparse, other], client_room_id="silent-member-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v4")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(
        scope,
        "allow-silence",
        "你们怎么看？",
        config,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=[member["id"] for member in room["members"]],
    )
    phases = []

    class QuietThenGreeting:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            phases.append(data["phase"])
            if data["phase"] == "generate":
                result = (
                    {"content": "", "dialogue_action": "no_comment", "claims": []}
                    if data["context"]["character_scope"]["character_id"] == sparse_id
                    else {"content": "你好。", "dialogue_action": "greet", "claims": []}
                )
            else:
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], QuietThenGreeting(), config
    )
    final = rounds.get_round(scope, turn["round_id"])
    assert final["status"] == "completed"
    assert [slot["status"] for slot in final["slots"]] == ["no_comment", "published"]
    assert phases == ["generate", "review", "generate", "review"]
    history = membership.rooms.read_messages(scope)["messages"]
    assert len(history) == 2 and history[-1]["speaker_member_id"] == room["members"][1]["id"]
    assert history[-1]["content"] == "你好。"


@pytest.mark.asyncio
async def test_natural_selection_is_bounded_fair_and_excludes_mention_only_members(book_library):
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    actors = [(await style_character(book_library))[3] for _ in range(4)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="natural-group")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    ids = [member["id"] for member in room["members"]]
    membership.control(scope, ids[3], speaking_mode="mention_only")
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    related = rounds.submit(
        scope, "related", "人物甲，请回应", config, time_limit_seconds=60, mode="natural"
    )
    assert [slot["member_id"] for slot in related["slots"]] == ids[:3]
    rounds.control(scope, related["round_id"], "cancel")
    first = rounds.submit(
        scope, "unrelated-first", "你好", config, time_limit_seconds=60, mode="natural"
    )
    assert [slot["member_id"] for slot in first["slots"]] == [ids[0]]

    class Greeting:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            result = (
                {"content": "你好。", "dialogue_action": "greet", "claims": []}
                if data["phase"] == "generate"
                else empty_review()
            )
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, first["round_id"], Greeting(), config
    )
    second = rounds.submit(
        scope, "unrelated-second", "你好", config, time_limit_seconds=60, mode="natural"
    )
    assert [slot["member_id"] for slot in second["slots"]] == [ids[1]]
    rounds.control(scope, second["round_id"], "cancel")
    directed = rounds.submit(
        scope,
        "explicit-mention",
        "你好",
        config,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=[ids[3]],
    )
    assert directed["slots"][0]["member_id"] == ids[3]


@pytest.mark.asyncio
async def test_cross_book_room_creation_is_atomic_idempotent_and_has_stable_public_seats(
    book_library,
):
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.rooms import BookRoomService
    from backend.services.book_world.source import BookWorldError

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    created = membership.create([first, second], client_room_id="cross-book-room", title="两书交流")
    repeated = membership.create([first, second], client_room_id="cross-book-room", title="重发")
    assert repeated["room_id"] == created["room_id"]
    assert created["title"] == "两书交流"
    assert created["epoch"] == 1 and created["next_seq"] == 1
    assert [member["seat_index"] for member in created["members"]] == [0, 1]
    assert len({member["id"] for member in created["members"]}) == 2
    assert [member["character_id"] for member in created["members"]] == [
        first.character_id,
        second.character_id,
    ]
    assert {source["book_id"] for source in created["sources"]} == {first.book_id, second.book_id}
    assert "暗藏秘密" not in str(created) and "approved_excerpt" not in str(created)
    assert [member["id"] for member in repeated["members"]] == [
        member["id"] for member in created["members"]
    ]
    with pytest.raises(BookWorldError) as conflict:
        membership.create([first], client_room_id="cross-book-room")
    assert conflict.value.code == "idempotency_conflict"
    assert BookRoomService(book_library.workspace_root).list_rooms()["total"] == 1


@pytest.mark.asyncio
async def test_adding_members_requires_an_idle_room_and_reuses_existing_seats(book_library):
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService
    from backend.services.book_world.source import BookWorldError

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([first], client_room_id="add-member-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(
        scope,
        "active-before-add",
        "你好",
        CharacterChatConfig(provider_id=1, model="fixture"),
        time_limit_seconds=60,
    )
    with pytest.raises(BookWorldError) as busy:
        membership.add(scope, [second])
    assert busy.value.code == "room_busy"
    assert len(membership.rooms.get_room(scope)["members"]) == 1
    rounds.control(scope, turn["round_id"], "cancel")
    joined = membership.add(scope, [second])
    repeated = membership.add(scope, [second])
    assert [member["seat_index"] for member in joined["members"]] == [0, 1]
    assert [member["id"] for member in joined["members"]] == [
        member["id"] for member in repeated["members"]
    ]
    assert joined["members"][0] == room["members"][0]


@pytest.mark.asyncio
async def test_member_control_revokes_pending_speech_and_rejoin_preserves_identity(book_library):
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, actor = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="controlled-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    member = room["members"][0]
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(
        scope,
        "mute-before-generation",
        "你好",
        CharacterChatConfig(provider_id=1, model="fixture"),
        time_limit_seconds=60,
    )
    muted = membership.control(scope, member["id"], speaking_mode="muted")
    assert muted["members"][0]["active"] == 1
    assert muted["members"][0]["membership_generation"] == 1
    after = rounds.get_round(scope, turn["round_id"])
    assert after["status"] == "completed" and after["slots"][0]["status"] == "no_comment"
    removed = membership.control(scope, member["id"], active=False)
    assert removed["members"][0]["active"] == 0
    assert removed["members"][0]["removed_reason"] == "user"
    joined = membership.control(scope, member["id"], active=True, speaking_mode="auto")
    current = joined["members"][0]
    assert current["id"] == member["id"] and current["seat_index"] == member["seat_index"]
    assert current["membership_generation"] == 3
    assert current["active"] == 1 and current["removed_reason"] is None
    assert rounds.get_round(scope, turn["round_id"])["slots"][0]["status"] == "no_comment"


@pytest.mark.asyncio
async def test_desktop_catalog_and_cross_book_creation_use_server_bound_character_scopes(
    book_library, monkeypatch
):
    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.book_world.rooms import BookRoomService

    first_item, first_build, first_actor, _ = await style_character(book_library)
    second_item, second_build, second_actor, _ = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    handler, socket = module.BookRoomHandler(object()), Socket()

    async def request(data):
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_ROOM,
                request_id="group-contract",
                data={"workspace_id": rooms.workspace_id, **data},
            ),
        )
        return socket.messages[-1]

    catalog = await request({"action": "list_room_characters"})
    assert catalog["type"] == "book_room_result"
    assert {entry["character_id"] for entry in catalog["data"]["characters"]} == {
        first_actor,
        second_actor,
    }
    assert "暗藏秘密" not in str(catalog)
    selections = [
        {"item_id": first_item, "build_id": first_build, "character_id": first_actor},
        {"item_id": second_item, "build_id": second_build, "character_id": second_actor},
    ]
    created = await request(
        {
            "action": "create_group_room",
            "client_room_id": "ws-group",
            "characters": selections,
            "title": "跨书交流",
        }
    )
    assert created["type"] == "book_room_result" and len(created["data"]["members"]) == 2
    repeated = await request(
        {"action": "create_group_room", "client_room_id": "ws-group", "characters": selections}
    )
    assert repeated["data"]["room_id"] == created["data"]["room_id"]
    tampered = await request(
        {
            "action": "create_group_room",
            "client_room_id": "bad-scope",
            "characters": [{**selections[0], "book_id": "untrusted-book"}],
        }
    )
    assert tampered["type"] == "error" and tampered["data"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_directed_cross_book_turn_runs_in_order_and_later_actor_receives_public_reply(
    book_library,
):
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([first, second], client_room_id="ordered-group")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    targets = [member["id"] for member in reversed(room["members"])]
    turn = rounds.submit(
        scope,
        "ordered-turn",
        "向两位问好",
        config,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=targets,
    )
    assert [slot["member_id"] for slot in turn["slots"]] == targets
    phases, actors = [], []

    class PublicReplies:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            phases.append(data["phase"])
            context = data["context"]
            assert "暗藏秘密" not in json.dumps(context, ensure_ascii=False)
            if data["phase"] == "generate":
                actors.append(context["character_scope"]["character_id"])
                if len(actors) == 1:
                    source = context["current_message"]["id"]
                    content = "用户向两位问好。"
                else:
                    prior = next(
                        message
                        for message in context["room_history"]
                        if message["speaker_type"] == "character"
                    )
                    source = prior["id"]
                    assert prior["speaker_member_id"] == targets[0]
                    content = "刚才另一位说，用户向两位问好。"
                result = {
                    "content": content,
                    "dialogue_action": "answer",
                    "claims": [
                        {"text": content, "origin": "room_hearsay", "message_ids": [source]}
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
        scope, turn["round_id"], PublicReplies(), config
    )
    assert phases == ["generate", "review", "generate", "review"]
    assert actors == [second.character_id, first.character_id]
    final = rounds.get_round(scope, turn["round_id"])
    assert final["status"] == "completed" and final["cursor"] == 2
    published = membership.rooms.read_messages(scope)["messages"]
    assert [message["seq"] for message in published] == [1, 2, 3]
    assert published[2]["refs"][0]["heard_message_id"] == published[1]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("restart_worker", [False, True])
async def test_muting_current_speaker_does_not_restart_the_remaining_turn_deadline(
    book_library, restart_worker
):
    import asyncio
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([first, second], client_room_id="control-deadline-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    targets = [member["id"] for member in room["members"]]
    turn = rounds.submit(
        scope,
        "one-second-group",
        "你好",
        config,
        time_limit_seconds=1,
        mode="directed",
        target_member_ids=targets,
    )
    started, release = asyncio.Event(), asyncio.Event()
    generations = 0

    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = Clock()

    class TimedReplies:
        async def chat(self, messages, **kwargs):
            nonlocal generations
            data = json.loads(messages[-1]["content"])
            if data["phase"] == "generate":
                generations += 1
                if generations == 1:
                    started.set()
                    await release.wait()
                else:
                    clock.value = 1.2
                result = {"content": "你好。", "dialogue_action": "greet", "claims": []}
            else:
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    worker = asyncio.create_task(
        BookChatWorker(book_library.workspace_root, monotonic=clock).run(
            scope, turn["round_id"], TimedReplies(), config
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        clock.value = 0.4
        membership.control(scope, targets[0], speaking_mode="muted")
        if restart_worker:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        else:
            release.set()
            await asyncio.wait_for(worker, 5)
        worker = asyncio.create_task(
            BookChatWorker(book_library.workspace_root, monotonic=clock).run(
                scope, turn["round_id"], TimedReplies(), config
            )
        )
        release.set()
        await asyncio.wait_for(worker, 5)
        final = rounds.get_round(scope, turn["round_id"])
        assert final["status"] == "paused" and final["error_code"] == "round_timeout"
        assert final["slots"][0]["status"] == "no_comment"
        assert final["slots"][1]["status"] == "pending"
        assert all(
            message["speaker_type"] == "user"
            for message in membership.rooms.read_messages(scope)["messages"]
        )
    finally:
        release.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
