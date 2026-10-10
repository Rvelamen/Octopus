"""Verify user timeout preferences, old databases, and the actual WebSocket path."""

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.provider_handlers import AgentDefaultsHandler
from backend.channels.desktop.schemas import AgentDefaultsUpdateRequest
from backend.core.book_room_settings import BookRoomTimeoutSettings
from backend.data.provider_store import AgentDefaultsRepository
from backend.data.schema import agent


class TemporaryDatabase:
    """Use a real SQLite connection without opening the user's application database."""

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        agent.create_tables(self.connection)

    def _get_connection(self) -> sqlite3.Connection:
        return self.connection


class RecordingSocket:
    def __init__(self):
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        # Real WebSocket serialization must also work for validation errors.
        json.dumps(payload)
        self.messages.append(payload)


@pytest.fixture
def database(tmp_path):
    db = TemporaryDatabase(tmp_path / "preferences.db")
    yield db
    db.connection.close()


def test_defaults_custom_values_and_reopen(database, tmp_path):
    repo = AgentDefaultsRepository(database)
    values = repo.get_or_create_defaults()
    assert (values.book_room_round_timeout_seconds, values.book_room_all_round_timeout_seconds) == (
        60, 300
    )
    assert repo.update_agent_defaults(
        book_room_round_timeout_seconds=120, book_room_all_round_timeout_seconds=600
    )
    reopened = TemporaryDatabase(tmp_path / "preferences.db")
    try:
        saved = AgentDefaultsRepository(reopened).get_or_create_defaults()
        assert saved.book_room_round_timeout_seconds == 120
        assert saved.book_room_all_round_timeout_seconds == 600
        repo.update_agent_defaults(book_room_round_timeout_seconds=90)
        saved = repo.get_or_create_defaults()
        assert saved.book_room_round_timeout_seconds == 90
        assert saved.book_room_all_round_timeout_seconds == 600
    finally:
        reopened.connection.close()


def test_old_database_upgrade_preserves_existing_values(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE agent_defaults(id INTEGER PRIMARY KEY, workspace_path TEXT)")
        conn.execute("INSERT INTO agent_defaults VALUES(1,'original-workspace')")
        agent.create_tables(conn)
        agent.ensure_book_room_timeout_columns(conn)
        row = conn.execute(
            "SELECT workspace_path,book_room_round_timeout_seconds,"
            "book_room_all_round_timeout_seconds FROM agent_defaults"
        ).fetchone()
        assert row == ("original-workspace", 60, 300)
        conn.execute("UPDATE agent_defaults SET book_room_round_timeout_seconds=150")
        agent.ensure_book_room_timeout_columns(conn)
        assert conn.execute("SELECT book_room_round_timeout_seconds FROM agent_defaults").fetchone()[0] == 150


@pytest.mark.parametrize("invalid", [0, -1, 1.5, 60.0, True, False, "60", float("inf"), 2**31])
def test_invalid_repository_value_cannot_partially_update(database, invalid):
    repo = AgentDefaultsRepository(database)
    before = repo.get_or_create_defaults()
    with pytest.raises(ValidationError):
        repo.update_agent_defaults(max_tokens=123, book_room_round_timeout_seconds=invalid)
    after = repo.get_or_create_defaults()
    assert after.max_tokens == before.max_tokens
    assert after.book_room_round_timeout_seconds == 60


@pytest.mark.parametrize("invalid", [None, 0, -1, 1.5, True, "60", 2**31])
def test_request_rejects_invalid_seconds(invalid):
    with pytest.raises(ValidationError):
        AgentDefaultsUpdateRequest.model_validate({"bookRoomAllRoundTimeoutSeconds": invalid})


def test_missing_fields_preserve_preferences_and_mode_selection(database):
    repo = AgentDefaultsRepository(database)
    repo.get_or_create_defaults()
    repo.update_agent_defaults(
        book_room_round_timeout_seconds=91, book_room_all_round_timeout_seconds=301
    )
    request = AgentDefaultsUpdateRequest.model_validate({"maxTokens": 1024})
    assert request.book_room_round_timeout_seconds is None
    repo.update_agent_defaults(max_tokens=request.max_tokens)
    current = repo.get_or_create_defaults()
    settings = BookRoomTimeoutSettings(
        bookRoomRoundTimeoutSeconds=current.book_room_round_timeout_seconds,
        bookRoomAllRoundTimeoutSeconds=current.book_room_all_round_timeout_seconds,
    )
    assert settings.seconds_for_mode("natural") == 91
    assert settings.seconds_for_mode("directed") == 91
    assert settings.seconds_for_mode("all") == 301
    with pytest.raises(ValueError):
        settings.seconds_for_mode("unknown")


@pytest.mark.asyncio
async def test_websocket_save_read_and_invalid_input(database):
    handler = AgentDefaultsHandler(None, database)
    socket = RecordingSocket()
    await handler.handle(socket, WSMessage(
        type=MessageType.AGENT_DEFAULTS_UPDATE,
        request_id="save",
        data={"bookRoomRoundTimeoutSeconds": 75, "bookRoomAllRoundTimeoutSeconds": 450},
    ))
    assert socket.messages[-1]["data"]["success"] is True
    await handler.handle(socket, WSMessage(
        type=MessageType.AGENT_DEFAULTS_GET, request_id="read", data={},
    ))
    assert socket.messages[-1]["data"]["bookRoomRoundTimeoutSeconds"] == 75
    assert socket.messages[-1]["data"]["bookRoomAllRoundTimeoutSeconds"] == 450
    for invalid in [None, True, 0, 0.5]:
        await handler.handle(socket, WSMessage(
            type=MessageType.AGENT_DEFAULTS_UPDATE,
            request_id="invalid",
            data={"bookRoomRoundTimeoutSeconds": invalid, "maxTokens": 123},
        ))
        assert socket.messages[-1]["type"] == MessageType.ERROR.value
    saved = handler.agent_defaults_repo.get_or_create_defaults()
    assert saved.book_room_round_timeout_seconds == 75
    assert saved.max_tokens == 8192
