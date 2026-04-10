"""Context compression for managing conversation history length."""

from typing import Any, Callable

from loguru import logger

from backend.agent.config_service import AgentConfigService
from backend.data.session_manager import SessionManager
from backend.data.token_store import TokenUsageRepository


# Structured summary template for organized context compression
STRUCTURED_SUMMARY_TEMPLATE = """[CONTEXT COMPACTION] Earlier turns in this conversation were compacted to save context space. The summary below describes work that was already completed, and the current session state may still reflect that work (for example, files may already be changed). Use the summary and the current state to continue from where things left off, and avoid repeating work:

**Goal**: What is the user trying to accomplish?
**Progress**: What has been completed so far?
**Decisions**: What key decisions were made?
**Files**: What files were created or modified?
**Next Steps**: What should be done next?

If any section is not applicable, you can omit it."""

# System prompt for structured summarization
STRUCTURED_SUMMARY_SYSTEM_PROMPT = """你是一个对话摘要助手。请按照以下结构总结对话内容：

**目标**：用户想要完成什么？
**进展**：目前完成了什么？
**决策**：做出了哪些关键决策？
**文件**：创建或修改了哪些文件？
**下一步**：接下来应该做什么？

如果某些部分不适用，可以省略。请确保摘要简洁明了，便于后续对话快速参考。"""


async def compress_messages(
    messages: list[dict[str, Any]],
    provider: Any,
    model: str,
    provider_type: str,
    record_token_usage: Callable | None = None,
    session_instance_id: int | None = None,
    request_type: str = "compression",
) -> str:
    """
    Compress a list of messages using LLM with structured summary (standalone function).

    This is a utility function that can be used by both AgentLoop and SubagentManager
    without needing a full ContextCompressor instance.

    Args:
        messages: Messages to compress.
        provider: LLM provider instance.
        model: Model ID to use.
        provider_type: Provider type for token recording.
        record_token_usage: Optional callback to record token usage.
        session_instance_id: Optional session instance ID for token recording.
        request_type: Type of request for token recording.

    Returns:
        Compressed context summary with structured format.
    """
    if len(messages) < 4:
        return ""

    conversation_text = "\n".join([
        f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
        for m in messages
    ])

    # Use structured summary template
    compression_prompt = f"""{STRUCTURED_SUMMARY_TEMPLATE}

Conversation to summarize:
{conversation_text}"""

    compression_messages = [
        {"role": "system", "content": STRUCTURED_SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": compression_prompt}
    ]
    
    try:
        response = await provider.chat(
            messages=compression_messages,
            tools=[],
            model=model
        )
        
        if response.usage and record_token_usage:
            record_token_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_type,
                model_id=model,
                usage=response.usage,
                request_type=request_type
            )
        
        summary = response.content or ""
        logger.info(f"Context compressed to {len(summary)} characters")
        return summary
    except Exception as e:
        logger.error(f"Context compression failed: {e}")
        return ""


class ContextCompressor:
    """
    Handles context compression to manage conversation history length.
    
    Provides two compression strategies:
    1. First-time compression: Summarize entire conversation history
    2. Incremental compression: Update existing summary with new messages
    
    Compression is triggered by:
    - Token threshold (primary): When prompt tokens exceed threshold
    - Turn threshold (fallback): When turn count reaches threshold
    """

    def __init__(
        self,
        db: Any,
        sessions: SessionManager,
        token_usage: TokenUsageRepository,
        get_provider_and_model: Callable[[], tuple],
        record_token_usage: Callable,
    ):
        """
        Initialize the context compressor.
        
        Args:
            db: Database connection for config retrieval.
            sessions: Session manager for saving sessions.
            token_usage: Token usage repository for recording usage.
            get_provider_and_model: Callback to get current provider and model.
            record_token_usage: Callback to record token usage.
        """
        self.db = db
        self.sessions = sessions
        self.token_usage = token_usage
        self._get_provider_and_model = get_provider_and_model
        self._record_token_usage = record_token_usage

    @property
    def compression_enabled(self) -> bool:
        """Get context_compression_enabled from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_context_compression_enabled()
        except Exception:
            return False

    @property
    def compression_turns(self) -> int:
        """Get context_compression_turns from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_context_compression_turns()
        except Exception:
            return 10

    @property
    def compression_token_threshold(self) -> int:
        """Get context_compression_token_threshold from database dynamically."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_context_compression_token_threshold()
        except Exception:
            return 200000

    async def compress_context(
        self,
        session,
        messages: list[dict[str, Any]],
    ) -> str:
        """
        Compress conversation history using LLM with structured summary (first-time compression).

        Args:
            session: The current session.
            messages: Messages to compress.

        Returns:
            Compressed context summary with structured format.
        """
        to_compress = messages or session.messages[:-6] if len(session.messages) > 6 else session.messages

        if len(to_compress) < 4:
            return ""

        conversation_text = "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
            for m in to_compress
        ])

        # Use structured summary prompt
        compression_prompt = f"""{STRUCTURED_SUMMARY_TEMPLATE}

Conversation to summarize:
{conversation_text}"""

        provider, model, provider_type, max_tokens, temperature = self._get_provider_and_model()
        compression_messages = [
            {"role": "system", "content": STRUCTURED_SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": compression_prompt}
        ]

        try:
            response = await provider.chat(
                messages=compression_messages,
                tools=[],
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            if response.usage:
                session_instance_id = session.active_instance.id if session.active_instance else None
                self._record_token_usage(
                    session_instance_id=session_instance_id,
                    provider_name=provider_type,
                    model_id=model,
                    usage=response.usage,
                    request_type="compression"
                )
            
            summary = response.content or ""
            logger.info(f"Context compressed to {len(summary)} characters")
            return summary
        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            return ""

    async def compress_incremental(self, last_summary: str, new_messages: list) -> str:
        """
        Incremental compression: last_summary + new_messages -> new structured summary.

        Args:
            last_summary: The previous compressed summary.
            new_messages: New messages to compress.

        Returns:
            New complete structured summary.
        """
        if len(new_messages) < 4:
            return last_summary

        new_conversation = "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
            for m in new_messages
        ])

        # Use structured summary template for incremental compression
        prompt = f"""{STRUCTURED_SUMMARY_TEMPLATE}

## Previous Summary
{last_summary}

## New Conversation to Integrate
{new_conversation}

Please generate a complete structured summary that integrates both the previous summary and the new conversation."""

        provider, model, provider_type, max_tokens, temperature = self._get_provider_and_model()
        compression_messages = [
            {"role": "system", "content": STRUCTURED_SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await provider.chat(
                messages=compression_messages,
                tools=[],
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            if response.usage:
                self._record_token_usage(
                    session_instance_id=None,
                    provider_name=provider_type,
                    model_id=model,
                    usage=response.usage,
                    request_type="compression"
                )
            
            summary = response.content or last_summary
            logger.info(f"Incremental compression: {len(last_summary)} -> {len(summary)} characters")
            return summary
        except Exception as e:
            logger.error(f"Incremental compression failed: {e}")
            return last_summary

    async def do_compress(self, session, current_turns: int) -> None:
        """
        Perform context compression.
        
        Args:
            session: The current session.
            current_turns: Current turn count.
        """
        instance_id = session.active_instance.id if session.active_instance else None
        keep_count = 6
        
        # Filter out system messages and keep only the last 6 non-system messages
        non_system_messages = [m for m in session.messages if m.get("role") != "system"]
        to_compress = non_system_messages[:-keep_count] if len(non_system_messages) > keep_count else []
        
        if len(to_compress) < 4:
            logger.info(f"Not enough messages to compress: {len(to_compress)}")
            return
        
        last_summary = session.compressed_context
        
        if last_summary:
            logger.info(f"Performing incremental compression at turn {current_turns}")
            summary = await self.compress_incremental(last_summary, to_compress)
        else:
            logger.info(f"Performing first-time compression at turn {current_turns}")
            summary = await self.compress_context(session, to_compress)
        
        if not summary:
            logger.warning("Compression returned empty summary")
            return
        
        session.compressed_context = summary
        session.compressed_message_count += len(to_compress)
        session.last_compressed_turn = current_turns
        
        message_ids = [m.get('id') for m in to_compress if m.get('id')]
        if instance_id and message_ids:
            self.sessions.db.mark_messages_compressed(instance_id, message_ids)
        
        # Keep the last 6 non-system messages plus all system messages
        system_messages = [m for m in session.messages if m.get("role") == "system"]
        remaining_non_system = non_system_messages[-keep_count:] if len(non_system_messages) > keep_count else non_system_messages
        session.messages = system_messages + remaining_non_system
        
        self.sessions.save(session)
        logger.info(f"Context compressed: {len(to_compress)} messages, total compressed: {session.compressed_message_count}")

    async def maybe_compress(self, session, prompt_tokens: int = 0) -> None:
        """
        Check if context compression is needed and perform it.
        
        Hybrid trigger strategy:
        1. Token threshold (primary): trigger when prompt_tokens >= token_threshold
        2. Turn threshold (fallback): trigger when turn % turn_threshold == 0
        
        Args:
            session: The current session.
            prompt_tokens: The prompt tokens from last LLM call (0 if unknown).
        """
        if not self.compression_enabled:
            return
        
        current_turns = session.get_turn_count()
        
        if session.last_compressed_turn >= current_turns:
            return
        
        should_compress = False
        trigger_reason = ""
        
        token_threshold = self.compression_token_threshold
        if token_threshold and prompt_tokens >= token_threshold:
            should_compress = True
            trigger_reason = f"token threshold ({prompt_tokens} >= {token_threshold})"
        
        turn_threshold = self.compression_turns
        if not should_compress and current_turns >= turn_threshold and current_turns % turn_threshold == 0:
            should_compress = True
            trigger_reason = f"turn threshold (turn {current_turns})"
        
        if should_compress:
            logger.info(f"Compressing context triggered by {trigger_reason}")
            await self.do_compress(session, current_turns)
