-- T06 room/round/publication foundation, adapted from the approved storage contract.
CREATE TABLE IF NOT EXISTS book_rooms (
  id TEXT PRIMARY KEY NOT NULL,
  title TEXT NOT NULL,
  client_room_id TEXT NOT NULL UNIQUE,
  current_epoch INTEGER NOT NULL DEFAULT 1 CHECK (current_epoch>0),
  next_seq INTEGER NOT NULL DEFAULT 1 CHECK (next_seq>0),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','readonly','archived')),
  policy_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(policy_snapshot_json)),
  scene_layout_version INTEGER NOT NULL DEFAULT 1 CHECK (typeof(scene_layout_version)='integer' AND scene_layout_version>0),
  scene_capacity INTEGER NOT NULL DEFAULT 8 CHECK (typeof(scene_capacity)='integer' AND scene_capacity>0),
  discussion_mode TEXT NOT NULL DEFAULT 'free' CHECK (discussion_mode IN ('free','topic')),
  discussion_topic TEXT,
  discussion_goal TEXT,
  discussion_revision INTEGER NOT NULL DEFAULT 0 CHECK (typeof(discussion_revision)='integer' AND discussion_revision>=0),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (id,current_epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CHECK ((discussion_mode='free' AND discussion_topic IS NULL AND discussion_goal IS NULL) OR
    (discussion_mode='topic' AND typeof(discussion_topic)='text' AND length(trim(discussion_topic)) BETWEEN 1 AND 200
     AND (discussion_goal IS NULL OR (typeof(discussion_goal)='text' AND length(trim(discussion_goal)) BETWEEN 1 AND 1000))))
);

CREATE INDEX IF NOT EXISTS ix_book_rooms_catalog ON book_rooms(status,created_at,id);

CREATE TABLE IF NOT EXISTS book_room_sources (
  room_id TEXT NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','source_removed','inactive')),
  source_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_snapshot_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (room_id,book_id, source_version_id, build_id),
  FOREIGN KEY (room_id) REFERENCES book_rooms(id) ON DELETE CASCADE,
  FOREIGN KEY (book_id, source_version_id, build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  UNIQUE (room_id,book_id)
);

CREATE INDEX IF NOT EXISTS ix_book_source_rooms ON book_room_sources(book_id, source_version_id, build_id,status,room_id);

CREATE TABLE IF NOT EXISTS book_room_epochs (
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL CHECK (epoch>0),
  state TEXT NOT NULL CHECK (state IN ('active','cleared')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  cleared_at TEXT,
  PRIMARY KEY (room_id,epoch),
  FOREIGN KEY (room_id) REFERENCES book_rooms(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_active_epoch ON book_room_epochs(room_id) WHERE state='active';

CREATE TABLE IF NOT EXISTS book_room_members (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  seat_index INTEGER NOT NULL CHECK (typeof(seat_index)='integer' AND seat_index>=0),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  speaking_mode TEXT NOT NULL DEFAULT 'auto' CHECK (speaking_mode IN ('auto','mention_only','muted')),
  membership_generation INTEGER NOT NULL DEFAULT 0 CHECK (membership_generation>=0),
  removed_reason TEXT CHECK (removed_reason IS NULL OR removed_reason IN ('user','source_removed')),
  identity_snapshot_json TEXT NOT NULL CHECK (json_valid(identity_snapshot_json)),
  state_epoch INTEGER NOT NULL,
  ephemeral_state_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(ephemeral_state_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (room_id,book_id, source_version_id, build_id) REFERENCES book_room_sources(room_id,book_id, source_version_id, build_id) ON DELETE RESTRICT,
  FOREIGN KEY (book_id, source_version_id, build_id,character_id) REFERENCES book_characters(book_id, source_version_id, build_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (room_id,state_epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  UNIQUE (room_id,id),
  UNIQUE (room_id,character_id),
  UNIQUE (room_id,book_id, source_version_id, build_id,id,character_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_room_seat ON book_room_members(room_id,seat_index);

CREATE TABLE IF NOT EXISTS book_room_rounds (
  id TEXT PRIMARY KEY NOT NULL,
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  client_turn_id TEXT NOT NULL,
  generation_snapshot_json TEXT NOT NULL CHECK(json_valid(generation_snapshot_json)),
  mode TEXT NOT NULL CHECK (mode IN ('directed','natural','all')),
  discussion_snapshot_json TEXT NOT NULL DEFAULT '{"revision":0,"mode":"free","topic":null,"goal":null}'
    CHECK (json_valid(discussion_snapshot_json)
      AND coalesce(json_type(discussion_snapshot_json,'$.revision')='integer',0)
      AND json_extract(discussion_snapshot_json,'$.revision')>=0
      AND coalesce(json_type(discussion_snapshot_json,'$.mode')='text',0)
      AND json_extract(discussion_snapshot_json,'$.mode') IN ('free','topic')
      AND ((json_extract(discussion_snapshot_json,'$.mode')='free'
            AND coalesce(json_type(discussion_snapshot_json,'$.topic')='null',0)
            AND coalesce(json_type(discussion_snapshot_json,'$.goal')='null',0))
        OR (json_extract(discussion_snapshot_json,'$.mode')='topic'
            AND coalesce(json_type(discussion_snapshot_json,'$.topic')='text',0)
            AND length(trim(json_extract(discussion_snapshot_json,'$.topic'))) BETWEEN 1 AND 200
            AND (coalesce(json_type(discussion_snapshot_json,'$.goal')='null',0)
              OR (coalesce(json_type(discussion_snapshot_json,'$.goal')='text',0)
                AND length(trim(json_extract(discussion_snapshot_json,'$.goal'))) BETWEEN 1 AND 1000))))),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','paused','completed','cancelled','interrupted','failed')),
  cursor INTEGER NOT NULL DEFAULT 0 CHECK (cursor>=0),
  lease_owner TEXT,
  lease_generation INTEGER NOT NULL DEFAULT 0 CHECK (lease_generation>=0),
  lease_expires_at TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  error_code TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  time_limit_seconds INTEGER NOT NULL CHECK (typeof(time_limit_seconds)='integer' AND time_limit_seconds>0),
  execution_window INTEGER NOT NULL DEFAULT 1 CHECK (execution_window>0),
  window_elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK (typeof(window_elapsed_ms)='integer' AND window_elapsed_ms>=0),
  total_elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK (typeof(total_elapsed_ms)='integer' AND total_elapsed_ms>=window_elapsed_ms),
  run_started_at TEXT,
  FOREIGN KEY (room_id,epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE CASCADE,
  UNIQUE (room_id,epoch,id),
  UNIQUE (room_id,epoch,client_turn_id),
  CHECK (status<>'running' OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_active_round ON book_room_rounds(room_id) WHERE status IN ('queued','running','paused','interrupted');

CREATE INDEX IF NOT EXISTS ix_book_round_recovery ON book_room_rounds(status,lease_expires_at,id);

CREATE TABLE IF NOT EXISTS book_round_slots (
  id TEXT PRIMARY KEY NOT NULL,
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  round_id TEXT NOT NULL,
  position INTEGER NOT NULL CHECK (position>=0),
  member_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','published','no_comment','failed','cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts>=0),
  member_generation INTEGER NOT NULL CHECK (member_generation>=0),
  FOREIGN KEY (room_id,epoch,round_id) REFERENCES book_room_rounds(room_id,epoch,id) ON DELETE CASCADE,
  FOREIGN KEY (room_id,member_id) REFERENCES book_room_members(room_id,id) ON DELETE RESTRICT,
  UNIQUE (round_id,position),
  UNIQUE (round_id,member_id),
  UNIQUE (room_id,epoch,round_id,id,member_id)
);

CREATE TABLE IF NOT EXISTS book_room_messages (
  id TEXT PRIMARY KEY NOT NULL,
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  seq INTEGER NOT NULL CHECK (seq>0),
  round_id TEXT,
  slot_id TEXT,
  speaker_type TEXT NOT NULL CHECK (speaker_type IN ('user','character','system')),
  speaker_member_id TEXT,
  identity_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(identity_snapshot_json)),
  reply_to_id TEXT,
  content TEXT NOT NULL,
  validation_state TEXT NOT NULL CHECK (validation_state IN ('accepted','not_applicable')),
  publish_lease_generation INTEGER,
  display_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(display_snapshot_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  publish_member_generation INTEGER,
  FOREIGN KEY (room_id,epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE CASCADE,
  FOREIGN KEY (room_id,epoch,round_id) REFERENCES book_room_rounds(room_id,epoch,id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (room_id,epoch,round_id,slot_id,speaker_member_id) REFERENCES book_round_slots(room_id,epoch,round_id,id,member_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (room_id,epoch,reply_to_id) REFERENCES book_room_messages(room_id,epoch,id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  UNIQUE (room_id,seq),
  UNIQUE (room_id,epoch,id),
  UNIQUE (room_id,epoch,id,speaker_member_id),
  CHECK ((speaker_type='character' AND round_id IS NOT NULL AND slot_id IS NOT NULL AND speaker_member_id IS NOT NULL AND publish_lease_generation IS NOT NULL AND publish_member_generation IS NOT NULL AND validation_state='accepted') OR (speaker_type<>'character' AND slot_id IS NULL AND speaker_member_id IS NULL AND publish_lease_generation IS NULL AND publish_member_generation IS NULL)),
  CHECK (speaker_type<>'user' OR round_id IS NOT NULL),
  UNIQUE (room_id,epoch,seq)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_slot_message ON book_room_messages(slot_id) WHERE slot_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_user_turn ON book_room_messages(round_id) WHERE speaker_type='user';

CREATE INDEX IF NOT EXISTS ix_book_room_history ON book_room_messages(room_id,epoch,seq);

CREATE INDEX IF NOT EXISTS ix_book_message_reply ON book_room_messages(room_id,epoch,reply_to_id);

CREATE TABLE IF NOT EXISTS book_message_refs (
  id TEXT PRIMARY KEY NOT NULL,
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  message_id TEXT NOT NULL,
  speaker_member_id TEXT NOT NULL,
  assertion_ordinal INTEGER NOT NULL CHECK (assertion_ordinal>=0),
  assertion_text TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('canon','character_belief','inference','room_hearsay')),
  book_id TEXT,
  source_version_id TEXT,
  build_id TEXT,
  character_id TEXT,
  claim_id TEXT,
  evidence_id TEXT,
  heard_message_id TEXT,
  FOREIGN KEY (room_id,epoch,message_id,speaker_member_id) REFERENCES book_room_messages(room_id,epoch,id,speaker_member_id) ON DELETE CASCADE,
  FOREIGN KEY (room_id,book_id, source_version_id, build_id,speaker_member_id,character_id) REFERENCES book_room_members(room_id,book_id, source_version_id, build_id,id,character_id) ON DELETE RESTRICT,
  FOREIGN KEY (book_id, source_version_id, build_id,character_id,claim_id,evidence_id) REFERENCES book_access_evidence(book_id, source_version_id, build_id,character_id,claim_id,evidence_id) ON DELETE CASCADE,
  FOREIGN KEY (room_id,epoch,heard_message_id) REFERENCES book_room_messages(room_id,epoch,id) ON DELETE CASCADE,
  CHECK ((origin='room_hearsay' AND heard_message_id IS NOT NULL AND book_id IS NULL AND source_version_id IS NULL AND build_id IS NULL AND character_id IS NULL AND claim_id IS NULL AND evidence_id IS NULL) OR (origin<>'room_hearsay' AND heard_message_id IS NULL AND book_id IS NOT NULL AND source_version_id IS NOT NULL AND build_id IS NOT NULL AND character_id IS NOT NULL AND claim_id IS NOT NULL AND evidence_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_canon_ref ON book_message_refs(message_id,assertion_ordinal,claim_id,evidence_id) WHERE origin<>'room_hearsay';

CREATE UNIQUE INDEX IF NOT EXISTS ux_book_heard_ref ON book_message_refs(message_id,assertion_ordinal,heard_message_id) WHERE origin='room_hearsay';

CREATE INDEX IF NOT EXISTS ix_book_ref_access ON book_message_refs(book_id, source_version_id, build_id,character_id,claim_id,evidence_id);

CREATE INDEX IF NOT EXISTS ix_book_heard_source ON book_message_refs(room_id,epoch,heard_message_id);

CREATE TRIGGER IF NOT EXISTS tr_book_room_epochs_scope_update BEFORE UPDATE OF room_id,epoch ON book_room_epochs
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_room_members_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id,room_id,character_id ON book_room_members
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id OR NEW.room_id IS NOT OLD.room_id OR NEW.character_id IS NOT OLD.character_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_room_rounds_scope_update BEFORE UPDATE OF room_id,epoch ON book_room_rounds
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_round_slots_scope_update BEFORE UPDATE OF room_id,epoch ON book_round_slots
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_refs_scope_update BEFORE UPDATE OF room_id,epoch,book_id,source_version_id,build_id ON book_message_refs
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch OR NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_sequence BEFORE INSERT ON book_room_messages
WHEN NEW.seq<>(SELECT next_seq FROM book_rooms WHERE id=NEW.room_id)
BEGIN SELECT RAISE(ABORT,'invalid_message_sequence'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_sequence_advance AFTER INSERT ON book_room_messages
BEGIN UPDATE book_rooms SET next_seq=next_seq+1 WHERE id=NEW.room_id; END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_immutable BEFORE UPDATE ON book_room_messages
BEGIN SELECT RAISE(ABORT,'immutable_published_message'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_hearsay_order BEFORE INSERT ON book_message_refs
WHEN NEW.origin='room_hearsay' AND NOT EXISTS (
 SELECT 1 FROM book_room_messages src JOIN book_room_messages dst ON dst.id=NEW.message_id
 WHERE src.id=NEW.heard_message_id AND src.room_id=NEW.room_id AND src.epoch=NEW.epoch AND src.seq<dst.seq)
BEGIN SELECT RAISE(ABORT,'invalid_hearsay_order'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_epoch BEFORE INSERT ON book_room_messages
WHEN NOT EXISTS (SELECT 1 FROM book_rooms r JOIN book_room_epochs ep ON ep.room_id=r.id AND ep.epoch=r.current_epoch
 WHERE r.id=NEW.room_id AND r.current_epoch=NEW.epoch AND ep.state='active' AND r.status='active')
 OR NOT EXISTS (SELECT 1 FROM book_room_sources rs
 JOIN book_books bk ON bk.id=rs.book_id
 JOIN book_source_versions s ON s.id=rs.source_version_id AND s.book_id=rs.book_id
 JOIN book_builds b ON b.id=rs.build_id AND b.book_id=rs.book_id AND b.source_version_id=rs.source_version_id
 WHERE rs.room_id=NEW.room_id AND rs.status='active' AND bk.lifecycle_state='active'
 AND s.lifecycle_state='available' AND b.lifecycle_state='active' AND b.status IN ('published','partial_published'))
BEGIN SELECT RAISE(ABORT,'stale_epoch_or_unavailable_source'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_round_epoch BEFORE INSERT ON book_room_rounds
WHEN NOT EXISTS (SELECT 1 FROM book_rooms r JOIN book_room_epochs ep ON ep.room_id=r.id AND ep.epoch=r.current_epoch
 WHERE r.id=NEW.room_id AND r.current_epoch=NEW.epoch AND ep.state='active' AND r.status='active')
 OR NOT EXISTS (SELECT 1 FROM book_room_sources rs
 JOIN book_books bk ON bk.id=rs.book_id
 JOIN book_source_versions s ON s.id=rs.source_version_id AND s.book_id=rs.book_id
 JOIN book_builds b ON b.id=rs.build_id AND b.book_id=rs.book_id AND b.source_version_id=rs.source_version_id
 WHERE rs.room_id=NEW.room_id AND rs.status='active' AND bk.lifecycle_state='active'
 AND s.lifecycle_state='available' AND b.lifecycle_state='active' AND b.status IN ('published','partial_published'))
BEGIN SELECT RAISE(ABORT,'stale_round_epoch_or_source'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_lease BEFORE INSERT ON book_room_messages
WHEN NEW.speaker_type='character' AND NOT EXISTS (
 SELECT 1 FROM book_room_rounds ro JOIN book_round_slots sl ON sl.round_id=ro.id
 JOIN book_room_members m ON m.id=sl.member_id AND m.room_id=ro.room_id
 JOIN book_room_sources rs ON rs.room_id=m.room_id AND rs.book_id=m.book_id
  AND rs.source_version_id=m.source_version_id AND rs.build_id=m.build_id
 JOIN book_characters c ON c.id=m.character_id AND c.book_id=m.book_id
  AND c.source_version_id=m.source_version_id AND c.build_id=m.build_id
 JOIN book_books bk ON bk.id=m.book_id
 JOIN book_source_versions s ON s.id=m.source_version_id AND s.book_id=m.book_id
 JOIN book_builds b ON b.id=m.build_id AND b.book_id=m.book_id AND b.source_version_id=m.source_version_id
 WHERE ro.id=NEW.round_id AND ro.room_id=NEW.room_id AND ro.epoch=NEW.epoch
 AND ro.status='running' AND ro.cancel_requested=0 AND ro.lease_generation=NEW.publish_lease_generation
 AND ro.lease_expires_at>strftime('%Y-%m-%dT%H:%M:%fZ','now')
 AND sl.id=NEW.slot_id AND sl.member_id=NEW.speaker_member_id AND sl.status='running'
 AND m.active=1 AND m.state_epoch=NEW.epoch AND c.agent_status IN ('ready','sparse')
 AND m.membership_generation=sl.member_generation AND m.membership_generation=NEW.publish_member_generation
 AND (m.speaking_mode='auto' OR (m.speaking_mode='mention_only' AND ro.mode IN ('directed','all')))
 AND rs.status='active' AND bk.lifecycle_state='active' AND s.lifecycle_state='available'
 AND b.lifecycle_state='active' AND b.status IN ('published','partial_published'))
BEGIN SELECT RAISE(ABORT,'stale_lease_or_inactive_member'); END;

-- Discussion scope is independent of the existing directed/natural/all speaker mode.
CREATE TRIGGER IF NOT EXISTS tr_book_discussion_update BEFORE UPDATE OF discussion_mode,discussion_topic,discussion_goal,discussion_revision ON book_rooms
WHEN NEW.discussion_mode IS NOT OLD.discussion_mode OR NEW.discussion_topic IS NOT OLD.discussion_topic OR NEW.discussion_goal IS NOT OLD.discussion_goal OR NEW.discussion_revision IS NOT OLD.discussion_revision
BEGIN
  SELECT CASE WHEN NEW.discussion_revision<>OLD.discussion_revision+1 THEN RAISE(ABORT,'discussion_revision_required') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM book_room_rounds WHERE room_id=OLD.id AND status IN ('queued','running','paused','interrupted')
  ) THEN RAISE(ABORT,'room_busy') END;
END;

CREATE TRIGGER IF NOT EXISTS tr_book_discussion_snapshot_insert BEFORE INSERT ON book_room_rounds
WHEN NOT EXISTS (
  SELECT 1 FROM book_rooms WHERE id=NEW.room_id
    AND discussion_revision=json_extract(NEW.discussion_snapshot_json,'$.revision')
    AND discussion_mode=json_extract(NEW.discussion_snapshot_json,'$.mode')
    AND discussion_topic IS json_extract(NEW.discussion_snapshot_json,'$.topic')
    AND discussion_goal IS json_extract(NEW.discussion_snapshot_json,'$.goal')
)
BEGIN SELECT RAISE(ABORT,'discussion_snapshot_mismatch'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_discussion_snapshot_immutable BEFORE UPDATE OF discussion_snapshot_json ON book_room_rounds
WHEN NEW.discussion_snapshot_json IS NOT OLD.discussion_snapshot_json
BEGIN SELECT RAISE(ABORT,'immutable_discussion_snapshot'); END;

-- Roundtable positions are presentation data, reserved even when a member leaves.
CREATE TRIGGER IF NOT EXISTS tr_book_member_seat_insert BEFORE INSERT ON book_room_members
WHEN NEW.seat_index >= (SELECT scene_capacity FROM book_rooms WHERE id=NEW.room_id)
BEGIN SELECT RAISE(ABORT,'seat_out_of_capacity'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_member_seat_immutable BEFORE UPDATE OF seat_index ON book_room_members
WHEN NEW.seat_index IS NOT OLD.seat_index
BEGIN SELECT RAISE(ABORT,'immutable_member_seat'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_layout_immutable BEFORE UPDATE OF scene_layout_version ON book_rooms
WHEN NEW.scene_layout_version IS NOT OLD.scene_layout_version
BEGIN SELECT RAISE(ABORT,'immutable_scene_layout'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_capacity_update BEFORE UPDATE OF scene_capacity ON book_rooms
WHEN NEW.scene_capacity IS NOT OLD.scene_capacity
BEGIN
  SELECT CASE WHEN NEW.scene_capacity<OLD.scene_capacity THEN RAISE(ABORT,'scene_capacity_shrink_denied') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM book_room_rounds WHERE room_id=OLD.id AND status IN ('queued','running','paused','interrupted')
  ) THEN RAISE(ABORT,'room_busy') END;
END;

CREATE TRIGGER IF NOT EXISTS tr_book_room_sources_scope BEFORE UPDATE OF room_id,book_id,source_version_id,build_id ON book_room_sources
WHEN NEW.room_id<>OLD.room_id OR NEW.book_id<>OLD.book_id OR NEW.source_version_id<>OLD.source_version_id OR NEW.build_id<>OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_member_control_generation BEFORE UPDATE OF active,speaking_mode ON book_room_members
WHEN (NEW.active<>OLD.active OR NEW.speaking_mode<>OLD.speaking_mode) AND NEW.membership_generation<>OLD.membership_generation+1
BEGIN SELECT RAISE(ABORT,'member_generation_required'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_slot_member_snapshot BEFORE UPDATE OF member_id,member_generation ON book_round_slots
WHEN NEW.member_id<>OLD.member_id OR NEW.member_generation<>OLD.member_generation
BEGIN SELECT RAISE(ABORT,'immutable_slot_member_snapshot'); END;

-- Time is snapshotted per explicitly started execution window.
CREATE TRIGGER IF NOT EXISTS tr_book_running_timeout_snapshot BEFORE UPDATE OF time_limit_seconds,execution_window ON book_room_rounds
WHEN OLD.status='running' AND (NEW.time_limit_seconds<>OLD.time_limit_seconds OR NEW.execution_window<>OLD.execution_window)
BEGIN SELECT RAISE(ABORT,'running_timeout_snapshot_immutable'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_time_budget BEFORE INSERT ON book_room_messages
WHEN NEW.speaker_type='character' AND EXISTS (SELECT 1 FROM book_room_rounds r
 WHERE r.id=NEW.round_id AND r.window_elapsed_ms>=r.time_limit_seconds*1000)
BEGIN SELECT RAISE(ABORT,'round_timeout'); END;
