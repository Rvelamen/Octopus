"""Notes Chat Agent — an independent, configurable agent for knowledge note conversations."""

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from backend.agent.config_service import AgentConfigService
from backend.agent.loader import SubAgentConfig, SubAgentLoader
from backend.agent.memory import MemoryStore
from backend.core.config.schema import AgentDefaults, ProviderConfig
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import create_provider
from backend.data import Database
from backend.data.provider_store import ModelRepository, ProviderRepository
from backend.extensions.loader import SkillsLoader
from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.services.notes_chat_service import NotesChatService
from backend.tools.action import ActionTool
from backend.tools.base import Tool
from backend.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from backend.tools.knowledge import (
    KBListLinksTool,
    KBReadNoteTool,
    KBTimelineTool,
    KBWriteNoteTool,
)
from backend.tools.memory import MemoryReadTool, MemorySearchTool, MemoryTimelineTool
from backend.tools.memory_write import MemoryWriteTool
from backend.tools.message import MessageTool
from backend.tools.registry import ToolRegistry
from backend.tools.shell import ExecTool


class ScopedKBSearchTool(Tool):
    """Search knowledge base notes within a scoped set of paths."""

    def __init__(self, scope_paths: list[str] | None = None, vault_filter: str | None = None):
        self._scope_paths = scope_paths or []
        self._vault_filter = vault_filter

    @property
    def name(self) -> str:
        return "kb_search"

    @property
    def description(self) -> str:
        return (
            "Search the user's knowledge base for markdown notes that match a query. "
            "Uses full-text search (FTS5) across titles and note contents, ranked by relevance. "
            "Returns a list of note paths and titles. Use this when the user asks about "
            "a topic that might be covered in their notes. "
            "Only searches notes within the current knowledge scope."
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
        results = engine.search_notes_fts(query, limit=limit * 2, vault_filter=self._vault_filter)
        if not results:
            results = engine.search_notes(query, limit=limit * 2, vault_filter=self._vault_filter)

        if not results:
            return "No matching notes found."

        # Filter by scope paths
        if self._scope_paths:
            filtered = []
            for r in results:
                path = r.get("path", "")
                for scope_path in self._scope_paths:
                    if path.startswith(scope_path):
                        filtered.append(r)
                        break
            results = filtered

        if not results:
            return "No matching notes found in the current scope."

        lines = [f"Found {len(results)} note(s) in scope:"]
        for r in results[:limit]:
            rank_info = f", relevance: {r['rank']}" if "rank" in r else ""
            estimated_tokens = int((r.get("word_count") or 0) * 1.5)
            lines.append(
                f"- {r['path']} (title: {r['title']}{rank_info}, estimated_tokens: ~{estimated_tokens})"
            )
        return "\n".join(lines)


class NotesChatAgent:
    """Independent agent for Notes chat with configurable tools, model, and system prompt."""

    def __init__(self, workspace: Path, db: Database | None = None):
        self.workspace = workspace
        self.db = db or Database()
        self.chat_service = NotesChatService(self.db)
        self.knowledge_engine = KnowledgeGraphEngine(str(workspace))
        self._config_service = AgentConfigService(self.db)
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace, self.db)

    async def chat(
        self,
        session_id: int,
        user_content: str,
        scope: dict[str, Any] | None = None,
        on_token: Callable[[str], Any] | None = None,
        on_tool_start: Callable[[dict], Any] | None = None,
        on_tool_result: Callable[[dict], Any] | None = None,
    ) -> str:
        """Process a user message in a Notes chat session and return the assistant response."""
        session = self.chat_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Save user message
        self.chat_service.add_message(
            session_id=session_id,
            role="user",
            content=user_content,
            metadata={"scope": scope},
        )

        # Load agent config
        agent_config = self._load_agent_config(session.agent_config_id)

        # Get provider, model, tools
        provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(
            agent_config
        )

        # Build scope context
        scope_paths = self._build_scope_paths(scope)
        scope_context = self._build_scope_context(scope)

        # Build system prompt
        system_prompt = self._build_system_prompt(
            agent_config, session.title, scope_context, scope_paths
        )

        # Build messages
        messages = self._build_messages(session_id, system_prompt, user_content)

        # Build tools with scope
        tools = self._build_tools_for_config(agent_config, scope_paths)

        # Run LLM with tool support
        final_content = ""
        accumulated_reasoning = ""
        iteration = 0
        max_iterations = agent_config.max_iterations if agent_config else 10

        while iteration < max_iterations:
            iteration += 1
            full_content = ""
            accumulated_reasoning = ""
            tool_calls_buffer: dict[str, dict] = {}

            try:
                async for chunk in provider.chat_stream(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ):
                    if chunk.content:
                        full_content += chunk.content
                        if on_token:
                            with contextlib.suppress(Exception):
                                on_token(chunk.content)

                    if chunk.reasoning_content:
                        accumulated_reasoning += chunk.reasoning_content

                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            if tc.id not in tool_calls_buffer:
                                tool_calls_buffer[tc.id] = {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "arguments": tc.arguments,
                                }
                                if on_tool_start:
                                    with contextlib.suppress(Exception):
                                        on_tool_start(
                                            {
                                                "tool": tc.name,
                                                "args": tc.arguments,
                                                "tool_call_id": tc.id,
                                            }
                                        )
                            else:
                                tool_calls_buffer[tc.id]["arguments"].update(tc.arguments)

            except Exception as e:
                logger.error(f"[NotesChatAgent] LLM call failed: {e}")
                raise

            if tool_calls_buffer:
                tool_calls_list = []
                for tc_data in tool_calls_buffer.values():
                    tool_calls_list.append(
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": json.dumps(tc_data["arguments"], ensure_ascii=False),
                            },
                        }
                    )
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": tool_calls_list,
                }
                if accumulated_reasoning:
                    assistant_msg["reasoning_content"] = accumulated_reasoning
                messages.append(assistant_msg)
                if full_content:
                    final_content = full_content

                # Persist assistant message with tool_calls
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content or "",
                    tool_calls=tool_calls_list,
                )
            else:
                if full_content:
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": full_content,
                    }
                    if accumulated_reasoning:
                        assistant_msg["reasoning_content"] = accumulated_reasoning
                    messages.append(assistant_msg)
                    final_content = full_content

                # Persist final assistant message
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content or "",
                )
                break

            # Execute tools and persist tool results
            for tc_data in tool_calls_buffer.values():
                tool_args = dict(tc_data.get("arguments", {}))
                try:
                    result = await tools.execute(tc_data["name"], tool_args)
                except Exception as e:
                    logger.error(f"[NotesChatAgent] Tool {tc_data['name']} failed: {e}")
                    result = f"Error: {e}"

                if on_tool_result:
                    with contextlib.suppress(Exception):
                        on_tool_result(
                            {
                                "tool": tc_data["name"],
                                "result": result,
                                "tool_call_id": tc_data["id"],
                            }
                        )

                messages.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tc_data["id"],
                    }
                )

                # Persist tool result
                self.chat_service.add_message(
                    session_id=session_id,
                    role="tool",
                    content=str(result),
                    tool_call_id=tc_data["id"],
                    metadata={"tool": tc_data["name"], "args": tc_data["arguments"]},
                )

        return final_content

    # ── Configuration ──

    def _load_agent_config(self, agent_config_id: int | None) -> SubAgentConfig | None:
        """Load agent config. Fallback to default if not found."""
        if agent_config_id:
            from backend.data.subagent_store import SubagentRepository

            repo = SubagentRepository(self.db)
            record = repo.get_subagent_by_id(agent_config_id)
            if record:
                return SubAgentConfig(
                    name=record.name,
                    description=record.description,
                    provider_id=record.provider_id,
                    model_id=record.model_id,
                    tools=record.tools,
                    extensions=record.extensions,
                    max_iterations=record.max_iterations,
                    temperature=record.temperature,
                    system_prompt=record.system_prompt,
                )

        # Try to load "notes-chat" role from database
        config = self._agent_loader.get("notes-chat", reload=False)
        if config:
            return config

        # Default fallback
        return SubAgentConfig(
            name="notes-chat",
            description="Knowledge notes assistant",
            tools=[
                "read",
                "write",
                "list",
                "edit",
                "kb_search",
                "kb_read_note",
                "kb_list_links",
                "kb_timeline",
                "kb_write_note",
                "memory_search",
                "memory_read",
                "memory_write",
            ],
            max_iterations=10,
            temperature=0.5,
            system_prompt=(
                "You are a helpful knowledge notes assistant. You help users understand, analyze, "
                "and manage their markdown notes in the knowledge base. You can search notes, "
                "read note contents, explore note relationships via wiki-links, and write or edit "
                "notes. Always be concise and cite the note paths you reference."
            ),
        )

    def _get_provider_for_config(
        self, config: SubAgentConfig | None
    ) -> tuple[LLMProvider, str, str, int, float]:
        """Get provider and model for the agent config."""
        defaults = self._config_service._get_agent_defaults_repo().get_or_create_defaults()
        max_tokens = getattr(defaults, "max_tokens", 8192) or 8192
        temperature = getattr(defaults, "temperature", 0.7) or 0.7

        if config and config.provider_id and config.model_id:
            provider_repo = ProviderRepository(self.db)
            model_repo = ModelRepository(self.db)
            provider_record = provider_repo.get_provider_by_id(config.provider_id)
            model_record = model_repo.get_model_by_id(config.model_id)

            if provider_record and model_record:
                provider_config = ProviderConfig(
                    type=provider_record.provider_type,
                    api_key=provider_record.api_key,
                    api_base=provider_record.api_host,
                )
                agent_defaults = AgentDefaults(
                    provider=provider_record.name,
                    model=model_record.model_id,
                    max_tokens=max_tokens,
                    temperature=config.temperature if config else temperature,
                    llm_max_retries=getattr(defaults, "llm_max_retries", 3) or 3,
                    llm_retry_base_delay=getattr(defaults, "llm_retry_base_delay", 1.0) or 1.0,
                    llm_retry_max_delay=getattr(defaults, "llm_max_retry_max_delay", 30.0) or 30.0,
                )
                providers_dict = {provider_record.name: provider_config}
                provider = create_provider(providers_dict, agent_defaults)
                return (
                    provider,
                    model_record.model_id,
                    provider_record.provider_type,
                    max_tokens,
                    config.temperature,
                )

        # Fallback to default
        return self._config_service.get_default_provider_and_model()

    def _build_tools_for_config(
        self, config: SubAgentConfig | None, scope_paths: list[str]
    ) -> ToolRegistry:
        """Build tool registry based on agent configuration and scope."""
        tools = ToolRegistry()

        # Determine vault filter from scope paths
        vault_filter = None
        if scope_paths:
            # If all scope paths share the same vault prefix, use it as vault filter
            for path in scope_paths:
                parts = Path(path).parts
                if len(parts) >= 3 and parts[0] == "knowledge" and parts[1] == "notes":
                    vault_filter = parts[2] if len(parts) > 2 else None
                    break

        tool_mapping = {
            "read": ReadFileTool,
            "write": WriteFileTool,
            "edit": EditFileTool,
            "list": ListDirTool,
            "exec": lambda: ExecTool(
                working_dir=str(self.workspace),
                timeout=60,
                restrict_to_workspace=True,
            ),
            "action": ActionTool,
            "message": lambda: MessageTool(send_callback=lambda x: None),
            "kb_search": lambda: ScopedKBSearchTool(
                scope_paths=scope_paths, vault_filter=vault_filter
            ),
            "kb_timeline": lambda: KBTimelineTool(vault_filter=vault_filter),
            "kb_read_note": KBReadNoteTool,
            "kb_list_links": lambda: KBListLinksTool(vault_filter=vault_filter),
            "kb_write_note": KBWriteNoteTool,
            "memory_write": lambda: MemoryWriteTool(store=MemoryStore(self.workspace)),
            "memory_search": MemorySearchTool,
            "memory_read": MemoryReadTool,
            "memory_timeline": MemoryTimelineTool,
        }

        tool_names = config.tools if config else []
        for tool_name in tool_names:
            tool_name_lower = tool_name.lower()
            if tool_name_lower in tool_mapping:
                try:
                    tool = tool_mapping[tool_name_lower]()
                    tools.register(tool)
                except Exception as e:
                    logger.warning(f"[NotesChatAgent] Failed to register tool '{tool_name}': {e}")
            else:
                logger.warning(f"[NotesChatAgent] Unknown tool '{tool_name}'")

        return tools

    # ── Scope ──

    def _build_scope_paths(self, scope: dict[str, Any] | None) -> list[str]:
        """Build list of file paths that are within the current scope."""
        if not scope:
            return []

        scope_type = scope.get("type", "global")
        paths: list[str] = []

        if scope_type == "global":
            # All notes
            rows = self.knowledge_engine.db.execute(
                "SELECT path FROM knowledge_nodes WHERE path LIKE 'knowledge/notes/%' ORDER BY mtime DESC LIMIT 1000"
            ).fetchall()
            paths = [r["path"] for r in rows]
        elif scope_type == "vault":
            vault = scope.get("vault", "")
            if vault:
                rows = self.knowledge_engine.db.execute(
                    "SELECT path FROM knowledge_nodes WHERE vault = ? ORDER BY mtime DESC LIMIT 1000",
                    (vault,),
                ).fetchall()
                paths = [r["path"] for r in rows]
        elif scope_type == "file":
            file_path = scope.get("file_path", "")
            if file_path:
                paths = [file_path]

        return paths

    def _build_scope_context(self, scope: dict[str, Any] | None) -> str:
        """Build human-readable scope description."""
        if not scope:
            return "Global scope (all notes)."

        scope_type = scope.get("type", "global")

        if scope_type == "global":
            count = self.knowledge_engine.db.execute(
                "SELECT COUNT(*) as c FROM knowledge_nodes WHERE path LIKE 'knowledge/notes/%'"
            ).fetchone()["c"]
            return f"Global scope — {count} note(s) in the knowledge base."

        elif scope_type == "vault":
            vault = scope.get("vault", "")
            count = self.knowledge_engine.db.execute(
                "SELECT COUNT(*) as c FROM knowledge_nodes WHERE vault = ?", (vault,)
            ).fetchone()["c"]
            return f'Vault scope — "{vault}" ({count} note(s)).'

        elif scope_type == "file":
            file_path = scope.get("file_path", "")
            node = self.knowledge_engine.db.execute(
                "SELECT title, word_count FROM knowledge_nodes WHERE path = ?", (file_path,)
            ).fetchone()
            if node:
                return (
                    f'File scope — "{file_path}"\n'
                    f"Title: {node['title']}\n"
                    f"Words: {node['word_count']} (estimated_tokens: ~{int(node['word_count'] * 1.5)})"
                )
            return f'File scope — "{file_path}"'

        return "Unknown scope."

    def _build_system_prompt(
        self,
        config: SubAgentConfig | None,
        session_title: str,
        scope_context: str,
        scope_paths: list[str],
    ) -> str:
        """Build system prompt for the Notes chat agent."""
        base_prompt = (
            config.system_prompt if config else ("You are a helpful knowledge notes assistant.")
        )

        skills_section = ""
        if config and config.extensions:
            skills_summary = self._skills.build_skills_summary(exclude_types=["longtask"])
            if skills_summary:
                skills_section = f"\n\n## Available Skills\n\n{skills_summary}"

        scope_constraint = ""
        if scope_paths:
            scope_constraint = (
                "\n\n## Scope Constraint\n"
                "You MUST ONLY access files within the listed scope paths. "
                "Do not read files outside these directories. "
                "When searching, the search tool will automatically filter to scope."
            )

        return f"""# {config.display_name if config else "Notes Chat Agent"}

{base_prompt}

## Session
Current session: {session_title}

## Knowledge Scope
{scope_context}

## Workspace
Your workspace is at: {self.workspace}{skills_section}{scope_constraint}

## Tools Guide
- `list` — List directory contents. Use this to get an overview of files.
- `read` — Read any file (md, txt, etc.). Use this when you need specific content.
- `write` — Write or overwrite a file. Use this to create or update notes.
- `edit` — Edit a file in-place. Use this for small modifications.
- `kb_search` — Search notes by keyword. Use this when you need to find notes on a topic.
- `kb_read_note` — Read a specific note by path.
- `kb_list_links` — Explore wiki-links between notes.
- `kb_timeline` — Preview a note's context (tags, links) before reading it.
- `kb_write_note` — Write or overwrite a note with automatic indexing.

## Efficiency Rules
1. **The scope summary above already tells you how many notes exist.** For questions like "how many notes?" or "what's in this vault?", answer directly from the scope info. Do NOT search or list unless the user asks for content details.
2. **Search only when necessary.** If the scope is small (< 10 notes), prefer `list` + `read` over `kb_search` for precision.
3. **Avoid redundant searches.** One search is usually enough. Do not search the same query twice with different parameters.
4. **Be concise.** Do not list all note titles unless the user asks. Give summaries, not dumps.
5. **Cite sources.** When referencing specific content, mention the note path.

## Response Style
- Direct and factual. No filler phrases like "Let me search..." unless you genuinely need to.
- For counts and overviews: give the number and a 1-sentence summary.
- For analysis: synthesize findings, don't just paste raw tool output.
- When the user asks you to write or edit a note, use `kb_write_note` or `write` tools directly."""

    def _build_messages(
        self,
        session_id: int,
        system_prompt: str,
        user_content: str,
    ) -> list[dict[str, Any]]:
        """Build message list for LLM call, restoring full tool call context."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Load history
        history = self.chat_service.list_messages(session_id)
        # Exclude the last user message (just added)
        for msg in history[:-1]:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            messages.append(entry)

        messages.append({"role": "user", "content": user_content})
        return messages
