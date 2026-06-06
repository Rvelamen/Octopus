"""Library note tools for agent integration.

Completely separate from knowledge base tools. These tools operate on
library_notes / library_note_links / library_tags tables.
"""

from typing import Any

from backend.tools.base import Tool


class LibrarySearchTool(Tool):
    """Search the library note index for AI-generated notes."""

    def __init__(self, vault_filter: str | None = None, name_override: str | None = None):
        self._vault_filter = vault_filter
        self._name_override = name_override

    @property
    def name(self) -> str:
        return self._name_override or "library_search"

    @property
    def description(self) -> str:
        base = (
            "Search the user's library notes for markdown notes that match a query. "
            "Uses full-text search (FTS5) across titles and note contents, ranked by relevance. "
            "Returns a list of note paths and titles. Use this when the user asks about "
            "a topic that might be covered in their library notes (e.g. paper summaries, "
            "AI-generated extracts). Prefer this over guessing note titles."
        )
        if self._vault_filter:
            base += f" Only searches notes in the '{self._vault_filter}' vault."
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
        from backend.services.library_note_engine import LibraryNoteEngine
        from backend.utils.helpers import get_workspace_path

        engine = LibraryNoteEngine(str(get_workspace_path()))

        results = engine.search_notes_fts(
            query,
            limit=limit,
            vault_filter=self._vault_filter,
        )
        if not results:
            results = engine.search_notes(
                query,
                limit=limit,
                vault_filter=self._vault_filter,
            )

        if not results:
            return "No matching library notes found."
        lines = [f"Found {len(results)} library note(s):"]
        for r in results:
            rank_info = f", relevance: {r['rank']}" if "rank" in r else ""
            estimated_tokens = int((r.get("word_count") or 0) * 1.5)
            lines.append(
                f"- {r['path']} (title: {r['title']}{rank_info}, estimated_tokens: ~{estimated_tokens})"
            )
        return "\n".join(lines)


class LibraryReadNoteTool(Tool):
    """Read the full content of a library note."""

    def __init__(self, name_override: str | None = None):
        self._name_override = name_override

    @property
    def name(self) -> str:
        return self._name_override or "library_read_note"

    @property
    def description(self) -> str:
        return (
            "Read the full Markdown content of a library note by its relative path. "
            "Use this after library_search to retrieve the actual content of a note."
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
                        "(e.g., 'knowledge/library/papers/my_paper.md')."
                    ),
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        from pathlib import Path

        from backend.utils.helpers import get_workspace_path

        file_path = Path(path).expanduser()
        workspace = get_workspace_path()
        if not file_path.is_absolute():
            file_path = workspace / file_path

        if not file_path.exists():
            return f"Library note not found: {path}"

        try:
            content = file_path.read_text(encoding="utf-8")
            return content
        except Exception as e:
            return f"Error reading library note: {str(e)}"


class LibraryTimelineTool(Tool):
    """Preview a library note's context before reading: links, tags, and related notes."""

    def __init__(self, vault_filter: str | None = None, name_override: str | None = None):
        self._vault_filter = vault_filter
        self._name_override = name_override

    @property
    def name(self) -> str:
        return self._name_override or "library_timeline"

    @property
    def description(self) -> str:
        base = (
            "Get a contextual preview of a library note before reading it. "
            "Returns the note's metadata, outgoing/incoming wiki-links, tags, and "
            "recently modified related notes. Use this after library_search to decide "
            "which notes are worth reading with library_read_note."
        )
        if self._vault_filter:
            base += f" Only works with notes in the '{self._vault_filter}' vault."
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
                        "(e.g., 'knowledge/library/papers/my_paper.md')."
                    ),
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        from backend.services.library_note_engine import LibraryNoteEngine
        from backend.utils.helpers import get_workspace_path

        engine = LibraryNoteEngine(str(get_workspace_path()))

        # Enforce vault isolation
        node = engine.get_note(path)
        if not node:
            return f"Library note not found: {path}"
        if self._vault_filter and node.get("vault") != self._vault_filter:
            return f"Library note not found: {path}"

        try:
            timeline = engine.get_timeline(path)
        except FileNotFoundError:
            return f"Library note not found: {path}"

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


class LibraryWriteNoteTool(Tool):
    """Write or overwrite a library note, automatically indexing it."""

    @property
    def name(self) -> str:
        return "library_write_note"

    @property
    def description(self) -> str:
        return (
            "Write or overwrite a library note. If the note already exists, "
            "it will be overwritten with the new content. The note is automatically "
            "indexed: [[wiki-links]], #tags, and the title (from the first # heading) "
            "are extracted and registered in the library graph. "
            "Use this to create new library notes or update existing ones."
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
                        "(e.g., 'knowledge/library/papers/my_paper.md'). "
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
        from backend.utils.helpers import get_workspace_path

        if not path.endswith(".md"):
            return f"Error: note path must end with .md, got: {path}"

        workspace = str(get_workspace_path())
        from backend.services.library_note_engine import LibraryNoteEngine

        engine = LibraryNoteEngine(workspace)
        engine.write_note(path, content)
        engine.update_note(path, force=True)

        word_count = len(content.split())
        title = engine._extract_title(content, path)
        return (
            f"Note written and indexed to library graph: {path}\n"
            f"Title: {title}\n"
            f"Words: {word_count} (estimated_tokens: ~{int(word_count * 1.5)})"
        )


class LibraryListLinksTool(Tool):
    """List bidirectional links for a given library note path."""

    def __init__(self, vault_filter: str | None = None, name_override: str | None = None):
        self._vault_filter = vault_filter
        self._name_override = name_override

    @property
    def name(self) -> str:
        return self._name_override or "library_list_links"

    @property
    def description(self) -> str:
        base = (
            "List the outgoing and/or incoming [[wiki-style links]] for a library note. "
            "Use this to explore the library note graph around a note after reading it."
        )
        if self._vault_filter:
            base += f" Only works with notes in the '{self._vault_filter}' vault."
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
        from backend.services.library_note_engine import LibraryNoteEngine
        from backend.utils.helpers import get_workspace_path

        engine = LibraryNoteEngine(str(get_workspace_path()))

        # Enforce vault isolation
        node = engine.get_note(path)
        if not node:
            return f"Library note not found: {path}"
        if self._vault_filter and node.get("vault") != self._vault_filter:
            return f"Library note not found: {path}"

        graph = engine.get_graph(
            center_path=path,
            depth=1,
            vault_filter=self._vault_filter,
        )
        edges = graph.get("edges", [])

        outgoing = []
        incoming = []
        for e in edges:
            if e.get("source") == path:
                outgoing.append(e.get("target"))
            if e.get("target") == path:
                incoming.append(e.get("source"))

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
            return "No links found for this library note."
        return "\n".join(lines)
