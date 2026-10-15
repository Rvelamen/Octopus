"""Independent discovery work continues without releasing incomplete source builds."""

import asyncio
import json

import pytest
from test_book_discovery import story

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.storage import connect


def empty_unit(data):
    return LLMResponse(
        content=json.dumps(
            {"scenes": [{"segment_ids": [r["id"] for r in data["segments"]], "characters": []}]}
        )
    )


@pytest.mark.asyncio
async def test_exhausted_early_unit_does_not_block_independent_tail_and_remains_failed(
    book_library,
):
    item, source = story(book_library, "第一段。\n\n第二段。\n\n末尾段。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_segment_limit=1)
    build = service.create_build(item, source, config)
    calls = []

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data["unit_key"])
            return LLMResponse(content="{") if data["unit_key"] == "0" else empty_unit(data)

    await service.run(build["build_id"], Provider(), config)
    state = service.get_build(item, build["build_id"])
    assert calls == ["0", "0", "1", "2"]
    assert state["status"] == "failed" and state["stage"] == "character_discovery"
    assert state["completed_units"] == state["processed_segments"] == 2
    assert state["failed_units"] == 1 and "unit 0 failed twice" in state["error_detail"]
    with connect(service.db_path) as db:
        saved = [
            tuple(r)
            for r in db.execute(
                "SELECT unit_key,input_hash,result_json FROM book_build_steps WHERE build_id=? AND status='validated' ORDER BY unit_key",
                (build["build_id"],),
            )
        ]
    service.retry_build(item, build["build_id"])

    class Fixed:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data["unit_key"])
            return empty_unit(data)

    await service.run(build["build_id"], Fixed(), config)
    assert calls == ["0", "0", "1", "2", "0"]
    assert service.get_build(item, build["build_id"])["stage"] == "discovery_complete"
    with connect(service.db_path) as db:
        after = [
            tuple(r)
            for r in db.execute(
                "SELECT unit_key,input_hash,result_json FROM book_build_steps WHERE build_id=? AND unit_key IN ('1','2') ORDER BY unit_key",
                (build["build_id"],),
            )
        ]
    assert saved == after


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupted_unit", ["0", "2"])
async def test_expired_lease_continues_tail_without_a_third_exhausted_attempt(
    book_library, monkeypatch, interrupted_unit
):
    import backend.services.book_world.discovery as module

    item, source = story(book_library, "第一段。\n\n第二段。\n\n末尾段。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_segment_limit=1)
    build = service.create_build(item, source, config)
    calls = []
    offset = [0]
    real_now = module._now
    monkeypatch.setattr(module, "_now", lambda seconds=0: real_now(seconds + offset[0]))

    class Interrupted:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            key = data["unit_key"]
            calls.append(key)
            if key == interrupted_unit and (key != "0" or calls.count("0") == 2):
                raise asyncio.CancelledError()
            return LLMResponse(content="{") if key == "0" else empty_unit(data)

    with pytest.raises(asyncio.CancelledError):
        await service.run(build["build_id"], Interrupted(), config)
    offset[0] += 1000
    resumed = []

    class Resumed:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            resumed.append(data["unit_key"])
            return empty_unit(data)

    await service.run(build["build_id"], Resumed(), config)
    assert resumed == (["1", "2"] if interrupted_unit == "0" else ["2"])
    state = service.get_build(item, build["build_id"])
    assert state["status"] == "failed" and state["failed_units"] == 1
    assert state["completed_units"] == 2
    with connect(service.db_path) as db:
        row = db.execute(
            "SELECT attempts,status FROM book_build_steps WHERE build_id=? AND unit_key='0'",
            (build["build_id"],),
        ).fetchone()
    assert tuple(row) == (2, "failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["interrupted", "provider_failed"])
async def test_auto_recovery_or_pending_continue_preserves_exhausted_units(
    book_library, monkeypatch, stop
):
    from backend.services.book_world.automatic import AutoImportService
    from backend.services.book_world.discovery_provider import DiscoveryModel
    from backend.services.book_world.source import BookWorldError

    path = book_library.workspace_root / "pending-auto.txt"
    path.write_text("第一段。\n\n第二段。\n\n末尾段。", encoding="utf-8")
    item = book_library.create_item(
        pdf_path=path,
        metadata={"item_type": "book", "book_world": {"kind": "novel", "automatic": True}},
    )
    book_library.import_text_attachment(item["id"], path)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_segment_limit=1)
    calls = []
    blocked = [True]

    class Provider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            key = data["unit_key"]
            calls.append(key)
            if key == "2" and blocked[0]:
                if stop == "interrupted":
                    raise asyncio.CancelledError()
                raise RuntimeError("fixture transport unavailable")
            return LLMResponse(content="{") if key == "0" else empty_unit(data)

    service = AutoImportService(
        book_library.workspace_root,
        resolve_model=lambda **kwargs: DiscoveryModel(
            Provider(), kwargs.get("original_config", config)
        ),
    )
    job = service.scan()[0]
    if stop == "interrupted":
        with pytest.raises(asyncio.CancelledError):
            await service.run(job["job_id"])
    else:
        await service.run(job["job_id"])
    before = service.get_job(item["id"])
    assert calls == ["0", "0", "1", "2"]
    assert before["pending_discovery_units"] == 1
    if stop == "interrupted":
        assert service.recover() == [job["job_id"]]
    else:
        from test_book_world_handler import Socket

        import backend.channels.desktop.handlers.book_world as handler_module
        import backend.services.book_world.features as features
        from backend.channels.desktop.protocol import MessageType, WSMessage
        from backend.services.book_world.automatic_runner import AutoImportRunner

        monkeypatch.setattr(
            handler_module, "get_workspace_path", lambda: book_library.workspace_root
        )
        monkeypatch.setattr(
            features, "get_features", lambda: features.BookWorldFeatures(True, True, True, True)
        )
        starts = []
        monkeypatch.setattr(AutoImportRunner, "start", lambda root: starts.append(root))
        socket = Socket()
        payload = {
            "action": "continue_auto_import",
            "item_id": item["id"],
            "workspace_id": "foreign",
            "automatic_job_id": job["job_id"],
        }
        handler = handler_module.BookWorldHandler(object())
        await handler.handle(socket, WSMessage(type=MessageType.BOOK_WORLD, data=payload))
        assert socket.messages[-1]["data"]["code"] == "invalid_scope" and not starts
        assert service.get_job(item["id"])["generation"] == before["generation"]
        payload["workspace_id"] = service.workspace_id
        await handler.handle(
            socket,
            WSMessage(type=MessageType.BOOK_WORLD, request_id="continue-pending", data=payload),
        )
        assert socket.messages[-1]["request_id"] == "continue-pending"
        assert socket.messages[-1]["data"]["job"]["status"] == "queued"
        assert starts == [book_library.workspace_root.resolve()]
        with pytest.raises(BookWorldError, match="active"):
            service.control(item["id"], job["job_id"], "continue")
    blocked[0] = False
    await service.run(job["job_id"])
    after = service.get_job(item["id"])
    assert calls == ["0", "0", "1", "2", "2"]
    assert after["status"] == "failed" and after["actual_calls"] == 5
    assert after["discovery_build_id"] == before["discovery_build_id"]
    assert after["pending_discovery_units"] == 0 and after["persona_build_id"] is None
    with connect(service.db_path) as db:
        exhausted = db.execute(
            "SELECT attempts,status FROM book_build_steps WHERE build_id=? AND unit_key='0'",
            (after["discovery_build_id"],),
        ).fetchone()
    assert tuple(exhausted) == (2, "failed")
    with pytest.raises(BookWorldError, match="unprocessed"):
        service.control(item["id"], job["job_id"], "continue")
    assert service.get_job(item["id"])["generation"] == after["generation"]
    service.control(item["id"], job["job_id"], "retry")
    with connect(service.db_path) as db:
        retried = db.execute(
            "SELECT attempts,status FROM book_build_steps WHERE build_id=? AND unit_key='0'",
            (after["discovery_build_id"],),
        ).fetchone()
    assert tuple(retried) == (0, "pending")


@pytest.mark.parametrize("missing", ["workspace_id", "automatic_job_id"])
def test_pending_continue_contract_requires_both_authority_identities(missing):
    from pydantic import ValidationError

    from backend.services.book_world.contracts import BookWorldRequest

    payload = {
        "action": "continue_auto_import",
        "item_id": 1,
        "workspace_id": "workspace",
        "automatic_job_id": "job",
    }
    assert BookWorldRequest.model_validate(payload).action == "continue_auto_import"
    payload.pop(missing)
    with pytest.raises(ValidationError, match="workspace and current pipeline identity"):
        BookWorldRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_disabled_auto_feature_blocks_pending_continue_before_controls(
    book_library, monkeypatch
):
    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_world as handler_module
    import backend.services.book_world.features as features
    from backend.channels.desktop.protocol import MessageType, WSMessage

    monkeypatch.setattr(handler_module, "get_workspace_path", lambda: book_library.workspace_root)
    monkeypatch.setattr(
        features, "get_features", lambda: features.BookWorldFeatures(True, True, True, False)
    )
    socket = Socket()
    await handler_module.BookWorldHandler(object()).handle(
        socket,
        WSMessage(
            type=MessageType.BOOK_WORLD,
            data={
                "action": "continue_auto_import",
                "item_id": 1,
                "workspace_id": "workspace",
                "automatic_job_id": "job",
            },
        ),
    )
    assert socket.messages[-1]["data"]["code"] == "feature_disabled"
