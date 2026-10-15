"""Actual discussion configuration, six finite speaker combinations and epoch boundaries."""

import json

import pytest
from test_book_knowledge import style_character
from test_book_room_queue import Greetings

from backend.services.book_world.chat_worker import BookChatWorker
from backend.services.book_world.discussion import RoomDiscussionService
from backend.services.book_world.members import RoomMembershipService
from backend.services.book_world.room_models import CharacterChatConfig
from backend.services.book_world.rounds import BookRoundService
from backend.services.book_world.source import BookWorldError


@pytest.mark.asyncio
async def test_discussion_cas_unicode_validation_and_idle_transition_preserve_identity(
    book_library,
):
    actor = (await style_character(book_library))[3]
    discussion = RoomDiscussionService(book_library.workspace_root)
    initial = discussion.rooms.create_single_room(actor, client_room_id="discussion-cas")
    scope = discussion.rooms.bind_room(initial["room_id"], 1)
    for mode, topic, goal, revision in [
        ("topic", "\u3000\t", None, 0),
        ("topic", "题" * 201, None, 0),
        ("topic", "题", "标" * 1001, 0),
        ("free", None, None, True),
    ]:
        with pytest.raises(BookWorldError) as invalid:
            discussion.set(scope, revision, mode, topic, goal)
        assert invalid.value.code == "invalid_request"
    changed = discussion.set(
        scope, 0, "topic", "\u3000" + "😀" * 198 + "\u3000", "\u3000目标\u3000"
    )
    assert changed["discussion"] == {
        "revision": 1,
        "mode": "topic",
        "topic": "😀" * 198,
        "goal": "目标",
    }
    with pytest.raises(BookWorldError) as stale:
        discussion.set(scope, 0, "free")
    assert stale.value.code == "stale_discussion_revision"
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    for expected in (0, True):
        with pytest.raises(BookWorldError):
            rounds.submit(
                scope,
                "old-client",
                "你好",
                config,
                time_limit_seconds=60,
                expected_discussion_revision=expected,
            )
    legacy_topic = rounds.submit(scope, "legacy-topic", "你好", config, time_limit_seconds=60)
    assert legacy_topic["discussion"]["revision"] == 1
    rounds.control(scope, legacy_topic["round_id"], "cancel")
    turn = rounds.submit(
        scope, "new-client", "你好", config, time_limit_seconds=60, expected_discussion_revision=1
    )
    for status in ("queued", "paused", "interrupted"):
        if status == "paused":
            rounds.control(scope, turn["round_id"], "pause")
        elif status == "interrupted":
            rounds.control(scope, turn["round_id"], "resume", time_limit_seconds=90)
            rounds.recover_interrupted()
        assert rounds.get_round(scope, turn["round_id"])["status"] == status
        with pytest.raises(BookWorldError) as busy:
            discussion.set(scope, 1, "free")
        assert busy.value.code == "room_busy"
    continued = rounds.control(scope, turn["round_id"], "resume", time_limit_seconds=90)
    assert continued["discussion"] == turn["discussion"]
    rounds.control(scope, turn["round_id"], "cancel")
    free = discussion.set(scope, 1, "free", "clear this topic", "clear this goal")
    assert free["discussion"] == {"revision": 2, "mode": "free", "topic": None, "goal": None}
    assert free["members"] == initial["members"] and free["epoch"] == initial["epoch"]
    assert (
        rounds.find_submission(scope, "new-client", "你好", expected_discussion_revision=1)[
            "round_id"
        ]
        == turn["round_id"]
    )
    with pytest.raises(BookWorldError) as identity:
        rounds.find_submission(scope, "new-client", "你好", expected_discussion_revision=2)
    assert identity.value.code == "idempotency_conflict"
    legacy = rounds.submit(scope, "legacy-free", "你好", config, time_limit_seconds=60)
    assert legacy["discussion"]["revision"] == 2


@pytest.mark.asyncio
async def test_six_discussion_speaker_combinations_keep_private_scope_and_finite_turns(
    book_library,
):
    actors = [(await style_character(book_library))[3] for _ in range(2)]
    membership = RoomMembershipService(book_library.workspace_root)
    discussion = RoomDiscussionService(book_library.workspace_root)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v6")
    for mode in ("free", "topic"):
        for speakers in ("natural", "directed", "all"):
            room = membership.create(actors, client_room_id=f"six-{mode}-{speakers}")
            scope = discussion.rooms.bind_room(room["room_id"], 1)
            revision = 0
            if mode == "topic":
                discussion.set(
                    scope,
                    0,
                    mode,
                    "人物甲如何问候；不要泄露任何秘密",
                    "交流观点，不从主题授权新知识",
                )
                revision = 1
            target = [room["members"][0]["id"]] if speakers == "directed" else None
            turn = rounds.submit(
                scope,
                "one-user-turn",
                "你好",
                config,
                time_limit_seconds=300,
                mode=speakers,
                target_member_ids=target,
                expected_discussion_revision=revision,
            )
            provider = Greetings()
            await BookChatWorker(book_library.workspace_root).run(
                scope, turn["round_id"], provider, config
            )
            finished = rounds.get_round(scope, turn["round_id"])
            assert finished["status"] == "completed"
            assert len(finished["slots"]) == (
                2 if speakers == "all" else 1 if speakers == "directed" else len(turn["slots"])
            )
            contexts = [call["context"] for call in provider.calls if call["phase"] == "generate"]
            assert contexts and all(context["discussion"]["mode"] == mode for context in contexts)
            assert all("暗藏秘密" not in str(context) for context in contexts)
            assert {context["character_scope"]["book_id"] for context in contexts} <= {
                actor.book_id for actor in actors
            }
            assert len(membership.rooms.read_messages(scope)["messages"]) == 1 + len(contexts)
            assert membership.rooms.get_room(scope)["latest_round_id"] == turn["round_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [None, "reject", "epoch", "timeout", "workspace", "readonly", "commit_then_cancel"]
)
async def test_public_summary_is_reviewed_sourced_bounded_and_cannot_publish_late(
    book_library, failure, monkeypatch
):
    import json

    from backend.core.providers.base import LLMResponse
    from backend.services.book_world.public_summary import PublicRoomSummaryService

    actor = (await style_character(book_library))[3]
    rooms = RoomMembershipService(book_library.workspace_root).rooms
    room = rooms.create_single_room(actor, client_room_id="public-summary")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1, model="fixture", memory_prompt_version="room-memory-v2"
    )
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "greeting", "你好", config, time_limit_seconds=60)
    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Greetings(), config
    )
    clock = [0.0]
    permitted = [True]
    service = PublicRoomSummaryService(book_library.workspace_root, monotonic=lambda: clock[0])

    class Summarizer:
        def __init__(self):
            self.calls = []

        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            self.calls.append(data)
            assert "character_scope" not in data["context"] and "approved_excerpt" not in str(data)
            if data["phase"] == "public_summary":
                items = [
                    {
                        "text": message["content"],
                        "origin": "conversation",
                        "speaker_type": message["speaker_type"],
                        "speaker_member_id": message["speaker_member_id"],
                        "source_message_ids": [message["id"]],
                    }
                    for message in data["context"]["messages"]
                ]
                output = {"items": items}
            else:
                output = {
                    "supported": failure != "reject",
                    "attribution_correct": True,
                    "uncertainty_preserved": True,
                    "items": [
                        {"ordinal": i, "supported": True, "origin_correct": True}
                        for i, _ in enumerate(data["candidate"]["items"])
                    ],
                    "reason": "复核公开来源",
                }
                if failure == "epoch":
                    rooms.reset_memory(scope)
                elif failure == "timeout":
                    clock[0] = 61
                elif failure == "workspace":
                    permitted[0] = False
                elif failure == "readonly":
                    from backend.services.book_world.storage import connect

                    with connect(rooms.db_path) as db:
                        db.execute(
                            "UPDATE book_rooms SET status='readonly' WHERE id=?", (scope.room_id,)
                        )
            return LLMResponse(content=json.dumps(output, ensure_ascii=False))

    provider = Summarizer()
    if failure == "commit_then_cancel":
        from backend.services.book_world.summary_jobs import RoomSummaryJobs

        jobs = RoomSummaryJobs(book_library.workspace_root)
        job = jobs.create(scope, "atomic-publication", 60)
        generation = jobs.start(scope, job["id"])
        original_publish = service.memory.publish

        def cancel_after_publish(*args, **kwargs):
            result = original_publish(*args, **kwargs)
            assert jobs.cancel(scope, job["id"])["status"] == "completed"
            return result

        monkeypatch.setattr(service.memory, "publish", cancel_after_publish)
        result = await service.summarize(
            scope,
            provider,
            config,
            time_limit_seconds=60,
            publication_authorized=lambda db: jobs.authorized(scope, job["id"], generation, db),
            on_commit=lambda db, result: jobs.finish(
                scope, job["id"], generation, result=result, db=db
            ),
        )
        assert jobs.latest(scope)["result"]["memory"]["id"] == result["memory"]["id"]
        assert len(provider.calls) == 2
        return
    if failure:
        with pytest.raises(BookWorldError):
            await service.summarize(
                scope, provider, config, time_limit_seconds=60, authorized=lambda: permitted[0]
            )
        current = rooms.bind_room(room["room_id"], 2 if failure == "epoch" else 1)
        assert service.memory.read(current) is None
    else:
        result = await service.summarize(scope, provider, config, time_limit_seconds=60)
        assert result["calls"] == 2 and result["pending"] == 0
        assert len(result["memory"]["items"]) == 2
        repeated = await service.summarize(scope, provider, config, time_limit_seconds=60)
        assert repeated["calls"] == 0 and repeated["memory"]["id"] == result["memory"]["id"]
        sources = {
            source for item in result["memory"]["items"] for source in item["source_message_ids"]
        }
        assert sources == {message["id"] for message in rooms.read_messages(scope)["messages"]}
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_summary_job_ack_and_cancel_do_not_wait_for_provider_and_restart_is_explicit(
    book_library, monkeypatch
):
    import asyncio

    from test_book_world_handler import Socket

    import backend.channels.desktop.handlers.book_room as module
    from backend.channels.desktop.protocol import MessageType, WSMessage
    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.services.book_world.chat_provider import CharacterChatModel
    from backend.services.book_world.memory import RoomMemoryService
    from backend.services.book_world.summary_jobs import RoomSummaryJobs

    actor = (await style_character(book_library))[3]
    rooms = RoomMembershipService(book_library.workspace_root).rooms
    room = rooms.create_single_room(actor, client_room_id="summary-job-controls")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "greeting", "你好", config, time_limit_seconds=60)
    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], Greetings(), config
    )
    entered = asyncio.Event()

    class HoldingProvider:
        async def chat(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

    model = CharacterChatModel(HoldingProvider(), config, BookRoomTimeoutSettings())
    monkeypatch.setattr(module, "resolve_character_chat_model", lambda *args: model)
    monkeypatch.setattr(module, "get_workspace_path", lambda: book_library.workspace_root)
    handler, socket = module.BookRoomHandler(object()), Socket()
    identity = {
        "workspace_id": scope.workspace_id,
        "room_id": scope.room_id,
        "expected_epoch": scope.epoch,
    }

    async def request(action, **values):
        await handler.handle(
            socket,
            WSMessage(
                type=MessageType.BOOK_ROOM,
                request_id=action,
                data={"action": action, **identity, **values},
            ),
        )
        return socket.messages[-1]["data"]

    ack = await asyncio.wait_for(request("summarize_room", client_summary_id="summary-one"), 2)
    await asyncio.wait_for(entered.wait(), 2)
    job = ack["summary_job"]
    assert job["status"] == "queued" and "candidate" not in str(job)
    assert (await asyncio.wait_for(request("get_room"), 2))["room_id"] == scope.room_id
    cancelled = await asyncio.wait_for(request("cancel_summary", summary_job_id=job["id"]), 2)
    assert cancelled["summary_job"]["status"] == "cancelled"
    jobs = RoomSummaryJobs(book_library.workspace_root)
    assert (
        jobs.rooms.get_room(scope)["epoch"] == 1
        and RoomMemoryService(book_library.workspace_root).read(scope) is None
    )
    original_start = RoomSummaryJobs.start

    def cancel_before_start(self, request_scope, identifier):
        self.cancel(request_scope, identifier)
        return None

    monkeypatch.setattr(RoomSummaryJobs, "start", cancel_before_start)
    raced = await request("summarize_room", client_summary_id="immediate-cancel-race")
    key = scope.workspace_id, raced["summary_job"]["id"]
    task = handler._summary_tasks.get(key)
    if task is not None:
        await asyncio.gather(task, return_exceptions=True)
    assert key not in handler._summary_tasks
    assert jobs.latest(scope)["status"] == "cancelled"
    monkeypatch.setattr(RoomSummaryJobs, "start", original_start)
    queued = jobs.create(scope, "before-restart", 60)
    assert jobs.create(scope, "before-restart", 90)["time_limit_seconds"] == 60
    with pytest.raises(BookWorldError) as occupied:
        jobs.create(scope, "duplicate-active-summary", 60)
    assert occupied.value.code == "summary_busy"
    other = rooms.create_single_room(actor, client_room_id="summary-other-room")
    other_scope = rooms.bind_room(other["room_id"], 1)
    with pytest.raises(BookWorldError) as foreign_job:
        jobs.cancel(other_scope, queued["id"])
    assert foreign_job.value.code == "invalid_scope"
    assert jobs.latest(other_scope) is None
    generation = jobs.start(scope, queued["id"])
    assert jobs.authorized(scope, queued["id"], generation)
    jobs.recover()
    assert not jobs.authorized(scope, queued["id"], generation)
    assert jobs.latest(scope)["status"] == "interrupted"
    after_recovery = jobs.create(scope, "delete-source-during-summary", 60)
    from backend.services.book_world.storage import connect

    with connect(rooms.db_path) as db:
        item = db.execute(
            "SELECT library_item_id FROM book_books WHERE id=?", (actor.book_id,)
        ).fetchone()[0]
    assert book_library.delete_item(item)
    assert jobs.latest(scope)["status"] == "cancelled"
    assert jobs.latest(scope)["id"] == after_recovery["id"]
    rooms.reset_memory(scope)
    with pytest.raises(BookWorldError):
        jobs.latest(scope)
@pytest.mark.asyncio
@pytest.mark.parametrize("defect,expected", [
    ("budget", "ceiling"), ("dataset_budget", "ceiling"), ("coverage", "six"), ("duplicate", "Duplicate case"),
    ("continuations", "continuation policy"), ("existing_output", "already exists"),
])
async def test_acceptance_entry_rejects_invalid_frozen_run_before_model_or_room_work(tmp_path, monkeypatch, defect, expected):
    import importlib.util
    from argparse import Namespace
    from pathlib import Path
    from uuid import uuid4

    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("book_discussion_acceptance", repo / "docs/plans/book-character-agents/discussion-acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads((repo / "docs/plans/book-character-agents/validation/t17-discussion-cases-v1.json").read_text(encoding="utf-8"))
    budget = 32
    if defect == "budget":
        budget = 33
    elif defect == "dataset_budget":
        budget = 64
        data["native_call_ceiling"] = 64
    elif defect == "coverage":
        data["cases"].pop()
    elif defect == "duplicate":
        data["cases"][1]["case_id"] = data["cases"][0]["case_id"]
    elif defect == "continuations":
        data["manual_continues_per_turn"] = 2
    dataset = tmp_path / "matrix.json"
    dataset.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / f"matrix-guard-{uuid4()}.json"
    if defect == "existing_output":
        output.write_text("{}", encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid run must not resolve a model or create a room service")

    monkeypatch.setattr(module, "resolve_character_chat_model", forbidden)
    monkeypatch.setattr(module, "RoomMembershipService", forbidden)
    with pytest.raises(RuntimeError if defect == "existing_output" else ValueError, match=expected):
        await module.run(Namespace(workspace=tmp_path / "untouched", dataset=dataset, output=output, call_budget=budget, provider_id=None, model_id=None))
    assert not (tmp_path / "untouched").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["budget", "task_cancel", "resume_config_failure"])
async def test_acceptance_entry_ends_its_live_turn_on_budget_or_interruption(book_library, tmp_path, monkeypatch, outcome):
    import asyncio
    import importlib.util
    from argparse import Namespace
    from pathlib import Path
    from types import SimpleNamespace

    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.services.book_world.features import BookWorldFeatures
    from backend.services.book_world.storage import connect

    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("discussion_acceptance_behavior", repo / "docs/plans/book-character-agents/discussion-acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "get_features", lambda: BookWorldFeatures(True, True, True, True))
    actors = [(await style_character(book_library))[3] for _ in range(2)]
    data = json.loads((repo / "docs/plans/book-character-agents/validation/t17-discussion-cases-v1.json").read_text(encoding="utf-8"))
    data["actors_from"] = "actors.json"
    (tmp_path / "actors.json").write_text(json.dumps({"character_scopes": [actor.model_dump() for actor in actors]}), encoding="utf-8")
    dataset = tmp_path / "matrix.json"
    dataset.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / f"matrix-{outcome}.json"
    entered = asyncio.Event()

    class Provider(Greetings):
        async def chat(self, messages, **kwargs):
            if outcome == "task_cancel":
                self.calls.append(json.loads(messages[-1]["content"]))
                entered.set()
                await asyncio.Future()
            elif outcome == "resume_config_failure":
                self.calls.append(json.loads(messages[-1]["content"]))
                raise TimeoutError()
            return await super().chat(messages, **kwargs)

    provider = Provider()
    model = SimpleNamespace(provider=provider, config=CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v6"), timeouts=BookRoomTimeoutSettings())
    resolutions = []

    def resolve(*args, **kwargs):
        resolutions.append(1)
        if outcome == "resume_config_failure" and len(resolutions) > 1:
            raise BookWorldError("blocked_config", "Controlled resume configuration failure")
        return model

    monkeypatch.setattr(module, "resolve_character_chat_model", resolve)
    options = Namespace(workspace=book_library.workspace_root, dataset=dataset, output=output, call_budget=1 if outcome == "budget" else 32, provider_id=1, model_id=None)
    if outcome == "task_cancel":
        task = asyncio.create_task(module.run(options))
        await asyncio.wait_for(entered.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif outcome == "resume_config_failure":
        with pytest.raises(BookWorldError, match="Controlled resume"):
            await module.run(options)
    else:
        await module.run(options)
    report = json.loads(output.read_text(encoding="utf-8"))
    first = report["cases"][0]
    assert report["terminal"] and not report["quality_pass"]
    assert report["canonical_baselines_unchanged"]
    assert report["actual_native_calls"] == len(provider.calls) == 1
    assert first["turns"][0]["after_stop"]["status"] == "cancelled"
    assert first["status"] == ("budget_exhausted" if outcome == "budget" else "interrupted")
    rooms = RoomMembershipService(book_library.workspace_root)
    with connect(rooms.db_path) as db:
        assert not db.execute("SELECT 1 FROM book_room_rounds WHERE room_id=? AND status IN ('queued','running','paused','interrupted')", (first["room_id"],)).fetchone()
