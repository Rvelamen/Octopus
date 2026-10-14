"""Public finite all-member queue and execution controls in disposable workspaces."""

import json

import pytest
from test_book_knowledge import style_character
from test_book_rooms import empty_review

from backend.core.providers.base import LLMResponse
from backend.services.book_world.chat_worker import BookChatWorker
from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.room_models import CharacterChatConfig
from backend.services.book_world.rounds import BookRoundService


@pytest.mark.asyncio
async def test_first_workspace_entry_after_restart_recovers_old_turn_but_reentry_keeps_new_turn(
    book_library,
):
    from backend.channels.desktop.handlers.book_room import BookRoomHandler

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="workspace-entry")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    old = rounds.submit(
        scope, "old-process-turn", "大家好", config, time_limit_seconds=300, mode="all"
    )

    class FreshServer(BookRoomHandler):
        _initialized_workspaces = set()

    assert await FreshServer.initialize_workspace(book_library.workspace_root) == [old["round_id"]]
    assert rounds.get_round(scope, old["round_id"])["status"] == "interrupted"
    rounds.control(scope, old["round_id"], "resume", time_limit_seconds=300)
    assert await FreshServer.initialize_workspace(book_library.workspace_root) == []
    assert rounds.get_round(scope, old["round_id"])["status"] == "queued"


class Greetings:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.calls.append(data)
        return LLMResponse(
            content=json.dumps(
                {"content": "你好。", "dialogue_action": "greet", "claims": []}
                if data["phase"] == "generate"
                else empty_review(),
                ensure_ascii=False,
            )
        )


@pytest.mark.asyncio
async def test_source_loss_during_generation_continues_other_book_without_publishing_late_text(
    book_library,
):
    entries = [await style_character(book_library) for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([entry[3] for entry in entries], client_room_id="inflight-source-loss")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        scope, "inflight-source-turn", "大家好", config, time_limit_seconds=300, mode="all"
    )
    calls = Greetings()

    class RemoveCurrent:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if (
                data["phase"] == "generate"
                and data["context"]["character_scope"]["character_id"] == entries[0][3].character_id
            ):
                assert book_library.delete_item(entries[0][0])
            return await calls.chat(messages, **kwargs)

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], RemoveCurrent(), config
    )
    final = rounds.get_round(scope, turn["round_id"])
    assert final["status"] == "completed" and final["cursor"] == 2
    assert (
        final["slots"][0]["status"] == "no_comment"
        and final["slots"][0]["skip_reason"] == "source_unavailable"
    )
    history = membership.rooms.read_messages(scope)["messages"]
    assert len(history) == 2 and history[1]["speaker_member_id"] == room["members"][1]["id"]


@pytest.mark.asyncio
async def test_all_keeps_every_slot_and_explicitly_skips_muted_and_removed(
    book_library,
):
    actors = [(await style_character(book_library))[3] for _ in range(6)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="all-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    ids = [member["id"] for member in room["members"]]
    membership.control(scope, ids[0], speaking_mode="muted")
    membership.control(scope, ids[1], active=False)
    membership.control(scope, ids[2], speaking_mode="mention_only")
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        scope, "all-question", "大家好", config, time_limit_seconds=300, mode="all"
    )
    assert len(turn["slots"]) == 6 and turn["cursor"] == 2
    assert [slot["skip_reason"] for slot in turn["slots"][:2]] == ["muted", "removed"]
    provider = Greetings()
    await BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], provider, config)
    final = rounds.get_round(scope, turn["round_id"])
    assert final["status"] == "completed" and final["cursor"] == 6
    assert [slot["status"] for slot in final["slots"]] == ["no_comment"] * 2 + ["published"] * 4
    assert len(provider.calls) == 8
    assert [
        m["speaker_member_id"] for m in membership.rooms.read_messages(scope)["messages"][1:]
    ] == ids[2:]


@pytest.mark.asyncio
async def test_pause_revokes_inflight_text_and_resume_keeps_published_slots(book_library):
    import asyncio

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="pause-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        scope, "pause-question", "大家好", config, time_limit_seconds=300, mode="all"
    )
    started, release = asyncio.Event(), asyncio.Event()
    provider = Greetings()

    class SlowSecond:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if (
                data["phase"] == "generate"
                and data["context"]["character_scope"]["character_id"] == actors[1].character_id
            ):
                started.set()
                await release.wait()
            return await provider.chat(messages, **kwargs)

    task = asyncio.create_task(
        BookChatWorker(book_library.workspace_root).run(
            scope, turn["round_id"], SlowSecond(), config
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 10)
        current = rounds.get_round(scope, turn["round_id"])
        assert current["generation"]["member_id"] == room["members"][1]["id"]
        paused = rounds.control(scope, turn["round_id"], "pause")
        assert (
            paused["status"] == "paused" and paused["cursor"] == 1 and paused["generation"] is None
        )
        release.set()
        await asyncio.wait_for(task, 10)
        assert len(membership.rooms.read_messages(scope)["messages"]) == 2
        resumed = rounds.control(scope, turn["round_id"], "resume", time_limit_seconds=120)
        assert resumed["execution_window"] == 2 and resumed["time_limit_seconds"] == 120
        await BookChatWorker(book_library.workspace_root).run(
            scope, turn["round_id"], provider, config
        )
        history = membership.rooms.read_messages(scope)["messages"]
        assert [m["seq"] for m in history] == [1, 2, 3]
        assert len({m["speaker_member_id"] for m in history[1:]}) == 2
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_restart_marks_work_interrupted_without_model_calls_and_replays_no_published_slot(
    book_library,
):
    import asyncio

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="restart-queue")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        scope, "restart-question", "大家好", config, time_limit_seconds=300, mode="all"
    )
    held, release = asyncio.Event(), asyncio.Event()
    provider = Greetings()

    class CrashAtSecond:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if (
                data["phase"] == "generate"
                and data["context"]["character_scope"]["character_id"] == actors[1].character_id
            ):
                held.set()
                await release.wait()
            return await provider.chat(messages, **kwargs)

    old = asyncio.create_task(
        BookChatWorker(book_library.workspace_root).run(
            scope, turn["round_id"], CrashAtSecond(), config
        )
    )
    try:
        await asyncio.wait_for(held.wait(), 10)
        restarted = BookRoundService(book_library.workspace_root)
        assert restarted.recover_interrupted() == [turn["round_id"]]
        current = restarted.get_round(scope, turn["round_id"])
        assert (
            current["status"] == "interrupted"
            and current["cursor"] == 1
            and current["generation"] is None
        )
        assert restarted.recover_interrupted() == []
        fresh = Greetings()
        await BookChatWorker(book_library.workspace_root).run(
            scope, turn["round_id"], fresh, config
        )
        assert fresh.calls == []
        restarted.control(scope, turn["round_id"], "resume", time_limit_seconds=300)
        await BookChatWorker(book_library.workspace_root).run(
            scope, turn["round_id"], fresh, config
        )
        release.set()
        await asyncio.wait_for(old, 10)
        assert [
            slot["status"] for slot in restarted.get_round(scope, turn["round_id"])["slots"]
        ] == ["published", "published"]
        assert [
            message["seq"] for message in membership.rooms.read_messages(scope)["messages"]
        ] == [1, 2, 3]
        assert len(fresh.calls) == 2
    finally:
        release.set()
        if not old.done():
            old.cancel()
            await asyncio.gather(old, return_exceptions=True)


@pytest.mark.asyncio
async def test_source_loss_after_all_snapshot_skips_only_that_member(book_library):
    entries = [await style_character(book_library) for _ in range(3)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([entry[3] for entry in entries], client_room_id="source-loss")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        scope, "before-source-loss", "大家好", config, time_limit_seconds=300, mode="all"
    )
    assert book_library.delete_item(entries[1][0])
    provider = Greetings()
    await BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], provider, config)
    final = rounds.get_round(scope, turn["round_id"])
    assert final["status"] == "completed"
    assert [slot["status"] for slot in final["slots"]] == ["published", "no_comment", "published"]
    assert final["slots"][1]["skip_reason"] == "source_unavailable"
    assert len(provider.calls) == 4
    next_turn = rounds.submit(
        scope, "after-source-loss", "大家好", config, time_limit_seconds=300, mode="all"
    )
    assert (
        len(next_turn["slots"]) == 3
        and next_turn["slots"][1]["skip_reason"] == "source_unavailable"
    )


@pytest.mark.asyncio
async def test_handler_all_seconds_pause_and_continue_use_current_preferences(
    book_library, monkeypatch
):
    import asyncio

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as handler_module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.services.book_world.chat_provider import CharacterChatModel

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="handler-all")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    settings = [
        BookRoomTimeoutSettings(bookRoomRoundTimeoutSeconds=2, bookRoomAllRoundTimeoutSeconds=7)
    ]
    started = asyncio.Event()
    calls = Greetings()

    class FirstCallHeld:
        first = True

        async def chat(self, messages, **kwargs):
            if self.first:
                self.first = False
                started.set()
                await asyncio.Event().wait()
            return await calls.chat(messages, **kwargs)

    provider = FirstCallHeld()
    monkeypatch.setattr(handler_module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        handler_module,
        "resolve_character_chat_model",
        lambda *args, **kwargs: CharacterChatModel(
            provider, kwargs.get("original_config", config), settings[0]
        ),
    )
    handler, socket = handler_module.BookRoomHandler(object()), Socket()

    async def request(action, **values):
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
        assert socket.messages[-1]["type"] == "book_room_result", socket.messages[-1]
        return socket.messages[-1]["data"]

    try:
        submitted = await request(
            "submit_turn", client_turn_id="all-settings", content="大家好", mode="all"
        )
        assert submitted["time_limit_seconds"] == 7
        await asyncio.wait_for(started.wait(), 10)
        paused = await request("pause_round", round_id=submitted["round_id"])
        assert paused["status"] == "paused" and paused["generation"] is None
        settings[0] = BookRoomTimeoutSettings(
            bookRoomRoundTimeoutSeconds=3, bookRoomAllRoundTimeoutSeconds=11
        )
        assert (await request("get_round", round_id=submitted["round_id"]))[
            "time_limit_seconds"
        ] == 7
        resumed = await request("resume_round", round_id=submitted["round_id"])
        assert resumed["time_limit_seconds"] == 11 and resumed["execution_window"] == 2
        task = handler._tasks.get((scope.workspace_id, submitted["round_id"]))
        if task:
            await asyncio.wait_for(asyncio.shield(task), 10)
        complete = await request("get_round", round_id=submitted["round_id"])
        assert complete["status"] == "completed" and complete["generation"] is None
        history = await request("read_messages", after_seq=1)
        assert [message["seq"] for message in history["messages"]] == [2, 3]
    finally:
        for key, task in list(handler._tasks.items()):
            if key[0] == scope.workspace_id:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
