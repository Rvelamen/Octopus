"""Knowledge graph indexing engine for note management.

Maintains a SQLite index for markdown files, extracts [[bidirectional links]],
and provides graph queries with in-memory caching.
"""

import re
import sqlite3
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.services.knowledge_migrations import run_knowledge_index_migrations


class KnowledgeGraphEngine:
    """Knowledge base indexing engine - per-workspace singleton.

    Responsible for maintaining the SQLite index, parsing markdown links,
    and providing query interfaces.
    """

    _instances: dict[str, "KnowledgeGraphEngine"] = {}

    def __new__(cls, workspace_root: str) -> "KnowledgeGraphEngine":
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
        self.raw_dir = self.knowledge_dir / "raw"
        self.notes_dir = self.knowledge_dir / "notes"

        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self.db_path = self.knowledge_dir / ".knowledge_index.db"
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

        # In-memory cache
        self._cache: Optional[dict[str, Any]] = None
        self._cache_dirty = True

    def _init_db(self) -> None:
        """Initialize SQLite schema, pragmas, and version tracking."""
        pragmas = [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA cache_size = -64000;",
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA mmap_size = 268435456;",
            "PRAGMA foreign_keys = ON;",
        ]
        for pragma in pragmas:
            self.db.execute(pragma)

        run_knowledge_index_migrations(self.db_path)
        self._ensure_fts_populated()

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path and ensure it stays within the workspace."""
        full_path = (self.workspace_root / relative_path).resolve()
        workspace_resolved = self.workspace_root.resolve()
        if not str(full_path).startswith(str(workspace_resolved)):
            raise PermissionError("Access denied: path outside workspace")
        return full_path

    def _extract_frontmatter(self, content: str) -> dict[str, Any] | None:
        """Extract YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return None
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None
        try:
            import yaml
            return self._make_json_safe(yaml.safe_load(match.group(1))) or None
        except Exception:
            return None

    @staticmethod
    def _make_json_safe(value: Any) -> Any:
        """Recursively convert datetime/date objects to ISO strings for JSON serialization."""
        from datetime import date, datetime

        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: KnowledgeGraphEngine._make_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [KnowledgeGraphEngine._make_json_safe(v) for v in value]
        return value

    def _extract_title(self, content: str, fallback_path: str) -> str:
        """Extract the first level-1 markdown heading as title, or use the filename."""
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return Path(fallback_path).stem

    def _extract_tags(self, content: str) -> list[str]:
        """Extract #tag patterns from markdown content."""
        tags: list[str] = []
        for match in re.finditer(r"(?<!\w)#([\w\u4e00-\u9fa5\-]+)", content):
            tag = match.group(1).strip().lower()
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    def _resolve_title(self, title: str, vault: str | None = None) -> Optional[str]:
        """Case-insensitive title match within a vault; falls back to path stem match."""
        clean = title.strip().rstrip("\\")
        # 1. Exact title match within the same vault
        if vault is not None:
            rows = self.db.execute(
                "SELECT path FROM knowledge_nodes WHERE LOWER(title) = LOWER(?) AND vault = ? ORDER BY mtime DESC LIMIT 1",
                (clean, vault),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT path FROM knowledge_nodes WHERE LOWER(title) = LOWER(?) ORDER BY mtime DESC LIMIT 1",
                (clean,),
            ).fetchall()
        if rows:
            return rows[0]["path"]
        # 2. Path stem match (Obsidian links often reference file names)
        stem = Path(clean).stem
        if vault is not None:
            rows = self.db.execute(
                "SELECT path FROM knowledge_nodes WHERE LOWER(path) LIKE LOWER(?) AND vault = ? ORDER BY mtime DESC LIMIT 1",
                (f"%/{stem}.md", vault),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT path FROM knowledge_nodes WHERE LOWER(path) LIKE LOWER(?) ORDER BY mtime DESC LIMIT 1",
                (f"%/{stem}.md",),
            ).fetchall()
        return rows[0]["path"] if rows else None

    def _invalidate_cache(self) -> None:
        """Mark the graph cache as dirty."""
        self._cache_dirty = True

    def _resolve_vault_from_path(self, relative_path: str) -> str:
        """Infer vault name from note path.

        knowledge/notes/                → 'default'
        knowledge/notes/paper/        → 'paper'
        knowledge/notes/obsidian_xxx/ → 'obsidian_xxx'
        """
        parts = Path(relative_path).parts
        if len(parts) >= 3 and parts[0] == "knowledge" and parts[1] == "notes":
            return parts[2]
        return "default"

    def update_note(self, relative_path: str, force: bool = False) -> None:
        """Read a markdown file, extract title and [[links]], and update the index.

        Skips if mtime has not changed. Cleans up DB records if the file is gone.
        """
        full_path = self._resolve_path(relative_path)

        if not full_path.exists():
            # File deleted: clean up index
            self.db.execute("DELETE FROM knowledge_nodes WHERE path = ?", (relative_path,))
            self.db.commit()
            self._invalidate_cache()
            return

        current_mtime = full_path.stat().st_mtime
        row = self.db.execute(
            "SELECT mtime FROM knowledge_nodes WHERE path = ?", (relative_path,)
        ).fetchone()

        if not force and row and abs(row["mtime"] - current_mtime) < 0.001:
            return  # No change

        content = full_path.read_text(encoding="utf-8")
        title = self._extract_title(content, relative_path)
        raw_links = re.findall(r"\[\[(.*?)\]\]", content)
        links = [re.split(r"\\?\|", link, maxsplit=1)[0].strip().rstrip("\\") for link in raw_links]
        tags = self._extract_tags(content)

        vault = self._resolve_vault_from_path(relative_path)

        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO knowledge_nodes
                (path, title, type, mtime, word_count, updated_at, content, vault)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relative_path,
                    title,
                    "note",
                    current_mtime,
                    len(content.split()),
                    datetime.now().isoformat(),
                    content,
                    vault,
                ),
            )
            # Preserve links that were unresolved (to_path=NULL) before this reindex.
            # If they still exist in the file they will be re-inserted; if the user
            # removed the [[wikilink]] from the file they remain orphaned (harmless).
            existing_unresolved = {
                row["to_title"]
                for row in self.db.execute(
                    "SELECT to_title FROM knowledge_links WHERE from_path = ? AND to_path IS NULL",
                    (relative_path,),
                ).fetchall()
            }
            self.db.execute("DELETE FROM knowledge_links WHERE from_path = ?", (relative_path,))
            inserted_titles: set[str] = set()
            for raw_title in links:
                clean_title = raw_title.strip()
                to_path = self._resolve_title(clean_title, vault)
                self.db.execute(
                    "INSERT INTO knowledge_links (from_path, to_title, to_path) VALUES (?, ?, ?)",
                    (relative_path, clean_title, to_path),
                )
                inserted_titles.add(clean_title)
            # Restore unresolved links that are no longer in the file
            for title in existing_unresolved:
                if title not in inserted_titles:
                    self.db.execute(
                        "INSERT INTO knowledge_links (from_path, to_title, to_path) VALUES (?, ?, NULL)",
                        (relative_path, title),
                    )

            # Update tags
            self.db.execute("DELETE FROM knowledge_node_tags WHERE node_path = ?", (relative_path,))
            for tag in tags:
                self.db.execute(
                    "INSERT OR IGNORE INTO knowledge_tags (name) VALUES (?)", (tag,)
                )
                tag_row = self.db.execute("SELECT id FROM knowledge_tags WHERE name = ?", (tag,)).fetchone()
                if tag_row:
                    self.db.execute(
                        "INSERT OR IGNORE INTO knowledge_node_tags (tag_id, node_path) VALUES (?, ?)",
                        (tag_row["id"], relative_path),
                    )

        self._invalidate_cache()
        logger.debug(f"Indexed note: {relative_path}")

    def list_directory(self, relative_path: str) -> list[dict[str, Any]]:
        """Return a list of files/folders under the given relative path."""
        full_path = self._resolve_path(relative_path)
        if not full_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {relative_path}")

        items: list[dict[str, Any]] = []
        for entry in sorted(full_path.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
            stat = entry.stat()
            item: dict[str, Any] = {
                "name": entry.name,
                "path": str(entry.relative_to(self.workspace_root)),
                "is_directory": entry.is_dir(),
                "size": stat.st_size if entry.is_file() else 0,
                "mtime": stat.st_mtime,
                "meta": None,
            }

            # Parse frontmatter for markdown files
            if not entry.is_dir() and entry.suffix == ".md":
                try:
                    content = entry.read_text(encoding="utf-8", errors="ignore")[:4096]
                    item["meta"] = self._extract_frontmatter(content)
                except Exception:
                    pass

            # Compute sha256 for common document files (PDF, etc.) for metadata binding
            if not entry.is_dir() and entry.suffix.lower() in (".pdf", ".docx", ".pptx", ".xlsx"):
                try:
                    import hashlib
                    h = hashlib.sha256()
                    with open(entry, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    item["sha256"] = h.hexdigest()
                except Exception:
                    pass

            items.append(item)
        return items

    def read_note(self, relative_path: str) -> str:
        """Read the full content of a note."""
        full_path = self._resolve_path(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")
        return full_path.read_text(encoding="utf-8")

    def write_note(self, relative_path: str, content: str) -> None:
        """Write content to a note file.

        Does NOT automatically update the index; the caller should invoke
        update_note if appropriate.
        """
        full_path = self._resolve_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Document metadata
    # ------------------------------------------------------------------

    def upsert_document_meta(self, sha256: str, data: dict[str, Any]) -> None:
        """Insert or update metadata for a document identified by sha256."""
        import json
        self.db.execute(
            """
            INSERT INTO knowledge_documents_meta (
                sha256, source_type, title, authors, year, venue, doi, url,
                summary, page_count, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
                source_type = excluded.source_type,
                title = excluded.title,
                authors = excluded.authors,
                year = excluded.year,
                venue = excluded.venue,
                doi = excluded.doi,
                url = excluded.url,
                summary = excluded.summary,
                page_count = excluded.page_count,
                metadata_json = excluded.metadata_json,
                extracted_at = CURRENT_TIMESTAMP
            """,
            (
                sha256,
                data.get("source_type"),
                data.get("title"),
                json.dumps(data.get("authors", [])) if isinstance(data.get("authors"), list) else data.get("authors"),
                data.get("year"),
                data.get("venue"),
                data.get("doi"),
                data.get("url"),
                data.get("summary"),
                data.get("page_count"),
                json.dumps(data.get("metadata_json", {})) if isinstance(data.get("metadata_json"), dict) else data.get("metadata_json"),
            ),
        )
        self.db.commit()

    def get_document_meta(self, sha256: str) -> dict[str, Any] | None:
        """Retrieve metadata for a document by sha256."""
        import json
        row = self.db.execute(
            "SELECT * FROM knowledge_documents_meta WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        for field in ("authors",):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except Exception:
                    pass
        if result.get("metadata_json"):
            try:
                result["metadata_json"] = json.loads(result["metadata_json"])
            except Exception:
                pass
        return result

    def get_document_metas_batch(self, sha256s: list[str]) -> dict[str, dict[str, Any]]:
        """Batch retrieve metadata by sha256 list."""
        import json
        if not sha256s:
            return {}
        placeholders = ",".join(["?"] * len(sha256s))
        rows = self.db.execute(
            f"SELECT * FROM knowledge_documents_meta WHERE sha256 IN ({placeholders})",
            tuple(sha256s),
        ).fetchall()
        result = {}
        for row in rows:
            item = dict(row)
            for field in ("authors",):
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            if item.get("metadata_json"):
                try:
                    item["metadata_json"] = json.loads(item["metadata_json"])
                except Exception:
                    pass
            result[item["sha256"]] = item
        return result

    def search_notes(self, query: str, limit: int = 20, vault_filter: Optional[str] = None) -> list[dict[str, Any]]:
        """Fuzzy search notes by path or title, optionally scoped to a vault."""
        stripped = query.strip()
        if not stripped:
            return []

        vault_cond = " AND vault = ?" if vault_filter else ""
        vault_args: tuple = (vault_filter,) if vault_filter else ()

        # 1. Exact title match
        row = self.db.execute(
            f"SELECT path, title, mtime, word_count FROM knowledge_nodes WHERE title = ?{vault_cond} LIMIT 1",
            (stripped,) + vault_args,
        ).fetchone()
        if row:
            return [{"path": row["path"], "title": row["title"], "mtime": row["mtime"], "word_count": row["word_count"]}]

        # 2. Path stem match (e.g. "Foo" -> ".../Foo.md")
        row = self.db.execute(
            f"SELECT path, title, mtime, word_count FROM knowledge_nodes WHERE path LIKE ?{vault_cond} LIMIT 1",
            (f"%/{stripped}.md",) + vault_args,
        ).fetchone()
        if row:
            return [{"path": row["path"], "title": row["title"], "mtime": row["mtime"], "word_count": row["word_count"]}]

        # 3. FTS5 match (more intelligent for long titles / phrases)
        try:
            vault_join = f" AND n.vault = ?" if vault_filter else ""
            rows = self.db.execute(
                f"""
                SELECT n.path, n.title, n.mtime, n.word_count, rank
                FROM knowledge_nodes_fts
                JOIN knowledge_nodes n ON knowledge_nodes_fts.rowid = n.rowid
                WHERE knowledge_nodes_fts MATCH ?{vault_join}
                ORDER BY rank
                LIMIT ?
                """,
                (stripped,) + (vault_filter,) * bool(vault_filter) + (limit,),
            ).fetchall()
            if rows:
                return [{"path": r["path"], "title": r["title"], "mtime": r["mtime"], "word_count": r["word_count"], "rank": r["rank"]} for r in rows]
        except Exception:
            pass

        # 4. Fallback LIKE on path or title
        pattern = f"%{stripped}%"
        rows = self.db.execute(
            f"""
            SELECT path, title, mtime, word_count FROM knowledge_nodes
            WHERE (path LIKE ? OR title LIKE ?){vault_cond}
            ORDER BY mtime DESC
            LIMIT ?
            """,
            (pattern, pattern) + vault_args + (limit,),
        ).fetchall()
        return [{"path": r["path"], "title": r["title"], "mtime": r["mtime"], "word_count": r["word_count"]} for r in rows]

    def list_vaults(self) -> list[dict[str, Any]]:
        """Return all vaults with note counts."""
        rows = self.db.execute(
            """
            SELECT vault, COUNT(*) as note_count
            FROM knowledge_nodes
            GROUP BY vault
            ORDER BY vault ASC
            """
        ).fetchall()
        return [{"name": r["vault"], "note_count": r["note_count"]} for r in rows]

    def search_notes_fts(self, query: str, limit: int = 20, vault_filter: Optional[str] = None) -> list[dict[str, Any]]:
        """Full-text search using SQLite FTS5 with BM25 ranking.

        Falls back to path/title search if FTS5 is unavailable or returns no results.
        Optionally scoped to a vault.
        """
        try:
            vault_join = f" AND n.vault = ?" if vault_filter else ""
            rows = self.db.execute(
                f"""
                SELECT n.path, n.title, n.mtime, n.word_count, rank
                FROM knowledge_nodes_fts
                JOIN knowledge_nodes n ON knowledge_nodes_fts.rowid = n.rowid
                WHERE knowledge_nodes_fts MATCH ?{vault_join}
                ORDER BY rank
                LIMIT ?
                """,
                (query,) + (vault_filter,) * bool(vault_filter) + (limit,),
            ).fetchall()
            if rows:
                return [
                    {
                        "path": r["path"],
                        "title": r["title"],
                        "mtime": r["mtime"],
                        "word_count": r["word_count"],
                        "rank": round(r["rank"], 4),
                        "source": "fts5",
                    }
                    for r in rows
                ]
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 search failed: {e}")
        return []

    def rebuild_fts_index(self) -> None:
        """Rebuild the FTS5 index from scratch."""
        try:
            self.db.execute("DELETE FROM knowledge_nodes_fts")
            self.db.execute(
                """
                INSERT INTO knowledge_nodes_fts(rowid, title, content)
                SELECT rowid, title, content FROM knowledge_nodes
                WHERE content IS NOT NULL
                """
            )
            self.db.commit()
            logger.info("Rebuilt FTS5 index")
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to rebuild FTS5 index: {e}")

    def _ensure_fts_populated(self) -> None:
        """Ensure FTS5 index is populated if table exists but is empty."""
        try:
            fts_count = self.db.execute(
                "SELECT COUNT(*) FROM knowledge_nodes_fts"
            ).fetchone()[0]
            node_count = self.db.execute(
                "SELECT COUNT(*) FROM knowledge_nodes"
            ).fetchone()[0]
            if fts_count == 0 and node_count > 0:
                logger.info("FTS5 index empty, rebuilding from existing nodes")
                self.rebuild_fts_index()
        except sqlite3.OperationalError:
            pass

    def get_tags(self, vault_filter: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all tags (optionally scoped to a vault) with usage counts."""
        if vault_filter:
            rows = self.db.execute(
                """
                SELECT t.name, COUNT(nt.node_path) as count
                FROM knowledge_tags t
                JOIN knowledge_node_tags nt ON t.id = nt.tag_id
                JOIN knowledge_nodes n ON nt.node_path = n.path
                WHERE n.vault = ?
                GROUP BY t.id
                ORDER BY count DESC, t.name ASC
                """,
                (vault_filter,),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT t.name, COUNT(nt.node_path) as count
                FROM knowledge_tags t
                LEFT JOIN knowledge_node_tags nt ON t.id = nt.tag_id
                GROUP BY t.id
                ORDER BY count DESC, t.name ASC
                """
            ).fetchall()
        return [{"name": r["name"], "count": r["count"]} for r in rows]

    def get_node_tags(self, path: str) -> list[str]:
        """Return tags for a specific note."""
        rows = self.db.execute(
            """
            SELECT t.name FROM knowledge_tags t
            JOIN knowledge_node_tags nt ON t.id = nt.tag_id
            WHERE nt.node_path = ?
            ORDER BY t.name ASC
            """,
            (path,),
        ).fetchall()
        return [r["name"] for r in rows]

    def search_by_tag(self, tag: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search notes by tag name."""
        rows = self.db.execute(
            """
            SELECT n.path, n.title, n.mtime FROM knowledge_nodes n
            JOIN knowledge_node_tags nt ON n.path = nt.node_path
            JOIN knowledge_tags t ON t.id = nt.tag_id
            WHERE t.name = ?
            ORDER BY n.mtime DESC
            LIMIT ?
            """,
            (tag.lower(), limit),
        ).fetchall()
        return [{"path": r["path"], "title": r["title"], "mtime": r["mtime"]} for r in rows]

    def get_graph(
        self, center_path: Optional[str] = None, depth: int = 1, limit: int = 200, tag_filter: Optional[str] = None,
        vault_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return a subgraph as {nodes, edges}.

        If center_path is given, perform BFS up to `depth` layers using both
        outgoing and incoming links. Otherwise return the whole graph up to
        `limit` nodes.
        If tag_filter is given, only include nodes that have the tag.
        If vault_filter is given, only include nodes in that vault.
        """
        if self._cache_dirty or self._cache is None:
            self._rebuild_cache()

        cache = self._cache
        assert cache is not None

        all_nodes: dict[str, dict[str, Any]] = {}
        all_edges: list[dict[str, Any]] = []

        def _include_node(key: str) -> bool:
            if vault_filter is not None and cache["node_vaults"].get(key) != vault_filter:
                return False
            if tag_filter is None:
                return True
            return tag_filter.lower() in cache["node_tags"].get(key, [])

        if center_path is None:
            # Whole graph, limited by node count
            node_keys = [k for k in list(cache["nodes"].keys()) if _include_node(k)][:limit]
            for key in node_keys:
                all_nodes[key] = cache["nodes"][key]
            edge_set = set()
            for edge in cache["edges"]:
                if edge["source"] in all_nodes and edge["target"] in all_nodes:
                    eid = (edge["source"], edge["target"])
                    if eid not in edge_set:
                        edge_set.add(eid)
                        all_edges.append(edge)
            return {"nodes": list(all_nodes.values()), "edges": all_edges}

        if center_path not in cache["nodes"]:
            return {"nodes": [], "edges": []}

        # BFS from center
        visited: set[str] = {center_path} if _include_node(center_path) else set()
        queue: deque[tuple[str, int]] = deque([(center_path, 0)]) if _include_node(center_path) else deque()

        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue

            # Outgoing
            for target in cache["adj_out"].get(current, []):
                if target not in visited and _include_node(target):
                    visited.add(target)
                    queue.append((target, d + 1))

            # Incoming
            for source in cache["adj_in"].get(current, []):
                if source not in visited and _include_node(source):
                    visited.add(source)
                    queue.append((source, d + 1))

        for key in visited:
            all_nodes[key] = cache["nodes"][key]

        edge_set: set[tuple[str, str]] = set()
        for edge in cache["edges"]:
            if edge["source"] in all_nodes and edge["target"] in all_nodes:
                eid = (edge["source"], edge["target"])
                if eid not in edge_set:
                    edge_set.add(eid)
                    all_edges.append(edge)

        return {"nodes": list(all_nodes.values()), "edges": all_edges}

    def _rebuild_cache(self) -> None:
        """Rebuild the in-memory graph cache from SQLite."""
        nodes: dict[str, dict[str, Any]] = {}
        title_to_path: dict[str, str] = {}
        for row in self.db.execute(
            "SELECT path, title, type, mtime FROM knowledge_nodes"
        ).fetchall():
            nodes[row["path"]] = {
                "id": row["path"],
                "label": row["title"],
                "type": row["type"],
                "mtime": row["mtime"],
            }
            title_to_path[row["title"].lower()] = row["path"]

        edges: list[dict[str, Any]] = []
        adj_out: dict[str, list[str]] = {}
        adj_in: dict[str, list[str]] = {}
        stem_to_path: dict[str, str] = {}
        for path in nodes:
            stem = Path(path).stem.lower()
            stem_to_path[stem] = path

        for row in self.db.execute(
            "SELECT from_path, to_title, to_path FROM knowledge_links"
        ).fetchall():
            src = row["from_path"]
            to_title = row["to_title"].strip().rstrip("\\")
            tgt = row["to_path"] or title_to_path.get(to_title.lower())
            if not tgt:
                stem = Path(to_title).stem.lower()
                tgt = stem_to_path.get(stem)
            if src in nodes and tgt in nodes:
                edges.append({"source": src, "target": tgt})
                adj_out.setdefault(src, []).append(tgt)
                adj_in.setdefault(tgt, []).append(src)

        node_tags: dict[str, list[str]] = {}
        for row in self.db.execute(
            "SELECT nt.node_path, t.name FROM knowledge_node_tags nt JOIN knowledge_tags t ON nt.tag_id = t.id"
        ).fetchall():
            node_tags.setdefault(row["node_path"], []).append(row["name"])

        node_vaults: dict[str, str] = {}
        for row in self.db.execute("SELECT path, vault FROM knowledge_nodes").fetchall():
            node_vaults[row["path"]] = row["vault"]

        for node_path in nodes:
            nodes[node_path]["tags"] = node_tags.get(node_path, [])
            nodes[node_path]["vault"] = node_vaults.get(node_path, "default")

        self._cache = {"nodes": nodes, "edges": edges, "adj_out": adj_out, "adj_in": adj_in, "node_tags": node_tags, "node_vaults": node_vaults}
        self._cache_dirty = False

    def get_timeline(self, relative_path: str) -> dict[str, Any]:
        """Return contextual timeline and metadata for a note.

        Includes: basic info, outgoing/incoming links, tags, and recently
        modified related notes (linked by graph or tags).
        """
        row = self.db.execute(
            "SELECT path, title, mtime, word_count, updated_at FROM knowledge_nodes WHERE path = ?",
            (relative_path,),
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"Note not found: {relative_path}")

        # Links
        outgoing_rows = self.db.execute(
            "SELECT to_title, to_path FROM knowledge_links WHERE from_path = ?",
            (relative_path,),
        ).fetchall()
        incoming_rows = self.db.execute(
            "SELECT from_path FROM knowledge_links WHERE to_path = ?",
            (relative_path,),
        ).fetchall()

        outgoing = []
        for r in outgoing_rows:
            outgoing.append({"title": r["to_title"], "path": r["to_path"]})

        incoming = [{"path": r["from_path"]} for r in incoming_rows]

        # Tags
        tags = self.get_node_tags(relative_path)

        # Related notes: notes linked to or from this note, or sharing tags
        related_paths: set[str] = set()
        for o in outgoing:
            if o["path"]:
                related_paths.add(o["path"])
        for i in incoming:
            related_paths.add(i["path"])

        if tags:
            placeholders = ",".join("?" * len(tags))
            tag_rows = self.db.execute(
                f"""
                SELECT DISTINCT node_path FROM knowledge_node_tags nt
                JOIN knowledge_tags t ON nt.tag_id = t.id
                WHERE t.name IN ({placeholders}) AND nt.node_path != ?
                """,
                (*tags, relative_path),
            ).fetchall()
            for tr in tag_rows:
                related_paths.add(tr["node_path"])

        related = []
        if related_paths:
            placeholders = ",".join("?" * len(related_paths))
            rel_rows = self.db.execute(
                f"""
                SELECT path, title, mtime, word_count FROM knowledge_nodes
                WHERE path IN ({placeholders})
                ORDER BY mtime DESC
                LIMIT 10
                """,
                tuple(related_paths),
            ).fetchall()
            related = [
                {"path": r["path"], "title": r["title"], "mtime": r["mtime"], "word_count": r["word_count"]}
                for r in rel_rows
            ]

        return {
            "path": row["path"],
            "title": row["title"],
            "mtime": row["mtime"],
            "word_count": row["word_count"],
            "updated_at": row["updated_at"],
            "tags": tags,
            "outgoing_links": outgoing,
            "incoming_links": incoming,
            "related_notes": related,
        }

    def delete_note(self, relative_path: str, delete_file: bool = True) -> None:
        """Delete the note file and clean up its index entries."""
        if delete_file:
            full_path = self._resolve_path(relative_path)
            if full_path.exists():
                full_path.unlink()

        self.db.execute("DELETE FROM knowledge_nodes WHERE path = ?", (relative_path,))
        self.db.commit()
        self._invalidate_cache()
        logger.debug(f"Deleted note: {relative_path}")
