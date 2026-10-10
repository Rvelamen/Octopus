-- Octopus cross-book character room storage schema draft, 2026-10-10.
-- Design artifact only; not a registered production migration.
-- Requires existing library_items, SQLite JSON/FTS5 and FK enabled per connection.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS book_books (
  id TEXT PRIMARY KEY NOT NULL,
  library_item_id INTEGER UNIQUE,
  title_snapshot TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active','purging','removed')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  removed_at TEXT,
  FOREIGN KEY (library_item_id) REFERENCES library_items(id) ON DELETE SET NULL,
  CHECK (lifecycle_state <> 'active' OR library_item_id IS NOT NULL)
);


CREATE TABLE IF NOT EXISTS book_source_versions (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  attachment_sha256 TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  canonical_text_sha256 TEXT NOT NULL,
  asset_rel_path TEXT,
  text_rel_path TEXT,
  format TEXT NOT NULL CHECK (format IN ('pdf','epub','txt')),
  lifecycle_state TEXT NOT NULL DEFAULT 'available' CHECK (lifecycle_state IN ('available','unavailable','purged')),
  quality_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(quality_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (book_id) REFERENCES book_books(id) ON DELETE RESTRICT,
  UNIQUE (book_id,id),
  UNIQUE (book_id,attachment_sha256,parser_version,canonical_text_sha256)
);


CREATE TABLE IF NOT EXISTS book_segments (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  page INTEGER CHECK (page IS NULL OR page > 0),
  chapter TEXT,
  start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
  end_offset INTEGER NOT NULL,
  text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  FOREIGN KEY (book_id,source_version_id) REFERENCES book_source_versions(book_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id,source_version_id,id),
  UNIQUE (book_id,source_version_id,ordinal),
  CHECK (end_offset > start_offset AND end_offset-start_offset=length(text))
);
CREATE INDEX IF NOT EXISTS ix_book_segments_page ON book_segments(book_id,source_version_id,page,ordinal);

CREATE TABLE IF NOT EXISTS book_builds (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  parent_build_id TEXT,
  build_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','published','partial_published','failed','cancelled','needs_ocr','blocked_config')),
  stage TEXT NOT NULL DEFAULT 'waiting_source',
  lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active','unavailable','purged')),
  config_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_snapshot_json)),
  policy_version TEXT NOT NULL,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  lease_owner TEXT,
  lease_generation INTEGER NOT NULL DEFAULT 0 CHECK (lease_generation>=0),
  lease_expires_at TEXT,
  error_code TEXT,
  error_detail TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (book_id,source_version_id) REFERENCES book_source_versions(book_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id,source_version_id,id),
  FOREIGN KEY (book_id,source_version_id,parent_build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id,source_version_id,build_fingerprint),
  CHECK (parent_build_id IS NULL OR parent_build_id<>id)
);
CREATE INDEX IF NOT EXISTS ix_book_build_resume ON book_builds(status,lease_expires_at,id);
CREATE INDEX IF NOT EXISTS ix_book_build_catalog ON book_builds(book_id,source_version_id,status,created_at,id);

CREATE TABLE IF NOT EXISTS book_build_steps (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  unit_key TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','running','validated','failed')),
  result_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(result_json)),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts>=0),
  lease_generation INTEGER NOT NULL CHECK (lease_generation>=0),
  FOREIGN KEY (book_id, source_version_id, build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  PRIMARY KEY (book_id, source_version_id, build_id,stage,unit_key,input_hash)
);


CREATE TABLE IF NOT EXISTS book_scenes (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  narrative_order INTEGER NOT NULL CHECK (narrative_order>=0),
  story_time_json TEXT CHECK (story_time_json IS NULL OR json_valid(story_time_json)),
  location_label TEXT,
  FOREIGN KEY (book_id, source_version_id, build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id, source_version_id, build_id,id),
  UNIQUE (book_id, source_version_id, build_id,narrative_order)
);


CREATE TABLE IF NOT EXISTS book_scene_segments (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  position INTEGER NOT NULL CHECK (position>=0),
  segment_id TEXT NOT NULL,
  PRIMARY KEY (book_id, source_version_id, build_id,scene_id,position),
  FOREIGN KEY (book_id, source_version_id, build_id,scene_id) REFERENCES book_scenes(book_id, source_version_id, build_id,id) ON DELETE CASCADE,
  FOREIGN KEY (book_id,source_version_id,segment_id) REFERENCES book_segments(book_id,source_version_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_scene_segment_reverse ON book_scene_segments(book_id,source_version_id,segment_id,build_id,scene_id);

CREATE TABLE IF NOT EXISTS book_characters (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  lineage_id TEXT NOT NULL,
  name TEXT NOT NULL,
  agent_status TEXT NOT NULL DEFAULT 'candidate' CHECK (agent_status IN ('candidate','ready','sparse','needs_review','failed','source_removed')),
  public_profile_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(public_profile_json)),
  runtime_policy_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(runtime_policy_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (book_id, source_version_id, build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id, source_version_id, build_id,id),
  UNIQUE (book_id, source_version_id, build_id,lineage_id)
);
CREATE INDEX IF NOT EXISTS ix_book_character_catalog ON book_characters(book_id, source_version_id, build_id,agent_status,name,id);

CREATE TABLE IF NOT EXISTS book_character_aliases (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  alias TEXT NOT NULL,
  normalized_alias TEXT NOT NULL,
  review_state TEXT NOT NULL CHECK (review_state IN ('candidate','accepted','ambiguous')),
  provenance_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(provenance_json)),
  PRIMARY KEY (book_id, source_version_id, build_id,character_id,normalized_alias),
  FOREIGN KEY (book_id, source_version_id, build_id,character_id) REFERENCES book_characters(book_id, source_version_id, build_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_alias_lookup ON book_character_aliases(book_id, source_version_id, build_id,normalized_alias,character_id);

CREATE TABLE IF NOT EXISTS book_scene_characters (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  presence TEXT NOT NULL CHECK (presence IN ('active','silent','referenced','uncertain')),
  PRIMARY KEY (book_id, source_version_id, build_id,scene_id,character_id),
  FOREIGN KEY (book_id, source_version_id, build_id,scene_id) REFERENCES book_scenes(book_id, source_version_id, build_id,id) ON DELETE CASCADE,
  FOREIGN KEY (book_id, source_version_id, build_id,character_id) REFERENCES book_characters(book_id, source_version_id, build_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_character_scenes ON book_scene_characters(book_id, source_version_id, build_id,character_id,scene_id);

CREATE TABLE IF NOT EXISTS book_claims (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('fact','episode','belief','trait','relation','emotion','style')),
  owner_character_id TEXT,
  proposition TEXT NOT NULL,
  truth_state TEXT NOT NULL DEFAULT 'unknown' CHECK (truth_state IN ('true','false','disputed','unknown')),
  interpretation_level TEXT NOT NULL CHECK (interpretation_level IN ('explicit','supported','speculative')),
  support_state TEXT NOT NULL DEFAULT 'pending' CHECK (support_state IN ('pending','accepted','rejected')),
  scene_id TEXT,
  supersedes_claim_id TEXT,
  search_terms TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (book_id, source_version_id, build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
  UNIQUE (book_id, source_version_id, build_id,id),
  FOREIGN KEY (book_id, source_version_id, build_id,owner_character_id) REFERENCES book_characters(book_id, source_version_id, build_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (book_id, source_version_id, build_id,scene_id) REFERENCES book_scenes(book_id, source_version_id, build_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (book_id, source_version_id, build_id,supersedes_claim_id) REFERENCES book_claims(book_id, source_version_id, build_id,id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CHECK ((kind='fact' AND owner_character_id IS NULL) OR (kind<>'fact' AND owner_character_id IS NOT NULL)),
  CHECK (supersedes_claim_id IS NULL OR supersedes_claim_id<>id)
);
CREATE INDEX IF NOT EXISTS ix_book_claim_owner ON book_claims(book_id, source_version_id, build_id,owner_character_id,kind,id);
CREATE INDEX IF NOT EXISTS ix_book_claim_scene ON book_claims(book_id, source_version_id, build_id,scene_id,id);

CREATE TABLE IF NOT EXISTS book_evidence (
  id TEXT PRIMARY KEY NOT NULL,
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  local_start INTEGER NOT NULL CHECK (local_start>=0),
  local_end INTEGER NOT NULL,
  quote_text TEXT NOT NULL,
  quote_hash TEXT NOT NULL,
  support_state TEXT NOT NULL DEFAULT 'pending' CHECK (support_state IN ('pending','accepted','rejected')),
  UNIQUE (book_id, source_version_id, build_id,claim_id,id),
  FOREIGN KEY (book_id, source_version_id, build_id,claim_id) REFERENCES book_claims(book_id, source_version_id, build_id,id) ON DELETE CASCADE,
  FOREIGN KEY (book_id,source_version_id,segment_id) REFERENCES book_segments(book_id,source_version_id,id) ON DELETE RESTRICT,
  CHECK (local_end>local_start)
);
CREATE INDEX IF NOT EXISTS ix_book_evidence_segment ON book_evidence(book_id,source_version_id,segment_id,build_id,claim_id);

CREATE TABLE IF NOT EXISTS book_claim_access (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  route TEXT NOT NULL CHECK (route IN ('firsthand','observed','told','common')),
  acquisition_scene_id TEXT,
  disclosure TEXT NOT NULL DEFAULT 'private' CHECK (disclosure IN ('private','public')),
  access_state TEXT NOT NULL DEFAULT 'pending' CHECK (access_state IN ('pending','accepted','revoked')),
  PRIMARY KEY (book_id, source_version_id, build_id,character_id,claim_id),
  FOREIGN KEY (book_id, source_version_id, build_id,character_id) REFERENCES book_characters(book_id, source_version_id, build_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (book_id, source_version_id, build_id,claim_id) REFERENCES book_claims(book_id, source_version_id, build_id,id) ON DELETE CASCADE,
  FOREIGN KEY (book_id, source_version_id, build_id,acquisition_scene_id) REFERENCES book_scenes(book_id, source_version_id, build_id,id) ON DELETE RESTRICT,
  CHECK (route='common' OR acquisition_scene_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_book_claim_grantees ON book_claim_access(book_id, source_version_id, build_id,claim_id,character_id);

CREATE TABLE IF NOT EXISTS book_access_evidence (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  approved_excerpt TEXT NOT NULL DEFAULT '',
  visibility_state TEXT NOT NULL DEFAULT 'pending' CHECK (visibility_state IN ('pending','accepted','rejected')),
  PRIMARY KEY (book_id, source_version_id, build_id,character_id,claim_id,evidence_id),
  FOREIGN KEY (book_id, source_version_id, build_id,character_id,claim_id) REFERENCES book_claim_access(book_id, source_version_id, build_id,character_id,claim_id) ON DELETE CASCADE,
  FOREIGN KEY (book_id, source_version_id, build_id,claim_id,evidence_id) REFERENCES book_evidence(book_id, source_version_id, build_id,claim_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_book_evidence_views ON book_access_evidence(book_id, source_version_id, build_id,claim_id,evidence_id,character_id);

CREATE TABLE IF NOT EXISTS book_character_baselines (
  book_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  build_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  slot_key TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  PRIMARY KEY (book_id, source_version_id, build_id,character_id,slot_key),
  FOREIGN KEY (book_id, source_version_id, build_id,character_id,claim_id) REFERENCES book_claim_access(book_id, source_version_id, build_id,character_id,claim_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_book_baseline_claim ON book_character_baselines(book_id, source_version_id, build_id,character_id,claim_id);

CREATE TABLE IF NOT EXISTS book_rooms (
  id TEXT PRIMARY KEY NOT NULL,
  title TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS book_room_summaries (
  id TEXT PRIMARY KEY NOT NULL,
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  through_seq INTEGER NOT NULL CHECK (through_seq>0),
  summary_json TEXT NOT NULL CHECK (json_valid(summary_json)),
  validation_state TEXT NOT NULL CHECK (validation_state IN ('pending','accepted','rejected')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY (room_id,epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE CASCADE,
  UNIQUE (room_id,epoch,id),
  UNIQUE (room_id,epoch,through_seq),
  FOREIGN KEY (room_id,epoch,through_seq) REFERENCES book_room_messages(room_id,epoch,seq) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS ix_book_summary_latest ON book_room_summaries(room_id,epoch,validation_state,through_seq DESC);

CREATE TABLE IF NOT EXISTS book_summary_sources (
  room_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  summary_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  PRIMARY KEY (room_id,epoch,summary_id,message_id),
  FOREIGN KEY (room_id,epoch,summary_id) REFERENCES book_room_summaries(room_id,epoch,id) ON DELETE CASCADE,
  FOREIGN KEY (room_id,epoch,message_id) REFERENCES book_room_messages(room_id,epoch,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_book_summary_message ON book_summary_sources(room_id,epoch,message_id,summary_id);

-- Publication, scope and evidence guards.
-- Immutable identity and source-version fields.
CREATE TRIGGER IF NOT EXISTS tr_book_source_identity BEFORE UPDATE OF book_id,attachment_sha256,parser_version,canonical_text_sha256 ON book_source_versions
WHEN NEW.book_id<>OLD.book_id OR NEW.attachment_sha256<>OLD.attachment_sha256 OR NEW.parser_version<>OLD.parser_version OR NEW.canonical_text_sha256<>OLD.canonical_text_sha256
BEGIN SELECT RAISE(ABORT,'immutable_source_version'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_segment_immutable BEFORE UPDATE ON book_segments
BEGIN SELECT RAISE(ABORT,'immutable_source_segment'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_build_publication BEFORE UPDATE OF status ON book_builds
WHEN OLD.status IN ('published','partial_published') AND NEW.status<>OLD.status
BEGIN SELECT RAISE(ABORT,'immutable_build_publication'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_builds_scope_update BEFORE UPDATE OF book_id,source_version_id ON book_builds
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_build_steps_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_build_steps
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_scenes_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_scenes
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_scene_segments_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_scene_segments
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_characters_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_characters
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_character_aliases_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_character_aliases
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_scene_characters_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_scene_characters
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_claims_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_claims
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_evidence_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_evidence
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_claim_access_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_claim_access
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_access_evidence_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_access_evidence
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_character_baselines_scope_update BEFORE UPDATE OF book_id,source_version_id,build_id ON book_character_baselines
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.source_version_id IS NOT OLD.source_version_id OR NEW.build_id IS NOT OLD.build_id
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
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
CREATE TRIGGER IF NOT EXISTS tr_book_room_summaries_scope_update BEFORE UPDATE OF room_id,epoch ON book_room_summaries
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_summary_sources_scope_update BEFORE UPDATE OF room_id,epoch ON book_summary_sources
WHEN NEW.room_id IS NOT OLD.room_id OR NEW.epoch IS NOT OLD.epoch
BEGIN SELECT RAISE(ABORT,'immutable_record_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_evidence_span_insert BEFORE INSERT ON book_evidence
WHEN NOT EXISTS (SELECT 1 FROM book_segments s WHERE s.id=NEW.segment_id AND s.book_id=NEW.book_id AND s.source_version_id=NEW.source_version_id AND NEW.local_end<=length(s.text) AND NEW.quote_text=substr(s.text,NEW.local_start+1,NEW.local_end-NEW.local_start))
BEGIN SELECT RAISE(ABORT,'invalid_evidence_span'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_evidence_span_update BEFORE UPDATE ON book_evidence
WHEN NOT EXISTS (SELECT 1 FROM book_segments s WHERE s.id=NEW.segment_id AND s.book_id=NEW.book_id AND s.source_version_id=NEW.source_version_id AND NEW.local_end<=length(s.text) AND NEW.quote_text=substr(s.text,NEW.local_start+1,NEW.local_end-NEW.local_start))
BEGIN SELECT RAISE(ABORT,'invalid_evidence_span'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_personal_access_insert BEFORE INSERT ON book_claim_access
WHEN EXISTS (SELECT 1 FROM book_claims c WHERE c.id=NEW.claim_id AND c.kind<>'fact' AND c.owner_character_id<>NEW.character_id)
BEGIN SELECT RAISE(ABORT,'non_owner_personal_claim'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_personal_access_update BEFORE UPDATE ON book_claim_access
WHEN EXISTS (SELECT 1 FROM book_claims c WHERE c.id=NEW.claim_id AND c.kind<>'fact' AND c.owner_character_id<>NEW.character_id)
BEGIN SELECT RAISE(ABORT,'non_owner_personal_claim'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_excerpt_insert BEFORE INSERT ON book_access_evidence
WHEN NEW.approved_excerpt<>'' AND NOT EXISTS (SELECT 1 FROM book_evidence e WHERE e.id=NEW.evidence_id AND instr(e.quote_text,NEW.approved_excerpt)>0)
BEGIN SELECT RAISE(ABORT,'invalid_approved_excerpt'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_excerpt_update BEFORE UPDATE ON book_access_evidence
WHEN NEW.approved_excerpt<>'' AND NOT EXISTS (SELECT 1 FROM book_evidence e WHERE e.id=NEW.evidence_id AND instr(e.quote_text,NEW.approved_excerpt)>0)
BEGIN SELECT RAISE(ABORT,'invalid_approved_excerpt'); END;



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

CREATE TRIGGER IF NOT EXISTS tr_book_summary_epoch BEFORE INSERT ON book_room_summaries
WHEN NOT EXISTS (SELECT 1 FROM book_rooms r JOIN book_room_epochs e ON e.room_id=r.id AND e.epoch=r.current_epoch
 WHERE r.id=NEW.room_id AND r.current_epoch=NEW.epoch AND r.status='active' AND e.state='active')
BEGIN SELECT RAISE(ABORT,'stale_summary_epoch'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_summary_source_range BEFORE INSERT ON book_summary_sources
WHEN NOT EXISTS (SELECT 1 FROM book_room_messages m JOIN book_room_summaries s ON s.id=NEW.summary_id
 WHERE m.id=NEW.message_id AND m.room_id=NEW.room_id AND m.epoch=NEW.epoch AND m.seq<=s.through_seq)
BEGIN SELECT RAISE(ABORT,'invalid_summary_source'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scenes_frozen_insert BEFORE INSERT ON book_scenes
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scenes_frozen_update BEFORE UPDATE ON book_scenes
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scenes_frozen_delete BEFORE DELETE ON book_scenes
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_segments_frozen_insert BEFORE INSERT ON book_scene_segments
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_segments_frozen_update BEFORE UPDATE ON book_scene_segments
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_segments_frozen_delete BEFORE DELETE ON book_scene_segments
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_characters_frozen_insert BEFORE INSERT ON book_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_characters_frozen_update BEFORE UPDATE ON book_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_characters_frozen_delete BEFORE DELETE ON book_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_aliases_frozen_insert BEFORE INSERT ON book_character_aliases
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_aliases_frozen_update BEFORE UPDATE ON book_character_aliases
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_aliases_frozen_delete BEFORE DELETE ON book_character_aliases
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_characters_frozen_insert BEFORE INSERT ON book_scene_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_characters_frozen_update BEFORE UPDATE ON book_scene_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_scene_characters_frozen_delete BEFORE DELETE ON book_scene_characters
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claims_frozen_insert BEFORE INSERT ON book_claims
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claims_frozen_update BEFORE UPDATE ON book_claims
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claims_frozen_delete BEFORE DELETE ON book_claims
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_evidence_frozen_insert BEFORE INSERT ON book_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_evidence_frozen_update BEFORE UPDATE ON book_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_evidence_frozen_delete BEFORE DELETE ON book_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claim_access_frozen_insert BEFORE INSERT ON book_claim_access
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claim_access_frozen_update BEFORE UPDATE ON book_claim_access
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_claim_access_frozen_delete BEFORE DELETE ON book_claim_access
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_access_evidence_frozen_insert BEFORE INSERT ON book_access_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_access_evidence_frozen_update BEFORE UPDATE ON book_access_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_access_evidence_frozen_delete BEFORE DELETE ON book_access_evidence
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_baselines_frozen_insert BEFORE INSERT ON book_character_baselines
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=NEW.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_baselines_frozen_update BEFORE UPDATE ON book_character_baselines
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_character_baselines_frozen_delete BEFORE DELETE ON book_character_baselines
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books bk ON bk.id=b.book_id
 WHERE b.id=OLD.build_id AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND bk.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

-- Retrieval index; application supplies Chinese terms and joins the allow-list before LIMIT.
CREATE VIRTUAL TABLE IF NOT EXISTS book_claims_fts USING fts5(search_terms,content='book_claims',content_rowid='rowid',tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS tr_book_claim_fts_insert AFTER INSERT ON book_claims
BEGIN INSERT INTO book_claims_fts(rowid,search_terms) VALUES (NEW.rowid,NEW.search_terms); END;
CREATE TRIGGER IF NOT EXISTS tr_book_claim_fts_delete AFTER DELETE ON book_claims
BEGIN INSERT INTO book_claims_fts(book_claims_fts,rowid,search_terms) VALUES ('delete',OLD.rowid,OLD.search_terms); END;
CREATE TRIGGER IF NOT EXISTS tr_book_claim_fts_update AFTER UPDATE OF search_terms ON book_claims
BEGIN
 INSERT INTO book_claims_fts(book_claims_fts,rowid,search_terms) VALUES ('delete',OLD.rowid,OLD.search_terms);
 INSERT INTO book_claims_fts(rowid,search_terms) VALUES (NEW.rowid,NEW.search_terms);
END;




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

