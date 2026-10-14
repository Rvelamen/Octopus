"""Release gates preserve source access and never start disabled model work."""

import pytest
from test_book_world_handler import Socket

from backend.channels.desktop.handlers.book_world import BookWorldHandler
from backend.channels.desktop.handlers.config import GetConfigHandler
from backend.channels.desktop.protocol import MessageType, WSMessage


@pytest.fixture(autouse=True)
def reset_features_cache():
    from backend.services.book_world.features import get_features

    get_features.cache_clear()
    yield
    get_features.cache_clear()


@pytest.mark.asyncio
async def test_config_advertises_effective_disabled_book_features(monkeypatch):
    monkeypatch.setenv("OCTOPUS_BOOK_WORLD_ENABLED", "0")
    socket = Socket()
    await GetConfigHandler(object(), db=object()).handle(socket, WSMessage(type=MessageType.GET_CONFIG, request_id="features"))
    assert socket.messages[-1]["data"]["book_world_features"] == {
        "characters": False, "single_chat": False, "group_chat": False, "automatic_import": False,
    }


@pytest.mark.asyncio
async def test_disabled_character_entry_does_not_create_build_or_resolve_model(book_library, monkeypatch):
    from test_book_discovery import story

    from backend.services.book_world.storage import connect

    item, source = story(book_library, "人物甲读书。")
    monkeypatch.setenv("OCTOPUS_BOOK_WORLD_ENABLED", "0")
    monkeypatch.setattr("backend.channels.desktop.handlers.book_world.get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr("backend.channels.desktop.handlers.book_world.resolve_discovery_model", lambda: pytest.fail("Disabled entry must not resolve or invoke a model"))
    socket = Socket()
    await BookWorldHandler(object()).handle(socket, WSMessage(type=MessageType.BOOK_WORLD, request_id="disabled", data={"action":"start_discovery", "item_id":item, "source_version_id":source}))
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"
    with connect(book_library.db_path) as database:
        assert database.execute("SELECT count(*) FROM book_builds").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_disabled_characters_still_allow_source_reading(book_library, monkeypatch):
    from test_book_discovery import story

    item, source = story(book_library, "人物甲读书。")
    monkeypatch.setenv("OCTOPUS_BOOK_WORLD_ENABLED", "0")
    monkeypatch.setattr("backend.channels.desktop.handlers.book_world.get_workspace_path", lambda: book_library.workspace_root)
    socket = Socket()
    await BookWorldHandler(object()).handle(socket, WSMessage(type=MessageType.BOOK_WORLD, data={"action":"read_source", "item_id":item, "source_version_id":source}))
    assert socket.messages[-1]["type"] == "book_world_result"
    assert "人物甲读书。" in socket.messages[-1]["data"]["text"]


@pytest.mark.parametrize("environ,expected", [
    ({}, (True,True,True,True)),
    ({"OCTOPUS_BOOK_WORLD_ENABLED":"0"}, (False,False,False,False)),
    ({"OCTOPUS_BOOK_WORLD_ENABLED":"true"}, (False,False,False,False)),
    ({"OCTOPUS_BOOK_SINGLE_CHAT_ENABLED":"0"}, (True,False,False,True)),
    ({"OCTOPUS_BOOK_GROUP_CHAT_ENABLED":"0"}, (True,True,False,True)),
    ({"OCTOPUS_BOOK_AUTO_IMPORT_ENABLED":"0"}, (True,True,True,False)),
])
def test_feature_dependencies_and_invalid_environment_are_explicit(environ, expected):
    from backend.services.book_world.features import load_features

    policy = load_features(environ)
    assert tuple(policy.public().values()) == expected


def test_release_configuration_is_frozen_until_restart(monkeypatch):
    from backend.services.book_world.features import get_features

    assert get_features().characters
    monkeypatch.setenv("OCTOPUS_BOOK_WORLD_ENABLED", "0")
    assert get_features().characters
    get_features.cache_clear()
    assert not get_features().characters


@pytest.mark.asyncio
async def test_disabled_auto_runner_never_scans_or_schedules(book_library, monkeypatch):
    import asyncio

    from backend.services.book_world.automatic_runner import AutoImportRunner

    monkeypatch.setenv("OCTOPUS_BOOK_AUTO_IMPORT_ENABLED", "0")
    root = book_library.workspace_root
    before = set(AutoImportRunner._scanners)
    AutoImportRunner.start(root)
    await asyncio.sleep(0)
    assert set(AutoImportRunner._scanners) == before
    await AutoImportRunner.schedule(object(), root, {"job_id":"disabled"})
    assert not any(key[-1] == "disabled" for key in AutoImportRunner._workers)


@pytest.mark.asyncio
async def test_disabled_group_room_keeps_history_and_blocks_model_resolution(book_library, monkeypatch):
    from test_book_knowledge import style_character

    from backend.channels.desktop.handlers.book_room import BookRoomHandler
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="retained-disabled-group")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "original", "已存问题", CharacterChatConfig(provider_id=1,model="fixture"), time_limit_seconds=60, mode="all")
    rounds.control(scope, turn["round_id"], "pause")
    monkeypatch.setenv("OCTOPUS_BOOK_GROUP_CHAT_ENABLED", "0")
    monkeypatch.setattr("backend.channels.desktop.handlers.book_room.get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr("backend.channels.desktop.handlers.book_room.resolve_character_chat_model", lambda *args,**kwargs: pytest.fail("Disabled room cannot resolve a model"))
    handler, socket = BookRoomHandler(object()), Socket()
    base = {"workspace_id":scope.workspace_id,"room_id":scope.room_id,"expected_epoch":1}
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM,data={**base,"action":"resume_round","round_id":turn["round_id"]}))
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"
    assert rounds.get_round(scope,turn["round_id"])["status"] == "paused"
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM,data={**base,"action":"reset_memory"}))
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"
    assert membership.rooms.get_room(scope)["epoch"] == 1
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM,data={**base,"action":"read_messages"}))
    assert socket.messages[-1]["data"]["messages"][0]["content"] == "已存问题"
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM,data={**base,"action":"set_member","member_id":room["members"][0]["id"],"speaking_mode":"muted"}))
    assert socket.messages[-1]["type"] == "book_room_result"
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM,data={**base,"action":"set_member","member_id":room["members"][0]["id"],"active":False,"speaking_mode":"auto"}))
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"


@pytest.mark.asyncio
async def test_one_member_group_retains_group_release_policy(book_library, monkeypatch):
    from test_book_knowledge import style_character

    from backend.channels.desktop.handlers.book_room import BookRoomHandler
    from backend.services.book_world.members import RoomMembershipService

    actor = (await style_character(book_library))[3]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor],client_room_id="one-person-group")
    scope = membership.rooms.bind_room(room["room_id"],1)
    assert membership.rooms.get_room(scope)["kind"] == "group"
    monkeypatch.setenv("OCTOPUS_BOOK_GROUP_CHAT_ENABLED","0")
    monkeypatch.setattr("backend.channels.desktop.handlers.book_room.get_workspace_path",lambda:book_library.workspace_root)
    monkeypatch.setattr("backend.channels.desktop.handlers.book_room.resolve_character_chat_model",lambda *args,**kwargs:pytest.fail("Disabled group must not resolve a model"))
    socket = Socket()
    await BookRoomHandler(object()).handle(socket,WSMessage(type=MessageType.BOOK_ROOM,data={"action":"submit_turn","workspace_id":scope.workspace_id,"room_id":scope.room_id,"expected_epoch":1,"client_turn_id":"blocked-group","content":"不能启动的一人群聊"}))
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"
