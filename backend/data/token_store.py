"""Token usage tracking and storage."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class TokenUsageRecord:
    """Token usage record."""
    id: int
    session_instance_id: int | None
    provider_name: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    total_tokens: int
    request_type: str
    created_at: datetime


@dataclass
class TokenUsageSummary:
    """Token usage summary."""
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cached_tokens: int
    total_tokens: int
    request_count: int

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
        }


class TokenUsageRepository:
    """Repository for token usage operations."""

    def __init__(self, db: Database):
        self.db = db

    def record_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        request_type: str = "chat"
    ) -> TokenUsageRecord:
        """Record a token usage event.

        Args:
            session_instance_id: The session instance ID (optional)
            provider_name: Provider name (e.g., openai, anthropic)
            model_id: Model ID (e.g., gpt-4, claude-3-opus)
            prompt_tokens: Number of prompt/input tokens (including cache hits)
            completion_tokens: Number of completion/output tokens
            cached_tokens: Number of cache hit tokens
            request_type: Type of request (chat, compression, etc.)

        Returns:
            The created TokenUsageRecord
        """
        total_tokens = prompt_tokens + completion_tokens

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO token_usage
                   (session_instance_id, provider_name, model_id, prompt_tokens,
                    completion_tokens, cached_tokens, total_tokens, request_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (session_instance_id, provider_name, model_id,
                 prompt_tokens, completion_tokens, cached_tokens, total_tokens, request_type)
            )

            record_id = cursor.lastrowid

            row = conn.execute(
                "SELECT * FROM token_usage WHERE id = ?",
                (record_id,)
            ).fetchone()

            logger.debug(f"Recorded token usage: {provider_name}/{model_id} - "
                        f"prompt={prompt_tokens}, completion={completion_tokens}, cached={cached_tokens}")

            return self._row_to_record(row)

    def get_global_summary(self) -> TokenUsageSummary:
        """Get global token usage summary across all sessions."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage"""
            ).fetchone()

            return self._row_to_summary(row)

    def get_instance_summary(self, instance_id: int) -> TokenUsageSummary:
        """Get token usage summary for a session instance.

        Args:
            instance_id: The session instance ID

        Returns:
            TokenUsageSummary for the instance
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE session_instance_id = ?""",
                (instance_id,)
            ).fetchone()

            return self._row_to_summary(row)

    def get_session_summary(self, session_key: str) -> TokenUsageSummary:
        """Get token usage summary for a session (all instances).

        Args:
            session_key: The session key (channel:chat_id)

        Returns:
            TokenUsageSummary for all instances in the session
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(tu.prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(tu.completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(tu.cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage tu
                JOIN session_instances si ON tu.session_instance_id = si.id
                JOIN sessions s ON si.session_id = s.id
                WHERE s.session_key = ?""",
                (session_key,)
            ).fetchone()

            return self._row_to_summary(row)

    def get_provider_summary(self, provider_name: str) -> TokenUsageSummary:
        """Get token usage summary for a provider.

        Args:
            provider_name: The provider name

        Returns:
            TokenUsageSummary for the provider
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE provider_name = ?""",
                (provider_name,)
            ).fetchone()

            return self._row_to_summary(row)

    def get_model_summary(self, model_id: str) -> TokenUsageSummary:
        """Get token usage summary for a model.

        Args:
            model_id: The model ID

        Returns:
            TokenUsageSummary for the model
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE model_id = ?""",
                (model_id,)
            ).fetchone()

            return self._row_to_summary(row)

    def get_daily_usage(self, days: int = 7) -> list[dict]:
        """Get daily token usage for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of daily usage dicts with date and token counts
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    date(created_at) as date,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY date(created_at)
                ORDER BY date DESC""",
                (f'-{days} days',)
            ).fetchall()

            return [dict(row) for row in rows]

    def get_usage_by_provider(self, days: int = 30) -> list[dict]:
        """Get token usage grouped by provider.

        Args:
            days: Number of days to look back

        Returns:
            List of provider usage dicts
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    provider_name,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY provider_name
                ORDER BY total_tokens DESC""",
                (f'-{days} days',)
            ).fetchall()

            return [dict(row) for row in rows]

    def get_usage_by_model(self, days: int = 30) -> list[dict]:
        """Get token usage grouped by model.

        Args:
            days: Number of days to look back

        Returns:
            List of model usage dicts
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    provider_name,
                    model_id,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY provider_name, model_id
                ORDER BY total_tokens DESC""",
                (f'-{days} days',)
            ).fetchall()

            return [dict(row) for row in rows]

    def get_recent_usage(self, limit: int = 100) -> list[TokenUsageRecord]:
        """Get recent token usage records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of TokenUsageRecord
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM token_usage
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def get_instance_recent_usage(self, instance_id: int, limit: int = 50) -> list[TokenUsageRecord]:
        """Get recent token usage records for a session instance.

        Args:
            instance_id: The session instance ID
            limit: Maximum number of records to return

        Returns:
            List of TokenUsageRecord
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM token_usage
                   WHERE session_instance_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (instance_id, limit)
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row) -> TokenUsageRecord:
        """Convert database row to TokenUsageRecord."""
        return TokenUsageRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            provider_name=row["provider_name"],
            model_id=row["model_id"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cached_tokens=row["cached_tokens"] if "cached_tokens" in row.keys() else 0,
            total_tokens=row["total_tokens"],
            request_type=row["request_type"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
        )

    def _row_to_summary(self, row) -> TokenUsageSummary:
        """Convert database row to TokenUsageSummary."""
        return TokenUsageSummary(
            total_prompt_tokens=row["total_prompt_tokens"] if row["total_prompt_tokens"] else 0,
            total_completion_tokens=row["total_completion_tokens"] if row["total_completion_tokens"] else 0,
            total_cached_tokens=row["total_cached_tokens"] if "total_cached_tokens" in row.keys() and row["total_cached_tokens"] else 0,
            total_tokens=row["total_tokens"] if row["total_tokens"] else 0,
            request_count=row["request_count"] if row["request_count"] else 0,
        )
