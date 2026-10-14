"""Real persistent seats and route bootstrap; controlled publication is not persona QA."""
import pytest
from test_book_persona import ScriptedPersonaProvider, discovered, review_all

from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.room_models import CharacterChatConfig
from backend.services.book_world.rounds import BookRoundService
from backend.services.book_world.source import BookWorldError
from backend.services.book_world.storage import connect


async def cast(library, count=32):
    people = [(f"人物{index:02}", "active") for index in range(count)]
    text = " ".join(f"{name}说：你好。" for name, _ in people)
    item, parent = await discovered(library, text, people=people)
    personas = BookPersonaService(library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=8000)
    build = personas.request_build(item, parent, config)["build_id"]
    await personas.run(build, ScriptedPersonaProvider(lambda data: {"claims": []}, review_all), config)
    membership = RoomMembershipService(library.workspace_root)
    return [membership.rooms.knowledge.bind_character(item, build, person["id"]) for person in personas.discovery.list_characters(item, build, limit=100)["characters"]]


@pytest.mark.asyncio
async def test_32_persistent_seats_expand_only_when_idle_and_all_slots_cover_them(book_library):
    actors = await cast(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors[:8], client_room_id="scene-capacity")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    waiting = rounds.submit(scope, "busy", "你好", config, time_limit_seconds=60, mode="all")
    with pytest.raises(BookWorldError) as busy:
        membership.add(scope, actors[8:16])
    assert busy.value.code == "room_busy"
    rounds.control(scope, waiting["round_id"], "cancel")
    joined = membership.add(scope, actors[8:])
    assert joined["scene_capacity"] == 32
    assert [member["seat_index"] for member in joined["members"]] == list(range(32))
    identities = [(member["id"], member["seat_index"]) for member in joined["members"]]
    membership.control(scope, identities[0][0], active=False)
    assert membership.rooms.get_room(scope)["members"][0]["seat_index"] == 0
    membership.control(scope, identities[0][0], active=True)
    reset = membership.rooms.reset_memory(scope)
    reopened = membership.rooms.open_room(room["room_id"])
    assert reopened["epoch"] == reset["epoch"] == 2
    assert [(member["id"], member["seat_index"]) for member in reopened["members"]] == identities
    current = membership.rooms.bind_room(room["room_id"], 2)
    queued = rounds.submit(current, "32-all", "你好", config, time_limit_seconds=300, mode="all")
    assert len(queued["slots"]) == 32 and {slot["member_id"] for slot in queued["slots"]} == {identity[0] for identity in identities}
    assert "approved_excerpt" not in str(reopened) and "runtime_policy" not in str(reopened)


@pytest.mark.asyncio
async def test_route_bootstrap_requires_workspace_and_does_not_relax_mutation_epoch(book_library, monkeypatch):
    from test_book_knowledge import style_character
    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage

    actor = (await style_character(book_library))[3]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="route-current-epoch")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    membership.rooms.reset_memory(scope)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    handler, socket = module.BookRoomHandler(object()), Socket()
    data = {"action": "open_room", "workspace_id": membership.rooms.workspace_id, "room_id": room["room_id"]}
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM, request_id="open-current", data=data))
    assert socket.messages[-1]["data"]["epoch"] == 2
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM, request_id="wrong-root", data={**data, "workspace_id": "other"}))
    assert socket.messages[-1]["data"]["code"] == "invalid_scope"
    await handler.handle(socket, WSMessage(type=MessageType.BOOK_ROOM, request_id="missing-epoch", data={**data, "action": "reset_memory"}))
    assert socket.messages[-1]["data"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_public_member_profile_is_room_scoped_and_excludes_reader_material(book_library):
    from test_book_knowledge import style_character

    actor = (await style_character(book_library))[3]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="public-profile")
    other = membership.create([actor], client_room_id="other-profile-room")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    member_id = room["members"][0]["id"]
    profile = membership.rooms.get_member_profile(scope, member_id)
    assert profile["public"]["name"] == room["members"][0]["identity"]["name"]
    assert profile["build_id"] == actor.build_id
    assert not {"reader", "claims", "runtime_policy", "baseline", "evidence"}.intersection(profile)
    with pytest.raises(BookWorldError) as cross_room:
        membership.rooms.get_member_profile(scope, other["members"][0]["id"])
    assert cross_room.value.code == "invalid_scope"
    membership.rooms.reset_memory(scope)
    with pytest.raises(BookWorldError) as stale:
        membership.rooms.get_member_profile(scope, member_id)
    assert stale.value.code == "stale_room_epoch"


@pytest.mark.asyncio
async def test_shortcut_public_lookup_is_not_limited_to_first_catalog_page(book_library):
    from backend.services.book_world.room_catalog import RoomCharacterCatalog

    groups = [await cast(book_library) for _ in range(4)]
    catalog = RoomCharacterCatalog(book_library.workspace_root)
    first = catalog.list(limit=100)
    selected = groups[-1][-1]
    assert first["total"] == 128
    assert selected.character_id not in {person["character_id"] for person in first["characters"]}
    with pytest.raises(BookWorldError):
        catalog.get(1, selected.build_id, selected.character_id)
    with connect(catalog.rooms.db_path) as db:
        item = db.execute("SELECT library_item_id FROM book_books WHERE id=?", (selected.book_id,)).fetchone()[0]
    result = catalog.get(item, selected.build_id, selected.character_id)
    assert result["character"]["character_id"] == selected.character_id
    assert "quote" not in str(result) and "baseline" not in str(result)
