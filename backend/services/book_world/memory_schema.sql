-- T07 room/epoch-scoped reviewed summaries and immutable source links.
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
CREATE TRIGGER IF NOT EXISTS tr_book_summary_epoch BEFORE INSERT ON book_room_summaries
WHEN NOT EXISTS (SELECT 1 FROM book_rooms r JOIN book_room_epochs e ON e.room_id=r.id AND e.epoch=r.current_epoch
 WHERE r.id=NEW.room_id AND r.current_epoch=NEW.epoch AND r.status='active' AND e.state='active')
BEGIN SELECT RAISE(ABORT,'stale_summary_epoch'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_summary_source_range BEFORE INSERT ON book_summary_sources
WHEN NOT EXISTS (SELECT 1 FROM book_room_messages m JOIN book_room_summaries s ON s.id=NEW.summary_id
 WHERE s.room_id=NEW.room_id AND s.epoch=NEW.epoch AND m.id=NEW.message_id AND m.room_id=NEW.room_id AND m.epoch=NEW.epoch AND m.seq<=s.through_seq)
BEGIN SELECT RAISE(ABORT,'invalid_summary_source'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_summary_immutable BEFORE UPDATE ON book_room_summaries
BEGIN SELECT RAISE(ABORT,'immutable_room_summary'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_summary_source_immutable BEFORE UPDATE ON book_summary_sources
BEGIN SELECT RAISE(ABORT,'immutable_summary_source'); END;
