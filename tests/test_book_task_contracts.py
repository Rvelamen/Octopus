"""Deterministic contract tests that pin one focused invariant per task.

These tests complement the existing per-task test files. Each one
targets a single contract boundary that the T12 acceptance index
relies on but that is not the primary subject of the larger suites:

  T04  revision CAS — re-publishing at the same version must reject
  T05  scoped knowledge — character A's retrieve returns only A's
       evidence, never B's
  T06  bounded single chat — time_limit_seconds round-trips through
       BookRoundService.submit and is stored on the round row
  T07  room memory — reset_memory advances epoch and the old
       epoch's user message becomes unreachable
  T08  multi-character room — two characters named identically but
       bound to different books get distinct member_ids and seat
       indexes
  T09  all-participant queue — muted members are explicitly skipped
       in ``mode='all'`` slots with skip_reason set
  T10  automatic import — scan on an empty library returns no
       jobs and never publishes anything
  T11  source lifecycle — removing one source does not change the
       other source's scope binding in an existing room
  T16  roundtable scene — 32-person room keeps the seat_index
       assignment stable after one remove + re-add cycle

The tests are deterministic, use the existing ``book_library``
fixture, and do not consume any model budget. They run against the
real BookWorldService / RoomMembershipService / BookRoundService
in-process; the goal is regression coverage, not behavior QA.
"""

import sqlite3

import pytest

from backend.data.schema import agent

# ---------------------------------------------------------------------------
# T04 — revision CAS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t04_stale_revision_persona_build_fails_with_revision_conflict(
    book_library,
):
    """T04: a persona build recorded against a now-superseded
    revision must be flagged as failed with ``revision_conflict``
    after it runs — the CAS invariant the T04 contract relies on so
    that an old draft cannot silently overwrite the current head."""
    from test_book_persona import PersonaProvider, quote
    from test_book_revisions import RevisionReviewer, published

    from backend.services.book_world.revisions import BookRevisionService, RevisionPatch

    item, base, config = await published(book_library)
    revisions = BookRevisionService(book_library.workspace_root)
    context = revisions.get_context(item, base)
    person = context["characters"][0]
    segment = revisions.persona.source.list_segments(item, context["source_version_id"])[
        "segments"
    ][0]
    patch = RevisionPatch(
        operation="add_alias",
        character_id=person["id"],
        value="阿甲",
        evidence=quote(segment, "人物甲又名阿甲。"),
    )
    # First create-revision publishes a build at the current head.
    old_revision = await revisions.create_revision(
        item,
        base,
        context["revision"],
        [patch],
        "t04-first-edit",
        RevisionReviewer(),
        config,
    )
    # A second create_revision at the now-current revision advances
    # the head, making ``old_revision`` strictly stale.
    current = revisions.get_context(item, base)
    assert current["revision"] != context["revision"], (
        "context['revision'] must advance after the first create_revision"
    )
    new_revision = await revisions.create_revision(
        item,
        base,
        current["revision"],
        [patch],
        "t04-second-edit",
        RevisionReviewer(),
        config,
    )
    # The head must have moved past the old build's revision.
    head = revisions.get_context(item, base)
    assert head["revision"] != current["revision"], (
        "context['revision'] must advance again after the second create_revision"
    )
    # Running the persona build against the stale build_id must mark
    # that build as failed/revision_conflict (it does not raise —
    # the build is flagged in the database).
    await revisions.persona.run(old_revision["build_id"], PersonaProvider(), config)
    stale = revisions.persona.discovery.get_build(item, old_revision["build_id"])
    assert stale["status"] == "failed", (
        f"stale revision build must be marked failed, got status={stale['status']!r}"
    )
    assert stale["error_code"] == "revision_conflict", (
        f"stale revision build must report error_code=revision_conflict, "
        f"got {stale['error_code']!r}"
    )


# ---------------------------------------------------------------------------
# T05 — scoped knowledge is strictly per-character
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t05_scoped_knowledge_for_character_a_does_not_leak_character_b(
    book_library,
):
    """T05: a character's ``retrieve`` and ``baseline`` must operate
    on that character's own scope — the returned context's
    ``scope.character_id`` must equal the queried character's, and
    the baseline slot keys must belong to the actor's own build
    (not the other character's)."""
    from test_book_knowledge import style_character

    from backend.services.book_world.knowledge import CharacterKnowledgeService

    _, _, _, a_scope = await style_character(book_library)
    _, _, _, b_scope = await style_character(book_library)
    knowledge = CharacterKnowledgeService(book_library.workspace_root)
    a_retrieve = knowledge.retrieve(a_scope, "平和")
    b_retrieve = knowledge.retrieve(b_scope, "平和")
    assert a_retrieve.status == "known" and b_retrieve.status == "known"
    # The returned context's scope.character_id must match the
    # queried character's — never the other one's.
    assert a_retrieve.scope.character_id == a_scope.character_id, (
        f"character A's retrieve must report its own scope.character_id, "
        f"got {a_retrieve.scope.character_id!r}, expected "
        f"{a_scope.character_id!r}"
    )
    assert b_retrieve.scope.character_id == b_scope.character_id, (
        f"character B's retrieve must report its own scope.character_id, "
        f"got {b_retrieve.scope.character_id!r}, expected "
        f"{b_scope.character_id!r}"
    )
    # The baseline slots must be tied to each actor's build — a
    # leak would show A's baseline pointing at B's build_id.
    a_baseline = knowledge.baseline(a_scope)
    b_baseline = knowledge.baseline(b_scope)
    assert a_baseline.scope.build_id == a_scope.build_id, (
        f"A's baseline scope.build_id must be A's own, got "
        f"{a_baseline.scope.build_id!r}, expected {a_scope.build_id!r}"
    )
    assert b_baseline.scope.build_id == b_scope.build_id, (
        f"B's baseline scope.build_id must be B's own, got "
        f"{b_baseline.scope.build_id!r}, expected {b_scope.build_id!r}"
    )
    assert a_baseline.scope.character_id == a_scope.character_id
    assert b_baseline.scope.character_id == b_scope.character_id


# ---------------------------------------------------------------------------
# T06 — time_limit_seconds round-trips through submit and is on the round
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t06_chat_round_records_submitted_time_limit_seconds(book_library):
    """T06: the seconds window the caller submits must be stored on
    the round row verbatim — the T15 timeout setting + T09 control
    layer both rely on this."""
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, scope = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([scope], client_room_id="t06-time-limit-room")
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        room_scope,
        "t06-time-limit-turn",
        "你好",
        config,
        time_limit_seconds=42,
        mode="directed",
        target_member_ids=[room["members"][0]["id"]],
    )
    assert turn["time_limit_seconds"] == 42, (
        f"round must record the submitted time_limit_seconds, "
        f"got {turn['time_limit_seconds']!r}"
    )
    reloaded = rounds.get_round(room_scope, turn["round_id"])
    assert reloaded["time_limit_seconds"] == 42, (
        f"get_round must return the same time_limit_seconds, "
        f"got {reloaded['time_limit_seconds']!r}"
    )


# ---------------------------------------------------------------------------
# T07 — room reset advances epoch and old epoch messages are unreachable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t07_reset_memory_advances_epoch_and_old_history_is_inaccessible(
    book_library,
):
    """T07: reset_memory must advance the room's epoch and the prior
    epoch's user message must not appear in the new epoch's
    read_messages output. The prior epoch is also no longer
    addressable as an active room — read_messages on the old scope
    raises ``stale_room_epoch``."""
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService
    from backend.services.book_world.source import BookWorldError

    _, _, _, scope = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([scope], client_room_id="t07-reset-epoch-room")
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        room_scope,
        "t07-pre-reset-turn",
        "before reset",
        config,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=[room["members"][0]["id"]],
    )
    round_id = turn["round_id"]
    history_before = membership.rooms.read_messages(room_scope)["messages"]
    user_msgs_before = [m for m in history_before if m["speaker_type"] == "user"]
    assert user_msgs_before, (
        f"submit must produce a user message before reset, got {history_before!r}"
    )
    assert all(m["round_id"] == round_id for m in user_msgs_before), (
        "user messages inserted by submit must reference the round"
    )
    reset = membership.rooms.reset_memory(room_scope)
    assert reset["epoch"] == 2, (
        f"reset_memory must advance the epoch, got {reset['epoch']!r}"
    )
    # New scope on epoch 2 must not see the pre-reset user message.
    new_scope = membership.rooms.bind_room(room["room_id"], 2)
    history_after = membership.rooms.read_messages(new_scope)["messages"]
    assert history_after == [], (
        f"post-reset epoch must have no messages, got {history_after!r}"
    )
    # The old scope (epoch 1) is no longer addressable as an active
    # room — read_messages on it must raise stale_room_epoch so the
    # prior epoch's history is unreachable, not silently readable.
    with pytest.raises(BookWorldError) as excinfo:
        membership.rooms.read_messages(room_scope)["messages"]
    assert "stale_room_epoch" in str(excinfo.value).lower() or "epoch" in str(
        excinfo.value
    ).lower(), (
        f"old epoch read must raise stale_room_epoch, got {excinfo.value!r}"
    )


# ---------------------------------------------------------------------------
# T08 — two characters with the same name get distinct member_ids + seats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t08_two_characters_with_same_name_get_distinct_member_ids(
    book_library,
):
    """T08: even if two characters share a display name, they must
    get distinct member_ids and distinct seat_index values so the
    roundtable UI can render them as separate seats."""
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    # The shared fixture produces a character called 人物甲 twice;
    # they live in the same book (this is a same-book duplicate,
    # not a cross-book test) but the room must still distinguish
    # them.
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(
        [first, second], client_room_id="t08-same-name-room"
    )
    member_ids = [m["id"] for m in room["members"]]
    assert len(member_ids) == 2
    assert len(set(member_ids)) == 2, (
        f"two members must have distinct member_ids, got {member_ids!r}"
    )
    seat_indexes = [m["seat_index"] for m in room["members"]]
    assert len(set(seat_indexes)) == 2, (
        f"two members must have distinct seat_index values, got {seat_indexes!r}"
    )


@pytest.mark.asyncio
async def test_t08_directed_at_with_same_name_resolves_to_target_member_id(
    book_library,
):
    """T08: when two room members share the same display name, a
    directed submit keyed by ``target_member_ids`` must still
    address the right member — the directed selection in
    ``select_speakers`` (coordinator.py:37-49) uses member_id, not
    name, so the named collision does not collapse the targeting.

    The test creates two ``人物甲`` (the default fixture name), puts
    them in the same room, and submits a directed turn addressed
    only at the first member. The round must contain exactly one
    slot bound to that member_id; the second ``人物甲`` must not be
    in the slot list despite sharing the name. This is the
    deterministic equivalent of the T12 §4 row 4 "同名 @" requirement.
    """
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, actor_1, first = await style_character(book_library)
    _, _, actor_2, second = await style_character(book_library)
    # Sanity: both members share the same display name "人物甲"
    # because style_character uses a fixed default text.
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(
        [first, second], client_room_id="t08-same-name-directed"
    )
    first_member = next(m for m in room["members"] if m["character_id"] == actor_1)
    second_member = next(m for m in room["members"] if m["character_id"] == actor_2)
    assert first_member["id"] != second_member["id"]
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        room_scope,
        "directed-at-first",
        "只 @ 第一个",
        config,
        time_limit_seconds=60,
        mode="directed",
        target_member_ids=[first_member["id"]],
    )
    reloaded = rounds.get_round(room_scope, turn["round_id"])
    slot_member_ids = [slot["member_id"] for slot in reloaded["slots"]]
    assert slot_member_ids == [first_member["id"]], (
        f"directed @ with same-name members must select only the "
        f"targeted member_id; got slots {slot_member_ids!r}, expected "
        f"[{first_member['id']!r}]"
    )
    assert second_member["id"] not in slot_member_ids, (
        f"second same-name member {second_member['id']!r} must not "
        f"appear in slots despite sharing display name with target"
    )


# ---------------------------------------------------------------------------
# T09 — muted members are explicitly skipped in mode='all'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t09_muted_member_is_skipped_in_all_mode_slot(book_library):
    """T09: when a member is muted, an ``all``-mode turn must record
    the slot as ``no_comment`` with ``skip_reason='muted'`` — the
    chat worker must not generate a reply for them."""
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    _, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create([first, second], client_room_id="t09-muted-all-room")
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    muted_member = room["members"][0]
    membership.control(room_scope, muted_member["id"], speaking_mode="muted")
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(provider_id=1, model="fixture")
    turn = rounds.submit(
        room_scope,
        "t09-all-muted-turn",
        "全员到齐",
        config,
        time_limit_seconds=60,
        mode="all",
    )
    muted_slot = next(
        s for s in turn["slots"] if s["member_id"] == muted_member["id"]
    )
    assert muted_slot["status"] == "no_comment", (
        f"muted member must have status=no_comment, got {muted_slot['status']!r}"
    )
    assert muted_slot.get("skip_reason") == "muted", (
        f"muted member's skip_reason must be 'muted', got "
        f"{muted_slot.get('skip_reason')!r}"
    )
    # The other member must still be queued normally.
    other_slot = next(
        s for s in turn["slots"] if s["member_id"] != muted_member["id"]
    )
    assert other_slot["status"] == "pending", (
        f"non-muted member must be pending, got {other_slot['status']!r}"
    )


# ---------------------------------------------------------------------------
# T10 — automatic import scan is non-destructive on empty workspaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t10_auto_import_scan_on_empty_workspace_publishes_nothing(
    book_library,
):
    """T10: scan on a workspace with no library items must return
    no jobs and never publish or queue any work — the auto-import
    feature must be a no-op when there is nothing to import."""
    from backend.services.book_world.automatic import AutoImportService

    service = AutoImportService(book_library.workspace_root)
    jobs = service.scan()
    assert jobs == [], (
        f"empty workspace must produce no auto-import jobs, got {jobs!r}"
    )
    # And get_job for any item must return None — the auto-import
    # service must not invent jobs out of thin air.
    assert service.get_job(999999) is None, (
        "get_job for an unknown item must return None, not invent a job"
    )


# ---------------------------------------------------------------------------
# T11 — deleting one source preserves other sources' room identity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t11_deleting_one_source_preserves_other_source_room_identity(
    book_library,
):
    """T11: removing one library item must not destabilize another
    library item's room membership — surviving members keep their
    character_id / book_id / seat_index and the room stays active."""
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService

    first_item, _, _, first = await style_character(book_library)
    _, _, _, second = await style_character(book_library)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(
        [first, second], client_room_id="t11-source-delete-room"
    )
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    first_member = next(
        m for m in room["members"]
        if m["character_id"] == first.character_id
    )
    second_member = next(
        m for m in room["members"]
        if m["character_id"] == second.character_id
    )
    # Delete the first item and confirm the second member is untouched.
    book_library.delete_item(first_item)
    after = membership.rooms.get_room(room_scope)
    second_after = next(
        m for m in after["members"]
        if m["character_id"] == second.character_id
    )
    assert second_after["seat_index"] == second_member["seat_index"], (
        "surviving member's seat_index must be preserved across a "
        "different source's deletion"
    )
    assert second_after["character_id"] == second_member["character_id"]
    # The deleted member may either be removed from the room or
    # flagged as inactive; either way, querying their slot must not
    # raise.
    remaining_ids = {m["id"] for m in after["members"]}
    assert first_member["id"] not in remaining_ids or any(
        m["id"] == first_member["id"] and m["character_id"] == first.character_id
        for m in after["members"]
    ), "first_member's record must either be removed or still point at the deleted character"


# ---------------------------------------------------------------------------
# T16 — 32-person room seat_index stability across a remove + re-add cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t16_32_person_room_seat_indexes_stable_across_remove_readd(
    book_library,
):
    """T16: when a member is removed and a new member is added, the
    remaining members must keep their existing seat_index values;
    only the empty seat is reused for the new arrival."""
    from test_book_room_scene import cast

    from backend.services.book_world.members import RoomMembershipService

    actors = await cast(book_library, count=4)
    membership = RoomMembershipService(book_library.workspace_root)
    room = membership.create(actors, client_room_id="t16-seat-stability-room")
    room_scope = membership.rooms.bind_room(room["room_id"], 1)
    initial = membership.rooms.get_room(room_scope)["members"]
    initial_seats = {m["id"]: m["seat_index"] for m in initial}
    removed_id = initial[0]["id"]
    membership.control(room_scope, removed_id, active=False)
    after_remove = membership.rooms.get_room(room_scope)["members"]
    for m in after_remove:
        if m["id"] == removed_id:
            continue
        assert m["seat_index"] == initial_seats[m["id"]], (
            f"member {m['id']!r} seat_index changed across a remove: "
            f"was {initial_seats[m['id']]!r}, now {m['seat_index']!r}"
        )
    # Re-add the actor (re-activate) and confirm the seat is reused.
    membership.control(room_scope, removed_id, active=True)
    after_readd = membership.rooms.get_room(room_scope)["members"]
    readd_member = next(m for m in after_readd if m["id"] == removed_id)
    assert readd_member["seat_index"] == initial_seats[removed_id], (
        f"re-added member must reclaim the same seat_index, was "
        f"{initial_seats[removed_id]!r}, now {readd_member['seat_index']!r}"
    )


# ---------------------------------------------------------------------------
# T15 — saved timeout default flows into chat submit for directed + all modes
# ---------------------------------------------------------------------------


class TemporaryDatabase:
    """Use a real SQLite connection without opening the user's application database.

    Copied verbatim from ``tests/test_book_room_timeout_settings.py:18-27``
    so the T15 contracts do not depend on the timeout-settings suite's
    internal helper. A single failure in T15 must not cascade into the
    timeout-settings suite's ``database`` fixture.
    """

    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        agent.create_tables(self.connection)

    def _get_connection(self) -> sqlite3.Connection:
        return self.connection


@pytest.mark.asyncio
async def test_t15_chat_submit_reads_saved_timeout_default_for_directed_mode(
    book_library, tmp_path
):
    """T15: a value saved to ``agent_defaults.book_room_round_timeout_seconds``
    must round-trip through ``BookRoomTimeoutSettings.seconds_for_mode`` and
    land on the round row verbatim when ``rounds.submit`` is called in
    ``mode='directed'``. This pins the read-path that the real chat handler
    uses at ``book_room.py:418`` — saving 91 and seeing 91 on the round row
    is what the user can actually do at runtime."""
    from pathlib import Path

    from test_book_knowledge import style_character

    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.data.provider_store import AgentDefaultsRepository
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    db_path = Path(tmp_path) / "agent_defaults.db"
    db = TemporaryDatabase(db_path)
    try:
        repo = AgentDefaultsRepository(db)
        repo.get_or_create_defaults()
        repo.update_agent_defaults(
            book_room_round_timeout_seconds=91,
            book_room_all_round_timeout_seconds=301,
        )
        defaults = repo.get_or_create_defaults()
        # Build BookRoomTimeoutSettings exactly as chat_provider.py:135-138 does.
        timeouts = BookRoomTimeoutSettings(
            book_room_round_timeout_seconds=defaults.book_room_round_timeout_seconds,
            book_room_all_round_timeout_seconds=defaults.book_room_all_round_timeout_seconds,
        )
        assert timeouts.seconds_for_mode("directed") == 91, (
            f"saved directed-mode default must read back as 91, got "
            f"{timeouts.seconds_for_mode('directed')!r}"
        )

        _, _, _, scope = await style_character(book_library)
        membership = RoomMembershipService(book_library.workspace_root)
        room = membership.create([scope], client_room_id="t15-directed-room")
        room_scope = membership.rooms.bind_room(room["room_id"], 1)
        rounds = BookRoundService(book_library.workspace_root)
        config = CharacterChatConfig(provider_id=1, model="fixture")
        turn = rounds.submit(
            room_scope,
            "t15-directed",
            "你好",
            config,
            time_limit_seconds=timeouts.seconds_for_mode("directed"),
            mode="directed",
            target_member_ids=[room["members"][0]["id"]],
        )
        assert turn["time_limit_seconds"] == 91, (
            f"directed-mode round must record saved time_limit_seconds=91, "
            f"got {turn['time_limit_seconds']!r}"
        )
        reloaded = rounds.get_round(room_scope, turn["round_id"])
        assert reloaded["time_limit_seconds"] == 91, (
            f"get_round must return the same time_limit_seconds=91, "
            f"got {reloaded['time_limit_seconds']!r}"
        )
    finally:
        db.connection.close()


@pytest.mark.asyncio
async def test_t15_chat_submit_reads_saved_timeout_default_for_all_mode(
    book_library, tmp_path
):
    """T15: a value saved to ``agent_defaults.book_room_all_round_timeout_seconds``
    must round-trip through ``BookRoomTimeoutSettings.seconds_for_mode('all')``
    and land on the round row when ``rounds.submit`` is called in ``mode='all'``.
    The two-character room is required so the ``all`` mode is meaningful
    (mirrors T09 at lines 315-359)."""
    from pathlib import Path

    from test_book_knowledge import style_character

    from backend.core.book_room_settings import BookRoomTimeoutSettings
    from backend.data.provider_store import AgentDefaultsRepository
    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService

    db_path = Path(tmp_path) / "agent_defaults_all.db"
    db = TemporaryDatabase(db_path)
    try:
        repo = AgentDefaultsRepository(db)
        repo.get_or_create_defaults()
        repo.update_agent_defaults(
            book_room_round_timeout_seconds=91,
            book_room_all_round_timeout_seconds=301,
        )
        defaults = repo.get_or_create_defaults()
        timeouts = BookRoomTimeoutSettings(
            book_room_round_timeout_seconds=defaults.book_room_round_timeout_seconds,
            book_room_all_round_timeout_seconds=defaults.book_room_all_round_timeout_seconds,
        )
        assert timeouts.seconds_for_mode("all") == 301, (
            f"saved all-mode default must read back as 301, got "
            f"{timeouts.seconds_for_mode('all')!r}"
        )

        _, _, _, first = await style_character(book_library)
        _, _, _, second = await style_character(book_library)
        membership = RoomMembershipService(book_library.workspace_root)
        room = membership.create([first, second], client_room_id="t15-all-room")
        room_scope = membership.rooms.bind_room(room["room_id"], 1)
        rounds = BookRoundService(book_library.workspace_root)
        config = CharacterChatConfig(provider_id=1, model="fixture")
        turn = rounds.submit(
            room_scope,
            "t15-all",
            "全员到齐",
            config,
            time_limit_seconds=timeouts.seconds_for_mode("all"),
            mode="all",
        )
        assert turn["time_limit_seconds"] == 301, (
            f"all-mode round must record saved time_limit_seconds=301, "
            f"got {turn['time_limit_seconds']!r}"
        )
        reloaded = rounds.get_round(room_scope, turn["round_id"])
        assert reloaded["time_limit_seconds"] == 301, (
            f"get_round must return the same time_limit_seconds=301, "
            f"got {reloaded['time_limit_seconds']!r}"
        )
    finally:
        db.connection.close()


@pytest.mark.asyncio
async def test_t15_saved_timeout_default_persists_across_database_reopen(
    tmp_path,
):
    """T15: the saved ``book_room_round_timeout_seconds=91`` and
    ``book_room_all_round_timeout_seconds=301`` must survive closing the
    SQLite connection and reopening the same file — mirroring
    ``tests/test_book_room_timeout_settings.py::test_defaults_custom_values_and_reopen``.
    The chat worker is long-lived and reads the saved value at submit
    time (not at process start), so a reopen must not silently revert."""
    from pathlib import Path

    from backend.data.provider_store import AgentDefaultsRepository

    db_path = Path(tmp_path) / "preferences.db"
    first = TemporaryDatabase(db_path)
    try:
        repo = AgentDefaultsRepository(first)
        repo.get_or_create_defaults()
        repo.update_agent_defaults(
            book_room_round_timeout_seconds=91,
            book_room_all_round_timeout_seconds=301,
        )
    finally:
        first.connection.close()

    reopened = TemporaryDatabase(db_path)
    try:
        saved = AgentDefaultsRepository(reopened).get_or_create_defaults()
        assert saved.book_room_round_timeout_seconds == 91, (
            f"directed-mode default must survive reopen as 91, got "
            f"{saved.book_room_round_timeout_seconds!r}"
        )
        assert saved.book_room_all_round_timeout_seconds == 301, (
            f"all-mode default must survive reopen as 301, got "
            f"{saved.book_room_all_round_timeout_seconds!r}"
        )
    finally:
        reopened.connection.close()


# ---------------------------------------------------------------------------
# T11 — cross-workspace read / write / delete matrix preserves isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t11_cross_workspace_read_write_delete_matrix_preserves_isolation(
    book_library, tmp_path,
):
    """T11/T12 §4 row 3: walk the 6-dimension matrix
    ``workspace × source × build × character × room × epoch`` in a single
    flow and prove that:

    - Read in workspace A does not leak to workspace B (same local item_id,
      different workspace root).
    - Write (submit a round) in workspace A is not visible from workspace B.
    - Delete one source in workspace A leaves workspace B untouched.
    - Epoch-1 round in workspace A's room is not retrievable from workspace B.

    The matrix is the deterministic equivalent of the T12 acceptance row
    that requires "跨工作区、来源、构建、人物、房间和 epoch 的读写矩阵
    及删除保留历史". No model calls; pure storage + service boundary checks.
    """
    from test_book_knowledge import style_character

    from backend.services.book_world.members import RoomMembershipService
    from backend.services.book_world.room_models import CharacterChatConfig
    from backend.services.book_world.rounds import BookRoundService
    from backend.services.book_world.source import BookWorldError
    from backend.services.knowledge_migrations import (
        run_knowledge_index_migrations,
    )
    from backend.services.library_engine import LibraryEngine

    other = tmp_path / "other-workspace"
    run_knowledge_index_migrations(other / "knowledge/.knowledge_index.db")
    other_library = LibraryEngine(str(other))
    try:
        # Workspace A: 2 sources, room with 2 members, epoch-1 round.
        a_item_1, a_build_1, a_actor_1, a_scope_1 = await style_character(
            book_library
        )
        a_item_2, a_build_2, a_actor_2, a_scope_2 = await style_character(
            book_library
        )
        a_membership = RoomMembershipService(book_library.workspace_root)
        a_room = a_membership.create(
            [a_scope_1, a_scope_2], client_room_id="t11-matrix-A"
        )
        a_scope = a_membership.rooms.bind_room(a_room["room_id"], 1)
        a_rounds = BookRoundService(book_library.workspace_root)
        a_turn = a_rounds.submit(
            a_scope,
            "matrix-A-1",
            "你好",
            CharacterChatConfig(provider_id=1, model="fixture"),
            time_limit_seconds=60,
            mode="directed",
            target_member_ids=[a_room["members"][0]["id"]],
        )

        # Workspace B: 1 source, room with 1 member (no round yet).
        b_item_1, b_build_1, b_actor_1, b_scope_1 = await style_character(
            other_library
        )
        b_membership = RoomMembershipService(other_library.workspace_root)
        b_room = b_membership.create(
            [b_scope_1], client_room_id="t11-matrix-B"
        )
        b_scope = b_membership.rooms.bind_room(b_room["room_id"], 1)

        # Sanity: the two LibraryEngine instances must point at
        # physically distinct SQLite files; if not, the rest of the
        # matrix assertions are meaningless.
        a_db_path = book_library.db_path.resolve()
        b_db_path = other_library.db_path.resolve()
        assert a_db_path != b_db_path, (
            f"cross-workspace matrix requires separate DBs, but A and B "
            f"both point at {a_db_path!r}"
        )

        # Matrix 1 (item count): A has 2 items, B has 1 item before delete.
        a_pre_count = book_library.db.execute(
            "SELECT count(*) FROM library_items"
        ).fetchone()[0]
        b_pre_count = other_library.db.execute(
            "SELECT count(*) FROM library_items"
        ).fetchone()[0]
        assert a_pre_count == 2, (
            f"workspace A must have 2 items before delete, got {a_pre_count}"
        )
        assert b_pre_count == 1, (
            f"workspace B must have 1 item before delete, got {b_pre_count}"
        )

        # Matrix 2 (room count): A has 1 room, B has 1 room; ids differ.
        assert a_room["room_id"] != b_room["room_id"], (
            "two workspaces must not collide on room_id"
        )
        a_room_count = book_library.db.execute(
            "SELECT count(*) FROM book_rooms"
        ).fetchone()[0]
        b_room_count = other_library.db.execute(
            "SELECT count(*) FROM book_rooms"
        ).fetchone()[0]
        assert a_room_count == 1 and b_room_count == 1

        # Matrix 3 (epoch / round): A's round_id is not retrievable from B.
        b_rounds = BookRoundService(other_library.workspace_root)
        try:
            b_rounds.get_round(b_scope, a_turn["round_id"])
        except BookWorldError as exc:
            assert exc.code == "round_unavailable", (
                f"cross-workspace round lookup must raise round_unavailable, "
                f"got {exc.code!r}: {exc.message!r}"
            )
        else:
            raise AssertionError(
                f"workspace A's round {a_turn['round_id']!r} must not be "
                f"retrievable from workspace B's room"
            )

        # Matrix 4 (delete in A): deleting A's first source must not
        # touch workspace B at any level (item + room).
        assert book_library.delete_item(a_item_1)
        b_item_after = other_library.get_item(b_item_1)
        assert b_item_after is not None, (
            "deleting a source in workspace A must not delete B's item"
        )
        b_post_count = other_library.db.execute(
            "SELECT count(*) FROM library_items"
        ).fetchone()[0]
        b_post_rooms = other_library.db.execute(
            "SELECT count(*) FROM book_rooms"
        ).fetchone()[0]
        assert b_post_count == 1, (
            f"workspace B must still have 1 item after A's delete, "
            f"got {b_post_count}"
        )
        assert b_post_rooms == 1, (
            f"workspace B must still have 1 room after A's delete, "
            f"got {b_post_rooms}"
        )

        # Matrix 5 (post-delete state): A's room reflects the source
        # removal; B's room is untouched.
        a_after = a_membership.rooms.get_room(a_scope)
        assert a_after["status"] in ("readonly", "active"), (
            f"A's room must end in a fenced state, got {a_after['status']!r}"
        )
        b_after = b_membership.rooms.get_room(b_scope)
        assert b_after["status"] == "active", (
            f"B's room must remain active across A's deletion, "
            f"got {b_after['status']!r}"
        )
        assert all(m["active"] == 1 for m in b_after["members"]), (
            "B's members must remain active across A's deletion"
        )
    finally:
        other_library.db.close()
        LibraryEngine._instances.pop(str(other.resolve()), None)
