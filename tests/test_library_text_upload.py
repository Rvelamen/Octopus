"""Real multipart and desktop TXT creation boundaries in a disposable workspace."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from backend.api.routes.library_upload import router
from backend.channels.desktop.handlers.library import LibraryHandler
from backend.channels.desktop.protocol import MessageType, WSMessage


@pytest.mark.asyncio
async def test_txt_multipart_then_create_preserves_document_metadata(book_library, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.library_upload.get_workspace_path", lambda: book_library.workspace_root
    )
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.library.get_workspace_path",
        lambda: book_library.workspace_root,
    )
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload = await client.post(
            "/api/library/upload",
            files={"file": ("短篇.TXT", "第一章\n人物甲说：不。\n结尾。".encode(), "text/plain")},
        )
    payload = upload.json()
    assert payload["success"] is True
    assert payload["format"] == "txt"
    messages = []

    class Socket:
        async def send_json(self, message):
            json.dumps(message)
            messages.append(message)

    await LibraryHandler(object()).handle(
        Socket(),
        WSMessage(
            type=MessageType.LIBRARY_CREATE,
            request_id="txt-upload",
            data={"temp_file_path": payload["temp_path"], "metadata": {"title": "短篇"}},
        ),
    )
    assert messages[-1]["type"] == "library_create_result"
    item = messages[-1]["data"]["item"]
    assert item["title"] == "短篇"
    assert item["item_type"] == "book"
    assert item["source_format"] == "txt"
    assert item["attachments"][0]["rel_path"] == "main.txt"
    assert not (book_library.workspace_root / payload["temp_path"]).exists()


@pytest.mark.asyncio
async def test_unsupported_upload_has_clear_error(book_library, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.library_upload.get_workspace_path", lambda: book_library.workspace_root
    )
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/library/upload", files={"file": ("unsafe.exe", b"MZ", "application/octet-stream")}
        )
    assert result.status_code == 400
    assert "PDF and TXT" in result.json()["detail"]


@pytest.mark.asyncio
async def test_txt_cleanup_failure_does_not_turn_committed_import_into_error(
    book_library, monkeypatch
):
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.library.get_workspace_path",
        lambda: book_library.workspace_root,
    )
    path = book_library.library_dir / "_uploads" / "locked.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("人物甲说：你好。", encoding="utf-8")
    original_unlink = Path.unlink

    def fail_upload_cleanup(target, *args, **kwargs):
        if target == path:
            raise PermissionError("File is in use")
        return original_unlink(target, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_upload_cleanup)
    messages = []

    class Socket:
        async def send_json(self, value):
            messages.append(value)

    await LibraryHandler(object()).handle(
        Socket(),
        WSMessage(
            type=MessageType.LIBRARY_CREATE,
            data={
                "temp_file_path": str(path.relative_to(book_library.workspace_root)),
                "metadata": {"title": "Locked upload"},
            },
        ),
    )
    assert messages[-1]["type"] == "library_create_result"
    assert messages[-1]["data"]["item"]["chunk_status"] == "completed"
    assert book_library.list_items()[1] == 1
    assert path.exists()


@pytest.mark.asyncio
async def test_txt_creation_failure_is_visible_instead_of_pending(book_library, monkeypatch):
    from backend.services.library_engine import LibraryEngine

    monkeypatch.setattr(
        "backend.channels.desktop.handlers.library.get_workspace_path",
        lambda: book_library.workspace_root,
    )
    path = book_library.workspace_root / "failure.txt"
    path.write_text("这是完整的文本。", encoding="utf-8")

    def fail_import(*args):
        raise OSError("disk full")

    monkeypatch.setattr(LibraryEngine, "import_text_attachment", fail_import)
    messages = []

    class Socket:
        async def send_json(self, value):
            messages.append(value)

    await LibraryHandler(object()).handle(
        Socket(),
        WSMessage(
            type=MessageType.LIBRARY_CREATE,
            data={"temp_file_path": "failure.txt", "metadata": {"title": "Failed import"}},
        ),
    )
    assert messages[-1]["type"] == "error"
    items, total = book_library.list_items()
    assert total == 1
    assert items[0]["chunk_status"] == "failed"


@pytest.mark.asyncio
async def test_library_handler_binds_each_request_after_workspace_switch(
    book_library, tmp_path, monkeypatch
):
    from backend.services.book_world.storage import workspace_identity
    from backend.services.knowledge_migrations import run_knowledge_index_migrations
    from backend.services.library_engine import LibraryEngine

    current = [book_library.workspace_root]
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.library.get_workspace_path", lambda: current[0]
    )
    handler = LibraryHandler(object())
    second = tmp_path / "second-workspace"
    run_knowledge_index_migrations(second / "knowledge" / ".knowledge_index.db")
    second.mkdir(exist_ok=True)
    (second / "story.txt").write_text("第二工作区的人物。", encoding="utf-8")
    current[0] = second
    messages = []

    class Socket:
        async def send_json(self, value):
            messages.append(value)

    try:
        await handler.handle(
            Socket(),
            WSMessage(
                type=MessageType.LIBRARY_CREATE,
                data={
                    "temp_file_path": "story.txt",
                    "upload_workspace_id": workspace_identity(second),
                    "metadata": {"title": "Second workspace"},
                },
            ),
        )
        assert messages[-1]["type"] == "library_create_result"
        assert book_library.list_items()[1] == 0
        await handler.handle(Socket(), WSMessage(type=MessageType.LIBRARY_LIST))
        assert messages[-1]["data"]["pagination"]["total"] == 1
        await handler.handle(
            Socket(),
            WSMessage(
                type=MessageType.LIBRARY_CREATE,
                data={
                    "temp_file_path": "story.txt",
                    "upload_workspace_id": workspace_identity(book_library.workspace_root),
                },
            ),
        )
        assert messages[-1]["type"] == "error"
        assert "Workspace changed" in messages[-1]["data"]["error"]
    finally:
        engine = LibraryEngine(str(second))
        engine.db.close()
        LibraryEngine._instances.pop(str(second.resolve()), None)
