-- Production T03 evidence, access, baselines and publication guards.
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

CREATE TRIGGER IF NOT EXISTS tr_book_baseline_accepted_insert BEFORE INSERT ON book_character_baselines
WHEN NOT EXISTS (SELECT 1 FROM book_claim_access a JOIN book_claims c ON c.id=a.claim_id AND c.build_id=a.build_id
 WHERE a.book_id=NEW.book_id AND a.source_version_id=NEW.source_version_id AND a.build_id=NEW.build_id
 AND a.character_id=NEW.character_id AND a.claim_id=NEW.claim_id AND a.access_state='accepted' AND c.support_state='accepted')
BEGIN SELECT RAISE(ABORT,'unapproved_baseline'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_baseline_accepted_update BEFORE UPDATE ON book_character_baselines
WHEN NOT EXISTS (SELECT 1 FROM book_claim_access a JOIN book_claims c ON c.id=a.claim_id AND c.build_id=a.build_id
 WHERE a.book_id=NEW.book_id AND a.source_version_id=NEW.source_version_id AND a.build_id=NEW.build_id
 AND a.character_id=NEW.character_id AND a.claim_id=NEW.claim_id AND a.access_state='accepted' AND c.support_state='accepted')
BEGIN SELECT RAISE(ABORT,'unapproved_baseline'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_steps_frozen_insert BEFORE INSERT ON book_build_steps
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books k ON k.id=b.book_id WHERE b.id=NEW.build_id
 AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND k.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_steps_frozen_update BEFORE UPDATE ON book_build_steps
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books k ON k.id=b.book_id WHERE b.id=OLD.build_id
 AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND k.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_steps_frozen_delete BEFORE DELETE ON book_build_steps
WHEN EXISTS (SELECT 1 FROM book_builds b JOIN book_books k ON k.id=b.book_id WHERE b.id=OLD.build_id
 AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND k.lifecycle_state='active')
BEGIN SELECT RAISE(ABORT,'immutable_published_canon'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_published_config BEFORE UPDATE OF config_snapshot_json,build_fingerprint,policy_version,parent_build_id,stage ON book_builds
WHEN OLD.status IN ('published','partial_published') AND (NEW.config_snapshot_json IS NOT OLD.config_snapshot_json
 OR NEW.build_fingerprint IS NOT OLD.build_fingerprint OR NEW.policy_version IS NOT OLD.policy_version
 OR NEW.parent_build_id IS NOT OLD.parent_build_id OR NEW.stage IS NOT OLD.stage)
BEGIN SELECT RAISE(ABORT,'immutable_published_config'); END;
