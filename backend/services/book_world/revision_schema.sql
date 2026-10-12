-- T04 version heads, correction audits and reader-only extensions.
CREATE TABLE IF NOT EXISTS book_revision_heads (
 book_id TEXT NOT NULL, source_version_id TEXT NOT NULL, build_id TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1 CHECK (revision>0),
 PRIMARY KEY(book_id,source_version_id),
 FOREIGN KEY(book_id,source_version_id,build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS book_revisions (
 book_id TEXT NOT NULL, source_version_id TEXT NOT NULL, build_id TEXT NOT NULL,
 base_build_id TEXT NOT NULL, reserved_revision INTEGER NOT NULL CHECK(reserved_revision>0),
 request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 changes_json TEXT NOT NULL CHECK(json_valid(changes_json)),
 review_json TEXT NOT NULL CHECK(json_valid(review_json)),
 character_map_json TEXT NOT NULL CHECK(json_valid(character_map_json)),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(book_id,source_version_id,build_id),
 UNIQUE(book_id,source_version_id,request_id),
 FOREIGN KEY(book_id,source_version_id,build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(book_id,source_version_id,base_build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_revision_base ON book_revisions(book_id,source_version_id,base_build_id,created_at);
CREATE TABLE IF NOT EXISTS book_user_extensions (
 id TEXT PRIMARY KEY NOT NULL, book_id TEXT NOT NULL, source_version_id TEXT NOT NULL,
 build_id TEXT NOT NULL, character_id TEXT NOT NULL, text TEXT NOT NULL CHECK(length(text) BETWEEN 1 AND 4000),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(book_id,source_version_id,build_id,character_id) REFERENCES book_characters(book_id,source_version_id,build_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_book_extension_character ON book_user_extensions(book_id,source_version_id,build_id,character_id,created_at);
CREATE TRIGGER IF NOT EXISTS tr_book_revision_immutable BEFORE UPDATE ON book_revisions
BEGIN SELECT RAISE(ABORT,'immutable_revision_audit'); END;
