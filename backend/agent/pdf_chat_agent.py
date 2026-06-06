"""PDF Chat Agent — an independent, configurable agent for PDF reading conversations.

Built on top of SubagentManager patterns but designed for multi-turn real-time chat
instead of background task execution.
"""

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
from backend.services.pdf_chat_service import PdfChatService
from backend.tools.action import ActionTool
from backend.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from backend.tools.library_knowledge import (
    LibraryListLinksTool,
    LibraryReadNoteTool,
    LibrarySearchTool,
    LibraryTimelineTool,
)
from backend.tools.memory import MemoryReadTool, MemorySearchTool, MemoryTimelineTool
from backend.tools.memory_write import MemoryWriteTool
from backend.tools.message import MessageTool
from backend.tools.registry import ToolRegistry
from backend.tools.shell import ExecTool


class PdfChatAgent:
    """Independent agent for PDF chat with configurable tools, model, and system prompt."""

    def __init__(self, workspace: Path, db: Database | None = None):
        self.workspace = workspace
        self.db = db or Database()
        self.pdf_chat_service = PdfChatService(self.db)
        self._config_service = AgentConfigService(self.db)
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace, self.db)

    async def chat(
        self,
        session_id: int,
        user_content: str,
        page_number: int | None = None,
        selected_text: str | None = None,
        on_token: Callable[[str], Any] | None = None,
        on_tool_start: Callable[[dict], Any] | None = None,
        on_tool_result: Callable[[dict], Any] | None = None,
    ) -> str:
        """Process a user message in a PDF chat session and return the assistant response.

        Args:
            session_id: The PDF chat session ID.
            user_content: User's question/message.
            page_number: Optional page number of the selected text.
            selected_text: Optional selected text from the PDF.
            on_token: Callback for each streaming token.
            on_tool_start: Callback when a tool call starts.
            on_tool_result: Callback when a tool call completes.

        Returns:
            The full assistant response text.
        """
        # Load session and history
        session = self.pdf_chat_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Save user message
        self.pdf_chat_service.add_message(
            session_id=session_id,
            role="user",
            content=user_content,
            page_number=page_number,
            selected_text=selected_text,
        )

        # Load agent config (default to "pdf-chat" role, fallback to default)
        agent_config = self._load_agent_config(session.agent_config_id)

        # Get provider, model, tools
        provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(
            agent_config
        )
        tools = self._build_tools_for_config(agent_config)

        # Collect all referenced passages from session history for persistent context
        referenced_passages = self._collect_referenced_passages(session_id)
        system_prompt = self._build_system_prompt(
            agent_config, session.title, session.pdf_path, referenced_passages
        )

        # Build messages
        messages = self._build_messages(
            session_id, system_prompt, user_content, page_number, selected_text
        )

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

                    # DeepSeek reasoning content
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
                logger.error(f"[PdfChatAgent] LLM call failed: {e}")
                raise

            if tool_calls_buffer:
                # Build assistant message with tool_calls (required by OpenAI API)
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
                # DeepSeek requires reasoning_content to be passed back
                if accumulated_reasoning:
                    assistant_msg["reasoning_content"] = accumulated_reasoning
                messages.append(assistant_msg)
                if full_content:
                    final_content = full_content

                # Persist assistant message with tool_calls
                self.pdf_chat_service.add_message(
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
                    # DeepSeek requires reasoning_content to be passed back
                    if accumulated_reasoning:
                        assistant_msg["reasoning_content"] = accumulated_reasoning
                    messages.append(assistant_msg)
                    final_content = full_content

                # Persist final assistant message
                self.pdf_chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content or "",
                )
                break

            # Execute tools and persist tool results
            for tc_data in tool_calls_buffer.values():
                tool_args = self._inject_tool_args(tc_data, session_id)
                try:
                    result = await tools.execute(tc_data["name"], tool_args)
                except Exception as e:
                    logger.error(f"[PdfChatAgent] Tool {tc_data['name']} failed: {e}")
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
                self.pdf_chat_service.add_message(
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

        # Try to load "pdf-chat" role from database
        config = self._agent_loader.get("pdf-chat", reload=False)
        if config:
            return config

        # Default fallback
        return SubAgentConfig(
            name="pdf-chat",
            description="PDF reading assistant",
            tools=["read", "library_search", "library_read_note", "memory_search", "memory_read"],
            max_iterations=10,
            temperature=0.5,
            system_prompt=(
                "You are a helpful PDF reading assistant. You help users understand academic papers "
                "and documents by answering questions based on the provided context and your knowledge. "
                "You can search the knowledge base and read files to provide accurate answers. "
                "Be concise but thorough. When citing information from the PDF, reference the page number if available."
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

    def _build_tools_for_config(self, config: SubAgentConfig | None) -> ToolRegistry:
        """Build tool registry based on agent configuration."""
        tools = ToolRegistry()
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
            "kb_search": lambda: LibrarySearchTool(
                vault_filter="library", name_override="kb_search"
            ),
            "kb_timeline": lambda: LibraryTimelineTool(
                vault_filter="library", name_override="kb_timeline"
            ),
            "kb_read_note": lambda: LibraryReadNoteTool(name_override="kb_read_note"),
            "kb_list_links": lambda: LibraryListLinksTool(
                vault_filter="library", name_override="kb_list_links"
            ),
            "library_search": lambda: LibrarySearchTool(vault_filter="library"),
            "library_timeline": lambda: LibraryTimelineTool(vault_filter="library"),
            "library_read_note": LibraryReadNoteTool,
            "library_list_links": lambda: LibraryListLinksTool(vault_filter="library"),
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
                    logger.warning(f"[PdfChatAgent] Failed to register tool '{tool_name}': {e}")
            else:
                logger.warning(f"[PdfChatAgent] Unknown tool '{tool_name}'")

        return tools

    def _build_system_prompt(
        self,
        config: SubAgentConfig | None,
        session_title: str,
        pdf_path: str | None = None,
        referenced_passages: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build system prompt for the PDF chat agent."""
        base_prompt = (
            config.system_prompt if config else ("You are a helpful PDF reading assistant.")
        )

        skills_section = ""
        if config and config.extensions:
            skills_summary = self._skills.build_skills_summary(exclude_types=["longtask"])
            if skills_summary:
                skills_section = f"\n\n## Available Skills\n\n{skills_summary}"

        passages_section = ""
        if referenced_passages:
            lines = []
            for i, p in enumerate(referenced_passages, 1):
                page_info = f" (Page {p['page']})" if p.get("page") else ""
                text = p.get("text", "")
                # Truncate very long passages to avoid blowing up the prompt
                if len(text) > 800:
                    text = text[:800] + "..."
                lines.append(f"[{i}]{page_info}\n{text}")
            passages_section = (
                "\n\n## Referenced Passages from This Session\n"
                "The user has highlighted the following passages during this conversation. "
                "Use them as reference material when answering questions.\n\n"
                + "\n\n---\n\n".join(lines)
            )

        pdf_section = ""
        if pdf_path:
            resolved_pdf_path = self._resolve_pdf_path(pdf_path)
            if resolved_pdf_path:
                pdf_section = (
                    f"\n\n## Current PDF Document\n"
                    f"The user is currently reading the following PDF file. "
                    f"Use the read_file tool to read its contents when needed:\n"
                    f"{resolved_pdf_path}"
                )

        return f"""# {config.display_name if config else "PDF Chat Agent"}

{base_prompt}

## Session
Current session: {session_title}{pdf_section}

## Workspace
Your workspace is at: {self.workspace}{skills_section}{passages_section}

When answering, be concise but thorough. If you reference specific content from the PDF, mention the page number when available."""

    def _resolve_pdf_path(self, pdf_path: str | None) -> str | None:
        """Resolve the actual PDF file path from a potentially directory-based path.

        Library items store a directory path (e.g. knowledge/library/00001_Title).
        The actual PDF is inside as main.pdf.
        """
        if not pdf_path:
            return None

        p = Path(pdf_path).expanduser()
        if not p.is_absolute():
            p = self.workspace / p

        # If it's already a PDF file, use it directly
        if p.is_file() and p.suffix.lower() == ".pdf":
            return str(p)

        # If it's a directory, look for main.pdf inside
        main_pdf = p / "main.pdf"
        if main_pdf.is_file():
            return str(main_pdf)

        # Fallback: return the absolute path anyway
        return str(p)

    def _build_messages(
        self,
        session_id: int,
        system_prompt: str,
        user_content: str,
        page_number: int | None,
        selected_text: str | None,
    ) -> list[dict[str, Any]]:
        """Build message list for LLM call, restoring full tool call context."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Load history
        history = self.pdf_chat_service.list_messages(session_id)
        # Exclude the last user message (just added)
        for msg in history[:-1]:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            messages.append(entry)

        # Build current user message with context
        context_parts = []
        if page_number is not None:
            context_parts.append(f"[Page {page_number}]")
        if selected_text:
            context_parts.append(f'Selected text: "{selected_text}"')

        if context_parts:
            full_content = "\n\n".join(context_parts) + f"\n\nQuestion: {user_content}"
        else:
            full_content = user_content

        messages.append({"role": "user", "content": full_content})
        return messages

    def _collect_referenced_passages(self, session_id: int) -> list[dict[str, Any]]:
        """Collect all unique selected_text passages from the session history."""
        history = self.pdf_chat_service.list_messages(session_id)
        seen: set[str] = set()
        passages: list[dict[str, Any]] = []
        for msg in history:
            if msg.selected_text and msg.selected_text not in seen:
                seen.add(msg.selected_text)
                passages.append(
                    {
                        "text": msg.selected_text,
                        "page": msg.page_number,
                    }
                )
        return passages

    def _inject_tool_args(self, tc_data: dict, session_id: int) -> dict[str, Any]:
        """Inject useful context into tool arguments."""
        args = dict(tc_data.get("arguments", {}))
        # PdfChatAgent does not need special arg injection like subagents
        return args
