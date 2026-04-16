"""Context compression for managing conversation history length."""

import json
import os
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from backend.agent.config_service import AgentConfigService
from backend.data.session_manager import SessionManager
from backend.data.token_store import TokenUsageRepository


# 配置压缩日志输出到独立文件
_log_dir = Path(__file__).parent.parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)
_compression_log_file = _log_dir / "compression.log"

# 创建独立的压缩日志 logger
compression_logger = logger.bind(name="compression")
# 移除默认 handler
compression_logger.remove()
# 只输出到文件，避免循环依赖导致死锁
compression_logger.add(
    str(_compression_log_file),
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    encoding="utf-8"
)


# Token estimation constants
_CHARS_PER_TOKEN = 4
_TOKEN_OVERHEAD_PER_MESSAGE = 10

# Tool output pruning constants
_TOOL_RESULT_PRUNE_MAX_CHARS = 200
_TOOL_RESULT_PRUNE_PLACEHOLDER = "[Old tool output cleared to save context space]"


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


def _estimate_single_message_tokens(msg: dict[str, Any]) -> int:
    """估算单条消息的字符数（排除 subagent react 部分）。"""
    content = msg.get("content", "")
    content_str = str(content)

    # 如果是 spawn 的同步 subagent 结果，只计算 summary 部分
    # iterations（ReAct 流程）仅用于前端展示，不计入上下文 token
    if msg.get("role") == "tool" and content_str.strip().startswith("{"):
        try:
            parsed = json.loads(content_str)
            if isinstance(parsed, dict) and parsed.get("type") == "subagent_sync":
                summary = parsed.get("summary", "")
                return len(summary)
        except (json.JSONDecodeError, ValueError):
            pass

    return len(content_str)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    """
    快速估算消息列表的 token 数量 (基于字符数 / 4 + 固定开销)。
    
    Args:
        messages: 消息列表
        
    Returns:
        估算的 token 数量
    """
    total_chars = sum(_estimate_single_message_tokens(m) for m in messages)
    return (total_chars // _CHARS_PER_TOKEN) + (len(messages) * _TOKEN_OVERHEAD_PER_MESSAGE)


def prune_old_tool_results(
    messages: list[dict[str, Any]], 
    tail_token_budget: int = 15000
) -> list[dict[str, Any]]:
    """
    廉价预处理: 将尾部 token 预算外的旧 tool result 替换为占位符。
    
    零成本操作，无需 LLM 调用，可节省 30-50% 需要压缩的内容。
    从后向前遍历，保护尾部预算内的消息。
    
    Args:
        messages: 消息列表
        tail_token_budget: 尾部保护的 token 预算 (默认 15000)
        
    Returns:
        处理后的消息列表 (可能修改了部分 tool result 的内容)
    """
    if not messages:
        return messages
    
    result = []
    tokens_from_end = 0
    
    # 从后向前遍历，保护尾部预算
    for msg in reversed(messages):
        content = msg.get("content", "")
        token_estimate = len(str(content)) // _CHARS_PER_TOKEN
        tokens_from_end += token_estimate
        
        # 如果是 tool 消息，且超出尾部预算，且内容较长，则替换为占位符
        if (msg.get("role") == "tool" and
            tokens_from_end > tail_token_budget and
            len(str(content)) > _TOOL_RESULT_PRUNE_MAX_CHARS):
            msg = {**msg, "content": _TOOL_RESULT_PRUNE_PLACEHOLDER}
            compression_logger.debug(f"Pruned old tool result ({len(str(content))} chars) to save context space")
        
        result.append(msg)
    
    return list(reversed(result))


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
        compression_logger.info(f"Context compressed to {len(summary)} characters")
        return summary
    except Exception as e:
        compression_logger.error(f"Context compression failed: {e}")
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
        observation_manager=None,
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
        self.observation_manager = observation_manager

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
            return 100000  # Default fallback: 100K tokens

    @property
    def compression_trigger_ratio(self) -> float:
        """Get compression trigger ratio (上下文窗口使用率阈值) from database."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_compression_trigger_ratio()
        except Exception:
            return 0.60  # 默认 60% 上下文窗口时触发

    @property
    def compression_tail_token_budget(self) -> int:
        """Get compression tail token budget from database."""
        try:
            config_service = AgentConfigService(self.db)
            return config_service.get_compression_tail_token_budget()
        except Exception:
            return 15000  # 默认保护最近 ~15K tokens

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
            compression_logger.info(f"Context compressed to {len(summary)} characters")
            return summary
        except Exception as e:
            compression_logger.error(f"Context compression failed: {e}")
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
            compression_logger.info(f"Incremental compression: {len(last_summary)} -> {len(summary)} characters")
            return summary
        except Exception as e:
            compression_logger.error(f"Incremental compression failed: {e}")
            return last_summary

    async def do_compress(self, session, current_turns: int, model_context_window: int = 0) -> None:
        """
        Perform context compression with dynamic tail protection.

        方案1: 先执行廉价 tool output 裁剪
        方案3: 使用 Token 预算动态尾部保护 (替代固定6条)

        Args:
            session: The current session.
            current_turns: Current turn count.
            model_context_window: 模型的上下文窗口大小 (用于动态触发)
        """
        instance_id = session.active_instance.id if session.active_instance else None
        
        # 方案1: 廉价预处理 - Tool Output 裁剪
        tail_budget = self.compression_tail_token_budget
        session.messages = prune_old_tool_results(session.messages, tail_budget)
        compression_logger.info(f"Phase 1: Pruned old tool results (tail budget: {tail_budget} tokens)")
        
        # 方案3: 动态尾部保护 - 使用 Token 预算而非固定数量
        tail_messages = []
        tokens_in_tail = 0
        
        # 从后向前累加，确定保留区域 (跳过 system 消息)
        non_system_messages = [m for m in session.messages if m.get("role") != "system"]
        for msg in reversed(non_system_messages):
            token_est = len(str(msg.get("content", ""))) // _CHARS_PER_TOKEN
            # 至少保留 3 条消息，即使超出预算
            if tokens_in_tail + token_est > tail_budget and len(tail_messages) >= 3:
                break
            tail_messages.append(msg)
            tokens_in_tail += token_est
        
        tail_messages = list(reversed(tail_messages))
        to_compress = [m for m in session.messages if m.get("role") != "system"]
        to_compress = to_compress[:-len(tail_messages)] if tail_messages else to_compress
        
        if len(to_compress) < 4:
            compression_logger.info(f"Not enough messages to compress: {len(to_compress)}")
            return

        last_summary = session.compressed_context

        if last_summary:
            compression_logger.info(f"Performing incremental compression at turn {current_turns}")
            summary = await self.compress_incremental(last_summary, to_compress)
        else:
            compression_logger.info(f"Performing first-time compression at turn {current_turns}")
            summary = await self.compress_context(session, to_compress)

        if not summary:
            compression_logger.warning("Compression returned empty summary")
            return

        session.compressed_context = summary
        session.compressed_message_count += len(to_compress)
        session.last_compressed_turn = current_turns

        message_ids = [m.get('id') for m in to_compress if m.get('id')]
        if instance_id and message_ids:
            self.sessions.db.mark_messages_compressed(instance_id, message_ids)

        # 触发 observation 提取（通过独立的 ObservationManager）
        if instance_id and self.observation_manager:
            try:
                saved_count = await self.observation_manager.extract_from_messages(
                    session_instance_id=instance_id,
                    messages=to_compress,
                )
                if saved_count:
                    compression_logger.info(f"Extracted and saved {saved_count} observations")
            except Exception as e:
                compression_logger.warning(f"Observation extraction after compression failed: {e}")

        # 重建消息列表：系统消息 + 保留的尾部消息
        system_messages = [m for m in session.messages if m.get("role") == "system"]
        session.messages = system_messages + tail_messages

        self.sessions.save(session)
        compression_logger.info(
            f"Context compressed: {len(to_compress)} messages -> summary, "
            f"{len(tail_messages)} messages kept (tail: ~{tokens_in_tail} tokens), "
            f"total compressed: {session.compressed_message_count}"
        )

    async def maybe_compress(
        self, 
        session, 
        prompt_tokens: int = 0,
        model_context_window: int = 0
    ) -> None:
        """
        Check if context compression is needed and perform it.

        方案2: 智能触发机制 - 基于上下文窗口百分比的动态触发
        
        Hybrid trigger strategy:
        1. Token ratio (primary): trigger when prompt_tokens / model_context_window >= trigger_ratio
        2. Token threshold (fallback): trigger when prompt_tokens >= token_threshold
        3. Turn threshold (fallback): trigger when turn % turn_threshold == 0

        Args:
            session: The current session.
            prompt_tokens: The prompt tokens from last LLM call (0 if unknown).
            model_context_window: 模型的上下文窗口大小 (如 32768, 128000 等)
        """
        if not self.compression_enabled:
            return

        current_turns = session.get_turn_count()

        if session.last_compressed_turn >= current_turns:
            return

        should_compress = False
        trigger_reason = ""

        # 方案2: 优先使用动态百分比触发
        trigger_ratio = self.compression_trigger_ratio
        if model_context_window > 0 and prompt_tokens > 0:
            usage_ratio = prompt_tokens / model_context_window
            if usage_ratio >= trigger_ratio:
                should_compress = True
                trigger_reason = f"token ratio ({usage_ratio:.1%} >= {trigger_ratio:.1%})"
        
        # 回退到固定 token 阈值
        if not should_compress:
            token_threshold = self.compression_token_threshold
            if token_threshold and prompt_tokens >= token_threshold:
                should_compress = True
                trigger_reason = f"token threshold ({prompt_tokens} >= {token_threshold})"

        # 回退到轮次阈值
        if not should_compress:
            turn_threshold = self.compression_turns
            if current_turns >= turn_threshold and current_turns % turn_threshold == 0:
                should_compress = True
                trigger_reason = f"turn threshold (turn {current_turns})"

        if should_compress:
            compression_logger.info(f"Compressing context triggered by {trigger_reason}")
            await self.do_compress(session, current_turns, model_context_window)
