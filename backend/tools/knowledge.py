"""Knowledge base tools for agent integration."""

from typing import Any

from backend.tools.base import Tool
from backend.services.knowledge_engine import KnowledgeGraphEngine


class KBSearchTool(Tool):
    """Search the knowledge base for notes by path or title."""

    @property
    def name(self) -> str:
        return "kb_search"

    @property
    def description(self) -> str:
        return (
            "Search the user's knowledge base for markdown notes that match a query. "
            "Uses full-text search (FTS5) across titles and note contents, ranked by relevance. "
            "Returns a list of note paths and titles. Use this when the user asks about "
            "a topic that might be covered in their notes, or when you need to find a "
            "specific note before reading it. Prefer this over guessing note titles."
        )

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
        results = engine.search_notes_fts(query, limit=limit)
        if not results:
            results = engine.search_notes(query, limit=limit)

        if not results:
            return "No matching notes found."
        lines = [f"Found {len(results)} note(s):"]
        for r in results:
            rank_info = f", relevance: {r['rank']}" if "rank" in r else ""
            estimated_tokens = int((r.get("word_count") or 0) * 1.5)
            lines.append(
                f'- {r["path"]} (title: {r["title"]}{rank_info}, estimated_tokens: ~{estimated_tokens})'
            )
        return "\n".join(lines)


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

    @property
    def name(self) -> str:
        return "kb_timeline"

    @property
    def description(self) -> str:
        return (
            "Get a contextual preview of a knowledge base note before reading it. "
            "Returns the note's metadata, outgoing/incoming wiki-links, tags, and "
            "recently modified related notes. Use this after kb_search to decide "
            "which notes are worth reading with kb_read_note."
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
            timeline = engine.get_timeline(path)
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

    @property
    def name(self) -> str:
        return "kb_list_links"

    @property
    def description(self) -> str:
        return (
            "List the outgoing and/or incoming [[wiki-style links]] for a knowledge base note. "
            "Use this to explore the knowledge graph around a note after reading it."
        )

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
        graph = engine.get_graph(center_path=path, depth=1)
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
