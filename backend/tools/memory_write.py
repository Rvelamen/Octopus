from typing import Any
import json

from backend.tools.base import Tool
from backend.agent.memory import MemoryStore


class MemoryWriteTool(Tool):
    def __init__(self, store: MemoryStore):
        self.store = store

    @property
    def name(self) -> str:
        return "memory_write"

    @property
    def description(self) -> str:
        return """Save durable information to persistent curated memory.

This is your personal notebook about the user and the environment. It survives across sessions.

WHEN TO SAVE (do this proactively, don't wait to be asked):
- User corrects you or says "remember this" / "don't do that again"
- User shares a preference, habit, or personal detail
- You discover something about the environment (OS, tools, project structure)
- You learn a convention, API quirk, or workflow specific to this user's setup
- You identify a stable fact that will be useful again in future sessions

TWO TARGETS:
- 'user': who the user is -- name, role, preferences, communication style, pet peeves
- 'memory': your notes -- environment facts, project conventions, tool quirks, lessons learned

ACTIONS:
- add: append a new entry
- replace: update an existing entry (old_text must uniquely identify it)
- remove: delete an entry (old_text must uniquely identify it)

SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, temporary task state.
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "replace", "remove"]},
                "target": {"type": "string", "enum": ["memory", "user"]},
                "content": {"type": "string", "description": "The entry content. Required for 'add' and 'replace'."},
                "old_text": {"type": "string", "description": "Short unique substring identifying the entry to replace or remove."},
            },
            "required": ["action", "target"],
        }

    async def execute(self, action: str, target: str, content: str = None, old_text: str = None, **kwargs) -> str:
        if action == "add":
            if not content:
                return json.dumps({"success": False, "error": "content is required for add"}, ensure_ascii=False)
            result = self.store.add(target, content)
        elif action == "replace":
            if not old_text or not content:
                return json.dumps({"success": False, "error": "old_text and content are required for replace"}, ensure_ascii=False)
            result = self.store.replace(target, old_text, content)
        elif action == "remove":
            if not old_text:
                return json.dumps({"success": False, "error": "old_text is required for remove"}, ensure_ascii=False)
            result = self.store.remove(target, old_text)
        else:
            return json.dumps({"success": False, "error": f"Unknown action: {action}"}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False)
