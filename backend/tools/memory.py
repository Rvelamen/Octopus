"""Memory/observation tools for agent integration."""

from typing import Any

from backend.tools.base import Tool
from backend.data import Database, ObservationRepository


class MemorySearchTool(Tool):
    """Search the structured observation memory via FTS5."""

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "Search the agent's structured observation memory. "
            "Returns a compact index of observations with IDs, types, titles, and estimated token counts. "
            "Use this to find relevant past learnings, decisions, gotchas, or changes. "
            "After identifying interesting IDs, use `memory_read` to fetch full details."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or phrase to match against observation titles, narratives, and concepts.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "type_filter": {
                    "type": "string",
                    "description": (
                        "Optional filter by observation type. "
                        "Values: gotcha, problem-solution, how-it-works, what-changed, discovery, decision, trade-off, general"
                    ),
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        limit: int = 10,
        type_filter: str | None = None,
        **kwargs: Any,
    ) -> str:
        repo = ObservationRepository(Database())
        results = repo.search_fts(query, limit=limit, type_filter=type_filter)
        if not results:
            return "No matching observations found."

        type_icon = {
            "gotcha": "🔴",
            "problem-solution": "🟡",
            "how-it-works": "🔵",
            "what-changed": "🟢",
            "discovery": "🟣",
            "why-it-exists": "🟠",
            "decision": "🟤",
            "trade-off": "⚖️",
            "general": "⚪",
        }

        lines = [f"Found {len(results)} observation(s):"]
        for r in results:
            icon = type_icon.get(r.type, "⚪")
            lines.append(
                f'- #{r.id} [{icon} {r.type}] {r.title} (~{r.token_count} tokens)'
            )
        lines.append("")
        lines.append("Use `memory_read` with the observation ID to fetch full details.")
        return "\n".join(lines)


class MemoryReadTool(Tool):
    """Read the full content of an observation by ID."""

    @property
    def name(self) -> str:
        return "memory_read"

    @property
    def description(self) -> str:
        return (
            "Read the full content of a structured observation by its ID. "
            "Use this after `memory_search` to retrieve the actual narrative, files, and concepts."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "observation_id": {
                    "type": "integer",
                    "description": "The ID of the observation to read.",
                },
            },
            "required": ["observation_id"],
        }

    async def execute(self, observation_id: int, **kwargs: Any) -> str:
        repo = ObservationRepository(Database())
        record = repo.get_by_id(observation_id)
        if not record:
            return f"Observation #{observation_id} not found."

        icon = {
            "gotcha": "🔴",
            "problem-solution": "🟡",
            "how-it-works": "🔵",
            "what-changed": "🟢",
            "discovery": "🟣",
            "why-it-exists": "🟠",
            "decision": "🟤",
            "trade-off": "⚖️",
            "general": "⚪",
        }.get(record.type, "⚪")

        parts = [
            f"#{record.id} {icon} {record.type}: {record.title}",
            "-" * 40,
            f"**Narrative:**\n{record.narrative}",
        ]
        if record.files:
            parts.append(f"**Files:** {', '.join(record.files)}")
        if record.concepts:
            parts.append(f"**Concepts:** {', '.join(record.concepts)}")
        parts.append(f"**~Tokens:** {record.token_count}")
        return "\n\n".join(parts)


class MemoryTimelineTool(Tool):
    """Get chronological context around an observation."""

    @property
    def name(self) -> str:
        return "memory_timeline"

    @property
    def description(self) -> str:
        return (
            "Get chronological context around a specific observation. "
            "Returns observations that happened before and after the given ID. "
            "Use this to understand the narrative arc leading to a decision or fix."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "observation_id": {
                    "type": "integer",
                    "description": "The anchor observation ID.",
                },
                "depth_before": {
                    "type": "integer",
                    "description": "Number of observations to include before the anchor.",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                },
                "depth_after": {
                    "type": "integer",
                    "description": "Number of observations to include after the anchor.",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                },
            },
            "required": ["observation_id"],
        }

    async def execute(
        self,
        observation_id: int,
        depth_before: int = 2,
        depth_after: int = 2,
        **kwargs: Any,
    ) -> str:
        repo = ObservationRepository(Database())
        timeline = repo.get_timeline(observation_id, depth_before, depth_after)
        if not timeline:
            return f"No timeline context found for observation #{observation_id}."

        type_icon = {
            "gotcha": "🔴",
            "problem-solution": "🟡",
            "how-it-works": "🔵",
            "what-changed": "🟢",
            "discovery": "🟣",
            "why-it-exists": "🟠",
            "decision": "🟤",
            "trade-off": "⚖️",
            "general": "⚪",
        }

        lines = [f"Timeline around observation #{observation_id}:", ""]
        for r in timeline:
            marker = "👉" if r.id == observation_id else "  "
            icon = type_icon.get(r.type, "⚪")
            time_str = r.created_at.strftime("%H:%M") if r.created_at else ""
            lines.append(
                f"{marker} #{r.id} | {time_str} | {icon} {r.type} | {r.title}"
            )
        return "\n".join(lines)
