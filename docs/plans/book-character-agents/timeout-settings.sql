-- Design migration sketch for the GLOBAL app.db agent_defaults table.
-- Do not execute on a live database; a migration must inspect table_info first.
-- Not part of the workspace .knowledge_index.db migration sequence.
ALTER TABLE agent_defaults ADD COLUMN book_room_round_timeout_seconds
 INTEGER NOT NULL DEFAULT 60
 CHECK (typeof(book_room_round_timeout_seconds)='integer' AND book_room_round_timeout_seconds>0);
ALTER TABLE agent_defaults ADD COLUMN book_room_all_round_timeout_seconds
 INTEGER NOT NULL DEFAULT 300
 CHECK (typeof(book_room_all_round_timeout_seconds)='integer' AND book_room_all_round_timeout_seconds>0);

