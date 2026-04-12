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
            "Returns a list of note paths and titles. Use this when the user asks about "
            "a topic that might be covered in their notes, or when you need to find a "
            "specific note before reading it."
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
        results = engine.search_notes(query, limit=limit)
        if not results:
            return "No matching notes found."
        lines = [f"Found {len(results)} note(s):"]
        for r in results:
            lines.append(f'- {r["path"]} (title: {r["title"]})')
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
