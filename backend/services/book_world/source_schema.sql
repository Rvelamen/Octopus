CREATE TABLE IF NOT EXISTS book_books (
    id TEXT PRIMARY KEY NOT NULL,
    library_item_id INTEGER UNIQUE,
    title_snapshot TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active','purging','removed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    removed_at TEXT,
    FOREIGN KEY (library_item_id) REFERENCES library_items(id) ON DELETE SET NULL,
    CHECK (lifecycle_state <> 'active' OR library_item_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS book_source_versions (
    id TEXT PRIMARY KEY NOT NULL,
    book_id TEXT NOT NULL,
    attachment_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    canonical_text_sha256 TEXT NOT NULL,
    asset_rel_path TEXT,
    text_rel_path TEXT,
    format TEXT NOT NULL CHECK (format IN ('pdf','epub','txt')),
    lifecycle_state TEXT NOT NULL DEFAULT 'available' CHECK (lifecycle_state IN ('available','unavailable','purged')),
    quality_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(quality_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY (book_id) REFERENCES book_books(id) ON DELETE RESTRICT,
    UNIQUE (book_id,id),
    UNIQUE (book_id,attachment_sha256,parser_version,canonical_text_sha256)
);
CREATE TABLE IF NOT EXISTS book_segments (
    id TEXT PRIMARY KEY NOT NULL,
    book_id TEXT NOT NULL,
    source_version_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal>=0),
    page INTEGER CHECK (page IS NULL OR page>0),
    chapter TEXT,
    start_offset INTEGER NOT NULL CHECK (start_offset>=0),
    end_offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    FOREIGN KEY (book_id,source_version_id) REFERENCES book_source_versions(book_id,id) ON DELETE RESTRICT,
    UNIQUE (book_id,source_version_id,id),
    UNIQUE (book_id,source_version_id,ordinal),
    CHECK (end_offset>start_offset AND end_offset-start_offset=length(text))
);
CREATE INDEX IF NOT EXISTS ix_book_segments_page ON book_segments(book_id,source_version_id,page,ordinal);
CREATE TRIGGER IF NOT EXISTS tr_book_source_identity BEFORE UPDATE OF book_id,attachment_sha256,parser_version,canonical_text_sha256 ON book_source_versions
WHEN NEW.book_id IS NOT OLD.book_id OR NEW.attachment_sha256 IS NOT OLD.attachment_sha256 OR NEW.parser_version IS NOT OLD.parser_version OR NEW.canonical_text_sha256 IS NOT OLD.canonical_text_sha256
BEGIN SELECT RAISE(ABORT,'immutable_source_version'); END;
CREATE TRIGGER IF NOT EXISTS tr_book_segment_immutable BEFORE UPDATE ON book_segments
BEGIN SELECT RAISE(ABORT,'immutable_source_segment'); END;
