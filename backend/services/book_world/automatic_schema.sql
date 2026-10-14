-- T10 durable import pipeline; the library creation's metadata is its compensation source.
CREATE TABLE IF NOT EXISTS book_auto_imports (
 id TEXT PRIMARY KEY NOT NULL,
 library_item_id INTEGER UNIQUE,
 status TEXT NOT NULL CHECK (status IN ('waiting_attachment','queued','running','blocked_config','needs_ocr','failed','interrupted','cancelled','completed','partial')),
 phase TEXT NOT NULL DEFAULT 'source' CHECK (phase IN ('source','discovery','persona','expression','complete')),
 generation INTEGER NOT NULL DEFAULT 0 CHECK (generation>=0),
 book_id TEXT,
 source_version_id TEXT,
 discovery_build_id TEXT,
 persona_build_id TEXT,
 expression_sets_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(expression_sets_json)),
 strategy_json TEXT CHECK (strategy_json IS NULL OR json_valid(strategy_json)),
 actual_calls INTEGER NOT NULL DEFAULT 0 CHECK (actual_calls>=0),
 usage_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(usage_json)),
 error_code TEXT,
 error_detail TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY (library_item_id) REFERENCES library_items(id) ON DELETE SET NULL,
 FOREIGN KEY (book_id,source_version_id) REFERENCES book_source_versions(book_id,id) ON DELETE RESTRICT,
 FOREIGN KEY (book_id,source_version_id,discovery_build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
 FOREIGN KEY (book_id,source_version_id,persona_build_id) REFERENCES book_builds(book_id,source_version_id,id) ON DELETE RESTRICT,
 CHECK ((book_id IS NULL AND source_version_id IS NULL) OR (book_id IS NOT NULL AND source_version_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_book_auto_work ON book_auto_imports(status,created_at,id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_book_auto_canonical_binding ON book_auto_imports(book_id,source_version_id,persona_build_id,id);
CREATE TABLE IF NOT EXISTS book_auto_expression_tasks (
 job_id TEXT NOT NULL,book_id TEXT NOT NULL,source_version_id TEXT NOT NULL,build_id TEXT NOT NULL,character_id TEXT NOT NULL,set_id TEXT NOT NULL,
 PRIMARY KEY(job_id,character_id),
 FOREIGN KEY(book_id,source_version_id,build_id,job_id) REFERENCES book_auto_imports(book_id,source_version_id,persona_build_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(book_id,source_version_id,build_id,character_id,set_id) REFERENCES book_expression_sets(book_id,source_version_id,build_id,character_id,id) ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS tr_book_auto_binding_fixed
 BEFORE UPDATE OF book_id,source_version_id,discovery_build_id,persona_build_id,strategy_json ON book_auto_imports
 WHEN (old.book_id IS NOT NULL AND new.book_id IS NOT old.book_id)
 OR (old.source_version_id IS NOT NULL AND new.source_version_id IS NOT old.source_version_id)
 OR (old.discovery_build_id IS NOT NULL AND new.discovery_build_id IS NOT old.discovery_build_id)
 OR (old.persona_build_id IS NOT NULL AND new.persona_build_id IS NOT old.persona_build_id)
 OR (old.strategy_json IS NOT NULL AND new.strategy_json IS NOT old.strategy_json)
 BEGIN SELECT RAISE(ABORT,'immutable_auto_import_binding'); END;
