"""Automatic import intent survives queue gaps and never models an unready attachment."""

import pytest

from backend.services.book_world.discovery_models import DiscoveryConfig
from backend.services.book_world.discovery_provider import DiscoveryModel


def ready_automatic_item(library, name):
    path = library.workspace_root / (name + ".txt")
    path.write_text("人物甲说：我最看重诚信。", encoding="utf-8")
    item = library.create_item(
        pdf_path=path,
        metadata={"item_type": "book", "book_world": {"kind": "novel", "automatic": True}},
    )
    library.import_text_attachment(item["id"], path)
    return item["id"]


def test_original_extraction_budget_survives_lower_default_output_preference(monkeypatch):
    from types import SimpleNamespace

    import backend.services.book_world.discovery_provider as module

    provider = SimpleNamespace(
        id=1,
        enabled=True,
        api_key="test-only",
        provider_type="openai",
        api_host="https://fixture.invalid/v1",
        name="fixture",
    )
    record = SimpleNamespace(
        id=7,
        provider_id=1,
        enabled=True,
        is_default=True,
        max_tokens=4096,
        context_window=32768,
        model_id="fixture",
    )
    defaults = SimpleNamespace(
        library_extract_provider_id=1,
        default_provider_id=1,
        library_extract_model_id=7,
        default_model_id=7,
    )
    monkeypatch.setattr(module, "Database", lambda: object())
    monkeypatch.setattr(
        module,
        "AgentDefaultsRepository",
        lambda _: SimpleNamespace(get_or_create_defaults=lambda: defaults),
    )
    monkeypatch.setattr(
        module,
        "ProviderRepository",
        lambda _: SimpleNamespace(
            get_provider_by_id=lambda _: provider, get_enabled_providers=lambda: [provider]
        ),
    )
    monkeypatch.setattr(
        module,
        "ModelRepository",
        lambda _: SimpleNamespace(
            get_model_by_id=lambda _: record, get_enabled_models_by_provider=lambda _: [record]
        ),
    )
    monkeypatch.setattr(module, "create_provider", lambda *args, **kwargs: object())
    original = module.resolve_discovery_model()
    saved = original.config.model_copy(update={"max_tokens": 8192})
    defaults.library_extract_provider_id = 99
    defaults.library_extract_model_id = 88
    resumed = module.resolve_discovery_model(original_config=saved, model_record_id=7)
    assert resumed.config == saved and resumed.config.max_tokens == 8192
    assert record.max_tokens == 4096 and resumed.model_record_id == 7


@pytest.mark.asyncio
async def test_cancel_during_initial_scan_preserves_cancelled_generation(book_library):
    from backend.services.book_world.automatic import AutoImportService

    item_id = ready_automatic_item(book_library, "scan-cancel")
    cancellations = []

    def model():
        job = service.get_job(item_id)
        cancellations.append(service.control(item_id, job["job_id"], "cancel"))
        return DiscoveryModel(
            object(), DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)
        )

    service = AutoImportService(book_library.workspace_root, resolve_model=model)
    late = service.scan()[0]
    assert cancellations[0]["status"] == "cancelled"
    assert late["status"] == "cancelled" and late["generation"] == cancellations[0]["generation"]
    assert late["discovery_build_id"] is None and late["actual_calls"] == 0


@pytest.mark.asyncio
async def test_runner_schedule_waits_for_retry_stop_control_and_keeps_new_generation(book_library):
    import asyncio

    from backend.services.book_world.automatic import AutoImportService
    from backend.services.book_world.automatic_runner import AutoImportRunner

    item_id = ready_automatic_item(book_library, "schedule-race")
    cfg = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    service = AutoImportService(
        book_library.workspace_root,
        resolve_model=lambda **kwargs: DiscoveryModel(object(), kwargs.get("original_config", cfg)),
    )
    job = service.scan()[0]
    service.control(item_id, job["job_id"], "cancel")
    entered = asyncio.Event()

    async def run(identifier, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    service.run = run
    try:
        async with AutoImportRunner.control_lock(book_library.workspace_root, job["job_id"]):
            retried = service.control(item_id, job["job_id"], "retry")
            scheduled = asyncio.create_task(
                AutoImportRunner.schedule(service, book_library.workspace_root, retried)
            )
            await asyncio.sleep(0.05)
            assert not entered.is_set()
            await AutoImportRunner.stop_job(book_library.workspace_root, job["job_id"])
        await scheduled
        await asyncio.wait_for(entered.wait(), 5)
        assert (
            service.get_job(item_id)["generation"] == retried["generation"]
            and service.get_job(item_id)["status"] == "queued"
        )
    finally:
        await AutoImportRunner.stop_job(book_library.workspace_root, job["job_id"])


@pytest.mark.asyncio
async def test_scanner_recovers_after_one_transient_scan_failure(book_library, monkeypatch):
    import asyncio

    import backend.services.book_world.automatic_runner as module

    attempted, recovered = asyncio.Event(), asyncio.Event()

    class Transient:
        def __init__(self, *args):
            self.calls = 0

        def recover(self):
            return []

        def scan(self):
            self.calls += 1
            if self.calls == 1:
                attempted.set()
                raise OSError("Transient test I/O")
            recovered.set()
            return []

    monkeypatch.setattr(module, "AutoImportService", Transient)
    original_sleep = asyncio.sleep

    async def fast_wait(_):
        await original_sleep(0.01)

    monkeypatch.setattr(module.asyncio, "sleep", fast_wait)
    module.AutoImportRunner.start(book_library.workspace_root)
    try:
        await asyncio.wait_for(recovered.wait(), 2)
        assert attempted.is_set()
    finally:
        await module.AutoImportRunner.shutdown()


@pytest.mark.asyncio
async def test_import_intent_waits_for_attachment_then_compensates_once(book_library):
    from backend.services.book_world.automatic import AutoImportService

    path = book_library.workspace_root / "automatic-novel.txt"
    path.write_text("人物甲说：我最看重诚信。", encoding="utf-8")
    item = book_library.create_item(
        pdf_path=path,
        metadata={
            "title": "自动小说",
            "item_type": "book",
            "book_world": {"kind": "novel", "automatic": True},
        },
    )
    resolved = []

    def model():
        resolved.append(True)
        return DiscoveryModel(
            object(), DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)
        )

    service = AutoImportService(book_library.workspace_root, resolve_model=model)
    first = service.scan()
    assert len(first) == 1 and first[0]["status"] == "waiting_attachment"
    assert resolved == []
    book_library.import_text_attachment(item["id"], path)
    queued = service.scan()[0]
    assert queued["status"] == "queued" and queued["discovery_build_id"]
    assert queued["source_version_id"] and queued["workspace_id"] == service.workspace_id
    assert service.scan()[0]["job_id"] == queued["job_id"]
    restarted = AutoImportService(book_library.workspace_root, resolve_model=model)
    assert restarted.scan()[0]["discovery_build_id"] == queued["discovery_build_id"]


@pytest.mark.asyncio
async def test_automatic_pipeline_publishes_canon_before_independent_expression_stage(book_library):
    import json

    from test_book_persona import PersonaProvider

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.automatic import AutoImportService
    from backend.services.book_world.room_catalog import RoomCharacterCatalog

    path = book_library.workspace_root / "pipeline-novel.txt"
    path.write_text("人物甲说：我最看重诚信。", encoding="utf-8")
    item = book_library.create_item(
        pdf_path=path,
        metadata={"item_type": "book", "book_world": {"kind": "novel", "automatic": True}},
    )
    book_library.import_text_attachment(item["id"], path)
    phases = []
    persona = PersonaProvider()

    class PipelineModel:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            phases.append(data.get("phase", "discovery"))
            if "phase" not in data:
                segment = data["segments"][0]
                return LLMResponse(
                    content=json.dumps(
                        {
                            "scenes": [
                                {
                                    "segment_ids": [segment["id"]],
                                    "characters": [
                                        {
                                            "local_character_key": "甲",
                                            "name": "人物甲",
                                            "presence": "active",
                                            "identity": "new",
                                            "evidence": {
                                                "segment_id": segment["id"],
                                                "local_start": 0,
                                                "local_end": 3,
                                                "quote": "人物甲",
                                            },
                                        }
                                    ],
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                )
            return await persona.chat(messages, **kwargs)

    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)

    def model(**kwargs):
        return DiscoveryModel(PipelineModel(), kwargs.get("original_config", config))

    service = AutoImportService(book_library.workspace_root, resolve_model=model)
    job = service.scan()[0]
    await service.run(job["job_id"])
    finished = service.get_job(item["id"])
    assert finished["status"] == "completed" and finished["phase"] == "complete"
    assert finished["persona_build_id"] and finished["expression_sets"]
    assert finished["actual_calls"] == len(phases) and finished["actual_calls"] >= 3
    assert RoomCharacterCatalog(book_library.workspace_root).list()["total"] == 1
    previous_calls = len(phases)
    assert service.scan()[0]["job_id"] == finished["job_id"]
    await service.run(job["job_id"])
    assert len(phases) == previous_calls


@pytest.mark.asyncio
async def test_cancel_revokes_import_generation_and_late_discovery_cannot_publish(book_library):
    import asyncio
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.automatic import AutoImportService
    from backend.services.book_world.room_catalog import RoomCharacterCatalog

    path = book_library.workspace_root / "cancel-auto.txt"
    path.write_text("人物甲说：我最看重诚信。", encoding="utf-8")
    item = book_library.create_item(
        pdf_path=path,
        metadata={"item_type": "book", "book_world": {"kind": "novel", "automatic": True}},
    )
    book_library.import_text_attachment(item["id"], path)
    entered, release = asyncio.Event(), asyncio.Event()
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)

    class Held:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            entered.set()
            await release.wait()
            segment = data["segments"][0]
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [
                            {
                                "segment_ids": [segment["id"]],
                                "characters": [
                                    {
                                        "local_character_key": "甲",
                                        "name": "人物甲",
                                        "presence": "active",
                                        "identity": "new",
                                        "evidence": {
                                            "segment_id": segment["id"],
                                            "local_start": 0,
                                            "local_end": 3,
                                            "quote": "人物甲",
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )

    service = AutoImportService(
        book_library.workspace_root,
        resolve_model=lambda **kwargs: DiscoveryModel(
            Held(), kwargs.get("original_config", config)
        ),
    )
    job = service.scan()[0]
    task = asyncio.create_task(service.run(job["job_id"]))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        cancelled = service.control(item["id"], job["job_id"], "cancel")
        assert cancelled["status"] == "cancelled" and cancelled["generation"] > job["generation"]
        release.set()
        await asyncio.wait_for(task, 10)
        assert service.get_job(item["id"])["status"] == "cancelled"
        assert service.scan() == []
        assert RoomCharacterCatalog(book_library.workspace_root).list()["total"] == 0
        assert (
            service.discovery.get_build(item["id"], job["discovery_build_id"])["status"]
            == "cancelled"
        )
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_interrupted_auto_build_recovers_checkpoint_and_original_strategy_without_global_drift(
    book_library,
):
    import asyncio

    from backend.services.book_world.automatic import AutoImportService

    path = book_library.workspace_root / "restart-auto.txt"
    path.write_text("人物甲说：我最看重诚信。", encoding="utf-8")
    item = book_library.create_item(
        pdf_path=path,
        metadata={"item_type": "book", "book_world": {"kind": "novel", "automatic": True}},
    )
    book_library.import_text_attachment(item["id"], path)
    entered = asyncio.Event()
    original = DiscoveryConfig(provider_id=1, model="original-fixture", unit_char_limit=4000)

    class Wait:
        async def chat(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

    requested = []

    def model(**kwargs):
        requested.append(kwargs.get("original_config"))
        return DiscoveryModel(Wait(), kwargs.get("original_config", original))

    service = AutoImportService(book_library.workspace_root, resolve_model=model)
    queued = service.scan()[0]
    task = asyncio.create_task(service.run(queued["job_id"]))
    await asyncio.wait_for(entered.wait(), 10)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    interrupted = service.get_job(item["id"])
    assert interrupted["status"] == "interrupted" and interrupted["actual_calls"] == 1
    restarted = AutoImportService(book_library.workspace_root, resolve_model=model)
    assert restarted.recover() == [queued["job_id"]]
    ready = restarted.get_job(item["id"])
    assert ready["status"] == "queued" and ready["generation"] > interrupted["generation"]
    assert (
        ready["strategy"] == queued["strategy"]
        and ready["discovery_build_id"] == queued["discovery_build_id"]
    )
    assert requested == [None, original]
    assert restarted.recover() == []
    entered.clear()
    resumed = asyncio.create_task(restarted.run(queued["job_id"]))
    await asyncio.wait_for(entered.wait(), 10)
    resumed.cancel()
    await asyncio.gather(resumed, return_exceptions=True)
    assert requested == [None, original, original]
    assert restarted.get_job(item["id"])["actual_calls"] == 2
