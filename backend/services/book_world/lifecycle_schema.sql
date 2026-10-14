-- T11 retryable deletion state retains all B/R identity references.
CREATE TABLE IF NOT EXISTS book_source_purges (
 book_id TEXT PRIMARY KEY NOT NULL,
 library_item_id INTEGER NOT NULL,
 library_rel_path TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','failed','completed')),
 error_code TEXT,
 updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(book_id) REFERENCES book_books(id) ON DELETE RESTRICT
);

-- Segments retain identity/position/hash. Only irreversible whitespace redaction is
-- permitted after source authorization is disabled; the length contract stays true.
DROP TRIGGER IF EXISTS tr_book_segment_immutable;
CREATE TRIGGER tr_book_segment_immutable BEFORE UPDATE ON book_segments
WHEN NOT (
 NEW.id IS OLD.id AND NEW.book_id IS OLD.book_id AND NEW.source_version_id IS OLD.source_version_id
 AND NEW.ordinal IS OLD.ordinal AND NEW.page IS OLD.page AND NEW.chapter IS NULL
 AND NEW.start_offset IS OLD.start_offset AND NEW.end_offset IS OLD.end_offset AND NEW.text_sha256 IS OLD.text_sha256
 AND NEW.text=replace(hex(zeroblob(length(OLD.text))),'00',' ')
 AND EXISTS(SELECT 1 FROM book_source_versions s JOIN book_books b ON b.id=s.book_id
   WHERE s.book_id=OLD.book_id AND s.id=OLD.source_version_id AND s.lifecycle_state<>'available' AND b.lifecycle_state<>'active')
)
BEGIN SELECT RAISE(ABORT,'immutable_source_segment'); END;

DROP TRIGGER IF EXISTS tr_book_evidence_span_update;
CREATE TRIGGER tr_book_evidence_span_update BEFORE UPDATE ON book_evidence
WHEN NOT EXISTS (SELECT 1 FROM book_segments s WHERE s.id=NEW.segment_id AND s.book_id=NEW.book_id AND s.source_version_id=NEW.source_version_id AND NEW.local_end<=length(s.text) AND NEW.quote_text=substr(s.text,NEW.local_start+1,NEW.local_end-NEW.local_start))
 AND NOT (
 NEW.id IS OLD.id AND NEW.book_id IS OLD.book_id AND NEW.source_version_id IS OLD.source_version_id
 AND NEW.build_id IS OLD.build_id AND NEW.claim_id IS OLD.claim_id AND NEW.segment_id IS OLD.segment_id
 AND NEW.local_start IS OLD.local_start AND NEW.local_end IS OLD.local_end AND NEW.quote_hash IS OLD.quote_hash
 AND NEW.support_state IS OLD.support_state AND NEW.quote_text=''
 AND EXISTS(SELECT 1 FROM book_source_versions s JOIN book_books b ON b.id=s.book_id
   WHERE s.book_id=OLD.book_id AND s.id=OLD.source_version_id AND s.lifecycle_state<>'available' AND b.lifecycle_state<>'active')
 )
BEGIN SELECT RAISE(ABORT,'invalid_evidence_span'); END;

DROP TRIGGER IF EXISTS tr_book_revision_immutable;
CREATE TRIGGER tr_book_revision_immutable BEFORE UPDATE ON book_revisions
WHEN NOT (
 NEW.book_id IS OLD.book_id AND NEW.source_version_id IS OLD.source_version_id AND NEW.build_id IS OLD.build_id
 AND NEW.base_build_id IS OLD.base_build_id AND NEW.reserved_revision IS OLD.reserved_revision
 AND NEW.request_id IS OLD.request_id AND NEW.request_hash IS OLD.request_hash
 AND NEW.character_map_json IS OLD.character_map_json AND NEW.created_at IS OLD.created_at
 AND NEW.changes_json='[]' AND NEW.review_json='{}'
 AND EXISTS(SELECT 1 FROM book_books b WHERE b.id=OLD.book_id AND b.lifecycle_state<>'active')
)
BEGIN SELECT RAISE(ABORT,'immutable_revision_audit'); END;

-- An old PDF extraction may finish after source deletion. It cannot repopulate
-- ordinary-library original text or embeddings, even when files remain locked.
CREATE TRIGGER IF NOT EXISTS tr_library_chunk_removed_source_insert BEFORE INSERT ON library_chunks
WHEN EXISTS(SELECT 1 FROM book_books b WHERE b.library_item_id=NEW.item_id AND b.lifecycle_state<>'active')
BEGIN SELECT RAISE(ABORT,'source_removed'); END;
CREATE TRIGGER IF NOT EXISTS tr_library_chunk_removed_source_update BEFORE UPDATE ON library_chunks
WHEN EXISTS(SELECT 1 FROM book_books b WHERE b.library_item_id=NEW.item_id AND b.lifecycle_state<>'active')
BEGIN SELECT RAISE(ABORT,'source_removed'); END;
