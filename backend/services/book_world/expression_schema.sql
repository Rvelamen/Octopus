-- T05 derived expressions have independent state; published canonical rows are untouched.
CREATE TABLE IF NOT EXISTS book_expression_sets (
 id TEXT PRIMARY KEY NOT NULL, book_id TEXT NOT NULL,source_version_id TEXT NOT NULL,build_id TEXT NOT NULL,character_id TEXT NOT NULL,
 canonical_policy_version TEXT NOT NULL,knowledge_policy_version TEXT NOT NULL,
 input_fingerprint TEXT NOT NULL,baseline_hash TEXT NOT NULL,config_json TEXT NOT NULL CHECK(json_valid(config_json)),
 status TEXT NOT NULL CHECK(status IN ('queued','running','ready','partial','failed','paused','cancelled')),
 lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle_state IN ('active','unavailable')),
 progress_json TEXT NOT NULL CHECK(json_valid(progress_json)),error_code TEXT,error_detail TEXT,
 cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),lease_owner TEXT,lease_generation INTEGER NOT NULL DEFAULT 0,lease_expires_at TEXT,
 window_calls INTEGER NOT NULL DEFAULT 0 CHECK(window_calls>=0),total_calls INTEGER NOT NULL DEFAULT 0 CHECK(total_calls>=0),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(book_id,source_version_id,build_id,character_id,id),
 UNIQUE(book_id,source_version_id,build_id,character_id,input_fingerprint),
 FOREIGN KEY(book_id,source_version_id,build_id,character_id) REFERENCES book_characters(book_id,source_version_id,build_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_expression_sets_scope ON book_expression_sets(book_id,source_version_id,build_id,character_id,status,created_at);
CREATE TABLE IF NOT EXISTS book_expression_materials (
 id TEXT PRIMARY KEY NOT NULL,set_id TEXT NOT NULL,book_id TEXT NOT NULL,source_version_id TEXT NOT NULL,build_id TEXT NOT NULL,character_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('style_rule','dialogue_example')),text TEXT NOT NULL CHECK(length(text)>0 AND length(text)<=300 AND (kind<>'dialogue_example' OR length(text)<=160)),
 dialogue_action TEXT NOT NULL,topic_terms_json TEXT NOT NULL CHECK(json_valid(topic_terms_json)),review_state TEXT NOT NULL CHECK(review_state IN ('accepted','rejected')),
 material_fingerprint TEXT NOT NULL,review_json TEXT NOT NULL CHECK(json_valid(review_json)),
 UNIQUE(book_id,source_version_id,build_id,character_id,set_id,id),UNIQUE(set_id,material_fingerprint),
 FOREIGN KEY(book_id,source_version_id,build_id,character_id,set_id) REFERENCES book_expression_sets(book_id,source_version_id,build_id,character_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_expression_materials_scope ON book_expression_materials(book_id,source_version_id,build_id,character_id,set_id,kind,review_state,dialogue_action);
CREATE TABLE IF NOT EXISTS book_expression_refs (
 material_id TEXT NOT NULL,set_id TEXT NOT NULL,book_id TEXT NOT NULL,source_version_id TEXT NOT NULL,build_id TEXT NOT NULL,character_id TEXT NOT NULL,
 claim_id TEXT NOT NULL,evidence_id TEXT NOT NULL,purpose TEXT NOT NULL CHECK(purpose IN ('speaker','style','fact','stance')),
 segment_id TEXT NOT NULL,local_start INTEGER NOT NULL CHECK(local_start>=0),local_end INTEGER NOT NULL CHECK(local_end>local_start),approved_excerpt_hash TEXT NOT NULL,
 PRIMARY KEY(material_id,claim_id,evidence_id,purpose),
 FOREIGN KEY(book_id,source_version_id,build_id,character_id,set_id,material_id) REFERENCES book_expression_materials(book_id,source_version_id,build_id,character_id,set_id,id) ON DELETE CASCADE,
 FOREIGN KEY(book_id,source_version_id,build_id,character_id,claim_id,evidence_id) REFERENCES book_access_evidence(book_id,source_version_id,build_id,character_id,claim_id,evidence_id) ON DELETE CASCADE,
 FOREIGN KEY(book_id,source_version_id,segment_id) REFERENCES book_segments(book_id,source_version_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_expression_refs_view ON book_expression_refs(book_id,source_version_id,build_id,character_id,claim_id,evidence_id,material_id);
CREATE TRIGGER IF NOT EXISTS tr_book_expression_sets_scope BEFORE UPDATE OF book_id,source_version_id,build_id,character_id ON book_expression_sets
WHEN new.book_id IS NOT old.book_id OR new.source_version_id IS NOT old.source_version_id OR new.build_id IS NOT old.build_id OR new.character_id IS NOT old.character_id
BEGIN SELECT RAISE(ABORT,'immutable_expression_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_sets_definition BEFORE UPDATE OF input_fingerprint,baseline_hash,config_json,canonical_policy_version,knowledge_policy_version ON book_expression_sets
BEGIN SELECT RAISE(ABORT,'immutable_expression_definition'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_materials_scope BEFORE UPDATE OF set_id,book_id,source_version_id,build_id,character_id ON book_expression_materials
BEGIN SELECT RAISE(ABORT,'immutable_expression_scope'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_refs_scope BEFORE UPDATE ON book_expression_refs
BEGIN SELECT RAISE(ABORT,'immutable_expression_reference'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_materials_ready_update BEFORE UPDATE ON book_expression_materials
WHEN EXISTS(SELECT 1 FROM book_expression_sets s WHERE s.id=old.set_id AND s.lifecycle_state='active' AND s.status IN ('ready','partial'))
BEGIN SELECT RAISE(ABORT,'immutable_expression_material'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_materials_ready_delete BEFORE DELETE ON book_expression_materials
WHEN EXISTS(SELECT 1 FROM book_expression_sets s WHERE s.id=old.set_id AND s.lifecycle_state='active' AND s.status IN ('ready','partial'))
BEGIN SELECT RAISE(ABORT,'immutable_expression_material'); END;
