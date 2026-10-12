-- Production T02 discovery tables; scope B = book/source/build.
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

