-- T09 durable public reasons and generation progress; existing identities stay fixed.
ALTER TABLE book_round_slots ADD COLUMN skip_reason TEXT;
ALTER TABLE book_room_rounds ADD COLUMN progress_phase TEXT
  CHECK (progress_phase IS NULL OR progress_phase IN ('preparing','generating','validating'));

CREATE TRIGGER IF NOT EXISTS tr_book_slot_identity_immutable
BEFORE UPDATE OF round_id,position,member_id,member_generation ON book_round_slots
WHEN new.round_id IS NOT old.round_id OR new.position IS NOT old.position
 OR new.member_id IS NOT old.member_id OR new.member_generation IS NOT old.member_generation
BEGIN SELECT RAISE(ABORT,'immutable_slot_authorization'); END;
