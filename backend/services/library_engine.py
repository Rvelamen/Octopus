"""Library engine for Zotero-style academic paper management.

Manages library_items, collections, attachments, and FTS5 indexing
within the workspace/knowledge/library/ directory.
"""

import contextlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger


class LibraryEngine:
    """Library engine - per-workspace singleton for paper management."""

    _instances: dict[str, "LibraryEngine"] = {}

    def __new__(cls, workspace_root: str) -> "LibraryEngine":
        key = str(Path(workspace_root).resolve())
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, workspace_root: str) -> None:
        key = str(Path(workspace_root).resolve())
        if getattr(self, "_engine_key", None) == key:
            return
        self._engine_key = key

        self.workspace_root = Path(workspace_root).resolve()
        self.knowledge_dir = self.workspace_root / "knowledge"
        self.library_dir = self.knowledge_dir / "library"
        self.library_dir.mkdir(parents=True, exist_ok=True)

        # Database is shared with KnowledgeGraphEngine
        self.db_path = self.knowledge_dir / ".knowledge_index.db"
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_pragmas()

    def _init_pragmas(self) -> None:
        pragmas = [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA foreign_keys = ON;",
            "PRAGMA busy_timeout = 5000;",
        ]
        for pragma in pragmas:
            self.db.execute(pragma)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_slug(self, title: str) -> str:
        """Generate a URL-safe slug from paper title."""
        slug = re.sub(r"[^\w\s-]", "", title or "untitled")
        slug = re.sub(r"[-\s]+", "_", slug).strip("_")
        return slug[:50] if slug else "untitled"

    def _ensure_unique_citekey(
        self, citekey: str | None, exclude_item_id: int | None = None
    ) -> str | None:
        """Ensure citekey is unique by appending _2, _3, etc. if needed."""
        if not citekey:
            return None
        query = "SELECT id FROM library_items WHERE citekey = ?"
        params: list[Any] = [citekey]
        if exclude_item_id is not None:
            query += " AND id != ?"
            params.append(exclude_item_id)
        row = self.db.execute(query, params).fetchone()
        if not row:
            return citekey
        base = citekey
        counter = 2
        while True:
            new_citekey = f"{base}_{counter}"
            row = self.db.execute(
                "SELECT id FROM library_items WHERE citekey = ?", (new_citekey,)
            ).fetchone()
            if not row:
                return new_citekey
            counter += 1

    def _make_item_dir(self, item_id: int, title: str) -> Path:
        """Create and return the item directory path."""
        slug = self._generate_slug(title)
        dirname = f"{item_id:05d}_{slug}"
        item_dir = self.library_dir / dirname
        item_dir.mkdir(parents=True, exist_ok=True)
        return item_dir

    def _item_dir(self, item_id: int) -> Path | None:
        """Find existing item directory by item_id."""
        for entry in self.library_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(f"{item_id:05d}_"):
                return entry
        return None

    def _write_metadata_yaml(self, item_dir: Path, metadata: dict) -> None:
        """Write metadata.yaml for Obsidian compatibility."""
        yaml_path = item_dir / "metadata.yaml"
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for v in value:
                    lines.append(f"  - {v}")
            elif isinstance(value, str) and "\n" in value:
                lines.append(f"{key}: |")
                for line in value.split("\n"):
                    lines.append(f"  {line}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        yaml_path.write_text("\n".join(lines), encoding="utf-8")

    def _write_octopus_meta(self, item_dir: Path, item_id: int, meta: dict) -> None:
        """Write .octopus_meta.json for internal tracking."""
        meta_path = item_dir / ".octopus_meta.json"
        meta_path.write_text(json.dumps({"item_id": item_id, **meta}, indent=2), encoding="utf-8")

    def _compute_sha256(self, file_path: Path) -> str:
        import hashlib

        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def _extract_title_from_pdf(self, pdf_path: Path) -> str:
        """Heuristic title extraction from first page of PDF."""
        try:
            import fitz

            doc = fitz.open(str(pdf_path))
            if len(doc) == 0:
                doc.close()
                return pdf_path.stem
            page = doc[0]
            text = page.get_text()
            doc.close()

            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if not lines:
                return pdf_path.stem

            # Filter out common header/footer patterns
            candidates = []
            for line in lines[:30]:  # Only look at first 30 lines
                # Skip lines that look like headers/footers/page numbers
                if re.match(r"^\d+$", line):
                    continue
                if re.match(
                    r"^(arXiv:|doi:|http|www\.|©|Copyright|Received|Accepted|Published)", line, re.I
                ):
                    continue
                if len(line) < 10:
                    continue
                candidates.append(line)

            if candidates:
                # Title is usually the longest line near the top
                return max(candidates, key=len)
            return lines[0] if lines else pdf_path.stem
        except Exception:
            return pdf_path.stem

    def _try_parse_arxiv_from_filename(self, filename: str) -> str | None:
        """Extract arXiv ID from filename like '2511.04550v1.pdf' or '_tmp_xxx_2511.04550v1.pdf'."""
        m = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", filename)
        if m:
            return m.group(1)
        return None

    def create_item(
        self,
        pdf_path: Path | None = None,
        metadata: dict | None = None,
        collection_ids: list[int] | None = None,
    ) -> dict:
        """Create a new library item from an optional PDF file.

        This is a lightweight synchronous method: it only creates the DB record
        and directory. All heavy PDF processing (copy, hash, chunk extraction)
        should be done in the background via _process_pdf_background().
        """
        metadata = metadata or {}
        title = metadata.get("title")
        if not title:
            title = pdf_path.stem if pdf_path else "untitled"

        # Ensure citekey is unique before inserting
        citekey = self._ensure_unique_citekey(metadata.get("citekey"))
        if citekey != metadata.get("citekey"):
            metadata = {**metadata, "citekey": citekey}

        # Determine chunk_status based on whether PDF is present
        chunk_status = "pending" if (pdf_path and pdf_path.exists()) else None

        # Insert DB record first to get item_id
        cursor = self.db.execute(
            """
            INSERT INTO library_items (citekey, item_type, title, authors_json, year, venue, doi, url, abstract, tags_json, metadata_json, pdf_sha256, chunk_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citekey,
                metadata.get("item_type", "journalArticle"),
                title,
                json.dumps(metadata.get("authors", [])) if metadata.get("authors") else None,
                metadata.get("year"),
                metadata.get("venue"),
                metadata.get("doi"),
                metadata.get("url"),
                metadata.get("abstract"),
                json.dumps(metadata.get("tags", [])) if metadata.get("tags") else None,
                json.dumps(metadata) if metadata else None,
                None,
                chunk_status,
            ),
        )
        item_id = cursor.lastrowid

        # Create directory
        item_dir = self._make_item_dir(item_id, title)
        library_path = str(item_dir.relative_to(self.workspace_root))

        # Create notes subdirectory for AI-generated notes
        (item_dir / "notes").mkdir(exist_ok=True)

        # Write metadata files (lightweight, no PDF reading)
        self.db.execute(
            "UPDATE library_items SET library_path = ? WHERE id = ?",
            (library_path, item_id),
        )
        self._write_octopus_meta(item_dir, item_id, metadata)
        self._write_metadata_yaml(item_dir, metadata)

        # Add to collections — filter out non-existent collections to avoid FK errors
        valid_collection_ids = []
        if collection_ids:
            placeholders = ",".join("?" * len(collection_ids))
            existing = self.db.execute(
                f"SELECT id FROM library_collections WHERE id IN ({placeholders})",
                tuple(collection_ids),
            ).fetchall()
            valid_collection_ids = [r["id"] for r in existing]

        if valid_collection_ids:
            for cid in valid_collection_ids:
                self.db.execute(
                    "INSERT OR IGNORE INTO library_collection_items (collection_id, item_id) VALUES (?, ?)",
                    (cid, item_id),
                )
        else:
            # Default to Uncategorized
            self.db.execute(
                "INSERT OR IGNORE INTO library_collection_items (collection_id, item_id) VALUES (?, ?)",
                (2, item_id),
            )

        self.db.commit()
        return self.get_item(item_id)

    def _process_pdf_background(
        self,
        item_id: int,
        pdf_temp_path: Path,
    ) -> None:
        """Process a PDF file in the background: copy, hash, extract title, write metadata, record attachment, then extract chunks.

        This runs in a background thread so the frontend never waits for large file operations.
        """
        try:
            item = self.get_item(item_id)
            if not item:
                logger.warning(f"Background PDF processing: item {item_id} not found")
                return

            item_dir = self._item_dir(item_id)
            if not item_dir:
                logger.warning(f"Background PDF processing: item dir not found for {item_id}")
                self._set_chunk_status(item_id, "failed")
                return

            main_pdf = item_dir / "main.pdf"

            # Copy PDF from temp location
            if pdf_temp_path.exists():
                import shutil

                shutil.copy2(pdf_temp_path, main_pdf)
                # Clean up temp file
                with contextlib.suppress(Exception):
                    pdf_temp_path.unlink()
            elif not main_pdf.exists():
                logger.warning(f"Background PDF processing: temp PDF not found for item {item_id}")
                self._set_chunk_status(item_id, "failed")
                return

            # Compute sha256
            pdf_sha256 = self._compute_sha256(main_pdf)

            # Extract title from PDF if not already set (or was just the stem)
            title = item.get("title") or ""
            if not title or title == "untitled" or title == main_pdf.stem:
                extracted_title = self._extract_title_from_pdf(main_pdf)
                if extracted_title and extracted_title != main_pdf.stem:
                    title = extracted_title
                    self.db.execute(
                        "UPDATE library_items SET title = ? WHERE id = ?",
                        (title, item_id),
                    )

            # Write metadata files
            metadata = json.loads(item.get("metadata_json") or "{}")
            self._write_octopus_meta(item_dir, item_id, metadata)
            self._write_metadata_yaml(item_dir, metadata)

            # Record attachment
            self.db.execute(
                "INSERT INTO library_attachments (item_id, filename, file_type, sha256, rel_path, size) VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, "main.pdf", "pdf", pdf_sha256, "main.pdf", main_pdf.stat().st_size),
            )

            # Update DB with sha256
            self.db.execute(
                "UPDATE library_items SET pdf_sha256 = ? WHERE id = ?",
                (pdf_sha256, item_id),
            )
            self.db.commit()

            # Extract chunks (this updates chunk_status internally)
            self.extract_pdf_chunks(item_id)

            logger.info(f"Background PDF processing complete for item {item_id}")

        except Exception as e:
            logger.error(f"Background PDF processing failed for item {item_id}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            self._set_chunk_status(item_id, "failed")
            self.db.commit()

    def get_item(self, item_id: int) -> dict:
        """Get item details with attachments and linked notes."""
        row = self.db.execute(
            """
            SELECT id, citekey, item_type, title, authors_json, year, venue, doi, url, abstract, tags_json,
                   metadata_json, library_path, pdf_sha256, chunk_status, created_at, updated_at
            FROM library_items WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        if not row:
            raise ValueError(f"Library item {item_id} not found")

        # Attachments
        attachments = [
            dict(r)
            for r in self.db.execute(
                "SELECT id, filename, file_type, sha256, rel_path, size, created_at FROM library_attachments WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        ]

        # Linked notes
        linked_notes = [
            dict(r)
            for r in self.db.execute(
                "SELECT id, note_path, relation, created_at FROM library_item_notes WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        ]

        # Collections
        collections = [
            dict(r)
            for r in self.db.execute(
                """
                SELECT c.id, c.name, c.color
                FROM library_collections c
                JOIN library_collection_items ci ON c.id = ci.collection_id
                WHERE ci.item_id = ?
                """,
                (item_id,),
            ).fetchall()
        ]

        return {
            "id": row["id"],
            "citekey": row["citekey"],
            "item_type": row["item_type"],
            "title": row["title"],
            "authors": json.loads(row["authors_json"]) if row["authors_json"] else [],
            "year": row["year"],
            "venue": row["venue"],
            "doi": row["doi"],
            "url": row["url"],
            "abstract": row["abstract"],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
            "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            "library_path": row["library_path"],
            "pdf_sha256": row["pdf_sha256"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "attachments": attachments,
            "linked_notes": linked_notes,
            "collections": collections,
        }

    def update_metadata(self, item_id: int, metadata: dict) -> dict:
        """Update item metadata and rewrite metadata.yaml."""
        item = self.get_item(item_id)
        if not item:
            raise ValueError(f"Library item {item_id} not found")

        title = metadata.get("title", item["title"])
        citekey = self._ensure_unique_citekey(
            metadata.get("citekey", item["citekey"]), exclude_item_id=item_id
        )
        self.db.execute(
            """
            UPDATE library_items
            SET citekey = ?, item_type = ?, title = ?, authors_json = ?, year = ?, venue = ?,
                doi = ?, url = ?, abstract = ?, tags_json = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                citekey,
                metadata.get("item_type", item["item_type"]),
                title,
                json.dumps(metadata.get("authors", item["authors"])),
                metadata.get("year", item["year"]),
                metadata.get("venue", item["venue"]),
                metadata.get("doi", item["doi"]),
                metadata.get("url", item["url"]),
                metadata.get("abstract", item["abstract"]),
                json.dumps(metadata.get("tags", item["tags"])),
                json.dumps(metadata),
                datetime.now().isoformat(),
                item_id,
            ),
        )
        self.db.commit()

        # Rewrite metadata files
        item_dir = self._item_dir(item_id)
        if item_dir:
            self._write_octopus_meta(item_dir, item_id, metadata)
            self._write_metadata_yaml(item_dir, metadata)

        return self.get_item(item_id)

    def delete_item(self, item_id: int) -> bool:
        """Delete item, its directory, and related knowledge graph nodes."""
        # Get library_path before deleting the DB record
        row = self.db.execute(
            "SELECT library_path FROM library_items WHERE id = ?", (item_id,)
        ).fetchone()
        library_path = row["library_path"] if row else None

        item_dir = self._item_dir(item_id)
        if item_dir and item_dir.exists():
            import shutil

            shutil.rmtree(item_dir)

        self.db.execute("DELETE FROM library_items WHERE id = ?", (item_id,))

        # Clean up library note index for this item's notes
        if library_path:
            prefix = f"{library_path}/%"
            self.db.execute("DELETE FROM library_notes WHERE path LIKE ?", (prefix,))
            # Also clean up legacy knowledge_nodes entries (migration safety)
            self.db.execute("DELETE FROM knowledge_nodes WHERE path LIKE ?", (prefix,))

        self.db.commit()
        return True

    def delete_items(self, item_ids: list[int]) -> dict:
        """Delete multiple items. Returns success/fail counts."""
        success = 0
        fail = 0
        for item_id in item_ids:
            try:
                self.delete_item(item_id)
                success += 1
            except Exception:
                fail += 1
        return {"success": success, "fail": fail}

    def list_items(
        self,
        collection_id: int | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List items with optional collection filter and FTS search."""
        if query and query.strip():
            # FTS search
            fts_rows = self.db.execute(
                "SELECT rowid FROM library_fts WHERE library_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
                (query.strip(), limit, offset),
            ).fetchall()
            item_ids = [r["rowid"] for r in fts_rows]
            if not item_ids:
                return [], 0
            placeholders = ",".join("?" * len(item_ids))
            rows = self.db.execute(
                f"""
                SELECT id, citekey, title, authors_json, year, venue, doi, url, abstract, tags_json,
                       library_path, pdf_sha256, chunk_status, created_at
                FROM library_items WHERE id IN ({placeholders}) ORDER BY year DESC NULLS LAST
                """,
                item_ids,
            ).fetchall()
            total = self.db.execute(
                "SELECT COUNT(*) FROM library_fts WHERE library_fts MATCH ?",
                (query.strip(),),
            ).fetchone()[0]
        elif collection_id:
            rows = self.db.execute(
                """
                SELECT i.id, i.citekey, i.title, i.authors_json, i.year, i.venue, i.doi, i.url, i.abstract, i.tags_json,
                       i.library_path, i.pdf_sha256, i.chunk_status, i.created_at
                FROM library_items i
                JOIN library_collection_items ci ON i.id = ci.item_id
                WHERE ci.collection_id = ?
                ORDER BY i.year DESC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                (collection_id, limit, offset),
            ).fetchall()
            total = self.db.execute(
                "SELECT COUNT(*) FROM library_collection_items WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()[0]
        else:
            rows = self.db.execute(
                """
                SELECT id, citekey, title, authors_json, year, venue, doi, url, abstract, tags_json,
                       library_path, pdf_sha256, chunk_status, created_at
                FROM library_items
                ORDER BY year DESC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            total = self.db.execute("SELECT COUNT(*) FROM library_items").fetchone()[0]

        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "citekey": row["citekey"],
                    "title": row["title"],
                    "authors": json.loads(row["authors_json"]) if row["authors_json"] else [],
                    "year": row["year"],
                    "venue": row["venue"],
                    "doi": row["doi"],
                    "url": row["url"],
                    "abstract": row["abstract"],
                    "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
                    "library_path": row["library_path"],
                    "pdf_sha256": row["pdf_sha256"],
                    "chunk_status": row["chunk_status"],
                    "created_at": row["created_at"],
                }
            )

        # Check for AI-generated notes in each item's notes/ directory
        for item in items:
            if item["library_path"]:
                notes_dir = self.workspace_root / item["library_path"] / "notes"
                item["has_notes"] = any(notes_dir.glob("*.md")) if notes_dir.exists() else False
            else:
                item["has_notes"] = False

        return items, total

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(
        self, name: str, parent_id: int | None = None, color: str | None = None
    ) -> dict:
        cursor = self.db.execute(
            "INSERT INTO library_collections (name, parent_id, color) VALUES (?, ?, ?)",
            (name, parent_id, color or "#1890ff"),
        )
        self.db.commit()
        return {
            "id": cursor.lastrowid,
            "name": name,
            "parent_id": parent_id,
            "color": color or "#1890ff",
        }

    def update_collection(
        self, collection_id: int, name: str | None = None, color: str | None = None
    ) -> dict:
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if not updates:
            return self.get_collection(collection_id)
        params.append(collection_id)
        self.db.execute(f"UPDATE library_collections SET {', '.join(updates)} WHERE id = ?", params)
        self.db.commit()
        return self.get_collection(collection_id)

    def delete_collection(self, collection_id: int) -> bool:
        self.db.execute("DELETE FROM library_collections WHERE id = ?", (collection_id,))
        self.db.commit()
        return True

    def move_collection(self, collection_id: int, new_parent_id: int | None) -> dict:
        self.db.execute(
            "UPDATE library_collections SET parent_id = ? WHERE id = ?",
            (new_parent_id, collection_id),
        )
        self.db.commit()
        return self.get_collection(collection_id)

    def get_collection(self, collection_id: int) -> dict:
        row = self.db.execute(
            "SELECT id, name, parent_id, color, sort_order, is_smart, search_query, created_at FROM library_collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Collection {collection_id} not found")
        return dict(row)

    def list_collections(self, flat: bool = False) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, name, parent_id, color, sort_order, is_smart, search_query, created_at FROM library_collections ORDER BY sort_order, name"
        ).fetchall()

        if flat:
            return [dict(r) for r in rows]

        # Build nested tree
        nodes = {r["id"]: {**dict(r), "children": [], "count": 0} for r in rows}
        roots = []
        for r in rows:
            node = nodes[r["id"]]
            if r["parent_id"] and r["parent_id"] in nodes:
                nodes[r["parent_id"]]["children"].append(node)
            else:
                roots.append(node)

        # Populate counts
        for node in nodes.values():
            node["count"] = self.db.execute(
                "SELECT COUNT(*) FROM library_collection_items WHERE collection_id = ?",
                (node["id"],),
            ).fetchone()[0]

        return roots

    def add_to_collection(self, item_id: int, collection_id: int) -> bool:
        """Move item to a user collection.

        Removes the item from all other user collections (id > 2) and from
        Uncategorized (id = 2), then adds to the target collection.
        """
        # Moving to a user collection: clean up previous user collection memberships
        if collection_id > 2:
            self.db.execute(
                "DELETE FROM library_collection_items WHERE item_id = ? AND collection_id > 2",
                (item_id,),
            )
            self.db.execute(
                "DELETE FROM library_collection_items WHERE item_id = ? AND collection_id = 2",
                (item_id,),
            )

        self.db.execute(
            "INSERT OR IGNORE INTO library_collection_items (collection_id, item_id) VALUES (?, ?)",
            (collection_id, item_id),
        )
        self.db.commit()
        return True

    def remove_from_collection(self, item_id: int, collection_id: int) -> bool:
        self.db.execute(
            "DELETE FROM library_collection_items WHERE collection_id = ? AND item_id = ?",
            (collection_id, item_id),
        )
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # AI metadata extraction
    # ------------------------------------------------------------------

    async def ai_extract_metadata(self, item_id: int) -> dict:
        """Use LLM to extract metadata from PDF text."""
        item = self.get_item(item_id)
        item_dir = self._item_dir(item_id)
        if not item_dir:
            raise ValueError(f"Item directory not found for {item_id}")

        main_pdf = item_dir / "main.pdf"
        if not main_pdf.exists():
            raise ValueError(f"PDF not found for item {item_id}")

        # Extract text from first 3 pages
        try:
            import fitz

            doc = fitz.open(str(main_pdf))
            text_pages = []
            for i in range(min(3, len(doc))):
                text_pages.append(doc[i].get_text())
            doc.close()
            pdf_text = "\n\n".join(text_pages)
        except Exception as e:
            raise ValueError(f"Failed to extract PDF text: {e}") from e

        if not pdf_text.strip():
            raise ValueError("PDF contains no extractable text")

        # Truncate if too long
        max_chars = 8000
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "\n...[truncated]"

        from backend.data.database import Database
        from backend.data.provider_store import (
            AgentDefaultsRepository,
            ModelRepository,
            ProviderRepository,
        )
        from backend.services.llm_service import LLMService

        # Load library extract provider/model/language from agent defaults
        db = Database()
        agent_repo = AgentDefaultsRepository(db)
        provider_repo = ProviderRepository(db)
        model_repo = ModelRepository(db)

        defaults = agent_repo.get_or_create_defaults()

        # Get language setting
        extract_language = getattr(defaults, "library_extract_language", "English") or "English"

        prompt = f"""You are an expert academic librarian. Extract bibliographic metadata from the following academic paper text.

Instructions:
1. Identify the paper title, authors, publication year, venue/journal, DOI, URL, abstract, and subject tags.
2. Return ONLY a valid JSON object with no markdown formatting, no explanations.
3. For the "abstract" field, write it in {extract_language}.
4. For "authors", keep the original names as they appear in the paper (do not translate).
5. For "tags", keep the original terms as they appear in the paper (do not translate).
6. For all other fields (title, venue, doi, url), keep the original text as it appears in the paper (do not translate).
7. If a field cannot be found, use null or an empty array.

Required JSON structure:
{{
  "title": "string or null",
  "authors": ["Author One", "Author Two"],
  "year": integer or null,
  "venue": "string or null",
  "doi": "string or null",
  "url": "string or null",
  "abstract": "string or null",
  "tags": ["tag1", "tag2"]
}}

--- PDF TEXT ---
{pdf_text}
--- END PDF TEXT ---

JSON output:"""
        provider_id = None
        model_id = None
        provider_name = None

        if defaults.library_extract_provider_id and defaults.library_extract_model_id:
            provider = provider_repo.get_provider_by_id(defaults.library_extract_provider_id)
            model = model_repo.get_model_by_id(defaults.library_extract_model_id)
            if provider and model and provider.api_key:
                provider_id = provider.name
                model_id = model.model_id
                provider_name = provider.name

        # Fallback to default provider/model if library extract not configured
        if not provider_id or not model_id:
            if defaults.default_provider_id and defaults.default_model_id:
                provider = provider_repo.get_provider_by_id(defaults.default_provider_id)
                model = model_repo.get_model_by_id(defaults.default_model_id)
                if provider and model and provider.api_key:
                    provider_id = provider.name
                    model_id = model.model_id
                    provider_name = provider.name

        # Final fallback to config file
        if not provider_id or not model_id:
            from backend.core.config.loader import load_config

            config = load_config()
            config_defaults = config.agents.defaults if config.agents else None
            model_id = config_defaults.model if config_defaults else "anthropic/claude-opus-4-5"

        llm = LLMService()
        response = await llm.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
            provider_id=provider_name,
        )

        content = response.get("content", "")
        # Try to extract JSON from response
        extracted = {}
        try:
            # Find JSON block
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            extracted = json.loads(json_match.group(0)) if json_match else json.loads(content)
        except json.JSONDecodeError as e:
            # Try to fix truncated JSON by adding missing closing brackets/quotes
            fixed_content = content
            # Balance braces
            open_braces = fixed_content.count("{") - fixed_content.count("}")
            fixed_content += "}" * open_braces
            # Balance brackets
            open_brackets = fixed_content.count("[") - fixed_content.count("]")
            fixed_content += "]" * open_brackets
            # Fix unterminated strings: find last unmatched quote
            # Simple heuristic: if content ends mid-string, try to close it
            if fixed_content.count('"') % 2 == 1:
                # Find last quote position and check if it's an open string
                last_quote = fixed_content.rfind('"')
                if last_quote != -1:
                    # Check if this quote is escaped
                    escaped = False
                    i = last_quote - 1
                    while i >= 0 and fixed_content[i] == "\\":
                        escaped = not escaped
                        i -= 1
                    if not escaped:
                        fixed_content += '"'
            try:
                json_match = re.search(r"\{.*\}", fixed_content, re.DOTALL)
                if json_match:
                    extracted = json.loads(json_match.group(0))
                else:
                    extracted = json.loads(fixed_content)
                logger.info(f"Fixed truncated JSON for item {item_id}")
            except json.JSONDecodeError:
                logger.warning(
                    f"LLM returned invalid JSON for item {item_id}: {e}\nContent: {content[:500]}"
                )
                # Try to extract individual fields with regex as last resort
                extracted = self._extract_metadata_from_text(content, item)

        # Normalize fields
        result = {
            "title": extracted.get("title") or item.get("title"),
            "authors": extracted.get("authors") or item.get("authors", []),
            "year": extracted.get("year") if extracted.get("year") else item.get("year"),
            "venue": extracted.get("venue") or item.get("venue"),
            "doi": extracted.get("doi") or item.get("doi"),
            "url": extracted.get("url") or item.get("url"),
            "abstract": extracted.get("abstract") or item.get("abstract"),
            "tags": extracted.get("tags") or item.get("tags", []),
            "citekey": item.get("citekey"),
            "item_type": item.get("item_type", "journalArticle"),
        }
        return result

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _extract_metadata_from_text(self, text: str, item: dict) -> dict:
        """Extract metadata fields from raw text when JSON parsing fails completely."""
        result = {}
        # title
        m = re.search(r'"title"\s*:\s*"([^"]*)"', text)
        if m:
            result["title"] = m.group(1)
        # authors
        m = re.search(r'"authors"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if m:
            authors_raw = m.group(1)
            result["authors"] = re.findall(r'"([^"]*)"', authors_raw)
        # year
        m = re.search(r'"year"\s*:\s*(\d{4})', text)
        if m:
            result["year"] = int(m.group(1))
        # venue
        m = re.search(r'"venue"\s*:\s*"([^"]*)"', text)
        if m:
            result["venue"] = m.group(1)
        # doi
        m = re.search(r'"doi"\s*:\s*"([^"]*)"', text)
        if m:
            result["doi"] = m.group(1)
        # url
        m = re.search(r'"url"\s*:\s*"([^"]*)"', text)
        if m:
            result["url"] = m.group(1)
        # abstract
        m = re.search(r'"abstract"\s*:\s*"([^"]*)"', text, re.DOTALL)
        if m:
            result["abstract"] = m.group(1).replace("\\n", "\n")
        # tags
        m = re.search(r'"tags"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if m:
            tags_raw = m.group(1)
            result["tags"] = re.findall(r'"([^"]*)"', tags_raw)
        return result

    async def fetch_metadata_by_doi(self, doi: str) -> dict:
        """Fetch metadata from CrossRef API."""
        url = f"https://api.crossref.org/works/{doi}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise ValueError(f"CrossRef API returned {resp.status}")
                data = await resp.json()
                work = data.get("message", {})

                authors = []
                for author in work.get("author", []):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    authors.append(f"{given} {family}".strip())

                return {
                    "title": work.get("title", [None])[0],
                    "authors": authors,
                    "year": work.get("published-print", {}).get("date-parts", [[None]])[0][0]
                    or work.get("published-online", {}).get("date-parts", [[None]])[0][0],
                    "venue": work.get("container-title", [None])[0] or work.get("publisher", ""),
                    "doi": doi,
                    "url": work.get("URL", f"https://doi.org/{doi}"),
                    "abstract": work.get("abstract", ""),
                    "tags": work.get("subject", []),
                }

    async def fetch_metadata_by_arxiv(self, arxiv_id: str) -> dict:
        """Fetch metadata from arXiv API with retry on rate limit."""
        import asyncio

        # Normalize arxiv_id
        arxiv_id = arxiv_id.strip()
        if arxiv_id.startswith("http"):
            # Extract ID from URL
            import re as re_mod

            m = re_mod.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+|\d+)", arxiv_id)
            if m:
                arxiv_id = m.group(1)

        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        headers = {
            "User-Agent": "OctopusAcademicBot/1.0 (https://github.com/octopus; contact@octopus.dev)",
        }

        max_retries = 3
        base_delay = 3.0
        async with aiohttp.ClientSession(headers=headers) as session:
            for attempt in range(max_retries):
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return self._parse_arxiv_atom(text, arxiv_id)
                    if resp.status == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            logger.warning(
                                f"arXiv API rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise ValueError(
                            "arXiv API returned 429 (Too Many Requests). Please wait a moment and try again."
                        )
                    raise ValueError(f"arXiv API returned {resp.status}")
            raise ValueError("arXiv API request failed after retries")

    def _parse_arxiv_atom(self, xml_text: str, arxiv_id: str) -> dict:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            raise ValueError("No entry found in arXiv response")

        title = entry.findtext("atom:title", "", ns).replace("\n", " ").strip()
        summary = entry.findtext("atom:summary", "", ns).strip()
        doi = entry.findtext("arxiv:doi", "", ns)
        published = entry.findtext("atom:published", "", ns)
        year = int(published[:4]) if published else None

        authors = []
        for author_el in entry.findall("atom:author", ns):
            name = author_el.findtext("atom:name", "", ns)
            if name:
                authors.append(name)

        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
                break

        categories = [
            cat.get("term", "") for cat in entry.findall("atom:category", ns) if cat.get("term")
        ]

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": "arXiv",
            "doi": doi or f"10.48550/arXiv.{arxiv_id}",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "abstract": summary,
            "tags": categories,
            "arxiv_id": arxiv_id,
            "pdf_url": pdf_url,
        }

    async def download_arxiv_pdf(self, arxiv_id: str, dest_path: Path) -> Path:
        """Download PDF from arXiv with retry on rate limit."""
        import asyncio

        arxiv_id = arxiv_id.strip()
        if arxiv_id.startswith("http"):
            import re as re_mod

            m = re_mod.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+|\d+)", arxiv_id)
            if m:
                arxiv_id = m.group(1)

        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        headers = {
            "User-Agent": "OctopusAcademicBot/1.0 (https://github.com/octopus; contact@octopus.dev)",
        }

        max_retries = 3
        base_delay = 3.0
        async with aiohttp.ClientSession(headers=headers) as session:
            for attempt in range(max_retries):
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        dest_path.write_bytes(await resp.read())
                        return dest_path
                    if resp.status == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            logger.warning(
                                f"arXiv PDF download rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise ValueError(
                            "arXiv PDF download returned 429 (Too Many Requests). Please wait a moment and try again."
                        )
                    raise ValueError(f"Failed to download PDF: {resp.status}")
            raise ValueError("arXiv PDF download failed after retries")

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def add_attachment(
        self, item_id: int, file_path: Path, file_type: str = "supplementary"
    ) -> dict:
        self.get_item(item_id)
        item_dir = self._item_dir(item_id)
        if not item_dir:
            raise ValueError(f"Item directory not found for {item_id}")

        if file_type == "supplementary":
            sub_dir = item_dir / "supplementary"
            sub_dir.mkdir(parents=True, exist_ok=True)
            dest = sub_dir / file_path.name
        else:
            dest = item_dir / file_path.name

        import shutil

        if file_path.resolve() != dest.resolve():
            shutil.copy2(file_path, dest)

        sha256 = self._compute_sha256(dest)
        rel = str(dest.relative_to(item_dir))
        cursor = self.db.execute(
            "INSERT INTO library_attachments (item_id, filename, file_type, sha256, rel_path, size) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, file_path.name, file_type, sha256, rel, dest.stat().st_size),
        )
        self.db.commit()
        return {
            "id": cursor.lastrowid,
            "filename": file_path.name,
            "file_type": file_type,
            "rel_path": rel,
        }

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def load_annotations(self, item_id: int) -> list[dict]:
        """Load all annotations for a library item."""
        rows = self.db.execute(
            """
            SELECT id, page, type, color, text, comment, rects, created_at
            FROM library_annotations
            WHERE item_id = ?
            ORDER BY page, created_at
            """,
            (item_id,),
        ).fetchall()
        annotations = []
        for row in rows:
            annot = dict(row)
            if annot.get("rects"):
                try:
                    import json

                    annot["rects"] = json.loads(annot["rects"])
                except Exception:
                    annot["rects"] = []
            else:
                annot["rects"] = []
            annotations.append(annot)
        return annotations

    def save_annotations(self, item_id: int, annotations: list[dict]) -> dict:
        """Replace all annotations for a library item."""
        import json
        from datetime import datetime

        # Delete existing
        self.db.execute("DELETE FROM library_annotations WHERE item_id = ?", (item_id,))

        now = datetime.now().isoformat()
        for annot in annotations:
            self.db.execute(
                """
                INSERT INTO library_annotations
                (item_id, page, type, color, text, comment, rects, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    annot.get("page", 0),
                    annot.get("type", "highlight"),
                    annot.get("color", "#ffeb3b"),
                    annot.get("text", ""),
                    annot.get("comment", ""),
                    json.dumps(annot.get("rects", [])) if annot.get("rects") else None,
                    annot.get("createdAt") or annot.get("created_at") or now,
                    now,
                ),
            )
        self.db.commit()
        return {"saved": len(annotations)}

    # ------------------------------------------------------------------
    # Note linking
    # ------------------------------------------------------------------

    def link_note(self, item_id: int, note_path: str, relation: str = "manual") -> dict:
        cursor = self.db.execute(
            "INSERT INTO library_item_notes (item_id, note_path, relation) VALUES (?, ?, ?)",
            (item_id, note_path, relation),
        )
        self.db.commit()
        return {
            "id": cursor.lastrowid,
            "item_id": item_id,
            "note_path": note_path,
            "relation": relation,
        }

    def unlink_note(self, link_id: int) -> bool:
        self.db.execute("DELETE FROM library_item_notes WHERE id = ?", (link_id,))
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # PDF Text Extraction & Chunking (RAG foundation)
    # ------------------------------------------------------------------

    def extract_pdf_chunks(self, item_id: int) -> list[dict]:
        """Extract text from PDF and split into chunks. Returns list of chunks."""
        import fitz

        self.get_item(item_id)
        item_dir = self._item_dir(item_id)
        if not item_dir:
            self._set_chunk_status(item_id, "failed")
            raise ValueError(f"Item directory not found for {item_id}")

        main_pdf = item_dir / "main.pdf"
        if not main_pdf.exists():
            self._set_chunk_status(item_id, "failed")
            raise ValueError(f"PDF not found for item {item_id}")

        doc = fitz.open(str(main_pdf))
        total_pages = len(doc)
        chunks: list[dict] = []
        chunk_index = 0

        # Mark as processing
        self._set_chunk_status(item_id, f"processing:0/{total_pages}")

        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            if not text.strip():
                # Still update progress even for empty pages
                if (page_num + 1) % 5 == 0 or page_num == total_pages - 1:
                    self._set_chunk_status(item_id, f"processing:{page_num + 1}/{total_pages}")
                continue

            # Simple paragraph-based chunking
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                # Skip very short fragments (likely headers/footers)
                if len(para) < 20:
                    continue
                chunks.append(
                    {
                        "item_id": item_id,
                        "chunk_index": chunk_index,
                        "page": page_num + 1,
                        "section": "",  # TODO: detect section headers
                        "text": para,
                        "token_count": len(para.split()),
                    }
                )
                chunk_index += 1

            # Update progress every 5 pages or on the last page
            if (page_num + 1) % 5 == 0 or page_num == total_pages - 1:
                self._set_chunk_status(item_id, f"processing:{page_num + 1}/{total_pages}")

        doc.close()

        # Clear existing chunks for this item
        self.db.execute("DELETE FROM library_chunks WHERE item_id = ?", (item_id,))
        for chunk in chunks:
            self.db.execute(
                """
                INSERT INTO library_chunks (item_id, chunk_index, page, section, text, token_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk["item_id"],
                    chunk["chunk_index"],
                    chunk["page"],
                    chunk["section"],
                    chunk["text"],
                    chunk["token_count"],
                ),
            )
        self.db.commit()

        # Mark as completed
        self._set_chunk_status(item_id, "completed")
        return chunks

    def _set_chunk_status(self, item_id: int, status: str) -> None:
        """Update the chunk extraction status for a library item."""
        try:
            self.db.execute(
                "UPDATE library_items SET chunk_status = ? WHERE id = ?",
                (status, item_id),
            )
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to update chunk_status for item {item_id}: {e}")

    def get_item_chunks(self, item_id: int, limit: int = 100) -> list[dict]:
        """Get all chunks for a library item."""
        rows = self.db.execute(
            "SELECT id, chunk_index, page, section, text, token_count FROM library_chunks WHERE item_id = ? ORDER BY chunk_index LIMIT ?",
            (item_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_chunks(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 search over chunk text."""
        rows = self.db.execute(
            """
            SELECT c.id, c.item_id, c.chunk_index, c.page, c.section, c.text, c.token_count,
                   i.title, i.authors_json, i.year
            FROM library_chunks_fts fts
            JOIN library_chunks c ON fts.rowid = c.id
            JOIN library_items i ON c.item_id = i.id
            WHERE library_chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query.strip(), limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["authors"] = json.loads(d["authors_json"]) if d.get("authors_json") else []
            del d["authors_json"]
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Paper Graph
    # ------------------------------------------------------------------

    def get_paper_graph(
        self, collection_id: int = None, center_item_id: int = None, limit: int = 300
    ) -> dict:
        """Return graph of library notes related to library items.

        Queries the dedicated library_notes / library_note_links tables.
        Completely separate from the knowledge graph.
        """
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        note_paths: set[str] = set()

        # Determine relevant library items
        where_clause = ""
        params: list = []
        if collection_id:
            where_clause = "WHERE i.id IN (SELECT item_id FROM library_collection_items WHERE collection_id = ?)"
            params = [collection_id]
        elif center_item_id:
            where_clause = "WHERE i.id = ?"
            params = [center_item_id]

        # Collect note paths linked to these library items
        sql = f"""
            SELECT ln.note_path, ln.item_id, i.library_path, i.title as item_title
            FROM library_item_notes ln
            JOIN library_items i ON ln.item_id = i.id
            {where_clause}
        """
        note_to_item: dict[str, dict] = {}
        for r in self.db.execute(sql, params).fetchall():
            note_paths.add(r["note_path"])
            note_to_item[r["note_path"]] = {
                "item_id": r["item_id"],
                "library_path": r["library_path"],
                "item_title": r["item_title"],
            }

        # Also include notes stored under knowledge/library/ paths
        for row in self.db.execute(
            "SELECT path FROM library_notes WHERE path LIKE 'knowledge/library/%'"
        ).fetchall():
            note_paths.add(row["path"])

        if not note_paths:
            return {"nodes": [], "edges": []}

        # Query library notes
        placeholders = ",".join("?" * len(note_paths))
        query_params = list(note_paths) + [limit]
        for row in self.db.execute(
            f"SELECT path, title, type, mtime FROM library_notes WHERE path IN ({placeholders}) LIMIT ?",
            query_params,
        ).fetchall():
            node_data = {
                "id": row["path"],
                "label": row["title"],
                "type": "note",
                "mtime": row["mtime"],
            }
            # Attach item info if this note is linked to a library item
            if row["path"] in note_to_item:
                item_info = note_to_item[row["path"]]
                node_data["item_id"] = item_info["item_id"]
                node_data["library_path"] = item_info["library_path"]
                node_data["item_title"] = item_info["item_title"]
            nodes[row["path"]] = node_data

        # Links between these notes (from library_note_links)
        if nodes:
            placeholders = ",".join("?" * len(nodes))
            node_keys = list(nodes.keys())
            for row in self.db.execute(
                f"SELECT from_path, to_path FROM library_note_links WHERE from_path IN ({placeholders}) AND to_path IN ({placeholders})",
                node_keys + node_keys,
            ).fetchall():
                edges.append({"source": row["from_path"], "target": row["to_path"]})

        return {"nodes": list(nodes.values()), "edges": edges}
