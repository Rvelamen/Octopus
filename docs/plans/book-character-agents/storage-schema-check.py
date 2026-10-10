"""Validate the design DDL in memory; never connects to a workspace database."""
import hashlib
import json
import sqlite3
from pathlib import Path

db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys=ON")
db.execute("CREATE TABLE library_items(id INTEGER PRIMARY KEY)")
ddl = Path(__file__).with_name("storage-schema.sql").read_text(encoding="utf-8")
db.executescript(ddl)
db.executescript(ddl)
checks = ["ddl-repeatable"]
def insert(table, **row):
    columns = ",".join(row)
    marks = ",".join("?" for _ in row)
    db.execute(f"INSERT INTO {table}({columns}) VALUES ({marks})", tuple(row.values()))
def expect(name, fn, error=None):
    try:
        fn()
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        if error is None or error not in str(exc):
            raise AssertionError(f"{name}: unexpected {exc}") from exc
    else:
        if error is not None:
            raise AssertionError(f"{name}: invalid operation accepted")
    checks.append(name)
def scope(build="a1"):
    mapping = {"a1":("a","s1"),"a2":("a","s1"),"a3":("a","s2"),"b1":("b","sb")}
    book, source = mapping[build]
    return dict(book_id=book, source_version_id=source, build_id=build)
def claim(cid, build="a1", **kwargs):
    insert("book_claims", id=cid, **scope(build), kind="fact",
           proposition="原著中的秘密", interpretation_level="explicit", support_state="accepted",
           search_terms="秘密 人物", **kwargs)
def room(rid, character="x", build="a1"):
    insert("book_rooms", id=rid, title=rid)
    insert("book_room_epochs", room_id=rid, epoch=1, state="active")
    insert("book_room_sources", room_id=rid, **scope(build))
    insert("book_room_members", id=f"{rid}-member", **scope(build), room_id=rid,
           character_id=character, seat_index=0, identity_snapshot_json="{}", state_epoch=1)
def turn(rid, tid, epoch=1, member_id=None, mode="directed", timeout_seconds=60):
    member_id = member_id or f"{rid}-member"
    generation = db.execute("SELECT membership_generation FROM book_room_members WHERE id=?",
                            (member_id,)).fetchone()[0]
    discussion = db.execute("SELECT discussion_revision,discussion_mode,discussion_topic,discussion_goal FROM book_rooms WHERE id=?", (rid,)).fetchone()
    discussion_snapshot = json.dumps(dict(zip(("revision","mode","topic","goal"), discussion)), ensure_ascii=False)
    insert("book_room_rounds", id=tid, room_id=rid, epoch=epoch, client_turn_id=tid,
           mode=mode, discussion_snapshot_json=discussion_snapshot, status="running", time_limit_seconds=timeout_seconds, lease_owner="worker", lease_generation=1,
           lease_expires_at="2099-01-01T00:00:00.000Z")
    insert("book_round_slots", id=f"{tid}-slot", room_id=rid, epoch=epoch, round_id=tid,
           position=0, member_id=member_id, member_generation=generation, status="running")
def message(mid, rid, tid, seq, epoch=1, character=False, **extra):
    row = dict(id=mid, room_id=rid, epoch=epoch, seq=seq, round_id=tid,
               speaker_type="character" if character else "user", content="公开发言",
               validation_state="accepted" if character else "not_applicable")
    if character:
        snapshot = db.execute("SELECT member_id,member_generation FROM book_round_slots WHERE id=?",
                              (f"{tid}-slot",)).fetchone()
        row.update(slot_id=f"{tid}-slot", speaker_member_id=snapshot[0],
                   publish_lease_generation=1, publish_member_generation=snapshot[1])
    row.update(extra)
    insert("book_room_messages", **row)
def ref(ref_id, rid="r1", message_id="m2", **extra):
    row = dict(id=ref_id, room_id=rid, epoch=1, message_id=message_id,
               speaker_member_id=f"{rid}-member", assertion_ordinal=0,
               assertion_text="我从原著获知", origin="canon", **scope(),
               character_id="x", claim_id="f1", evidence_id="e1")
    row.update(extra)
    insert("book_message_refs", **row)
def hearsay(ref_id, source, rid="r1", message_id="m2", epoch=1):
    insert("book_message_refs", id=ref_id, room_id=rid, epoch=epoch,
           message_id=message_id, speaker_member_id=f"{rid}-member",
           assertion_ordinal=1, assertion_text="刚刚有人说", origin="room_hearsay",
           heard_message_id=source)

db.executemany("INSERT INTO library_items VALUES (?)", [(1,), (2,)])
insert("book_books", id="a", library_item_id=1, title_snapshot="书甲")
insert("book_books", id="b", library_item_id=2, title_snapshot="书乙")
text = "甲说乙不知道秘密。"
for sid, book in [("s1","a"),("s2","a"),("sb","b")]:
    insert("book_source_versions", id=sid, book_id=book,
           attachment_sha256=sid, parser_version="v1", canonical_text_sha256=sid, format="pdf")
    insert("book_segments", id=f"{sid}-seg", book_id=book, source_version_id=sid,
           ordinal=0, start_offset=0, end_offset=len(text), text=text, text_sha256=sid)
for bid in ["a1","a2","a3","b1"]:
    sc = scope(bid)
    insert("book_builds", id=bid, book_id=sc["book_id"], source_version_id=sc["source_version_id"],
           build_fingerprint=bid, status="running", policy_version="v1")
    insert("book_scenes", id=f"{bid}-scene", **sc, narrative_order=0)
    insert("book_scene_segments", **sc, scene_id=f"{bid}-scene", position=0,
           segment_id=f'{sc["source_version_id"]}-seg')
for cid, bid in [("x","a1"),("y","a1"),("x2","a2"),("x3","a3"),("w","b1")]:
    insert("book_characters", id=cid, **scope(bid), lineage_id=cid,
           name=cid, agent_status="ready")
claim("f1")
claim("f2", build="a2")
claim("fb", build="b1")
insert("book_claims", id="belief", **scope(), kind="belief", owner_character_id="x",
       proposition="错误信念", interpretation_level="explicit", support_state="accepted")
insert("book_evidence", id="e1", **scope(), claim_id="f1", segment_id="s1-seg",
       local_start=0, local_end=len(text), quote_text=text,
       quote_hash=hashlib.sha256(text.encode()).hexdigest(), support_state="accepted")
insert("book_claim_access", **scope(), character_id="x", claim_id="f1", route="firsthand",
       acquisition_scene_id="a1-scene", access_state="accepted")
insert("book_claim_access", **scope(), character_id="x", claim_id="belief", route="firsthand",
       acquisition_scene_id="a1-scene", access_state="accepted")
insert("book_access_evidence", **scope(), character_id="x", claim_id="f1", evidence_id="e1",
       approved_excerpt="秘密", visibility_state="accepted")
insert("book_character_baselines", **scope(), character_id="x", slot_key="current-belief",
       claim_id="belief")
db.commit()
expect("cross-book-build", lambda: insert("book_builds", id="bad", book_id="b",
       source_version_id="s1", build_fingerprint="bad", policy_version="v1"), "FOREIGN KEY")
expect("cross-source-scene-segment", lambda: insert("book_scene_segments", **scope(),
       scene_id="a1-scene", position=1, segment_id="s2-seg"), "FOREIGN KEY")
expect("cross-build-character-claim", lambda: insert("book_claims", id="bad", **scope(),
       kind="belief", owner_character_id="x2", proposition="bad", interpretation_level="explicit"), "FOREIGN KEY")
expect("cross-build-access", lambda: insert("book_claim_access", **scope(), character_id="x",
       claim_id="f2", route="common"), "FOREIGN KEY")
expect("non-owner-belief", lambda: insert("book_claim_access", **scope(), character_id="y",
       claim_id="belief", route="common"), "non_owner_personal_claim")
expect("ungranted-baseline", lambda: insert("book_character_baselines", **scope(),
       character_id="y", slot_key="bad", claim_id="f1"), "FOREIGN KEY")
expect("invalid-evidence-span", lambda: insert("book_evidence", id="bad", **scope(),
       claim_id="f1", segment_id="s1-seg", local_start=0, local_end=99, quote_text="bad",
       quote_hash="bad"), "invalid_evidence_span")
expect("invalid-per-character-excerpt", lambda: insert("book_access_evidence", **scope(),
       character_id="x", claim_id="belief", evidence_id="e1", approved_excerpt="其他秘密"),
       "invalid_approved_excerpt")
expect("missing-scope-not-null", lambda: insert("book_claims", id="bad", book_id=None,
       source_version_id="s1", build_id="a1", kind="fact", proposition="bad",
       interpretation_level="explicit"), "NOT NULL")
expect("duplicate-build-fingerprint", lambda: insert("book_builds", id="bad",
       book_id="a", source_version_id="s1", build_fingerprint="a1", policy_version="v1"), "UNIQUE")
expect("duplicate-segment-ordinal", lambda: insert("book_segments", id="bad", book_id="a",
       source_version_id="s1", ordinal=0, start_offset=0, end_offset=1,
       text="字", text_sha256="bad"), "UNIQUE")
expect("ambiguous-alias-permitted", lambda: [
       insert("book_character_aliases", **scope(), character_id=c, alias="老爷",
              normalized_alias="老爷", review_state="ambiguous") for c in ["x","y"]])
insert("book_evidence", id="eb", **scope("b1"), claim_id="fb", segment_id="sb-seg",
       local_start=0, local_end=len(text), quote_text=text,
       quote_hash=hashlib.sha256(text.encode()).hexdigest(), support_state="accepted")
insert("book_claim_access", **scope("b1"), character_id="w", claim_id="fb",
       route="firsthand",acquisition_scene_id="b1-scene",access_state="accepted")
insert("book_access_evidence", **scope("b1"),character_id="w",claim_id="fb",evidence_id="eb",
       approved_excerpt="秘密",visibility_state="accepted")
db.commit()
db.execute("UPDATE book_builds SET status='published'")
db.commit()
expect("published-canon-frozen", lambda: db.execute(
       "UPDATE book_claims SET proposition='改写' WHERE id='f1'"), "immutable_published_canon")
expect("published-access-frozen", lambda: db.execute(
       "UPDATE book_claim_access SET access_state='revoked' WHERE claim_id='f1'"),
       "immutable_published_canon")
expect("source-version-fields-frozen", lambda: db.execute(
       "UPDATE book_source_versions SET canonical_text_sha256='changed' WHERE id='s1'"), "immutable_source_version")
expect("source-segment-text-frozen", lambda: db.execute(
       "UPDATE book_segments SET text='改写' WHERE id='s1-seg'"), "immutable_source_segment")
expect("published-build-cannot-reopen", lambda: db.execute(
       "UPDATE book_builds SET status='running' WHERE id='a1'"), "immutable_build_publication")
expect("room-current-epoch-deferred-create", lambda: room("r1"))
expect("second-room-independent-create", lambda: room("r2", character="y"))
expect("cross-build-room-member", lambda: insert("book_room_members", id="bad", **scope(),
       room_id="r1", character_id="x2", seat_index=1, identity_snapshot_json="{}", state_epoch=1), "FOREIGN KEY")
# Persistent roundtable seats and capacity, independent of canonical scope.
expect("roundtable-room-default-layout",lambda: room("seats"))
expect("roundtable-layout-defaults",lambda: (
       None if db.execute("SELECT scene_layout_version,scene_capacity FROM book_rooms WHERE id='seats'").fetchone()==(1,8)
       else (_ for _ in ()).throw(AssertionError("layout defaults mismatch"))))
expect("roundtable-seat-required",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope(),character_id="y",identity_snapshot_json="{}",state_epoch=1),"NOT NULL")
expect("roundtable-seat-negative-denied",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope(),character_id="y",seat_index=-1,identity_snapshot_json="{}",state_epoch=1),"CHECK")
expect("roundtable-seat-fraction-denied",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope(),character_id="y",seat_index=0.5,identity_snapshot_json="{}",state_epoch=1),"CHECK")
expect("roundtable-seat-capacity-denied",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope(),character_id="y",seat_index=8,identity_snapshot_json="{}",state_epoch=1),"seat_out_of_capacity")
expect("roundtable-seat-duplicate-denied",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope(),character_id="y",seat_index=0,identity_snapshot_json="{}",state_epoch=1),"UNIQUE")
expect("roundtable-last-seat-allowed",lambda: insert("book_room_members",id="seats-y",
       room_id="seats",**scope(),character_id="y",seat_index=7,identity_snapshot_json="{}",state_epoch=1))
expect("roundtable-seat-rebinding-denied",lambda: db.execute(
       "UPDATE book_room_members SET seat_index=6 WHERE id='seats-y'"),"immutable_member_seat")
expect("roundtable-layout-rebinding-denied",lambda: db.execute(
       "UPDATE book_rooms SET scene_layout_version=2 WHERE id='seats'"),"immutable_scene_layout")
expect("roundtable-capacity-zero-denied",lambda: insert("book_rooms",id="bad-scene",title="bad",scene_capacity=0),"CHECK")
expect("roundtable-capacity-fraction-denied",lambda: insert("book_rooms",id="bad-scene",title="bad",scene_capacity=1.5),"CHECK")
expect("roundtable-idle-expansion",lambda: db.execute(
       "UPDATE book_rooms SET scene_capacity=16 WHERE id='seats'"))
expect("roundtable-capacity-shrink-denied",lambda: db.execute(
       "UPDATE book_rooms SET scene_capacity=8 WHERE id='seats'"),"scene_capacity_shrink_denied")
expect("roundtable-reserved-seat-after-leave",lambda: db.execute(
       "UPDATE book_room_members SET active=0,removed_reason='user',membership_generation=membership_generation+1 WHERE id='seats-y'"))
expect("roundtable-cross-book-source",lambda: insert("book_room_sources",room_id="seats",**scope("b1")))
expect("roundtable-departed-seat-not-reused",lambda: insert("book_room_members",id="bad-seat",
       room_id="seats",**scope("b1"),character_id="w",seat_index=7,identity_snapshot_json="{}",state_epoch=1),"UNIQUE")
expect("roundtable-seat-beyond-eight",lambda: insert("book_room_members",id="seats-b",
       room_id="seats",**scope("b1"),character_id="w",seat_index=15,identity_snapshot_json="{}",state_epoch=1))
expect("roundtable-rejoin-original-seat",lambda: db.execute(
       "UPDATE book_room_members SET active=1,removed_reason=NULL,membership_generation=membership_generation+1 WHERE id='seats-y'"))
expect("roundtable-seat-preserved",lambda: (
       None if db.execute("SELECT seat_index FROM book_room_members WHERE id='seats-y'").fetchone()[0]==7
       else (_ for _ in ()).throw(AssertionError("seat changed on rejoin"))))
expect("roundtable-active-turn",lambda: turn("seats","seats1"))
expect("roundtable-no-expansion-during-turn",lambda: db.execute(
       "UPDATE book_rooms SET scene_capacity=24 WHERE id='seats'"),"room_busy")
expect("roundtable-finish-turn",lambda: (
       db.execute("UPDATE book_room_rounds SET status='completed' WHERE id='seats1'"),
       db.execute("UPDATE book_round_slots SET status='no_comment' WHERE round_id='seats1'")))

expect("room-source-binding-immutable", lambda: db.execute(
       "UPDATE book_room_sources SET build_id='a2' WHERE room_id='r1'"), "immutable_record_scope")
expect("member-character-binding-immutable", lambda: db.execute(
       "UPDATE book_room_members SET character_id='y' WHERE id='r1-member'"), "immutable_record_scope")
expect("running-round", lambda: turn("r1","t1"))
expect("duplicate-active-round", lambda: turn("r1","t1b"), "UNIQUE")
expect("user-message", lambda: message("m1","r1","t1",1))
expect("stale-lease-denied", lambda: message("bad","r1","t1",2,character=True,
       publish_lease_generation=0), "stale_lease")
expect("validated-character-message", lambda: message("m2","r1","t1",2,character=True))
expect("duplicate-slot-denied", lambda: message("bad","r1","t1",3,character=True), "UNIQUE")
expect("sequence-unaffected-by-failed-publish", lambda: (
       None if db.execute("SELECT next_seq FROM book_rooms WHERE id='r1'").fetchone()[0]==3
       else (_ for _ in ()).throw(AssertionError("sequence drift"))))
expect("allowed-canon-reference", lambda: ref("ref1"))
expect("cross-member-canon-reference", lambda: ref("bad", character_id="y", assertion_ordinal=3), "FOREIGN KEY")
expect("null-canonical-scope-denied", lambda: ref("bad",book_id=None,assertion_ordinal=4), "CHECK")
expect("same-room-hearsay-reference", lambda: hearsay("heard1","m1"))
expect("accepted-summary", lambda: insert("book_room_summaries", id="sum1",
       room_id="r1", epoch=1, through_seq=2, summary_json="{}", validation_state="accepted"))
expect("summary-source", lambda: insert("book_summary_sources", room_id="r1",
       epoch=1, summary_id="sum1", message_id="m1"))
expect("other-room-round", lambda: turn("r2","t2"))
expect("other-room-user-message", lambda: message("n1","r2","t2",1))
expect("cross-room-hearsay-denied", lambda: hearsay("bad","n1"), "invalid_hearsay_order")
expect("cross-room-summary-denied", lambda: insert("book_summary_sources",
       room_id="r1",epoch=1,summary_id="sum1",message_id="n1"), "invalid_summary_source")
expect("cross-room-reply-denied", lambda: insert("book_room_messages", id="bad",room_id="r1",
       epoch=1,seq=3,speaker_type="system",content="bad",validation_state="not_applicable",
       reply_to_id="n1"), "FOREIGN KEY")
expect("message-append-only",lambda: db.execute(
       "UPDATE book_room_messages SET content='替换' WHERE id='m2'"), "immutable_published_message")
def reset():
    db.execute("UPDATE book_room_rounds SET status='cancelled',cancel_requested=1 WHERE room_id='r1'")
    db.execute("UPDATE book_room_epochs SET state='cleared' WHERE room_id='r1' AND epoch=1")
    insert("book_room_epochs",room_id="r1",epoch=2,state="active")
    db.execute("UPDATE book_rooms SET current_epoch=2 WHERE id='r1'")
    db.execute("UPDATE book_room_members SET state_epoch=2,ephemeral_state_json='{}' WHERE room_id='r1'")
expect("atomic-room-reset",reset)
expect("roundtable-seat-survives-epoch-reset",lambda: (
       None if db.execute("SELECT seat_index FROM book_room_members WHERE id='r1-member'").fetchone()[0]==0
       else (_ for _ in ()).throw(AssertionError("seat changed on epoch reset"))))
expect("stale-epoch-message-denied",lambda: insert("book_room_messages",id="bad",room_id="r1",
       epoch=1,seq=3,speaker_type="system",content="old",validation_state="not_applicable"),
       "stale_epoch_or_unavailable_source")
expect("stale-epoch-round-denied",lambda: turn("r1","old",epoch=1), "stale_round_epoch_or_source")
expect("stale-summary-denied",lambda: insert("book_room_summaries",id="bad",room_id="r1",
       epoch=1,through_seq=2,summary_json="{}",validation_state="accepted"), "stale_summary_epoch")
expect("new-epoch-round",lambda: turn("r1","t3",epoch=2))
expect("new-epoch-user-message",lambda: message("p1","r1","t3",3,epoch=2))
expect("new-epoch-character-message",lambda: message("p2","r1","t3",4,epoch=2,character=True))
expect("current-epoch-read-excludes-old-history", lambda: (
       None if [r[0] for r in db.execute("SELECT m.id FROM book_room_messages m JOIN book_rooms r ON r.id=m.room_id AND r.current_epoch=m.epoch WHERE r.id='r1' ORDER BY m.seq")]==['p1','p2']
       else (_ for _ in ()).throw(AssertionError("old epoch leaked"))))
expect("cross-epoch-hearsay-denied",lambda: hearsay("bad","m1",message_id="p2",epoch=2),
       "invalid_hearsay_order")

# Global preferences are tested in a separate in-memory database.
prefs = sqlite3.connect(":memory:")
prefs.execute("CREATE TABLE agent_defaults(id INTEGER PRIMARY KEY)")
prefs.execute("INSERT INTO agent_defaults VALUES(1)")
prefs.executescript(Path(__file__).with_name("timeout-settings.sql").read_text(encoding="utf-8"))
assert prefs.execute("SELECT book_room_round_timeout_seconds,book_room_all_round_timeout_seconds FROM agent_defaults WHERE id=1").fetchone()==(60,300)
checks.append("timeout-preferences-default-seconds")
prefs.execute("UPDATE agent_defaults SET book_room_round_timeout_seconds=120,book_room_all_round_timeout_seconds=600 WHERE id=1")
assert prefs.execute("SELECT book_room_round_timeout_seconds,book_room_all_round_timeout_seconds FROM agent_defaults WHERE id=1").fetchone()==(120,600)
checks.append("timeout-preferences-custom-seconds")
prefs.commit()
for value in [0,-1,1.5,None]:
    try:
        prefs.execute("UPDATE agent_defaults SET book_room_round_timeout_seconds=? WHERE id=1",(value,))
        prefs.commit()
    except sqlite3.IntegrityError:
        prefs.rollback()
    else:
        raise AssertionError("Invalid timeout preference accepted")
    checks.append("invalid-timeout-preference-"+str(value))
def valid_timeout(value):
    if isinstance(value,bool) or not isinstance(value,int) or value<=0:
        raise ValueError("positive integer seconds required")
for value in [True,False,"60"]:
    try:
        valid_timeout(value)
    except ValueError:
        checks.append("strict-timeout-input-"+str(value))
    else:
        raise AssertionError("Noninteger API value accepted")
def clock_room():
    prefs.execute("UPDATE agent_defaults SET book_room_round_timeout_seconds=60,book_room_all_round_timeout_seconds=300 WHERE id=1")
    prefs.commit()
    room("clock")
    turn("clock","clock1")
    message("clock-user","clock","clock1",1)
expect("timeout-room-create",clock_room)
prefs.execute("UPDATE agent_defaults SET book_room_round_timeout_seconds=120,book_room_all_round_timeout_seconds=600 WHERE id=1")
prefs.commit()
assert db.execute("SELECT time_limit_seconds FROM book_room_rounds WHERE id='clock1'").fetchone()[0]==60
checks.append("running-window-keeps-snapshot-on-settings-change")
def selected_timeout(mode):
    column = "book_room_all_round_timeout_seconds" if mode=="all" else "book_room_round_timeout_seconds"
    return prefs.execute(f"SELECT {column} FROM agent_defaults WHERE id=1").fetchone()[0]
assert selected_timeout("all")==600
assert selected_timeout("directed")==120 and selected_timeout("natural")==120
checks.extend(["all-mode-selects-own-seconds","ordinary-modes-select-normal-seconds"])
expect("running-timeout-snapshot-frozen",lambda: db.execute(
       "UPDATE book_room_rounds SET time_limit_seconds=120 WHERE id='clock1'"),
       "running_timeout_snapshot_immutable")
expect("active-clock-used-time",lambda: db.execute(
       "UPDATE book_room_rounds SET window_elapsed_ms=60000,total_elapsed_ms=60000 WHERE id='clock1'"))
expect("elapsed-window-cannot-publish",lambda: message("bad-clock","clock","clock1",2,character=True),
       "round_timeout")
expect("timeout-pause-fences-lease",lambda: db.execute(
       "UPDATE book_room_rounds SET status='paused',error_code='round_timeout',lease_generation=lease_generation+1 WHERE id='clock1'"))
def continue_clock():
    seconds = prefs.execute("SELECT book_room_round_timeout_seconds FROM agent_defaults WHERE id=1").fetchone()[0]
    db.execute("UPDATE book_room_rounds SET time_limit_seconds=?,execution_window=execution_window+1,window_elapsed_ms=0 WHERE id='clock1'",(seconds,))
    db.execute("UPDATE book_room_rounds SET status='running',lease_owner='resumed',lease_generation=lease_generation+1 WHERE id='clock1'")
expect("explicit-continue-loads-latest-timeout",continue_clock)
expect("previous-window-result-rejected",lambda: message("bad-clock","clock","clock1",2,character=True),
       "stale_lease_or_inactive_member")
expect("continued-window-new-lease-publishes",lambda: message("clock-reply","clock","clock1",2,
       character=True,publish_lease_generation=3))
expect("clock-record-seconds-and-milliseconds",lambda: (
       None if db.execute("SELECT time_limit_seconds,execution_window,window_elapsed_ms,total_elapsed_ms FROM book_room_rounds WHERE id='clock1'").fetchone()==(120,2,0,60000)
       else (_ for _ in ()).throw(AssertionError("unit or window accounting mismatch"))))

# Free/topic content scope and immutable round snapshots.
expect("discussion-room-default-free",lambda: room("discussion"))
expect("discussion-profile-default",lambda: (
       None if db.execute("SELECT discussion_mode,discussion_topic,discussion_goal,discussion_revision FROM book_rooms WHERE id='discussion'").fetchone()==("free",None,None,0)
       else (_ for _ in ()).throw(AssertionError("discussion defaults mismatch"))))
for name, kwargs in [
    ("topic-required",dict(discussion_mode="topic")),
    ("topic-whitespace",dict(discussion_mode="topic",discussion_topic="   ")),
    ("topic-too-long",dict(discussion_mode="topic",discussion_topic="字"*201)),
    ("goal-too-long",dict(discussion_mode="topic",discussion_topic="主题",discussion_goal="字"*1001)),
    ("free-cannot-have-topic",dict(discussion_topic="主题")),
    ("free-cannot-have-goal",dict(discussion_goal="目标")),
    ("mode-enumeration",dict(discussion_mode="natural")),
    ("revision-integer",dict(discussion_revision=0.5)),
]:
    expect("discussion-"+name,lambda kwargs=kwargs: insert("book_rooms",id="bad-discussion",title="bad",**kwargs),"CHECK")
expect("discussion-change-needs-revision",lambda: db.execute(
       "UPDATE book_rooms SET discussion_mode='topic',discussion_topic='选择与命运' WHERE id='discussion'"),
       "discussion_revision_required")
expect("discussion-topic-configured",lambda: db.execute(
       "UPDATE book_rooms SET discussion_mode='topic',discussion_topic='选择与命运',discussion_goal='比较人物价值选择',discussion_revision=1 WHERE id='discussion'"))
expect("discussion-old-free-snapshot-rejected",lambda: insert("book_room_rounds",id="bad-discussion",
       room_id="discussion",epoch=1,client_turn_id="bad-discussion",mode="natural",time_limit_seconds=60),
       "discussion_snapshot_mismatch")
expect("discussion-boolean-snapshot-revision-rejected",lambda: insert("book_room_rounds",id="bad-discussion",
       room_id="discussion",epoch=1,client_turn_id="bad-discussion",mode="natural",time_limit_seconds=60,
       discussion_snapshot_json=json.dumps(dict(revision=True,mode="topic",topic="选择与命运",goal="比较人物价值选择"))),"CHECK")
expect("discussion-topic-natural-combination",lambda: turn("discussion","discussion1",mode="natural"))
expect("discussion-topic-snapshot-captured",lambda: (
       None if json.loads(db.execute("SELECT discussion_snapshot_json FROM book_room_rounds WHERE id='discussion1'").fetchone()[0])==dict(revision=1,mode="topic",topic="选择与命运",goal="比较人物价值选择")
       else (_ for _ in ()).throw(AssertionError("snapshot mismatch"))))
expect("discussion-running-switch-blocked",lambda: db.execute(
       "UPDATE book_rooms SET discussion_topic='新的主题',discussion_revision=2 WHERE id='discussion'"),"room_busy")
expect("discussion-pause-round",lambda: db.execute(
       "UPDATE book_room_rounds SET status='paused' WHERE id='discussion1'"))
expect("discussion-paused-switch-blocked",lambda: db.execute(
       "UPDATE book_rooms SET discussion_topic='新的主题',discussion_revision=2 WHERE id='discussion'"),"room_busy")
expect("discussion-paused-snapshot-immutable",lambda: db.execute(
       "UPDATE book_room_rounds SET discussion_snapshot_json=? WHERE id='discussion1'",
       (json.dumps(dict(revision=2,mode="free",topic=None,goal=None)),)),"immutable_discussion_snapshot")
expect("discussion-resume-same-topic",lambda: db.execute(
       "UPDATE book_room_rounds SET status='running',lease_generation=lease_generation+1 WHERE id='discussion1'"))
expect("discussion-user-message",lambda: message("discussion-user","discussion","discussion1",1))
expect("discussion-finish-turn",lambda: (
       db.execute("UPDATE book_room_rounds SET status='completed' WHERE id='discussion1'"),
       db.execute("UPDATE book_round_slots SET status='no_comment' WHERE round_id='discussion1'")))
expect("discussion-switch-free-idle",lambda: db.execute(
       "UPDATE book_rooms SET discussion_mode='free',discussion_topic=NULL,discussion_goal=NULL,discussion_revision=2 WHERE id='discussion'"))
expect("discussion-change-preserves-memory-seat",lambda: (
       None if db.execute("SELECT current_epoch FROM book_rooms WHERE id='discussion'").fetchone()[0]==1
       and db.execute("SELECT seat_index FROM book_room_members WHERE id='discussion-member'").fetchone()[0]==0
       and db.execute("SELECT count(*) FROM book_room_messages WHERE room_id='discussion' AND epoch=1").fetchone()[0]==1
       else (_ for _ in ()).throw(AssertionError("discussion change reset room"))))
expect("discussion-old-round-keeps-topic",lambda: (
       None if json.loads(db.execute("SELECT discussion_snapshot_json FROM book_room_rounds WHERE id='discussion1'").fetchone()[0])["topic"]=="选择与命运"
       else (_ for _ in ()).throw(AssertionError("old discussion overwritten"))))
expect("discussion-free-all-combination",lambda: turn("discussion","discussion2",mode="all",timeout_seconds=300))
expect("discussion-free-all-snapshot",lambda: (
       None if json.loads(db.execute("SELECT discussion_snapshot_json FROM book_room_rounds WHERE id='discussion2'").fetchone()[0])==dict(revision=2,mode="free",topic=None,goal=None)
       else (_ for _ in ()).throw(AssertionError("new free snapshot mismatch"))))
expect("discussion-stop-final-turn",lambda: (
       db.execute("UPDATE book_room_rounds SET status='cancelled',cancel_requested=1 WHERE id='discussion2'"),
       db.execute("UPDATE book_round_slots SET status='cancelled' WHERE round_id='discussion2'")))
expect("discussion-new-topic-no-goal",lambda: db.execute(
       "UPDATE book_rooms SET discussion_mode='topic',discussion_topic='自由与责任',discussion_goal=NULL,discussion_revision=3 WHERE id='discussion'"))
for speaker_mode in ("directed","all"):
    round_id = "discussion-" + speaker_mode
    expect("discussion-topic-"+speaker_mode+"-starts",lambda round_id=round_id,speaker_mode=speaker_mode:
           turn("discussion",round_id,mode=speaker_mode,timeout_seconds=300 if speaker_mode=="all" else 60))
    expect("discussion-topic-"+speaker_mode+"-snapshot",lambda round_id=round_id,speaker_mode=speaker_mode: (
           None if db.execute("SELECT mode FROM book_room_rounds WHERE id=?",(round_id,)).fetchone()[0]==speaker_mode
           and json.loads(db.execute("SELECT discussion_snapshot_json FROM book_room_rounds WHERE id=?",(round_id,)).fetchone()[0])==dict(revision=3,mode="topic",topic="自由与责任",goal=None)
           else (_ for _ in ()).throw(AssertionError("speaker/content modes conflated"))))
    expect("discussion-topic-"+speaker_mode+"-finishes",lambda round_id=round_id: (
           db.execute("UPDATE book_room_rounds SET status='completed' WHERE id=?",(round_id,)),
           db.execute("UPDATE book_round_slots SET status='no_comment' WHERE round_id=?",(round_id,))))

query = """SELECT c.id FROM book_claims_fts f JOIN book_claims c ON c.rowid=f.rowid
JOIN book_claim_access a ON a.book_id=c.book_id AND a.source_version_id=c.source_version_id
AND a.build_id=c.build_id AND a.claim_id=c.id
WHERE book_claims_fts MATCH ? AND a.book_id=? AND a.source_version_id=? AND a.build_id=?
AND a.character_id=? AND a.access_state='accepted' AND c.support_state='accepted'
ORDER BY rank LIMIT ?"""
expect("fts-allow-list-before-limit",lambda: (
       None if [r[0] for r in db.execute(query,("秘密","a","s1","a1","x",10))]==["f1"]
       else (_ for _ in ()).throw(AssertionError("retrieval scope leak"))))

# Mixed-source room and live member controls.
expect("mixed-room-initial-source",lambda: room("mix"))
expect("mixed-room-second-source",lambda: insert("book_room_sources",room_id="mix",**scope("b1")))
expect("mixed-room-second-character",lambda: insert("book_room_members",id="mix-b",
       room_id="mix",**scope("b1"),character_id="w",seat_index=1,identity_snapshot_json="{}",state_epoch=1))
expect("same-book-second-build-denied",lambda: insert("book_room_sources",
       room_id="mix",**scope("a2")),"UNIQUE")
expect("unregistered-source-member-denied",lambda: insert("book_room_members",id="bad",
       room_id="mix",**scope("a3"),character_id="x3",seat_index=2,identity_snapshot_json="{}",state_epoch=1),
       "FOREIGN KEY")
expect("mixed-round-b",lambda: turn("mix","mb1",member_id="mix-b"))
expect("mixed-user-message",lambda: message("mu1","mix","mb1",1))
expect("mixed-book-b-response",lambda: message("mc1","mix","mb1",2,character=True))
expect("mixed-book-b-canon-ref",lambda: ref("mix-ref",rid="mix",message_id="mc1",
       speaker_member_id="mix-b",**scope("b1"),character_id="w",claim_id="fb",evidence_id="eb"))
expect("other-book-canon-ref-denied",lambda: ref("bad",rid="mix",message_id="mc1",
       speaker_member_id="mix-b",assertion_ordinal=9),"FOREIGN KEY")
def finish(tid):
    db.execute("UPDATE book_room_rounds SET status='completed',cursor=1 WHERE id=?",(tid,))
    db.execute("UPDATE book_round_slots SET status=CASE WHEN EXISTS (SELECT 1 FROM book_room_messages m WHERE m.slot_id=book_round_slots.id) THEN 'published' ELSE 'no_comment' END WHERE round_id=?",(tid,))
expect("finish-mixed-first-turn",lambda: finish("mb1"))
expect("mention-only-mode",lambda: db.execute(
       "UPDATE book_room_members SET speaking_mode='mention_only',membership_generation=membership_generation+1 WHERE id='mix-b'"))
expect("mention-only-natural-turn",lambda: turn("mix","mb2",member_id="mix-b",mode="natural"))
expect("mention-only-not-natural-response",lambda: message("bad","mix","mb2",3,character=True),
       "stale_lease_or_inactive_member")
expect("finish-no-comment-turn",lambda: finish("mb2"))
expect("mention-only-directed-turn",lambda: turn("mix","mb3",member_id="mix-b"))
expect("mention-only-at-response",lambda: message("mc2","mix","mb3",3,character=True))
expect("finish-directed-turn",lambda: finish("mb3"))
expect("member-control-needs-generation",lambda: db.execute(
       "UPDATE book_room_members SET speaking_mode='muted' WHERE id='mix-b'"),
       "member_generation_required")
expect("pending-b-reply",lambda: turn("mix","mb4",member_id="mix-b"))
expect("mute-now",lambda: db.execute(
       "UPDATE book_room_members SET speaking_mode='muted',membership_generation=membership_generation+1 WHERE id='mix-b'"))
expect("muted-at-denied",lambda: message("bad","mix","mb4",4,character=True),
       "stale_lease_or_inactive_member")
expect("unmute",lambda: db.execute(
       "UPDATE book_room_members SET speaking_mode='auto',membership_generation=membership_generation+1 WHERE id='mix-b'"))
expect("old-reply-after-unmute-denied",lambda: message("bad","mix","mb4",4,character=True),
       "stale_lease_or_inactive_member")
expect("finish-muted-turn",lambda: finish("mb4"))
expect("pending-a-reply",lambda: turn("mix","ma1"))
expect("remove-now",lambda: db.execute(
       "UPDATE book_room_members SET active=0,removed_reason='user',membership_generation=membership_generation+1 WHERE id='mix-member'"))
expect("removed-reply-denied",lambda: message("bad","mix","ma1",4,character=True),
       "stale_lease_or_inactive_member")
expect("rejoin",lambda: db.execute(
       "UPDATE book_room_members SET active=1,removed_reason=NULL,membership_generation=membership_generation+1 WHERE id='mix-member'"))
expect("old-reply-after-rejoin-denied",lambda: message("bad","mix","ma1",4,character=True),
       "stale_lease_or_inactive_member")
expect("finish-removed-turn",lambda: finish("ma1"))
expect("surviving-b-turn-before-delete",lambda: turn("mix","mb5",member_id="mix-b"))

def remove(book="a"):
    item = 1 if book=="a" else 2
    db.execute("UPDATE book_books SET lifecycle_state='purging' WHERE id=?",(book,))
    db.execute("UPDATE book_source_versions SET lifecycle_state='unavailable' WHERE book_id=?",(book,))
    db.execute("UPDATE book_builds SET lifecycle_state='unavailable' WHERE book_id=?",(book,))
    db.execute("UPDATE book_room_sources SET status='source_removed' WHERE book_id=?",(book,))
    db.execute("UPDATE book_room_members SET active=0,removed_reason='source_removed',membership_generation=membership_generation+1 WHERE book_id=?",(book,))
    db.execute("UPDATE book_round_slots SET status='cancelled' WHERE status IN ('pending','running') AND member_id IN (SELECT id FROM book_room_members WHERE book_id=?)",(book,))
    db.execute("""UPDATE book_rooms SET status='readonly' WHERE NOT EXISTS (
        SELECT 1 FROM book_room_sources rs JOIN book_books bk ON bk.id=rs.book_id
        JOIN book_source_versions s ON s.id=rs.source_version_id
        JOIN book_builds b ON b.id=rs.build_id
        WHERE rs.room_id=book_rooms.id AND rs.status='active' AND bk.lifecycle_state='active'
        AND s.lifecycle_state='available' AND b.lifecycle_state='active'
        AND b.status IN ('published','partial_published'))""")
    db.execute("UPDATE book_room_rounds SET status='cancelled',cancel_requested=1 WHERE room_id IN (SELECT id FROM book_rooms WHERE status='readonly')")
    db.execute("DELETE FROM book_character_baselines WHERE book_id=?",(book,))
    db.execute("DELETE FROM book_claims WHERE book_id=?",(book,))
    db.execute("DELETE FROM book_scene_characters WHERE book_id=?",(book,))
    db.execute("DELETE FROM book_character_aliases WHERE book_id=?",(book,))
    db.execute("DELETE FROM book_scenes WHERE book_id=?",(book,))
    db.execute("DELETE FROM book_segments WHERE book_id=?",(book,))
    db.execute("UPDATE book_build_steps SET result_json='{}' WHERE book_id=?",(book,))
    db.execute("UPDATE book_builds SET error_detail=NULL WHERE book_id=?",(book,))
    db.execute("UPDATE book_characters SET agent_status='source_removed',public_profile_json='{}',runtime_policy_json='{}' WHERE book_id=?",(book,))
    db.execute("DELETE FROM library_items WHERE id=?",(item,))
    db.execute("UPDATE book_books SET lifecycle_state='removed' WHERE id=?",(book,))
expect("source-purge-keeps-required-scope-and-transcript",remove)
expect("source-removed-publish-denied",lambda: insert("book_room_messages",id="bad",room_id="r1",
       epoch=2,seq=5,speaker_type="system",content="late",validation_state="not_applicable"),
       "stale_epoch_or_unavailable_source")
expect("historical-identity-kept",lambda: (
       None if db.execute("SELECT build_id FROM book_room_sources WHERE room_id='r1' AND book_id='a'").fetchone()[0]=="a1"
       and db.execute("SELECT count(*) FROM book_room_messages WHERE room_id='r1'").fetchone()[0]==4
       else (_ for _ in ()).throw(AssertionError("history lost"))))
expect("mixed-room-stays-active-after-one-source-removed",lambda: (
       None if db.execute("SELECT status FROM book_rooms WHERE id='mix'").fetchone()[0]=='active'
       else (_ for _ in ()).throw(AssertionError("remaining source was disabled"))))
expect("other-book-pending-reply-survives-delete",lambda: message("mc3","mix","mb5",4,character=True))
expect("other-book-canon-ref-survives-delete",lambda: ref("mix-ref-after",rid="mix",message_id="mc3",
       speaker_member_id="mix-b",**scope("b1"),character_id="w",claim_id="fb",evidence_id="eb"))
expect("mixed-hearsay-from-prior-public-message",lambda: insert("book_message_refs",id="mix-heard",
       room_id="mix",epoch=1,message_id="mc3",speaker_member_id="mix-b",assertion_ordinal=1,
       assertion_text="我在房间里听到",origin="room_hearsay",heard_message_id="mu1"))
expect("remove-last-source",lambda: remove("b"))
expect("mixed-room-readonly-when-all-sources-removed",lambda: (
       None if db.execute("SELECT status FROM book_rooms WHERE id='mix'").fetchone()[0]=='readonly'
       else (_ for _ in ()).throw(AssertionError("empty-source room still active"))))
expect("no-source-mixed-room-publish-denied",lambda: insert("book_room_messages",id="bad",
       room_id="mix",epoch=1,seq=5,speaker_type="system",content="late",validation_state="not_applicable"),
       "stale_epoch_or_unavailable_source")
expect("final-foreign-key-check",lambda: (
       None if not db.execute("PRAGMA foreign_key_check").fetchall()
       else (_ for _ in ()).throw(AssertionError("invalid foreign keys"))))
print(json.dumps({"sqlite_version":sqlite3.sqlite_version,"database":":memory:",
                  "check_count":len(checks),"checks":checks},ensure_ascii=False))

