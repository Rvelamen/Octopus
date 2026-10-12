-- Follow-on T06 guards: submitted request/model identity and published citations stay fixed.
CREATE TRIGGER IF NOT EXISTS tr_book_round_request_immutable
BEFORE UPDATE OF client_turn_id,mode,generation_snapshot_json ON book_room_rounds
WHEN new.client_turn_id IS NOT old.client_turn_id OR new.mode IS NOT old.mode
 OR new.generation_snapshot_json IS NOT old.generation_snapshot_json
BEGIN SELECT RAISE(ABORT,'immutable_round_generation_snapshot'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_refs_immutable BEFORE UPDATE ON book_message_refs
BEGIN SELECT RAISE(ABORT,'immutable_published_reference'); END;

CREATE TRIGGER IF NOT EXISTS tr_book_message_refs_accepted BEFORE INSERT ON book_message_refs
WHEN new.origin<>'room_hearsay' AND NOT EXISTS(
 SELECT 1 FROM book_access_evidence v
 JOIN book_claim_access a ON a.book_id=v.book_id AND a.source_version_id=v.source_version_id AND a.build_id=v.build_id AND a.character_id=v.character_id AND a.claim_id=v.claim_id
 JOIN book_claims c ON c.book_id=v.book_id AND c.source_version_id=v.source_version_id AND c.build_id=v.build_id AND c.id=v.claim_id
 JOIN book_evidence e ON e.book_id=v.book_id AND e.source_version_id=v.source_version_id AND e.build_id=v.build_id AND e.claim_id=v.claim_id AND e.id=v.evidence_id
 WHERE v.book_id=new.book_id AND v.source_version_id=new.source_version_id AND v.build_id=new.build_id AND v.character_id=new.character_id AND v.claim_id=new.claim_id AND v.evidence_id=new.evidence_id
 AND v.visibility_state='accepted' AND a.access_state='accepted' AND c.support_state='accepted' AND e.support_state='accepted'
 AND (c.kind='fact' OR c.owner_character_id=v.character_id)
)
BEGIN SELECT RAISE(ABORT,'unapproved_message_reference'); END;
