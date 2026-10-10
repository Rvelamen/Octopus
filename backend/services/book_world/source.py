"""Prepare immutable narrative versions without using the legacy limited chunks."""

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.services.knowledge_migrations import run_knowledge_index_migrations

from .pdf_source import parse_pdf, sha256_file
from .storage import connect

PARSER_VERSION = "narrative-pdf-lines-v1"


class BookWorldError(ValueError):
    """An actionable domain failure safe to return to the desktop client."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


class BookSourceService:
    """Source operations bound to one immutable, server-selected workspace root."""

    def __init__(self, workspace_root: str | Path):
        self.root = Path(workspace_root).resolve()
        self.db_path = self.root / "knowledge" / ".knowledge_index.db"
        run_knowledge_index_migrations(self.db_path)

    def _path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise BookWorldError("invalid_source_path", "Source must belong to this workspace")
        return path

    def _item(self, db: sqlite3.Connection, item_id: int) -> sqlite3.Row:
        row = db.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise BookWorldError("item_not_found", "Library item no longer exists")
        return row

    def _source(self, db: sqlite3.Connection, item_id: int, version: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT s.* FROM book_source_versions s JOIN book_books b ON b.id=s.book_id "
            "WHERE b.library_item_id=? AND s.id=? AND b.lifecycle_state='active' "
            "AND s.lifecycle_state='available'",
            (item_id, version),
        ).fetchone()
        if row is None:
            raise BookWorldError("source_removed", "Source is unavailable for this item")
        return row

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> dict[str, Any]:
        quality = json.loads(row["quality_json"])
        return {
            "book_id": row["book_id"],
            "source_version_id": row["id"],
            "status": quality["status"],
            "quality": quality,
            "segment_count": quality["segment_count"],
            "parser_version": row["parser_version"],
        }

    def _verify_snapshot(self, row: sqlite3.Row) -> None:
        quality = json.loads(row["quality_json"])
        expected = (
            (row["asset_rel_path"], row["attachment_sha256"]),
            (row["text_rel_path"], row["canonical_text_sha256"]),
            (quality["locator_path"], quality["locator_sha256"]),
        )
        for relative, digest in expected:
            path = self._path(relative)
            if not path.is_file() or sha256_file(path) != digest:
                raise BookWorldError(
                    "source_changed", "The original source snapshot is missing or changed"
                )

    def get_source(self, item_id: int, source_version_id: str | None = None) -> dict[str, Any]:
        """Return a prepared version or an explicit not-prepared state."""
        with connect(self.db_path) as db:
            item = self._item(db, item_id)
            if source_version_id:
                return self._snapshot(self._source(db, item_id, source_version_id))
            row = db.execute(
                "SELECT s.* FROM book_source_versions s JOIN book_books b ON b.id=s.book_id "
                "WHERE b.library_item_id=? AND b.lifecycle_state='active' AND s.lifecycle_state='available' "
                "AND s.attachment_sha256=? AND s.parser_version=? "
                "ORDER BY s.created_at DESC,s.rowid DESC LIMIT 1",
                (item_id, item["pdf_sha256"], PARSER_VERSION),
            ).fetchone()
            return self._snapshot(row) if row else {"status": "not_prepared", "quality": {}}

    def prepare_source(
        self, item_id: int, *, expected_attachment_sha256: str | None = None
    ) -> dict[str, Any]:
        """Snapshot the ready PDF and atomically publish all narrative segments."""
        with connect(self.db_path) as db:
            item = self._item(db, item_id)
            if not item["library_path"] or not item["pdf_sha256"]:
                raise BookWorldError("source_not_ready", "Wait for the PDF attachment to be ready")
            folder = self._path(item["library_path"])
            pdf = self._path(str(folder / "main.pdf"))
            if not pdf.is_file():
                raise BookWorldError("source_not_ready", "The PDF attachment is missing")
            digest = sha256_file(pdf)
            if digest != item["pdf_sha256"] or (
                expected_attachment_sha256 and digest != expected_attachment_sha256
            ):
                raise BookWorldError(
                    "source_changed", "Attachment hash changed; re-import or retry after indexing"
                )
            cached = db.execute(
                "SELECT s.* FROM book_source_versions s JOIN book_books b ON b.id=s.book_id "
                "WHERE b.library_item_id=? AND b.lifecycle_state='active' AND s.lifecycle_state='available' "
                "AND s.attachment_sha256=? AND s.parser_version=? LIMIT 1",
                (item_id, digest, PARSER_VERSION),
            ).fetchone()
            if cached:
                self._verify_snapshot(cached)
                return self._snapshot(cached)
        version_id = str(uuid4())
        version_dir = folder / "narrative" / version_id
        version_dir.mkdir(parents=True, exist_ok=False)
        asset = version_dir / "main.pdf"
        text_file = version_dir / "canonical.txt"
        locator_file = version_dir / "locators.json"
        try:
            shutil.copyfile(pdf, asset)
            if sha256_file(asset) != digest:
                raise BookWorldError(
                    "source_changed", "Attachment changed while preparing its snapshot"
                )
            parsed = parse_pdf(asset)
            text_file.write_text(parsed.text, encoding="utf-8", newline="")
            locator_file.write_text(
                json.dumps(parsed.page_locators, ensure_ascii=False), encoding="utf-8"
            )
            text_digest = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
            quality = {
                **parsed.quality,
                "locator_path": locator_file.relative_to(self.root).as_posix(),
                "locator_sha256": sha256_file(locator_file),
            }
            with connect(self.db_path) as db:
                db.execute("BEGIN IMMEDIATE")
                current = self._item(db, item_id)
                if current["pdf_sha256"] != digest:
                    raise BookWorldError(
                        "source_changed", "The attachment was replaced during preparation"
                    )
                book = db.execute(
                    "SELECT * FROM book_books WHERE library_item_id=?", (item_id,)
                ).fetchone()
                if book and book["lifecycle_state"] != "active":
                    raise BookWorldError("source_removed", "Deletion is in progress")
                book_id = book["id"] if book else str(uuid4())
                if book is None:
                    db.execute(
                        "INSERT INTO book_books(id,library_item_id,title_snapshot) VALUES (?,?,?)",
                        (book_id, item_id, current["title"] or "Untitled"),
                    )
                cached = db.execute(
                    "SELECT * FROM book_source_versions WHERE book_id=? AND attachment_sha256=? "
                    "AND parser_version=? AND canonical_text_sha256=? AND lifecycle_state='available'",
                    (book_id, digest, PARSER_VERSION, text_digest),
                ).fetchone()
                if cached:
                    self._verify_snapshot(cached)
                    result = self._snapshot(cached)
                else:
                    db.execute(
                        "INSERT INTO book_source_versions(id,book_id,attachment_sha256,parser_version,canonical_text_sha256,"
                        "asset_rel_path,text_rel_path,format,quality_json) VALUES (?,?,?,?,?,?,?,'pdf',?)",
                        (
                            version_id,
                            book_id,
                            digest,
                            PARSER_VERSION,
                            text_digest,
                            asset.relative_to(self.root).as_posix(),
                            text_file.relative_to(self.root).as_posix(),
                            json.dumps(quality, ensure_ascii=False),
                        ),
                    )
                    db.executemany(
                        "INSERT INTO book_segments(id,book_id,source_version_id,ordinal,page,chapter,start_offset,end_offset,text,text_sha256) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [
                            (
                                str(uuid4()),
                                book_id,
                                version_id,
                                s["ordinal"],
                                s["page"],
                                s["chapter"],
                                s["start_offset"],
                                s["end_offset"],
                                s["text"],
                                s["text_sha256"],
                            )
                            for s in parsed.segments
                        ],
                    )
                    result = self._snapshot(self._source(db, item_id, version_id))
            if cached:
                self._discard(version_dir)
            return result
        except Exception:
            self._discard(version_dir)
            raise

    @staticmethod
    def _discard(folder: Path) -> None:
        for name in ("main.pdf", "canonical.txt", "locators.json"):
            (folder / name).unlink(missing_ok=True)
        if folder.exists():
            folder.rmdir()

    def list_segments(
        self, item_id: int, source_version_id: str, after_ordinal: int = -1, limit: int = 50
    ) -> dict[str, Any]:
        """Page through a source without a hidden first-100-segment cap."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise BookWorldError("invalid_request", "Segment page size must be between 1 and 200")
        if (
            isinstance(after_ordinal, bool)
            or not isinstance(after_ordinal, int)
            or after_ordinal < -1
        ):
            raise BookWorldError("invalid_request", "Invalid segment cursor")
        with connect(self.db_path) as db:
            source = self._source(db, item_id, source_version_id)
            rows = db.execute(
                "SELECT * FROM book_segments WHERE book_id=? AND source_version_id=? AND ordinal>? "
                "ORDER BY ordinal LIMIT ?",
                (source["book_id"], source_version_id, after_ordinal, limit + 1),
            ).fetchall()
            return {
                "segments": [dict(row) for row in rows[:limit]],
                "next_ordinal": rows[limit - 1]["ordinal"] if len(rows) > limit else None,
            }

    def resolve_evidence(
        self,
        item_id: int,
        source_version_id: str,
        segment_id: str,
        local_start: int = 0,
        local_end: int | None = None,
    ) -> dict[str, Any]:
        """Resolve a Unicode-codepoint span against the immutable PDF snapshot."""
        with connect(self.db_path) as db:
            source = self._source(db, item_id, source_version_id)
            row = db.execute(
                "SELECT * FROM book_segments WHERE id=? AND book_id=? AND source_version_id=?",
                (segment_id, source["book_id"], source_version_id),
            ).fetchone()
            if row is None:
                raise BookWorldError("invalid_evidence", "Segment does not belong to this source")
            end = len(row["text"]) if local_end is None else local_end
            if any(
                isinstance(v, bool) or not isinstance(v, int) for v in (local_start, end)
            ) or not 0 <= local_start < end <= len(row["text"]):
                raise BookWorldError("invalid_evidence", "Invalid Unicode span")
            self._verify_snapshot(source)
            quality = json.loads(source["quality_json"])
            locators = json.loads(self._path(quality["locator_path"]).read_text(encoding="utf-8"))
            locator = locators[row["ordinal"]]
            if locator["page_text"] != row["text"] or locator["page"] != row["page"]:
                raise BookWorldError(
                    "invalid_evidence", "The page locator does not match this segment"
                )
            return {
                "book_id": source["book_id"],
                "source_version_id": source_version_id,
                "segment_id": segment_id,
                "page": row["page"],
                "chapter": row["chapter"],
                "quote": row["text"][local_start:end],
                "start_offset": row["start_offset"] + local_start,
                "end_offset": row["start_offset"] + end,
                "asset_path": source["asset_rel_path"],
                "page_start": locator["page_start"] + local_start,
                "page_end": locator["page_start"] + end,
            }
