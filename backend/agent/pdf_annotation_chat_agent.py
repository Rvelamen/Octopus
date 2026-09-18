"""PDF Annotation Chat Agent.

Lightweight variant of PdfChatAgent: same LLM streaming/agent flow, but
binds the chat session to a single library_annotations row and injects
that annotation's quote + its thread comments into the system prompt as
persistent context (instead of pulling from the session's selected_text
history).

Implementation note: rather than inheriting from PdfChatAgent (which would
tightly couple to PdfChatService internals), this class composes a
PdfChatAgent-style flow on top of PdfAnnotationChatService.
"""

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from backend.agent.config_service import AgentConfigService
from backend.agent.loader import SubAgentConfig, SubAgentLoader
from backend.core.providers.base import LLMProvider
from backend.core.providers.factory import create_provider
from backend.data import Database
from backend.data.provider_store import ModelRepository, ProviderRepository
from backend.extensions.loader import SkillsLoader
from backend.services.pdf_annotation_chat_service import PdfAnnotationChatService
from backend.tools.registry import ToolRegistry


# Maximum characters from the annotation quote + comments to splice into
# the system prompt. Keeps the prompt bounded for long passages.
_MAX_ANNOTATION_CONTEXT_CHARS = 2000


class PdfAnnotationChatAgent:
    """PDF chat agent whose context is bound to one library annotation."""

    def __init__(self, workspace: Path, db: Database | None = None):
        self.workspace = workspace
        self.db = db or Database()
        self.chat_service = PdfAnnotationChatService(self.db)
        self._config_service = AgentConfigService(self.db)
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace, self.db)

    # ── Public entry point ──

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
        session = self.chat_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Persist user message
        self.chat_service.add_message(
            session_id=session_id,
            role="user",
            content=user_content,
            page_number=page_number,
            selected_text=selected_text,
        )

        agent_config = self._load_agent_config(session.agent_config_id)
        provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(
            agent_config
        )
        tools = self._build_tools_for_config(agent_config)

        # Annotation-bound context: this is the bit that diverges from PdfChatAgent.
        annotation_context = self._build_annotation_context(session.annotation_id)
        system_prompt = self._build_system_prompt(
            agent_config,
            session_title=session.title,
            pdf_path=session.pdf_path,
            annotation_context=annotation_context,
        )

        messages = self._build_messages(
            session_id=session_id,
            system_prompt=system_prompt,
            user_content=user_content,
            page_number=page_number,
            selected_text=selected_text,
        )

        return await self._run_stream(
            session_id=session_id,
            provider=provider,
            model=model,
            provider_type=provider_type,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            messages=messages,
            on_token=on_token,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
        )

    # ── Annotation context ──

    def _build_annotation_context(self, annotation_id: int) -> dict[str, Any] | None:
        """Read the annotation row + its thread comments from the library DB.

        Returns a dict {page, text, comments: [{author_name, content}]} suitable
        for splicing into the system prompt, or None if the annotation has
        been deleted in the meantime.
        """
        try:
            row = self.db.execute(
                "SELECT id, page, type, color, text FROM library_annotations WHERE id = ?",
                (annotation_id,),
            ).fetchone()
            if not row:
                return None
            comment_rows = self.db.execute(
                """
                SELECT author_name, content, created_at
                FROM library_annotation_comments
                WHERE annotation_id = ?
                ORDER BY created_at, id
                """,
                (annotation_id,),
            ).fetchall()
            return {
                "page": row["page"],
                "text": row["text"] or "",
                "type": row["type"],
                "color": row["color"],
                "comments": [
                    {"author_name": c["author_name"], "content": c["content"]}
                    for c in comment_rows
                ],
            }
        except Exception as e:
            logger.warning(f"[PdfAnnotationChatAgent] failed to load annotation context: {e}")
            return None

    # ── System prompt ──

    def _build_system_prompt(
        self,
        config: SubAgentConfig | None,
        session_title: str,
        pdf_path: str | None = None,
        annotation_context: dict[str, Any] | None = None,
    ) -> str:
        base_prompt = (
            config.system_prompt
            if config
            else ("You are a helpful PDF reading assistant.")
        )

        skills_section = ""
        if config and config.extensions:
            skills_summary = self._skills.build_skills_summary(exclude_types=["longtask"])
            if skills_summary:
                skills_section = f"\n\n## Available Skills\n\n{skills_summary}"

        annotation_section = ""
        if annotation_context:
            parts: list[str] = []
            quote = annotation_context.get("text", "")
            if quote:
                parts.append(f'"{quote}"')
            comments = annotation_context.get("comments") or []
            if comments:
                lines = [
                    f"- {c['author_name']}: {c['content']}" for c in comments if c.get("content")
                ]
                if lines:
                    parts.append("Discussion notes:\n" + "\n".join(lines))
            if parts:
                joined = "\n\n".join(parts)
                if len(joined) > _MAX_ANNOTATION_CONTEXT_CHARS:
                    joined = joined[:_MAX_ANNOTATION_CONTEXT_CHARS] + "…"
                page_info = (
                    f" on page {annotation_context['page']}"
                    if annotation_context.get("page")
                    else ""
                )
                annotation_section = (
                    "\n\n## Bound Annotation\n"
                    f"The user is currently discussing the following highlighted passage{page_info}. "
                    "Treat this as the primary context for the conversation and anchor every answer to it.\n\n"
                    + joined
                )

        pdf_section = ""
        if pdf_path:
            resolved_pdf_path = self._resolve_pdf_path(pdf_path)
            if resolved_pdf_path:
                pdf_section = (
                    "\n\n## Current PDF Document\n"
                    f"The user is currently reading the following PDF file. "
                    f"Use the read_file tool to read its contents when needed:\n"
                    f"{resolved_pdf_path}"
                )

        return f"""# {config.display_name if config else "PDF Annotation Chat Agent"}

{base_prompt}

## Session
Current session: {session_title}{pdf_section}{annotation_section}

## Workspace
Your workspace is at: {self.workspace}{skills_section}

When answering, be concise but thorough. If you reference specific content from the PDF or the annotation, mention the page number when available."""

    def _resolve_pdf_path(self, pdf_path: str | None) -> str | None:
        if not pdf_path:
            return None
        p = Path(pdf_path).expanduser()
        if not p.is_absolute():
            p = self.workspace / p
        if p.is_file() and p.suffix.lower() == ".pdf":
            return str(p)
        main_pdf = p / "main.pdf"
        if main_pdf.is_file():
            return str(main_pdf)
        return str(p)

    # ── Message list construction ──

    def _build_messages(
        self,
        session_id: int,
        system_prompt: str,
        user_content: str,
        page_number: int | None,
        selected_text: str | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        history = self.chat_service.list_messages(session_id)
        # Last entry is the user message we just persisted; skip it here.
        for msg in history[:-1]:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            messages.append(entry)

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

    # ── Agent config + provider ──

    def _load_agent_config(self, agent_config_id: int | None) -> SubAgentConfig | None:
        if agent_config_id:
            with contextlib.suppress(Exception):
                return self._agent_loader.load_by_id(agent_config_id)
        with contextlib.suppress(Exception):
            return self._agent_loader.load_by_name("pdf-chat")
        return None

    def _get_provider_for_config(
        self, config: SubAgentConfig | None
    ) -> tuple[LLMProvider, str, str, int, float]:
        provider_repo = ProviderRepository(self.db)
        model_repo = ModelRepository(self.db)
        model_id = (config.model if config else None) or "default"
        provider_cfg, model_cfg = None, None
        with contextlib.suppress(Exception):
            provider_cfg, model_cfg = provider_repo.find_model_by_id(model_id)
        if provider_cfg is None or model_cfg is None:
            from backend.core.config.schema import AgentDefaults

            defaults = AgentDefaults()
            model_id = defaults.model
            with contextlib.suppress(Exception):
                provider_cfg, model_cfg = provider_repo.find_model_by_id(model_id)
        if provider_cfg is None or model_cfg is None:
            raise RuntimeError(f"No provider/model found for {model_id}")
        provider = create_provider(provider_cfg)
        provider_type = provider_cfg.provider_type
        max_tokens = (
            (config.max_tokens if config else None)
            or (model_cfg.max_tokens if model_cfg else 8192)
            or 8192
        )
        temperature = (
            (config.temperature if config else None)
            or (model_cfg.temperature if model_cfg else 0.7)
            or 0.7
        )
        return provider, model_cfg.model_name, provider_type, int(max_tokens), float(temperature)

    def _build_tools_for_config(self, config: SubAgentConfig | None) -> ToolRegistry:
        registry = ToolRegistry()
        if not config or not config.extensions:
            return registry
        from backend.tools.action import ActionTool
        from backend.tools.filesystem import (
            EditFileTool,
            ListDirTool,
            ReadFileTool,
            WriteFileTool,
        )
        from backend.tools.library_knowledge import (
            LibraryListLinksTool,
            LibraryReadNoteTool,
            LibrarySearchTool,
            LibraryTimelineTool,
        )
        from backend.tools.memory import (
            MemoryReadTool,
            MemorySearchTool,
            MemoryTimelineTool,
        )
        from backend.tools.memory_write import MemoryWriteTool
        from backend.tools.message import MessageTool
        from backend.tools.shell import ExecTool

        builtin_map = {
            "read_file": ReadFileTool,
            "write_file": WriteFileTool,
            "edit_file": EditFileTool,
            "list_dir": ListDirTool,
            "exec": ExecTool,
            "send_message": MessageTool,
            "memory_search": MemorySearchTool,
            "memory_read": MemoryReadTool,
            "memory_timeline": MemoryTimelineTool,
            "memory_write": MemoryWriteTool,
            "library_search": LibrarySearchTool,
            "library_read_note": LibraryReadNoteTool,
            "library_list_links": LibraryListLinksTool,
            "library_timeline": LibraryTimelineTool,
            "action": ActionTool,
        }
        enabled = set(config.extensions or [])
        for name, cls in builtin_map.items():
            if name in enabled:
                with contextlib.suppress(Exception):
                    registry.register(cls())
        return registry

    # ── LLM streaming loop ──

    async def _run_stream(
        self,
        *,
        session_id: int,
        provider: LLMProvider,
        model: str,
        provider_type: str,
        max_tokens: int,
        temperature: float,
        tools: ToolRegistry,
        messages: list[dict[str, Any]],
        on_token: Callable[[str], Any] | None,
        on_tool_start: Callable[[dict], Any] | None,
        on_tool_result: Callable[[dict], Any] | None,
    ) -> str:
        full_content = ""
        accumulated_reasoning = ""
        iterations = 0
        max_iterations = 6

        while iterations < max_iterations:
            iterations += 1
            tool_calls_buffer: dict[str, dict[str, Any]] = {}

            try:
                stream = provider.stream_chat(
                    model=model,
                    messages=messages,
                    tools=tools.schemas() if tools else None,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except TypeError:
                # Some providers don't accept tools kwarg
                stream = provider.stream_chat(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

            async for chunk in stream:
                # Each chunk may be (token, reasoning_token) or a dict
                if isinstance(chunk, tuple):
                    token, reasoning = chunk
                else:
                    token = chunk
                    reasoning = None

                if reasoning:
                    accumulated_reasoning += reasoning
                if token:
                    full_content += token
                    if on_token:
                        with contextlib.suppress(Exception):
                            on_token(token)

                # Tool calls are reported alongside streaming by some providers
                tc = None
                if isinstance(chunk, dict):
                    tc = chunk.get("tool_calls")
                if tc:
                    for entry in tc:
                        tc_id = entry.get("id") or f"tc-{len(tool_calls_buffer)}"
                        tool_calls_buffer[tc_id] = entry

            if not tool_calls_buffer:
                # Done — persist assistant message
                self.chat_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content,
                )
                return full_content

            # Persist assistant turn with accumulated reasoning if any
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": full_content,
            }
            if accumulated_reasoning:
                assistant_msg["reasoning_content"] = accumulated_reasoning
            messages.append(assistant_msg)

            # Execute tools
            for tc_id, tc_data in tool_calls_buffer.items():
                args = dict(tc_data.get("arguments", {}))
                name = tc_data.get("name")
                if on_tool_start:
                    with contextlib.suppress(Exception):
                        on_tool_start(
                            {"tool": name, "args": args, "tool_call_id": tc_id}
                        )
                try:
                    result = await tools.execute(name, args) if name else "Error: missing tool name"
                except Exception as e:
                    logger.error(f"[PdfAnnotationChatAgent] tool {name} failed: {e}")
                    result = f"Error: {e}"
                if on_tool_result:
                    with contextlib.suppress(Exception):
                        on_tool_result(
                            {"tool": name, "result": result, "tool_call_id": tc_id}
                        )
                messages.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tc_id,
                    }
                )
                # Reset streaming accumulators for next iteration
                full_content = ""
                accumulated_reasoning = ""

        # Safety net
        self.chat_service.add_message(
            session_id=session_id,
            role="assistant",
            content=full_content or "(max iterations reached)",
        )
        return full_content
