"""Room memory advances independently of immutable original-character knowledge."""

import pytest
from test_book_knowledge import style_character

from backend.services.book_world.context import CharacterContextBuilder
from backend.services.book_world.room_models import CharacterChatConfig
from backend.services.book_world.rooms import BookRoomService
from backend.services.book_world.rounds import BookRoundService
from backend.services.book_world.source import BookWorldError


@pytest.mark.asyncio
async def test_reset_clears_only_one_room_epoch_and_keeps_sources_seats_and_original_baseline(
    book_library,
):
    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    rounds = BookRoundService(book_library.workspace_root)
    first = rooms.create_single_room(character, client_room_id="reset-room")
    second = rooms.create_single_room(character, client_room_id="other-memory-room")
    before = rooms.knowledge.baseline(character).model_dump()
    old = rooms.bind_room(first["room_id"], 1)
    other = rooms.bind_room(second["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    rounds.submit(old, "same-turn", "旧房间的记忆", config, time_limit_seconds=60)
    rounds.submit(other, "other-turn", "另一房间的记忆", config, time_limit_seconds=60)
    original_member = first["members"][0]

    reset = rooms.reset_memory(old)
    assert reset["epoch"] == 2 and reset["next_seq"] == 2
    current = rooms.bind_room(first["room_id"], 2)
    assert rooms.read_messages(current)["messages"] == []
    assert reset["latest_round_id"] is None
    member = reset["members"][0]
    assert (
        member["id"] == original_member["id"]
        and member["seat_index"] == original_member["seat_index"]
    )
    assert member["membership_generation"] == original_member["membership_generation"] + 1
    assert all(
        member[key] == original_member[key]
        for key in (
            "book_id",
            "source_version_id",
            "build_id",
            "character_id",
            "active",
            "speaking_mode",
            "available",
        )
    )
    assert rooms.knowledge.baseline(character).model_dump() == before
    assert [message["content"] for message in rooms.read_messages(other)["messages"]] == [
        "另一房间的记忆"
    ]
    with pytest.raises(BookWorldError) as stale:
        rooms.read_messages(old)
    assert stale.value.code == "stale_room_epoch"

    turn = rounds.submit(current, "same-turn", "新房间的交流", config, time_limit_seconds=60)
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        current, turn["round_id"], member["id"]
    )
    assert context.payload["current_message"]["content"] == "新房间的交流"
    assert context.payload["room_history"] == []
    assert "旧房间的记忆" not in context.serialized and "另一房间的记忆" not in context.serialized
    assert rooms.read_messages(current)["messages"][0]["seq"] == 2


@pytest.mark.asyncio
async def test_reply_finishing_after_memory_reset_cannot_enter_the_new_epoch(book_library):
    import asyncio
    import json

    from test_book_rooms import empty_review, pending_turn

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker

    rooms, old, rounds, turn, config = await pending_turn(book_library)
    started, release = asyncio.Event(), asyncio.Event()

    class DelayedReply:
        async def chat(self, messages, **kwargs):
            phase = json.loads(messages[-1]["content"])["phase"]
            if phase == "generate":
                started.set()
                await release.wait()
                result = {"content": "旧轮次的迟到回复", "dialogue_action": "answer", "claims": []}
            else:
                result = empty_review()
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    worker = asyncio.create_task(
        BookChatWorker(book_library.workspace_root).run(
            old, turn["round_id"], DelayedReply(), config
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        reset = rooms.reset_memory(old)
        release.set()
        await asyncio.wait_for(worker, 5)
        current = rooms.bind_room(reset["room_id"], reset["epoch"])
        assert reset["epoch"] == 2
        assert rooms.read_messages(current)["messages"] == []
        assert rooms.get_room(current)["latest_round_id"] is None
        with pytest.raises(BookWorldError) as stale:
            rounds.get_round(old, turn["round_id"])
        assert stale.value.code == "stale_room_epoch"
    finally:
        release.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_reviewed_summary_keeps_speaker_sources_after_restart_and_dies_with_epoch(
    book_library,
):
    from backend.services.book_world.memory import RoomMemoryService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="summary-room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    for index, content in enumerate(
        [
            "我的代号是青禾",
            "门在北边",
            "我猜门也许在南边",
            "我不知道门在哪里",
            "刚才的说法只是猜测",
            "现在聊点别的",
        ]
    ):
        turn = rounds.submit(scope, f"memory-{index}", content, config, time_limit_seconds=60)
        rounds.control(scope, turn["round_id"], "cancel")
    baseline = rooms.knowledge.baseline(character).model_dump()
    memory = RoomMemoryService(book_library.workspace_root)
    plan = memory.prepare(scope, before_seq=7, keep_recent=2, trigger_messages=4)
    assert plan is not None and plan.through_seq == 4
    source = plan.messages[0]
    candidate = {
        "items": [
            {
                "text": "用户说自己的代号是青禾",
                "origin": "room_hearsay",
                "speaker_type": "user",
                "speaker_member_id": None,
                "source_message_ids": [source["id"]],
            }
        ]
    }
    review = {
        "supported": True,
        "attribution_correct": True,
        "uncertainty_preserved": True,
        "items": [{"ordinal": 0, "supported": True, "origin_correct": True}],
        "reason": "用户原话；仅保存听说",
    }
    published = memory.publish(plan, candidate, review)
    assert published["through_seq"] == 4
    restored = RoomMemoryService(book_library.workspace_root).read(scope)
    assert restored["items"][0]["source_message_ids"] == [source["id"]]
    assert restored["items"][0]["origin"] == "room_hearsay"
    assert restored["items"][0]["speaker_type"] == "user"
    assert rooms.knowledge.baseline(character).model_dump() == baseline
    other = rooms.create_single_room(character, client_room_id="summary-other-room")
    assert memory.read(rooms.bind_room(other["room_id"], 1)) is None
    reset = rooms.reset_memory(scope)
    assert memory.read(rooms.bind_room(reset["room_id"], 2)) is None
    with pytest.raises(BookWorldError) as stale:
        memory.publish(plan, candidate, review)
    assert stale.value.code == "stale_room_epoch"


@pytest.mark.asyncio
async def test_long_dialogue_worker_uses_reviewed_old_memory_as_hearsay(book_library):
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.memory import RoomMemoryService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="long-memory-room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(
        provider_id=1, model="fixture", memory_policy_version="typed-room-memory-v1"
    )
    for index in range(42):
        turn = rounds.submit(
            scope,
            f"old-{index}",
            "我的代号是青禾" if index == 0 else f"旧话题 {index}",
            config,
            time_limit_seconds=60,
        )
        rounds.control(scope, turn["round_id"], "cancel")
    turn = rounds.submit(scope, "recall", "还记得我说的代号吗？", config, time_limit_seconds=60)
    phases = []

    class Remembering:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            phases.append(data["phase"])
            if data["phase"] == "summary_generate":
                source = data["context"]["messages"][0]
                result = {
                    "items": [
                        {
                            "text": "用户说自己的代号是青禾",
                            "origin": "room_hearsay",
                            "speaker_type": "user",
                            "speaker_member_id": None,
                            "source_message_ids": [source["id"]],
                        }
                    ]
                }
            elif data["phase"] == "summary_review":
                result = {
                    "supported": True,
                    "attribution_correct": True,
                    "uncertainty_preserved": True,
                    "items": [{"ordinal": 0, "supported": True, "origin_correct": True}],
                    "reason": "准确保存用户说法",
                }
            elif data["phase"] == "generate":
                memory = data["context"]["room_memory"]["items"][0]
                assert memory["origin"] == "room_hearsay"
                assert "青禾" not in json.dumps(data["context"]["baseline"], ensure_ascii=False)
                result = {
                    "content": "你说过自己的代号是青禾。",
                    "dialogue_action": "answer",
                    "claims": [
                        {
                            "text": "你说过自己的代号是青禾",
                            "origin": "room_hearsay",
                            "message_ids": memory["source_message_ids"],
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
        scope, turn["round_id"], Remembering(), config
    )
    assert phases == ["summary_generate", "summary_review", "generate", "review"]
    assert RoomMemoryService(book_library.workspace_root).read(scope)["through_seq"] == 20
    reply = rooms.read_messages(scope)["messages"][-1]
    assert reply["content"] == "你说过自己的代号是青禾。"
    assert reply["refs"][0]["origin"] == "room_hearsay"


@pytest.mark.asyncio
async def test_desktop_reset_advances_epoch_and_old_requests_cannot_read_memory(book_library):
    from unittest.mock import patch

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="protocol-memory-reset")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(
        scope,
        "old-protocol-message",
        "旧代数信息",
        CharacterChatConfig(provider_id=1, model="fixture"),
        time_limit_seconds=60,
    )
    handler, socket = module.BookRoomHandler(object()), Socket()
    with patch.object(module, "get_workspace_path", lambda: book_library.workspace_root):

        async def request(action, epoch):
            await handler.handle(
                socket,
                WSMessage(
                    type=MessageType.BOOK_ROOM,
                    request_id=action,
                    data={
                        "action": action,
                        "workspace_id": scope.workspace_id,
                        "room_id": scope.room_id,
                        "expected_epoch": epoch,
                    },
                ),
            )
            return socket.messages[-1]

        result = await request("reset_memory", 1)
        assert result["type"] == "book_room_result"
        assert result["data"]["epoch"] == 2
        assert turn["round_id"] in result["data"]["cancelled_round_ids"]
        assert (await request("get_memory", 2))["data"]["memory"] is None
        stale = await request("read_messages", 1)
        assert stale["type"] == "error" and stale["data"]["code"] == "stale_room_epoch"


async def summary_fixture(library, *, typed=False):
    from backend.services.book_world.memory import RoomMemoryService

    _, _, _, character = await style_character(library)
    rooms = BookRoomService(library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="memory-guard-room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(library.workspace_root)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        memory_policy_version="typed-room-memory-v1" if typed else "legacy-history-v1",
    )
    for index in range(6):
        turn = rounds.submit(
            scope, f"guard-{index}", f"用户公开说法 {index}", config, time_limit_seconds=60
        )
        rounds.control(scope, turn["round_id"], "cancel")
    memory = RoomMemoryService(library.workspace_root)
    plan = memory.prepare(scope, before_seq=7, keep_recent=2, trigger_messages=4)
    candidate = {
        "items": [
            {
                "text": "用户公开说法 0",
                "origin": "room_hearsay",
                "speaker_type": "user",
                "speaker_member_id": None,
                "source_message_ids": [plan.messages[0]["id"]],
            }
        ]
    }
    review = {
        "supported": True,
        "attribution_correct": True,
        "uncertainty_preserved": True,
        "items": [{"ordinal": 0, "supported": True, "origin_correct": True}],
        "reason": "原公开说法",
    }
    return rooms, rounds, scope, room, config, memory, plan, candidate, review, character


@pytest.mark.asyncio
async def test_committed_reset_succeeds_when_physical_cleanup_is_unavailable(book_library):
    import asyncio
    from unittest.mock import patch

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="cleanup-failure-room")
    cleanup_attempted = asyncio.Event()
    loop = asyncio.get_running_loop()

    def unavailable(_self, _scope):
        loop.call_soon_threadsafe(cleanup_attempted.set)
        raise OSError("temporary cleanup failure")

    handler, socket = module.BookRoomHandler(object()), Socket()
    with (
        patch.object(module, "get_workspace_path", lambda: book_library.workspace_root),
        patch.object(BookRoomService, "cleanup_cleared_memory", unavailable),
    ):
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_ROOM,
                request_id="reset-without-cleanup",
                data={
                    "action": "reset_memory",
                    "workspace_id": rooms.workspace_id,
                    "room_id": room["room_id"],
                    "expected_epoch": 1,
                },
            ),
        )
        await asyncio.wait_for(cleanup_attempted.wait(), 5)
        await asyncio.sleep(0)
        assert socket.messages[-1]["type"] == "book_room_result"
        assert socket.messages[-1]["data"]["epoch"] == 2
        assert rooms.read_messages(rooms.bind_room(room["room_id"], 2))["messages"] == []
        with pytest.raises(BookWorldError) as stale:
            rooms.bind_room(room["room_id"], 1)
        assert stale.value.code == "stale_room_epoch"


@pytest.mark.asyncio
async def test_summary_can_advance_past_a_long_message_without_truncating_sources(book_library):
    from backend.services.book_world.memory import RoomMemoryService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="summary-budget-room")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    long_message = "长" * 4000
    for index in range(30):
        content = "用户喜欢早起。" * 45 if index < 4 else long_message if index == 4 else "日常交流"
        turn = rounds.submit(scope, f"budget-{index}", content, config, time_limit_seconds=60)
        rounds.control(scope, turn["round_id"], "cancel")
    memory = RoomMemoryService(book_library.workspace_root)
    first = memory.prepare(scope, before_seq=7, keep_recent=2, trigger_messages=4)
    candidate = {
        "items": [
            {
                "text": first.messages[index % 4]["content"][:300],
                "origin": "room_hearsay",
                "speaker_type": "user",
                "speaker_member_id": None,
                "source_message_ids": [first.messages[index % 4]["id"]],
            }
            for index in range(12)
        ]
    }
    review = {
        "supported": True,
        "attribution_correct": True,
        "uncertainty_preserved": True,
        "items": [
            {"ordinal": index, "supported": True, "origin_correct": True} for index in range(12)
        ],
        "reason": "预算行为夹具；内容来自同一说话者原话",
    }
    published = memory.publish(first, candidate, review)
    next_plan = memory.prepare(scope, before_seq=31, max_input_bytes=18000)
    assert next_plan is not None and next_plan.through_seq >= 5
    assert next_plan.messages[0]["content"] == long_message
    assert next_plan.previous_id == published["id"]
    assert len(next_plan.previous_items) < 12
    assert all(item in published["items"] for item in next_plan.previous_items)
    # Whole original messages remain independently retrievable if an old summary item is omitted.
    assert memory.recall(scope, "早起", before_seq=31)[0]["content"].startswith("用户喜欢早起")


@pytest.mark.asyncio
@pytest.mark.parametrize("covered", [True, False])
async def test_optional_long_recalls_do_not_displace_current_question_or_sourced_summary(
    book_library, covered
):
    from backend.services.book_world.memory import RoomMemoryService

    _, _, _, character = await style_character(book_library)
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(character, client_room_id="context-memory-budget")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        memory_policy_version="typed-room-memory-v1",
        max_input_tokens=10000,
    )
    for index in range(7):
        turn = rounds.submit(
            scope,
            f"long-recall-{index}",
            "我喜欢看云。" + "云" * 3993 if index < 6 else "换个话题",
            config,
            time_limit_seconds=60,
        )
        rounds.control(scope, turn["round_id"], "cancel")
    memory = RoomMemoryService(book_library.workspace_root)
    plan = memory.prepare(
        scope, before_seq=8, keep_recent=1, trigger_messages=7, max_input_bytes=200000
    )
    candidate = {
        "items": [
            {
                "text": "用户说喜欢看云",
                "origin": "room_hearsay",
                "speaker_type": "user",
                "speaker_member_id": None,
                "source_message_ids": [message["id"]],
            }
            for message in plan.messages
        ]
        if covered
        else []
    }
    review = {
        "supported": True,
        "attribution_correct": True,
        "uncertainty_preserved": True,
        "items": [
            {"ordinal": index, "supported": True, "origin_correct": True}
            for index in range(len(candidate["items"]))
        ],
        "reason": "准确压缩同说话者的偏好；预算回归",
    }
    memory.publish(plan, candidate, review)
    question = "还记得我说喜欢看云吗？"
    turn = rounds.submit(scope, "short-current-query", question, config, time_limit_seconds=60)
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    assert context.payload["current_message"]["content"] == question
    assert context.diagnostics["input_bytes"] <= 10000
    assert context.payload["baseline"]
    if covered:
        assert len(context.payload["room_memory"]["items"]) == 6
        assert not {message["id"] for message in plan.messages} & {
            message["id"] for message in context.payload["room_history"]
        }
    else:
        assert context.diagnostics["omitted_history"] > 0


@pytest.mark.asyncio
async def test_cross_book_memory_is_public_hearsay_and_reset_preserves_both_bindings(book_library):
    import json
    from uuid import uuid4

    from backend.services.book_world.storage import connect

    (
        rooms,
        rounds,
        scope,
        _room,
        _config,
        memory,
        plan,
        candidate,
        review,
        first,
    ) = await summary_fixture(book_library, typed=True)
    _, _, _, second = await style_character(book_library)
    second_room = rooms.create_single_room(second, client_room_id="cross-book-other")
    other = second_room["members"][0]
    assert second.book_id != first.book_id
    # Approved temporary SQLite contract fixture: T08 owns public multi-member creation.
    with connect(rooms.db_path) as db:
        db.execute(
            "INSERT INTO book_room_sources(room_id,book_id,source_version_id,build_id,source_snapshot_json) SELECT ?,book_id,source_version_id,build_id,source_snapshot_json FROM book_room_sources WHERE room_id=?",
            (scope.room_id, second_room["room_id"]),
        )
        second_member = str(uuid4())
        db.execute(
            "INSERT INTO book_room_members(id,room_id,book_id,source_version_id,build_id,character_id,seat_index,identity_snapshot_json,state_epoch) VALUES (?,?,?,?,?,?,1,?,1)",
            (
                second_member,
                scope.room_id,
                *second.binding,
                json.dumps(other["identity"], ensure_ascii=False),
            ),
        )
    before = rooms.get_room(scope)
    baselines = [rooms.knowledge.baseline(actor).model_dump() for actor in (first, second)]
    memory.publish(plan, candidate, review)
    # Both actor inputs share the same public summary but retain their own original scopes.
    turn_id = rooms.read_messages(scope)["messages"][-1]["round_id"]
    for member, actor in zip(before["members"], (first, second), strict=True):
        context = CharacterContextBuilder(book_library.workspace_root).compose(
            scope, turn_id, member["id"]
        )
        assert context.character_scope == actor
        assert context.payload["room_memory"]["items"][0]["origin"] == "room_hearsay"
        assert (
            context.payload["room_memory"]["items"][0]["source_message_ids"]
            == candidate["items"][0]["source_message_ids"]
        )
        assert (member["book_id"], member["build_id"], member["character_id"]) == (
            actor.book_id,
            actor.build_id,
            actor.character_id,
        )
    assert rounds.get_round(scope, turn_id)["status"] == "cancelled"
    reset = rooms.reset_memory(scope)
    assert reset["epoch"] == 2 and reset["next_seq"] == before["next_seq"]
    assert len(reset["members"]) == 2
    for old, current in zip(before["members"], reset["members"], strict=True):
        assert all(
            current[key] == old[key]
            for key in (
                "id",
                "book_id",
                "source_version_id",
                "build_id",
                "character_id",
                "seat_index",
            )
        )
        assert current["membership_generation"] == old["membership_generation"] + 1
    assert memory.read(rooms.bind_room(scope.room_id, 2)) is None
    assert [rooms.knowledge.baseline(actor).model_dump() for actor in (first, second)] == baselines


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["foreign_room", "later_message", "wrong_speaker", "canon_upgrade", "mutated_input"]
)
async def test_summary_structure_rejects_ungranted_sources_even_if_review_is_permissive(
    book_library, failure
):
    (
        rooms,
        rounds,
        scope,
        room,
        config,
        memory,
        plan,
        candidate,
        review,
        character,
    ) = await summary_fixture(book_library)
    if failure == "foreign_room":
        other = rooms.create_single_room(character, client_room_id="foreign-summary-room")
        other_scope = rooms.bind_room(other["room_id"], 1)
        rounds.submit(other_scope, "foreign-turn", "其他房间消息", config, time_limit_seconds=60)
        candidate["items"][0]["source_message_ids"] = [
            rooms.read_messages(other_scope)["messages"][0]["id"]
        ]
    elif failure == "later_message":
        candidate["items"][0]["source_message_ids"] = [
            rooms.read_messages(scope)["messages"][4]["id"]
        ]
    elif failure == "wrong_speaker":
        candidate["items"][0].update(
            speaker_type="character", speaker_member_id=room["members"][0]["id"]
        )
    elif failure == "canon_upgrade":
        candidate["items"][0]["origin"] = "canon"
    else:
        plan.messages[0]["content"] = "篡改输入"
    with pytest.raises(ValueError):
        memory.publish(plan, candidate, review)
    assert memory.read(scope) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["cancelled", "deadline_crossing"])
async def test_memory_publication_is_fenced_by_the_round_and_time_window(book_library, failure):
    from backend.services.book_world.round_execution import RoundExecution

    (
        rooms,
        rounds,
        scope,
        room,
        config,
        memory,
        plan,
        candidate,
        review,
        _character,
    ) = await summary_fixture(book_library)
    turn = rounds.submit(scope, "memory-execution", "当前问题", config, time_limit_seconds=60)
    lease = RoundExecution(rounds).lease(scope, turn["round_id"], config)
    if failure == "cancelled":
        rounds.control(scope, turn["round_id"], "cancel")

        def elapsed():
            return 0

        expected = "stale_round"
    else:
        times = iter([0, 60000])

        def elapsed():
            return next(times)

        expected = "round_timeout"
    with pytest.raises(BookWorldError) as rejected:
        memory.publish(plan, candidate, review, fence=lease, elapsed=elapsed)
    assert rejected.value.code == expected
    assert memory.read(scope) is None
