-- Empty quotations retain authorized propositions, but cannot become dialogue.
DROP TRIGGER IF EXISTS tr_book_expression_refs_span;
CREATE TRIGGER tr_book_expression_refs_span BEFORE INSERT ON book_expression_refs
WHEN NOT EXISTS(
 SELECT 1 FROM book_access_evidence v
 JOIN book_evidence e ON e.book_id=v.book_id AND e.source_version_id=v.source_version_id AND e.build_id=v.build_id AND e.claim_id=v.claim_id AND e.id=v.evidence_id
 JOIN book_claim_access a ON a.book_id=v.book_id AND a.source_version_id=v.source_version_id AND a.build_id=v.build_id AND a.character_id=v.character_id AND a.claim_id=v.claim_id
 JOIN book_claims c ON c.book_id=v.book_id AND c.source_version_id=v.source_version_id AND c.build_id=v.build_id AND c.id=v.claim_id
 WHERE v.book_id=new.book_id AND v.source_version_id=new.source_version_id AND v.build_id=new.build_id AND v.character_id=new.character_id AND v.claim_id=new.claim_id AND v.evidence_id=new.evidence_id
 AND v.visibility_state='accepted' AND e.support_state='accepted' AND a.access_state='accepted' AND c.support_state='accepted'
 AND (c.kind='fact' OR c.owner_character_id=v.character_id) AND e.segment_id=new.segment_id
 AND (
  (length(v.approved_excerpt)>0 AND instr(e.quote_text,v.approved_excerpt)>0
   AND instr(substr(e.quote_text,instr(e.quote_text,v.approved_excerpt)+1),v.approved_excerpt)=0
   AND new.local_start>=e.local_start+instr(e.quote_text,v.approved_excerpt)-1
   AND new.local_end<=e.local_start+instr(e.quote_text,v.approved_excerpt)-1+length(v.approved_excerpt))
  OR (v.approved_excerpt='' AND new.purpose='style' AND c.kind='style'
   AND new.local_start=e.local_start AND new.local_end=e.local_end
   AND EXISTS(SELECT 1 FROM book_character_baselines b WHERE b.book_id=v.book_id AND b.source_version_id=v.source_version_id AND b.build_id=v.build_id AND b.character_id=v.character_id AND b.claim_id=v.claim_id AND b.slot_key LIKE 'style:%')
   AND EXISTS(SELECT 1 FROM book_expression_materials m WHERE m.id=new.material_id AND m.kind='style_rule' AND m.text=c.proposition))
 )
)
BEGIN SELECT RAISE(ABORT,'expression_outside_safe_projection'); END;
