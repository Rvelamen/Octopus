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
        ]
        for pragma in pragmas:
            self.db.execute(pragma)

        run_knowledge_index_migrations(self.db_path)

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

    def _resolve_title(self, title: str) -> Optional[str]:
        """Case-insensitive title match; returns the most recently modified path."""
        row = self.db.execute(
            "SELECT path FROM knowledge_nodes WHERE LOWER(title) = LOWER(?) ORDER BY mtime DESC LIMIT 1",
            (title.strip(),),
        ).fetchone()
        return row["path"] if row else None

    def _invalidate_cache(self) -> None:
        """Mark the graph cache as dirty."""
        self._cache_dirty = True

    def update_note(self, relative_path: str) -> None:
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

        if row and abs(row["mtime"] - current_mtime) < 0.001:
            return  # No change

        content = full_path.read_text(encoding="utf-8")
        title = self._extract_title(content, relative_path)
        links = re.findall(r"\[\[(.*?)\]\]", content)
        tags = self._extract_tags(content)

        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO knowledge_nodes
                (path, title, type, mtime, word_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relative_path,
                    title,
                    "note",
                    current_mtime,
                    len(content.split()),
                    datetime.now().isoformat(),
                ),
            )
            self.db.execute(
                "DELETE FROM knowledge_links WHERE from_path = ?",
                (relative_path,),
            )
            for raw_title in links:
                clean_title = raw_title.strip()
                to_path = self._resolve_title(clean_title)
                self.db.execute(
                    "INSERT INTO knowledge_links (from_path, to_title, to_path) VALUES (?, ?, ?)",
                    (relative_path, clean_title, to_path),
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
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(self.workspace_root)),
                    "is_directory": entry.is_dir(),
                    "size": stat.st_size if entry.is_file() else 0,
                    "mtime": stat.st_mtime,
                }
            )
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

    def search_notes(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fuzzy search notes by path or title."""
        pattern = f"%{query}%"
        rows = self.db.execute(
            """
            SELECT path, title, mtime FROM knowledge_nodes
            WHERE path LIKE ? OR title LIKE ?
            ORDER BY mtime DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [{"path": r["path"], "title": r["title"], "mtime": r["mtime"]} for r in rows]

    def get_tags(self) -> list[dict[str, Any]]:
        """Return all tags with usage counts."""
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
        self, center_path: Optional[str] = None, depth: int = 1, limit: int = 200, tag_filter: Optional[str] = None
    ) -> dict[str, Any]:
        """Return a subgraph as {nodes, edges}.

        If center_path is given, perform BFS up to `depth` layers using both
        outgoing and incoming links. Otherwise return the whole graph up to
        `limit` nodes.
        If tag_filter is given, only include nodes that have the tag.
        """
        if self._cache_dirty or self._cache is None:
            self._rebuild_cache()

        cache = self._cache
        assert cache is not None

        all_nodes: dict[str, dict[str, Any]] = {}
        all_edges: list[dict[str, Any]] = []

        def _include_node(key: str) -> bool:
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
        for row in self.db.execute(
            "SELECT from_path, to_title, to_path FROM knowledge_links"
        ).fetchall():
            src = row["from_path"]
            tgt = row["to_path"] or title_to_path.get(row["to_title"].lower())
            if src in nodes and tgt in nodes:
                edges.append({"source": src, "target": tgt})
                adj_out.setdefault(src, []).append(tgt)
                adj_in.setdefault(tgt, []).append(src)

        node_tags: dict[str, list[str]] = {}
        for row in self.db.execute(
            "SELECT nt.node_path, t.name FROM knowledge_node_tags nt JOIN knowledge_tags t ON nt.tag_id = t.id"
        ).fetchall():
            node_tags.setdefault(row["node_path"], []).append(row["name"])
        for node_path in nodes:
            nodes[node_path]["tags"] = node_tags.get(node_path, [])

        self._cache = {"nodes": nodes, "edges": edges, "adj_out": adj_out, "adj_in": adj_in, "node_tags": node_tags}
        self._cache_dirty = False

    def delete_note(self, relative_path: str) -> None:
        """Delete the note file and clean up its index entries."""
        full_path = self._resolve_path(relative_path)
        if full_path.exists():
            full_path.unlink()

        self.db.execute("DELETE FROM knowledge_nodes WHERE path = ?", (relative_path,))
        self.db.commit()
        self._invalidate_cache()
        logger.debug(f"Deleted note: {relative_path}")
