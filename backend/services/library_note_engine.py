"""Library note indexing engine for AI-generated notes under knowledge/library/.

Completely separate from the knowledge graph. Maintains its own SQLite tables:
- library_notes
- library_note_links
- library_tags / library_note_tags
- library_notes_fts (FTS5)
"""

import re
import sqlite3
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from backend.services.knowledge_migrations import run_knowledge_index_migrations


class LibraryNoteEngine:
    """Library note indexing engine - per-workspace singleton.

    Responsible for maintaining the SQLite index for markdown files under
    knowledge/library/, parsing markdown links, and providing query interfaces.
    Completely separate from KnowledgeGraphEngine.
    """

    _instances: dict[str, "LibraryNoteEngine"] = {}

    def __new__(cls, workspace_root: str) -> "LibraryNoteEngine":
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

        # Initialize database (shared with KnowledgeGraphEngine)
        self.db_path = self.knowledge_dir / ".knowledge_index.db"
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

        # In-memory cache
        self._cache: dict[str, Any] | None = None
        self._cache_dirty = True

    def _init_db(self) -> None:
        """Initialize SQLite schema via shared migration runner."""
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

    def _resolve_title(self, title: str, vault: str | None = None) -> str | None:
        """Case-insensitive title match within a vault; falls back to path stem match."""
        clean = title.strip().rstrip("\\")

        # Exact title match within the same vault
        if vault is not None:
            rows = self.db.execute(
                "SELECT path FROM library_notes WHERE LOWER(title) = LOWER(?) AND vault = ? ORDER BY mtime DESC LIMIT 1",
                (clean, vault),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT path FROM library_notes WHERE LOWER(title) = LOWER(?) ORDER BY mtime DESC LIMIT 1",
                (clean,),
            ).fetchall()
        if rows:
            return rows[0]["path"]

        # Path stem match
        stem = Path(clean).stem
        if vault is not None:
            rows = self.db.execute(
                "SELECT path FROM library_notes WHERE LOWER(path) LIKE LOWER(?) AND vault = ? ORDER BY mtime DESC LIMIT 1",
                (f"%/{stem}.md", vault),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT path FROM library_notes WHERE LOWER(path) LIKE LOWER(?) ORDER BY mtime DESC LIMIT 1",
                (f"%/{stem}.md",),
            ).fetchall()
        return rows[0]["path"] if rows else None

    def _invalidate_cache(self) -> None:
        self._cache_dirty = True

    def _resolve_vault_from_path(self, relative_path: str) -> str:
        """Library notes are always in the 'library' vault."""
        parts = Path(relative_path).parts
        if len(parts) >= 2 and parts[0] == "knowledge" and parts[1] == "library":
            return "library"
        return "library"

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def write_note(self, relative_path: str, content: str) -> None:
        """Write content to a note file."""
        full_path = self._resolve_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def read_note(self, relative_path: str) -> str:
        """Read the full content of a note."""
        full_path = self._resolve_path(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Note not found: {relative_path}")
        return full_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Core indexing
    # ------------------------------------------------------------------

    def update_note(self, relative_path: str, force: bool = False) -> None:
        """Read a markdown file, extract title and [[links]], and update the library index.

        Only indexes files under knowledge/library/. Non-library paths are silently ignored.
        """
        parts = Path(relative_path).parts
        if not (len(parts) >= 2 and parts[0] == "knowledge" and parts[1] == "library"):
            logger.debug(f"LibraryNoteEngine ignoring non-library path: {relative_path}")
            return

        full_path = self._resolve_path(relative_path)

        if not full_path.exists():
            self.db.execute("DELETE FROM library_notes WHERE path = ?", (relative_path,))
            self.db.commit()
            self._invalidate_cache()
            return

        current_mtime = full_path.stat().st_mtime
        row = self.db.execute(
            "SELECT mtime FROM library_notes WHERE path = ?", (relative_path,)
        ).fetchone()

        if not force and row and abs(row["mtime"] - current_mtime) < 0.001:
            return

        content = full_path.read_text(encoding="utf-8")
        title = self._extract_title(content, relative_path)
        raw_links = re.findall(r"\[\[(.*?)\]\]", content)
        links = [re.split(r"\\?\|", link, maxsplit=1)[0].strip().rstrip("\\") for link in raw_links]
        tags = self._extract_tags(content)

        vault = self._resolve_vault_from_path(relative_path)

        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO library_notes
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

            # Preserve unresolved links
            existing_unresolved = {
                row["to_title"]
                for row in self.db.execute(
                    "SELECT to_title FROM library_note_links WHERE from_path = ? AND to_path IS NULL",
                    (relative_path,),
                ).fetchall()
            }
            self.db.execute("DELETE FROM library_note_links WHERE from_path = ?", (relative_path,))
            inserted_titles: set[str] = set()
            for raw_title in links:
                clean_title = raw_title.strip()
                to_path = self._resolve_title(clean_title, vault)
                self.db.execute(
                    "INSERT INTO library_note_links (from_path, to_title, to_path) VALUES (?, ?, ?)",
                    (relative_path, clean_title, to_path),
                )
                inserted_titles.add(clean_title)
            for title in existing_unresolved:
                if title not in inserted_titles:
                    self.db.execute(
                        "INSERT INTO library_note_links (from_path, to_title, to_path) VALUES (?, ?, NULL)",
                        (relative_path, title),
                    )

            # Update tags
            self.db.execute("DELETE FROM library_note_tags WHERE note_path = ?", (relative_path,))
            for tag in tags:
                self.db.execute("INSERT OR IGNORE INTO library_tags (name) VALUES (?)", (tag,))
                tag_row = self.db.execute(
                    "SELECT id FROM library_tags WHERE name = ?", (tag,)
                ).fetchone()
                if tag_row:
                    self.db.execute(
                        "INSERT OR IGNORE INTO library_note_tags (tag_id, note_path) VALUES (?, ?)",
                        (tag_row["id"], relative_path),
                    )

        self._invalidate_cache()
        logger.debug(f"Indexed library note: {relative_path}")

    def remove_note(self, relative_path: str) -> None:
        """Remove a note from the library index."""
        self.db.execute("DELETE FROM library_notes WHERE path = ?", (relative_path,))
        self.db.commit()
        self._invalidate_cache()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_notes(
        self, query: str, limit: int = 20, vault_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Fuzzy search library notes by path or title."""
        stripped = query.strip()
        if not stripped:
            return []

        vault_cond = ""
        vault_args: tuple = ()
        if vault_filter:
            vault_cond = " AND vault = ?"
            vault_args = (vault_filter,)

        # Exact title match
        row = self.db.execute(
            f"SELECT path, title, mtime, word_count FROM library_notes WHERE title = ?{vault_cond} LIMIT 1",
            (stripped,) + vault_args,
        ).fetchone()
        if row:
            return [
                {
                    "path": row["path"],
                    "title": row["title"],
                    "mtime": row["mtime"],
                    "word_count": row["word_count"],
                }
            ]

        # Path stem match
        row = self.db.execute(
            f"SELECT path, title, mtime, word_count FROM library_notes WHERE path LIKE ?{vault_cond} LIMIT 1",
            (f"%/{stripped}.md",) + vault_args,
        ).fetchone()
        if row:
            return [
                {
                    "path": row["path"],
                    "title": row["title"],
                    "mtime": row["mtime"],
                    "word_count": row["word_count"],
                }
            ]

        # FTS5 match
        try:
            vault_join = ""
            fts_args: tuple = ()
            if vault_filter:
                vault_join = " AND n.vault = ?"
                fts_args = (vault_filter,)
            rows = self.db.execute(
                f"""
                SELECT n.path, n.title, n.mtime, n.word_count, rank
                FROM library_notes_fts
                JOIN library_notes n ON library_notes_fts.rowid = n.rowid
                WHERE library_notes_fts MATCH ?{vault_join}
                ORDER BY rank
                LIMIT ?
                """,
                (stripped,) + fts_args + (limit,),
            ).fetchall()
            if rows:
                return [
                    {
                        "path": r["path"],
                        "title": r["title"],
                        "mtime": r["mtime"],
                        "word_count": r["word_count"],
                        "rank": r["rank"],
                    }
                    for r in rows
                ]
        except Exception:
            pass

        # Fallback LIKE
        pattern = f"%{stripped}%"
        rows = self.db.execute(
            f"""
            SELECT path, title, mtime, word_count FROM library_notes
            WHERE (path LIKE ? OR title LIKE ?){vault_cond}
            ORDER BY mtime DESC
            LIMIT ?
            """,
            (pattern, pattern) + vault_args + (limit,),
        ).fetchall()
        return [
            {
                "path": r["path"],
                "title": r["title"],
                "mtime": r["mtime"],
                "word_count": r["word_count"],
            }
            for r in rows
        ]

    def search_notes_fts(
        self, query: str, limit: int = 20, vault_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Full-text search using SQLite FTS5 with BM25 ranking."""
        try:
            vault_join = ""
            args: tuple = ()
            if vault_filter:
                vault_join = " AND n.vault = ?"
                args = (vault_filter,)
            rows = self.db.execute(
                f"""
                SELECT n.path, n.title, n.mtime, n.word_count, rank
                FROM library_notes_fts
                JOIN library_notes n ON library_notes_fts.rowid = n.rowid
                WHERE library_notes_fts MATCH ?{vault_join}
                ORDER BY rank
                LIMIT ?
                """,
                (query,) + args + (limit,),
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
            logger.warning(f"Library FTS5 search failed: {e}")
        return []

    def rebuild_fts_index(self) -> None:
        """Rebuild the FTS5 index from scratch."""
        try:
            self.db.execute("DELETE FROM library_notes_fts")
            self.db.execute("""
                INSERT INTO library_notes_fts(rowid, title, content)
                SELECT rowid, title, content FROM library_notes
                WHERE content IS NOT NULL
                """)
            self.db.commit()
            logger.info("Rebuilt library FTS5 index")
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to rebuild library FTS5 index: {e}")

    def _ensure_fts_populated(self) -> None:
        """Ensure FTS5 index is populated if table exists but is empty."""
        try:
            fts_count = self.db.execute("SELECT COUNT(*) FROM library_notes_fts").fetchone()[0]
            node_count = self.db.execute("SELECT COUNT(*) FROM library_notes").fetchone()[0]
            if fts_count == 0 and node_count > 0:
                logger.info("Library FTS5 index empty, rebuilding from existing notes")
                self.rebuild_fts_index()
        except sqlite3.OperationalError:
            pass

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def get_tags(self, vault_filter: str | None = None) -> list[dict[str, Any]]:
        """Return all tags with usage counts."""
        if vault_filter:
            rows = self.db.execute(
                """
                SELECT t.name, COUNT(nt.note_path) as count
                FROM library_tags t
                JOIN library_note_tags nt ON t.id = nt.tag_id
                JOIN library_notes n ON nt.note_path = n.path
                WHERE n.vault = ?
                GROUP BY t.id
                ORDER BY count DESC, t.name ASC
                """,
                (vault_filter,),
            ).fetchall()
        else:
            rows = self.db.execute("""
                SELECT t.name, COUNT(nt.note_path) as count
                FROM library_tags t
                LEFT JOIN library_note_tags nt ON t.id = nt.tag_id
                GROUP BY t.id
                ORDER BY count DESC, t.name ASC
                """).fetchall()
        return [{"name": r["name"], "count": r["count"]} for r in rows]

    def get_node_tags(self, path: str) -> list[str]:
        """Return tags for a specific note."""
        rows = self.db.execute(
            """
            SELECT t.name FROM library_tags t
            JOIN library_note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_path = ?
            ORDER BY t.name ASC
            """,
            (path,),
        ).fetchall()
        return [r["name"] for r in rows]

    def search_by_tag(self, tag: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search notes by tag name."""
        rows = self.db.execute(
            """
            SELECT n.path, n.title, n.mtime FROM library_notes n
            JOIN library_note_tags nt ON n.path = nt.note_path
            JOIN library_tags t ON t.id = nt.tag_id
            WHERE t.name = ?
            ORDER BY n.mtime DESC
            LIMIT ?
            """,
            (tag.lower(), limit),
        ).fetchall()
        return [{"path": r["path"], "title": r["title"], "mtime": r["mtime"]} for r in rows]

    def list_vaults(self) -> list[dict[str, Any]]:
        """Return all vaults with note counts."""
        rows = self.db.execute("""
            SELECT vault, COUNT(*) as note_count
            FROM library_notes
            GROUP BY vault
            ORDER BY vault ASC
            """).fetchall()
        return [{"name": r["vault"], "note_count": r["note_count"]} for r in rows]

    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------

    def get_graph(
        self,
        center_path: str | None = None,
        depth: int = 1,
        limit: int = 200,
        tag_filter: str | None = None,
        vault_filter: str | None = None,
    ) -> dict[str, Any]:
        """Return a subgraph as {nodes, edges}."""
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

        visited: set[str] = {center_path} if _include_node(center_path) else set()
        queue: deque[tuple[str, int]] = (
            deque([(center_path, 0)]) if _include_node(center_path) else deque()
        )

        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for target in cache["adj_out"].get(current, []):
                if target not in visited and _include_node(target):
                    visited.add(target)
                    queue.append((target, d + 1))
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
        for row in self.db.execute("SELECT path, title, type, mtime FROM library_notes").fetchall():
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
            "SELECT from_path, to_title, to_path FROM library_note_links"
        ).fetchall():
            src = row["from_path"]
            to_title = row["to_title"].strip().rstrip("\\")
            tgt = row["to_path"] or title_to_path.get(to_title.lower())
            if not tgt:
                stem = Path(to_title).stem.lower()
                tgt = stem_to_path.get(stem)
            if src in nodes and tgt and tgt in nodes:
                edges.append({"source": src, "target": tgt})
                adj_out.setdefault(src, []).append(tgt)
                adj_in.setdefault(tgt, []).append(src)

        node_tags: dict[str, list[str]] = {}
        for row in self.db.execute(
            "SELECT nt.note_path, t.name FROM library_note_tags nt JOIN library_tags t ON nt.tag_id = t.id"
        ).fetchall():
            node_tags.setdefault(row["note_path"], []).append(row["name"])

        node_vaults: dict[str, str] = {}
        for row in self.db.execute("SELECT path, vault FROM library_notes").fetchall():
            node_vaults[row["path"]] = row["vault"]

        for node_path in nodes:
            nodes[node_path]["tags"] = node_tags.get(node_path, [])
            nodes[node_path]["vault"] = node_vaults.get(node_path, "library")

        self._cache = {
            "nodes": nodes,
            "edges": edges,
            "adj_out": adj_out,
            "adj_in": adj_in,
            "node_tags": node_tags,
            "node_vaults": node_vaults,
        }
        self._cache_dirty = False

    # ------------------------------------------------------------------
    # Single note queries
    # ------------------------------------------------------------------

    def get_note(self, relative_path: str) -> dict[str, Any] | None:
        """Return metadata for a single library note."""
        row = self.db.execute(
            "SELECT path, title, mtime, word_count, updated_at, vault FROM library_notes WHERE path = ?",
            (relative_path,),
        ).fetchone()
        if not row:
            return None
        return {
            "path": row["path"],
            "title": row["title"],
            "mtime": row["mtime"],
            "word_count": row["word_count"],
            "updated_at": row["updated_at"],
            "vault": row["vault"],
            "tags": self.get_node_tags(relative_path),
        }

    def get_timeline(self, relative_path: str, vault_filter: str | None = None) -> dict[str, Any]:
        """Return contextual timeline and metadata for a library note."""
        row = self.db.execute(
            "SELECT path, title, mtime, word_count, updated_at, vault FROM library_notes WHERE path = ?",
            (relative_path,),
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"Library note not found: {relative_path}")

        # Links (outgoing)
        outgoing_rows = self.db.execute(
            "SELECT to_title, to_path FROM library_note_links WHERE from_path = ?",
            (relative_path,),
        ).fetchall()

        # Links (incoming)
        incoming_rows = self.db.execute(
            "SELECT from_path FROM library_note_links WHERE to_path = ?",
            (relative_path,),
        ).fetchall()

        outgoing = [{"title": r["to_title"], "path": r["to_path"]} for r in outgoing_rows]
        incoming = [{"path": r["from_path"]} for r in incoming_rows]

        tags = self.get_node_tags(relative_path)

        # Related notes
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
                SELECT DISTINCT nt.note_path FROM library_note_tags nt
                JOIN library_tags t ON nt.tag_id = t.id
                WHERE t.name IN ({placeholders}) AND nt.note_path != ?
                """,
                (*tags, relative_path),
            ).fetchall()
            for tr in tag_rows:
                related_paths.add(tr["note_path"])

        related = []
        if related_paths:
            placeholders = ",".join("?" * len(related_paths))
            rel_rows = self.db.execute(
                f"""
                SELECT path, title, mtime, word_count FROM library_notes
                WHERE path IN ({placeholders})
                ORDER BY mtime DESC
                LIMIT 10
                """,
                tuple(related_paths),
            ).fetchall()
            related = [
                {
                    "path": r["path"],
                    "title": r["title"],
                    "mtime": r["mtime"],
                    "word_count": r["word_count"],
                }
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
