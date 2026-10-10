"""Desktop contract tests against real source services in temporary workspaces."""

import json

import pytest
from test_book_source import add_pdf

from backend.channels.desktop.handlers.book_world import BookWorldHandler
from backend.channels.desktop.protocol import MessageType, WSMessage

pytest_plugins = ["test_book_source"]


class Socket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        json.dumps(message)
        self.messages.append(message)


@pytest.mark.asyncio
async def test_source_contract_returns_scope_and_request_identity(library, monkeypatch):
    monkeypatch.setattr(
        "backend.channels.desktop.handlers.book_world.get_workspace_path",
        lambda: library.workspace_root,
    )
    item = add_pdf(library, [["A source for a character", "The end"]])
    socket = Socket()
    handler = BookWorldHandler(object())
    await handler.handle(
        socket,
        WSMessage(
            type=MessageType.BOOK_WORLD,
            request_id="source-request",
            data={"action": "prepare_source", "item_id": item["id"]},
        ),
    )
    response = socket.messages[-1]
    assert response["type"] == "book_world_result"
    assert response["request_id"] == "source-request"
    assert response["data"]["status"] == "ready"
    assert response["data"]["workspace_id"]
    assert response["data"]["item_id"] == item["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"action": "get_source", "item_id": True},
        {"action": "get_source", "item_id": 0},
        {"action": "get_source", "item_id": "1"},
        {"action": "get_source", "item_id": 1, "workspace_root": "elsewhere"},
        {"action": "list_segments", "item_id": 1},
    ],
)
async def test_invalid_source_requests_have_safe_serializable_errors(payload):
    socket = Socket()
    await BookWorldHandler(object()).handle(
        socket, WSMessage(type=MessageType.BOOK_WORLD, request_id="bad-request", data=payload)
    )
    assert socket.messages[-1]["type"] == "error"
    assert socket.messages[-1]["request_id"] == "bad-request"
    assert socket.messages[-1]["data"]["code"] == "invalid_request"
