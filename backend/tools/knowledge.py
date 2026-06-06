"""Knowledge base tools for agent integration."""

from typing import Any

from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.tools.base import Tool


class KBSearchTool(Tool):
    """Search the knowledge base for notes by path or title."""

    def __init__(self, vault_filter: str | None = None, exclude_vault: str | None = None):
        self._vault_filter = vault_filter
        self._exclude_vault = exclude_vault

    @property
    def name(self) -> str:
        return "kb_search"

    @property
    def description(self) -> str:
        base = (
            "Search the user's knowledge base for markdown notes that match a query. "
            "Uses full-text search (FTS5) across titles and note contents, ranked by relevance. "
            "Returns a list of note paths and titles. Use this when the user asks about "
            "a topic that might be covered in their notes, or when you need to find a "
            "specific note before reading it. Prefer this over guessing note titles."
        )
        if self._vault_filter:
            base += f" Only searches notes in the '{self._vault_filter}' vault."
        elif self._exclude_vault:
            base += f" Excludes notes in the '{self._exclude_vault}' vault."
        return base

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or phrase to match against note paths and titles.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 10, **kwargs: Any) -> str:
        from backend.utils.helpers import get_workspace_path

        engine = KnowledgeGraphEngine(str(get_workspace_path()))

        # Prefer FTS5 full-text search
        results = engine.search_notes_fts(
            query,
            limit=limit,
            vault_filter=self._vault_filter,
            exclude_vault=self._exclude_vault,
        )
        if not results:
            results = engine.search_notes(
                query,
                limit=limit,
                vault_filter=self._vault_filter,
                exclude_vault=self._exclude_vault,
            )

        if not results:
            return "No matching notes found."
        lines = [f"Found {len(results)} note(s):"]
        for r in results:
            rank_info = f", relevance: {r['rank']}" if "rank" in r else ""
            estimated_tokens = int((r.get("word_count") or 0) * 1.5)
            lines.append(
                f"- {r['path']} (title: {r['title']}{rank_info}, estimated_tokens: ~{estimated_tokens})"
            )
        return "\n".join(lines)


class KBWriteNoteTool(Tool):
    """Write or overwrite a knowledge base note, automatically indexing it."""

    @property
    def name(self) -> str:
        return "kb_write_note"

    @property
    def description(self) -> str:
        return (
            "Write or overwrite a knowledge base note. If the note already exists, "
            "it will be overwritten with the new content. The note is automatically "
            "indexed: [[wiki-links]], #tags, and the title (from the first # heading) "
            "are extracted and registered in the knowledge graph. "
            "Use this to create new notes or update existing ones."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path of the note inside the workspace "
                        "(e.g., 'knowledge/notes/my_note.md'). "
                        "Parent directories are created automatically if needed."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "Full markdown content of the note.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        from pathlib import Path

        from backend.utils.helpers import get_workspace_path

        if not path.endswith(".md"):
            return f"Error: note path must end with .md, got: {path}"

        workspace = str(get_workspace_path())
        parts = Path(path).parts
        is_library = len(parts) >= 2 and parts[0] == "knowledge" and parts[1] == "library"

        if is_library:
            from backend.services.library_note_engine import LibraryNoteEngine

            engine = LibraryNoteEngine(workspace)
        else:
            engine = KnowledgeGraphEngine(workspace)

        engine.write_note(path, content)
        engine.update_note(path, force=True)

        word_count = len(content.split())
        title = engine._extract_title(content, path)
        system = "library" if is_library else "knowledge"
        return (
            f"Note written and indexed to {system} graph: {path}\n"
            f"Title: {title}\n"
            f"Words: {word_count} (estimated_tokens: ~{int(word_count * 1.5)})"
        )


class KBReadNoteTool(Tool):
    """Read the full content of a knowledge base note."""

    @property
    def name(self) -> str:
        return "kb_read_note"

    @property
    def description(self) -> str:
        return (
            "Read the full Markdown content of a knowledge base note by its relative path. "
            "Use this after kb_search to retrieve the actual content of a note."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path of the note inside the workspace "
                        "(e.g., 'knowledge/notes/my_note.md')."
                    ),
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        from backend.utils.helpers import get_workspace_path

        engine = KnowledgeGraphEngine(str(get_workspace_path()))
        try:
            content = engine.read_note(path)
            return content
        except FileNotFoundError:
            return f"Note not found: {path}"


class KBTimelineTool(Tool):
    """Preview a note's context before reading: links, tags, and related notes."""

    def __init__(self, vault_filter: str | None = None, exclude_vault: str | None = None):
        self._vault_filter = vault_filter
        self._exclude_vault = exclude_vault

    @property
    def name(self) -> str:
        return "kb_timeline"

    @property
    def description(self) -> str:
        base = (
            "Get a contextual preview of a knowledge base note before reading it. "
            "Returns the note's metadata, outgoing/incoming wiki-links, tags, and "
            "recently modified related notes. Use this after kb_search to decide "
            "which notes are worth reading with kb_read_note."
        )
        if self._vault_filter:
            base += f" Only works with notes in the '{self._vault_filter}' vault."
        elif self._exclude_vault:
            base += f" Excludes notes in the '{self._exclude_vault}' vault."
        return base

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path of the note inside the workspace "
                        "(e.g., 'knowledge/notes/my_note.md')."
                    ),
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        from backend.utils.helpers import get_workspace_path

        engine = KnowledgeGraphEngine(str(get_workspace_path()))
        # Enforce vault isolation
        node = engine.db.execute(
            "SELECT vault FROM knowledge_nodes WHERE path = ?", (path,)
        ).fetchone()
        if not node:
            return f"Note not found: {path}"
        if self._vault_filter and node["vault"] != self._vault_filter:
            return f"Note not found: {path}"
        if self._exclude_vault and node["vault"] == self._exclude_vault:
            return f"Note not found: {path}"
        try:
            timeline = engine.get_timeline(
                path,
                vault_filter=self._vault_filter,
                exclude_vault=self._exclude_vault,
            )
        except FileNotFoundError:
            return f"Note not found: {path}"

        lines = [
            f"Note: {timeline['path']}",
            f"Title: {timeline['title']}",
            f"Words: {timeline['word_count']} (estimated_tokens: ~{int(timeline['word_count'] * 1.5)})",
            f"Last modified: {timeline['mtime']}",
        ]

        if timeline["tags"]:
            lines.append(f"Tags: {', '.join(timeline['tags'])}")

        if timeline["outgoing_links"]:
            lines.append("Outgoing links:")
            for link in timeline["outgoing_links"]:
                target = link.get("path") or link["title"]
                lines.append(f"- {target}")

        if timeline["incoming_links"]:
            lines.append("Incoming links:")
            for link in timeline["incoming_links"]:
                lines.append(f"- {link['path']}")

        if timeline["related_notes"]:
            lines.append("Recently modified related notes:")
            for note in timeline["related_notes"]:
                est = int((note.get("word_count") or 0) * 1.5)
                lines.append(f"- {note['path']} (title: {note['title']}, estimated_tokens: ~{est})")

        return "\n".join(lines)


class KBListLinksTool(Tool):
    """List bidirectional links for a given note path."""

    def __init__(self, vault_filter: str | None = None, exclude_vault: str | None = None):
        self._vault_filter = vault_filter
        self._exclude_vault = exclude_vault

    @property
    def name(self) -> str:
        return "kb_list_links"

    @property
    def description(self) -> str:
        base = (
            "List the outgoing and/or incoming [[wiki-style links]] for a knowledge base note. "
            "Use this to explore the knowledge graph around a note after reading it."
        )
        if self._vault_filter:
            base += f" Only works with notes in the '{self._vault_filter}' vault."
        elif self._exclude_vault:
            base += f" Excludes notes in the '{self._exclude_vault}' vault."
        return base

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the note.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["both", "outgoing", "incoming"],
                    "description": (
                        "Which links to return: 'outgoing' (this note links to others), "
                        "'incoming' (other notes link to this one), or 'both'."
                    ),
                    "default": "both",
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, direction: str = "both", **kwargs: Any) -> str:
        from backend.utils.helpers import get_workspace_path

        engine = KnowledgeGraphEngine(str(get_workspace_path()))
        # Enforce vault isolation
        node = engine.db.execute(
            "SELECT vault FROM knowledge_nodes WHERE path = ?", (path,)
        ).fetchone()
        if not node:
            return f"Note not found: {path}"
        if self._vault_filter and node["vault"] != self._vault_filter:
            return f"Note not found: {path}"
        if self._exclude_vault and node["vault"] == self._exclude_vault:
            return f"Note not found: {path}"
        graph = engine.get_graph(
            center_path=path,
            depth=1,
            vault_filter=self._vault_filter,
            exclude_vault=self._exclude_vault,
        )
        edges = graph.get("edges", [])

        outgoing = []
        incoming = []
        for e in edges:
            if e.get("source") == path:
                outgoing.append(e.get("target"))
            if e.get("target") == path:
                incoming.append(e.get("source"))

        # deduplicate while preserving order
        outgoing = list(dict.fromkeys(outgoing))
        incoming = list(dict.fromkeys(incoming))

        lines = []
        if direction in ("both", "outgoing") and outgoing:
            lines.append("Outgoing links:")
            for target in outgoing:
                lines.append(f"- {target}")
        if direction in ("both", "incoming") and incoming:
            lines.append("Incoming links:")
            for source in incoming:
                lines.append(f"- {source}")
        if not lines:
            return "No links found for this note."
        return "\n".join(lines)
