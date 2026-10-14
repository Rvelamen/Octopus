"""Source deletion fences current authorization and purges original payloads, not identities."""

import pytest
from test_book_knowledge import style_character

from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.storage import connect


@pytest.mark.asyncio
async def test_delete_purges_only_its_book_and_retains_room_identity_until_readonly(book_library):
    first = await style_character(book_library)
    second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([first[3], second[3]], client_room_id="lifecycle-mixed")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    ids = [member["id"] for member in room["members"]]
    assert book_library.delete_item(first[0])
    after = membership.rooms.get_room(scope)
    assert after["status"] == "active"
    assert after["members"][0]["id"] == ids[0] and after["members"][0]["active"] == 0
    assert after["members"][0]["removed_reason"] == "source_removed"
    assert after["members"][0]["build_id"] == first[3].build_id
    assert after["members"][1]["active"] == 1 and after["members"][1]["available"]
    assert (
        next(source for source in after["sources"] if source["book_id"] == first[3].book_id)[
            "status"
        ]
        == "source_removed"
    )
    with connect(membership.db_path) as db:
        # Forensic storage seam: no original private text survives source deletion.
        assert (
            db.execute(
                "SELECT count(*) FROM book_segments WHERE book_id=? AND instr(text,'人物甲')>0",
                (first[3].book_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT count(*) FROM book_evidence WHERE book_id=? AND length(quote_text)>0",
                (first[3].book_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT count(*) FROM book_claims WHERE book_id=? AND length(proposition)>0",
                (first[3].book_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT count(*) FROM book_build_steps WHERE book_id=? AND result_json<>'{}'",
                (first[3].book_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT lifecycle_state FROM book_source_versions WHERE id=?",
                (first[3].source_version_id,),
            ).fetchone()[0]
            == "purged"
        )
        assert (
            db.execute(
                "SELECT count(*) FROM book_segments WHERE book_id=? AND instr(text,'人物甲')>0",
                (second[3].book_id,),
            ).fetchone()[0]
            > 0
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert book_library.delete_item(second[0])
    final = membership.rooms.get_room(scope)
    assert final["status"] == "readonly" and [member["id"] for member in final["members"]] == ids
    assert all(member["removed_reason"] == "source_removed" for member in final["members"])


@pytest.mark.asyncio
async def test_file_cleanup_failure_remains_fenced_and_retry_retains_history(
    book_library, monkeypatch
):
    import backend.services.book_world.lifecycle as module
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService
    from backend.services.book_world.source import BookWorldError

    item, _, _, actor = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="retry-cleanup")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    turn = BookRoundService(book_library.workspace_root).submit(
        scope,
        "before-delete",
        "你好",
        CharacterChatConfig(provider_id=1, model="fixture"),
        time_limit_seconds=60,
    )
    original = module.shutil.rmtree
    note_path = book_library.get_item(item)["library_path"].replace("\\", "/") + "/notes/private.md"
    with connect(membership.db_path) as db:
        db.execute("INSERT INTO library_chunks(item_id,chunk_index,text,embedding_json) VALUES (?,900,?,'[0.1]')", (item, "人物乙暗藏秘密"))
        db.execute("INSERT INTO library_notes(path,title,mtime,content) VALUES (?,'source note',1,?)", (note_path, "人物乙暗藏秘密"))
    assert book_library.search_chunks("人物乙暗藏秘密")
    monkeypatch.setattr(
        module.shutil,
        "rmtree",
        lambda path: (_ for _ in ()).throw(PermissionError("Controlled file lock")),
    )
    with pytest.raises(BookWorldError, match="Source disabled"):
        book_library.delete_item(item)
    lifecycle = module.BookLifecycleService(book_library.workspace_root)
    assert lifecycle.status(actor.book_id)["status"] == "failed"
    assert membership.rooms.get_room(scope)["status"] == "readonly"
    assert membership.rooms.read_messages(scope)["messages"][0]["content"] == "你好"
    assert book_library.search_chunks("人物乙暗藏秘密") == []
    assert book_library.get_item_chunks(item) == []
    with connect(membership.db_path) as db:
        assert db.execute("SELECT 1 FROM library_notes WHERE path=?", (note_path,)).fetchone() is None
        assert (
            db.execute(
                "SELECT count(*) FROM book_evidence WHERE book_id=? AND quote_text<>''",
                (actor.book_id,),
            ).fetchone()[0]
            == 0
        )
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError, match="source_removed"):
            db.execute("INSERT INTO library_chunks(item_id,chunk_index,text) VALUES (?,901,?)", (item, "人物乙暗藏秘密"))
    monkeypatch.setattr(module.shutil, "rmtree", original)
    assert lifecycle.purge(actor.book_id)["status"] == "completed"
    with pytest.raises(ValueError):
        book_library.get_item(item)
    assert membership.rooms.read_messages(scope)["messages"][0]["round_id"] == turn["round_id"]
    assert lifecycle.purge(actor.book_id)["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("delete_current", [False, True])
@pytest.mark.parametrize("provider_outcome", ["reply", "timeout", "transport"])
async def test_partial_source_deletion_does_not_cancel_other_books_turn(
    book_library, delete_current, provider_outcome
):
    import asyncio
    import json

    from test_book_rooms import empty_review

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.chat_worker import BookChatWorker
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    entries = [await style_character(book_library) for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(
        [entry[3] for entry in entries], client_room_id="mixed-inflight-delete"
    )
    scope = membership.rooms.bind_room(room["room_id"], 1)
    ids = [member["id"] for member in room["members"]]
    cfg = CharacterChatConfig(provider_id=1, model="fixture")
    rounds = BookRoundService(book_library.workspace_root)
    target_order = ids if delete_current else list(reversed(ids))
    turn = rounds.submit(
        scope,
        "partial-delete",
        "你好",
        cfg,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=target_order,
    )
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Replies:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data)
            if len(calls) == 1:
                entered.set()
                await release.wait()
                if delete_current and provider_outcome == "timeout":
                    raise TimeoutError("Controlled late timeout")
                if delete_current and provider_outcome == "transport":
                    raise RuntimeError("Controlled late transport failure")
            return LLMResponse(
                content=json.dumps(
                    {"content": "你好。", "dialogue_action": "greet", "claims": []}
                    if data["phase"] == "generate"
                    else empty_review(),
                    ensure_ascii=False,
                )
            )

    task = asyncio.create_task(
        BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], Replies(), cfg)
    )
    try:
        await asyncio.wait_for(entered.wait(), 10)
        before = rounds.get_round(scope, turn["round_id"])
        assert book_library.delete_item(entries[0][0])
        after = rounds.get_round(scope, turn["round_id"])
        if not delete_current:
            assert (
                after["generation"]["lease_generation"] == before["generation"]["lease_generation"]
            )
        release.set()
        await asyncio.wait_for(task, 10)
        final = rounds.get_round(scope, turn["round_id"])
        assert final["status"] == "completed" and final["cursor"] == 2
        assert membership.rooms.get_room(scope)["status"] == "active"
        messages = membership.rooms.read_messages(scope)["messages"]
        assert len(messages) == 2 and messages[1]["speaker_member_id"] == ids[1]
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_concurrent_cleanup_and_repeat_are_monotonic(book_library, monkeypatch):
    import asyncio
    import threading

    import backend.services.book_world.lifecycle as module
    from backend.services.book_world.source import BookWorldError

    item, _, _, actor = await style_character(book_library)
    original = module.shutil.rmtree
    monkeypatch.setattr(module.shutil, "rmtree", lambda path: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(BookWorldError):
        book_library.delete_item(item)
    entered, release = threading.Event(), threading.Event()
    removed = []

    def held(path):
        removed.append(path)
        entered.set()
        assert release.wait(5)
        original(path)

    monkeypatch.setattr(module.shutil, "rmtree", held)
    lifecycle = module.BookLifecycleService(book_library.workspace_root)
    first = asyncio.create_task(asyncio.to_thread(lifecycle.purge, actor.book_id))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        second = asyncio.create_task(asyncio.to_thread(lifecycle.purge, actor.book_id))
        release.set()
        assert [result["status"] for result in await asyncio.gather(first, second)] == ["completed", "completed"]
        assert len(removed) == 1 and lifecycle.status(actor.book_id)["status"] == "completed"
    finally:
        release.set()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_deletion_transaction_isolated_from_concurrent_metadata_commit(book_library, monkeypatch):
    import asyncio
    import threading

    import backend.services.book_world.storage as module

    item, _, _, actor = await style_character(book_library)
    original = module.disable_item_sources
    entered, release = threading.Event(), threading.Event()

    def failed(db, item_id, **kwargs):
        original(db, item_id, **kwargs)
        entered.set()
        assert release.wait(5)
        raise RuntimeError("Controlled rollback")

    monkeypatch.setattr(module, "disable_item_sources", failed)
    deletion = asyncio.create_task(asyncio.to_thread(book_library.delete_item, item))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        update = asyncio.create_task(asyncio.to_thread(book_library.update_metadata, item, {"title": "updated independently"}))
        await asyncio.sleep(0.05)
        release.set()
        with pytest.raises(RuntimeError, match="Controlled rollback"):
            await deletion
        assert (await update)["title"] == "updated independently"
        with connect(book_library.db_path) as db:
            assert db.execute("SELECT lifecycle_state FROM book_books WHERE id=?", (actor.book_id,)).fetchone()[0] == "active"
            assert db.execute("SELECT lifecycle_state FROM book_source_versions WHERE id=?", (actor.source_version_id,)).fetchone()[0] == "available"
    finally:
        release.set()
        await asyncio.gather(deletion, return_exceptions=True)


@pytest.mark.asyncio
async def test_new_attachment_does_not_rebind_old_room_or_quote(book_library):
    from backend.services.book_world.source import BookSourceService

    item, _, _, actor = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="old-version")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    source = BookSourceService(book_library.workspace_root)
    old = source.list_segments(item, actor.source_version_id)["segments"][0]
    old_quote = source.resolve_evidence(item, actor.source_version_id, old["id"])["quote"]
    path = book_library.workspace_root / "new-source.txt"
    path.write_text("人物甲说：新版本明确写了另外一句话。", encoding="utf-8")
    book_library.import_text_attachment(item, path)
    newest = source.prepare_source(item)
    assert newest["source_version_id"] != actor.source_version_id
    snapshot = membership.rooms.get_room(scope)
    assert snapshot["members"][0]["available"]
    assert snapshot["sources"][0]["is_latest_version"] is False
    assert snapshot["sources"][0]["source_version_id"] == actor.source_version_id
    assert source.resolve_evidence(item, actor.source_version_id, old["id"])["quote"] == old_quote


@pytest.mark.asyncio
async def test_shutdown_revokes_live_worker_and_reopens_interrupted(book_library):
    import asyncio

    from backend.channels.desktop.handlers.book_room import BookRoomHandler
    from backend.services.book_world.chat_provider import CharacterChatModel
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, actor = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([actor], client_room_id="shutdown-held")
    scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(scope, "shutdown", "你好", config, time_limit_seconds=60)
    entered = asyncio.Event()

    class Held:
        async def chat(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

    handler = BookRoomHandler(object())
    handler._schedule(book_library.workspace_root, scope, turn["round_id"], CharacterChatModel(Held(), config, None))
    await asyncio.wait_for(entered.wait(), 10)
    await BookRoomHandler.shutdown()
    BookRoomHandler.startup()
    snapshot = BookRoundService(book_library.workspace_root).get_round(scope, turn["round_id"])
    assert snapshot["status"] == "interrupted" and snapshot["generation"] is None
    assert len(membership.rooms.read_messages(scope)["messages"]) == 1


@pytest.mark.asyncio
async def test_library_shutdown_drains_inflight_and_rejects_late_requests(book_library, monkeypatch):
    import asyncio
    import threading

    import backend.channels.desktop.handlers.library as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.library_engine import LibraryEngine

    entered, release = threading.Event(), threading.Event()
    responses = []

    def migration(*args):
        entered.set()
        assert release.wait(5)

    class Socket:
        async def send_json(self, data):
            responses.append(data)

    monkeypatch.setattr(module, "run_knowledge_index_migrations", migration)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(LibraryEngine, "_instances", {str(book_library.workspace_root): book_library})
    module.LibraryHandler.startup()
    handler = module.LibraryHandler(object())
    message = WSMessage(type=MessageType.LIBRARY_LIST, request_id="shutdown-list", data={})
    request = asyncio.create_task(handler.handle(Socket(), message))
    shutdown = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        shutdown = asyncio.create_task(module.LibraryHandler.shutdown())
        await asyncio.sleep(0)
        assert not shutdown.done()
        release.set()
        await asyncio.gather(request, shutdown)
        assert responses[-1]["type"] == "error" and not LibraryEngine._instances
        await handler.handle(Socket(), message)
        assert responses[-1]["data"]["error"] == "Service is shutting down"
        assert not LibraryEngine._instances
    finally:
        release.set()
        await asyncio.gather(request, *([shutdown] if shutdown else []), return_exceptions=True)
        module.LibraryHandler.startup()


@pytest.mark.asyncio
async def test_stale_workspace_delete_cannot_remove_same_local_item_id(book_library, monkeypatch, tmp_path):
    import backend.channels.desktop.handlers.library as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.services.book_world.storage import workspace_identity
    from backend.services.knowledge_migrations import run_knowledge_index_migrations
    from backend.services.library_engine import LibraryEngine

    old = book_library.create_item(metadata={"title": "old workspace book"})
    other = tmp_path / "other-workspace"
    run_knowledge_index_migrations(other / "knowledge/.knowledge_index.db")
    current = LibraryEngine(str(other))
    new = current.create_item(metadata={"title": "new workspace book"})
    assert old["id"] == new["id"]
    monkeypatch.setattr(module, "get_workspace_path", lambda: other)
    responses = []

    class Socket:
        async def send_json(self, data):
            responses.append(data)

    try:
        await module.LibraryHandler(object()).handle(Socket(), WSMessage(type=MessageType.LIBRARY_DELETE, request_id="old-workspace-delete", data={"item_id": old["id"], "workspace_id": workspace_identity(book_library.workspace_root)}))
        assert responses[-1]["type"] == "error" and "Workspace changed" in responses[-1]["data"]["error"]
        assert book_library.get_item(old["id"])["title"] == old["title"]
        assert current.get_item(new["id"])["title"] == new["title"]
    finally:
        current.db.close()
        LibraryEngine._instances.pop(str(other.resolve()), None)
