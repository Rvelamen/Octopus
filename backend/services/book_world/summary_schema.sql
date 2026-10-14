-- Public summary jobs have independent finite execution and cancellation generations.
CREATE TABLE IF NOT EXISTS book_room_summary_jobs (
 id TEXT PRIMARY KEY NOT NULL,
 room_id TEXT NOT NULL,
 epoch INTEGER NOT NULL,
 client_summary_id TEXT NOT NULL,
 generation INTEGER NOT NULL DEFAULT 0 CHECK (generation>=0),
 status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled','interrupted')),
 time_limit_seconds INTEGER NOT NULL CHECK (typeof(time_limit_seconds)='integer' AND time_limit_seconds>0),
 result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
 error_code TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY (room_id,epoch) REFERENCES book_room_epochs(room_id,epoch) ON DELETE CASCADE,
 UNIQUE(room_id,epoch,client_summary_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_book_active_summary_job ON book_room_summary_jobs(room_id) WHERE status IN ('queued','running');
CREATE INDEX IF NOT EXISTS ix_book_summary_job_latest ON book_room_summary_jobs(room_id,epoch,created_at);
