-- Follow-on migration: finalized derivative payloads cannot gain new materials/references.
CREATE TRIGGER IF NOT EXISTS tr_book_expression_sets_no_reopen BEFORE UPDATE OF status ON book_expression_sets
WHEN old.status IN ('ready','partial') AND new.status<>old.status
BEGIN SELECT RAISE(ABORT,'immutable_expression_publication'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_materials_insert BEFORE INSERT ON book_expression_materials
WHEN NOT EXISTS(SELECT 1 FROM book_expression_sets s WHERE s.id=new.set_id AND s.lifecycle_state='active' AND s.status IN ('queued','running'))
BEGIN SELECT RAISE(ABORT,'expression_not_writable'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_refs_insert BEFORE INSERT ON book_expression_refs
WHEN NOT EXISTS(SELECT 1 FROM book_expression_sets s WHERE s.id=new.set_id AND s.lifecycle_state='active' AND s.status IN ('queued','running'))
BEGIN SELECT RAISE(ABORT,'expression_not_writable'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_refs_ready_delete BEFORE DELETE ON book_expression_refs
WHEN EXISTS(SELECT 1 FROM book_expression_sets s WHERE s.id=old.set_id AND s.lifecycle_state='active' AND s.status IN ('ready','partial'))
BEGIN SELECT RAISE(ABORT,'immutable_expression_reference'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_expression_refs_span BEFORE INSERT ON book_expression_refs
WHEN NOT EXISTS(
 SELECT 1 FROM book_access_evidence v JOIN book_evidence e ON e.book_id=v.book_id AND e.source_version_id=v.source_version_id AND e.build_id=v.build_id AND e.claim_id=v.claim_id AND e.id=v.evidence_id
 WHERE v.book_id=new.book_id AND v.source_version_id=new.source_version_id AND v.build_id=new.build_id AND v.character_id=new.character_id AND v.claim_id=new.claim_id AND v.evidence_id=new.evidence_id
 AND v.visibility_state='accepted' AND e.support_state='accepted' AND length(v.approved_excerpt)>0 AND instr(e.quote_text,v.approved_excerpt)>0
 AND e.segment_id=new.segment_id
 AND new.local_start>=e.local_start+instr(e.quote_text,v.approved_excerpt)-1
 AND new.local_end<=e.local_start+instr(e.quote_text,v.approved_excerpt)-1+length(v.approved_excerpt)
)
BEGIN SELECT RAISE(ABORT,'expression_outside_safe_projection'); END;
