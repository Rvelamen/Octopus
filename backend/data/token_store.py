"""Token usage tracking and storage."""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from backend.core.pricing import calculate_cost
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
    cache_creation_tokens: int
    total_tokens: int
    request_type: str
    response_time_ms: int | None
    cost_usd: float | None
    tool_calls_count: int
    is_error: bool
    error_type: str | None
    parent_instance_id: int | None
    created_at: datetime


@dataclass
class TokenUsageSummary:
    """Token usage summary."""

    total_prompt_tokens: int
    total_completion_tokens: int
    total_cached_tokens: int
    total_cache_creation_tokens: int
    total_tokens: int
    total_cost_usd: float
    request_count: int
    avg_response_time_ms: float | None

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_cache_creation_tokens": self.total_cache_creation_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "request_count": self.request_count,
            "avg_response_time_ms": (
                round(self.avg_response_time_ms, 2) if self.avg_response_time_ms else None
            ),
        }


@dataclass
class TokenEfficiencyMetrics:
    """Efficiency metrics for token usage."""

    cache_hit_rate: float
    avg_tokens_per_second: float
    avg_response_time_ms: float
    error_rate: float
    cost_per_1k_tokens: float
    cost_per_request: float

    def to_dict(self) -> dict:
        return {
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "avg_tokens_per_second": round(self.avg_tokens_per_second, 2),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "cost_per_1k_tokens": round(self.cost_per_1k_tokens, 6),
            "cost_per_request": round(self.cost_per_request, 6),
        }


class TokenUsageRepository:
    """Repository for token usage operations."""

    def __init__(self, db: Database):
        self.db = db

    def _get_model_pricing(self, model_id: str) -> dict | None:
        """Get pricing from database for a model ID."""
        try:
            with self.db._get_connection() as conn:
                row = conn.execute(
                    "SELECT pricing_json FROM models WHERE model_id = ? LIMIT 1",
                    (model_id,)
                ).fetchone()
                if row and row["pricing_json"]:
                    import json
                    return json.loads(row["pricing_json"])
        except Exception:
            pass
        return None

    def record_usage(
        self,
        session_instance_id: int | None,
        provider_name: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        cache_creation_tokens: int = 0,
        request_type: str = "chat",
        response_time_ms: int | None = None,
        tool_calls_count: int = 0,
        is_error: bool = False,
        error_type: str | None = None,
        parent_instance_id: int | None = None,
    ) -> TokenUsageRecord:
        """Record a token usage event.

        Args:
            session_instance_id: The session instance ID (optional)
            provider_name: Provider name (e.g., openai, anthropic)
            model_id: Model ID (e.g., gpt-4, claude-3-opus)
            prompt_tokens: Number of prompt/input tokens (including cache hits)
            completion_tokens: Number of completion/output tokens
            cached_tokens: Number of cache hit tokens
            cache_creation_tokens: Number of cache creation tokens
            request_type: Type of request (chat, compression, etc.)
            response_time_ms: API response time in milliseconds
            tool_calls_count: Number of tool calls in this request
            is_error: Whether this request resulted in an error
            error_type: Type of error (rate_limit, context_exceeded, etc.)
            parent_instance_id: Parent session instance ID for call chain tracking

        Returns:
            The created TokenUsageRecord
        """
        total_tokens = prompt_tokens + completion_tokens

        # Try to get pricing from database first, fallback to hardcoded table
        db_pricing = self._get_model_pricing(model_id)

        cost_usd = None
        try:
            cost_usd = calculate_cost(
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cache_creation_tokens=cache_creation_tokens,
                db_pricing=db_pricing,
            )
        except Exception as e:
            logger.debug(f"Failed to calculate cost for {model_id}: {e}")

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO token_usage
                   (session_instance_id, provider_name, model_id, prompt_tokens,
                    completion_tokens, cached_tokens, cache_creation_tokens, total_tokens,
                    request_type, response_time_ms, cost_usd, tool_calls_count,
                    is_error, error_type, parent_instance_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (
                    session_instance_id,
                    provider_name,
                    model_id,
                    prompt_tokens,
                    completion_tokens,
                    cached_tokens,
                    cache_creation_tokens,
                    total_tokens,
                    request_type,
                    response_time_ms,
                    cost_usd,
                    tool_calls_count,
                    1 if is_error else 0,
                    error_type,
                    parent_instance_id,
                ),
            )

            record_id = cursor.lastrowid

            row = conn.execute("SELECT * FROM token_usage WHERE id = ?", (record_id,)).fetchone()

            logger.debug(
                f"Recorded token usage: {provider_name}/{model_id} - "
                f"prompt={prompt_tokens}, completion={completion_tokens}, "
                f"cached={cached_tokens}, cost=${cost_usd}"
            )

            return self._row_to_record(row)

    def get_global_summary(self) -> TokenUsageSummary:
        """Get global token usage summary across all sessions."""
        with self.db._get_connection() as conn:
            row = conn.execute("""SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage""").fetchone()

            return self._row_to_summary(row)

    def get_instance_summary(self, instance_id: int) -> TokenUsageSummary:
        """Get token usage summary for a session instance."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE session_instance_id = ?""",
                (instance_id,),
            ).fetchone()

            return self._row_to_summary(row)

    def get_session_summary(self, session_key: str) -> TokenUsageSummary:
        """Get token usage summary for a session (all instances)."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(tu.prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(tu.completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(tu.cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(tu.cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                    COALESCE(SUM(tu.cost_usd), 0) as total_cost_usd,
                    COUNT(*) as request_count,
                    AVG(tu.response_time_ms) as avg_response_time_ms
                FROM token_usage tu
                JOIN session_instances si ON tu.session_instance_id = si.id
                JOIN sessions s ON si.session_id = s.id
                WHERE s.session_key = ?""",
                (session_key,),
            ).fetchone()

            return self._row_to_summary(row)

    def get_provider_summary(self, provider_name: str) -> TokenUsageSummary:
        """Get token usage summary for a provider."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE provider_name = ?""",
                (provider_name,),
            ).fetchone()

            return self._row_to_summary(row)

    def get_model_summary(self, model_id: str) -> TokenUsageSummary:
        """Get token usage summary for a model."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE model_id = ?""",
                (model_id,),
            ).fetchone()

            return self._row_to_summary(row)

    def get_daily_usage(self, days: int = 7) -> list[dict]:
        """Get daily token usage for the last N days."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    date(created_at) as date,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY date(created_at)
                ORDER BY date DESC""",
                (f"-{days} days",),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_usage_by_provider(self, days: int = 30) -> list[dict]:
        """Get token usage grouped by provider."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    provider_name,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY provider_name
                ORDER BY total_tokens DESC""",
                (f"-{days} days",),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_usage_by_model(self, days: int = 30) -> list[dict]:
        """Get token usage grouped by model."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    provider_name,
                    model_id,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY provider_name, model_id
                ORDER BY total_tokens DESC""",
                (f"-{days} days",),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_usage_by_request_type(self, days: int = 30) -> list[dict]:
        """Get token usage grouped by request type."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    request_type,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY request_type
                ORDER BY total_tokens DESC""",
                (f"-{days} days",),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_recent_usage(self, limit: int = 100) -> list[TokenUsageRecord]:
        """Get recent token usage records."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM token_usage
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def get_instance_recent_usage(
        self, instance_id: int, limit: int = 50
    ) -> list[TokenUsageRecord]:
        """Get recent token usage records for a session instance."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM token_usage
                   WHERE session_instance_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (instance_id, limit),
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    # =================================================================
    # New Analytics Methods
    # =================================================================

    def get_efficiency_metrics(self, days: int = 7) -> dict:
        """Get efficiency metrics for token usage.

        Returns:
            Dict with cache_hit_rate, avg_latency, tokens_per_second, error_rate, etc.
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(cached_tokens), 0) as total_cached,
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN is_error = 1 THEN 1 ELSE 0 END) as error_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)""",
                (f"-{days} days",),
            ).fetchone()

            total_prompt = row["total_prompt"] or 0
            total_cached = row["total_cached"] or 0
            total_tokens = row["total_tokens"] or 0
            total_cost = row["total_cost"] or 0
            request_count = row["request_count"] or 0
            error_count = row["error_count"] or 0
            avg_response_time_ms = row["avg_response_time_ms"] or 0

            cache_hit_rate = (total_cached / total_prompt) if total_prompt > 0 else 0
            error_rate = (error_count / request_count) if request_count > 0 else 0

            # tokens per second = total_tokens / (total_response_time_ms / 1000)
            total_response_time = (
                conn.execute(
                    """SELECT COALESCE(SUM(response_time_ms), 0) as total_ms
                   FROM token_usage
                   WHERE created_at >= datetime('now', 'localtime', ?)
                   AND response_time_ms IS NOT NULL""",
                    (f"-{days} days",),
                ).fetchone()["total_ms"]
                or 1
            )

            avg_tokens_per_second = (
                (total_tokens / (total_response_time / 1000)) if total_response_time > 0 else 0
            )

            cost_per_1k_tokens = (total_cost / total_tokens * 1000) if total_tokens > 0 else 0
            cost_per_request = total_cost / request_count if request_count > 0 else 0

            return {
                "cache_hit_rate": round(cache_hit_rate, 4),
                "avg_tokens_per_second": round(avg_tokens_per_second, 2),
                "avg_response_time_ms": round(avg_response_time_ms, 2),
                "error_rate": round(error_rate, 4),
                "cost_per_1k_tokens": round(cost_per_1k_tokens, 6),
                "cost_per_request": round(cost_per_request, 6),
                "total_cost_usd": round(total_cost, 6),
                "total_tokens": total_tokens,
                "request_count": request_count,
                "error_count": error_count,
            }

    def get_cost_trend(self, days: int = 30, granularity: str = "daily") -> list[dict]:
        """Get cost trend data.

        Args:
            days: Number of days to look back
            granularity: 'daily' or 'hourly'
        """
        if granularity == "hourly":
            group_by = "strftime('%Y-%m-%d %H:00:00', created_at)"
        else:
            group_by = "date(created_at)"

        with self.db._get_connection() as conn:
            rows = conn.execute(
                f"""SELECT
                    {group_by} as period,
                    SUM(cost_usd) as cost_usd,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY {group_by}
                ORDER BY period DESC""",
                (f"-{days} days",),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_session_waterfall(self, instance_id: int) -> list[dict]:
        """Get all LLM calls for a session instance in chronological order.

        Returns call chain with parent-child relationships.
        """
        with self.db._get_connection() as conn:
            # Get the session_key from the instance
            session_row = conn.execute(
                """SELECT s.session_key, s.channel
                   FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE si.id = ?""",
                (instance_id,),
            ).fetchone()

            if not session_row:
                return []

            session_key = session_row["session_key"]

            # Get all instances for this session
            instance_rows = conn.execute(
                """SELECT si.id
                   FROM session_instances si
                   JOIN sessions s ON si.session_id = s.id
                   WHERE s.session_key = ?
                   ORDER BY si.created_at""",
                (session_key,),
            ).fetchall()

            instance_ids = [r["id"] for r in instance_rows]
            if not instance_ids:
                return []

            # Get all token usage records for these instances
            placeholders = ",".join("?" * len(instance_ids))
            rows = conn.execute(
                f"""SELECT
                    tu.id,
                    tu.session_instance_id,
                    tu.provider_name,
                    tu.model_id,
                    tu.prompt_tokens,
                    tu.completion_tokens,
                    tu.cached_tokens,
                    tu.cache_creation_tokens,
                    tu.total_tokens,
                    tu.request_type,
                    tu.response_time_ms,
                    tu.cost_usd,
                    tu.tool_calls_count,
                    tu.is_error,
                    tu.error_type,
                    tu.parent_instance_id,
                    tu.created_at,
                    si.created_at as instance_created_at
                FROM token_usage tu
                JOIN session_instances si ON tu.session_instance_id = si.id
                WHERE tu.session_instance_id IN ({placeholders})
                ORDER BY tu.created_at""",
                instance_ids,
            ).fetchall()

            return [dict(row) for row in rows]

    def get_cache_analytics(self, days: int = 7) -> dict:
        """Get cache efficiency analytics.

        Returns cache hit rate, savings estimation, and trend.
        """
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                    COALESCE(SUM(cached_tokens), 0) as total_cached,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)""",
                (f"-{days} days",),
            ).fetchone()

            total_prompt = row["total_prompt"] or 0
            total_cached = row["total_cached"] or 0
            total_cache_creation = row["total_cache_creation"] or 0
            total_cost = row["total_cost"] or 0

            cache_hit_rate = (total_cached / total_prompt) if total_prompt > 0 else 0

            # Estimate savings: cached tokens cost ~10% of regular input (rough estimate)
            # Use actual pricing when possible
            estimated_input_price_per_1m = 3.0  # average
            estimated_cached_price_per_1m = 0.3  # ~10%
            regular_cost = total_cached * estimated_input_price_per_1m / 1_000_000
            cached_cost = total_cached * estimated_cached_price_per_1m / 1_000_000
            estimated_savings = regular_cost - cached_cost

            # Daily cache trend
            daily_rows = conn.execute(
                """SELECT
                    date(created_at) as date,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(cost_usd) as cost_usd
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY date(created_at)
                ORDER BY date DESC""",
                (f"-{days} days",),
            ).fetchall()

            daily_trend = []
            for r in daily_rows:
                day_prompt = r["prompt_tokens"] or 0
                day_cached = r["cached_tokens"] or 0
                day_rate = (day_cached / day_prompt) if day_prompt > 0 else 0
                daily_trend.append(
                    {
                        "date": r["date"],
                        "prompt_tokens": day_prompt,
                        "cached_tokens": day_cached,
                        "cache_creation_tokens": r["cache_creation_tokens"] or 0,
                        "cache_hit_rate": round(day_rate, 4),
                        "cost_usd": round(r["cost_usd"] or 0, 6),
                    }
                )

            return {
                "cache_hit_rate": round(cache_hit_rate, 4),
                "total_cached_tokens": total_cached,
                "total_cache_creation_tokens": total_cache_creation,
                "total_prompt_tokens": total_prompt,
                "estimated_savings_usd": round(estimated_savings, 6),
                "total_cost_usd": round(total_cost, 6),
                "daily_trend": daily_trend,
            }

    def get_model_comparison(self, days: int = 30) -> list[dict]:
        """Get per-model comparison with efficiency metrics."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    model_id,
                    provider_name,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN is_error = 1 THEN 1 ELSE 0 END) as error_count,
                    AVG(response_time_ms) as avg_response_time_ms
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY model_id, provider_name
                ORDER BY cost_usd DESC""",
                (f"-{days} days",),
            ).fetchall()

            result = []
            for row in rows:
                total_tokens = row["total_tokens"] or 0
                total_cost = row["cost_usd"] or 0
                request_count = row["request_count"] or 0
                error_count = row["error_count"] or 0
                avg_ms = row["avg_response_time_ms"] or 0

                result.append(
                    {
                        "model_id": row["model_id"],
                        "provider_name": row["provider_name"],
                        "total_tokens": total_tokens,
                        "prompt_tokens": row["prompt_tokens"] or 0,
                        "completion_tokens": row["completion_tokens"] or 0,
                        "cached_tokens": row["cached_tokens"] or 0,
                        "cost_usd": round(total_cost, 6),
                        "request_count": request_count,
                        "error_count": error_count,
                        "error_rate": (
                            round(error_count / request_count, 4) if request_count > 0 else 0
                        ),
                        "avg_response_time_ms": round(avg_ms, 2),
                        "cost_per_1k_tokens": (
                            round(total_cost / total_tokens * 1000, 6) if total_tokens > 0 else 0
                        ),
                        "cost_per_request": (
                            round(total_cost / request_count, 6) if request_count > 0 else 0
                        ),
                    }
                )

            return result

    def get_heatmap(self, months: int = 6) -> dict:
        """Get heatmap data for calendar and hourly usage patterns.

        Args:
            months: Number of months to look back for calendar heatmap

        Returns:
            Dict with calendar_data (list of daily stats) and hourly_matrix (7x24 grid)
        """
        with self.db._get_connection() as conn:
            # Calendar heatmap: daily usage for the last N months
            calendar_rows = conn.execute(
                """SELECT
                    date(created_at) as date,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as cost_usd,
                    COUNT(*) as request_count,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY date(created_at)
                ORDER BY date""",
                (f'-{months} months',)
            ).fetchall()

            calendar_data = []
            for row in calendar_rows:
                calendar_data.append({
                    "date": row["date"],
                    "total_tokens": row["total_tokens"] or 0,
                    "cost_usd": round(row["cost_usd"] or 0, 6),
                    "request_count": row["request_count"] or 0,
                    "prompt_tokens": row["prompt_tokens"] or 0,
                    "completion_tokens": row["completion_tokens"] or 0,
                })

            # Hourly heatmap: usage by weekday (0=Sun) and hour
            hourly_rows = conn.execute(
                """SELECT
                    CAST(strftime('%w', created_at) AS INTEGER) as weekday,
                    CAST(strftime('%H', created_at) AS INTEGER) as hour,
                    SUM(total_tokens) as total_tokens,
                    COUNT(*) as request_count,
                    SUM(cost_usd) as cost_usd
                FROM token_usage
                WHERE created_at >= datetime('now', 'localtime', ?)
                GROUP BY weekday, hour""",
                (f'-{months} months',)
            ).fetchall()

            # Build 7x24 matrix (weekday x hour)
            hourly_matrix = [[0 for _ in range(24)] for _ in range(7)]
            for row in hourly_rows:
                wd = row["weekday"]  # 0=Sunday, 1=Monday, ..., 6=Saturday
                hr = row["hour"]
                hourly_matrix[wd][hr] = row["total_tokens"] or 0

            # Get max values for normalization
            max_daily_tokens = max((d["total_tokens"] for d in calendar_data), default=1)
            max_hourly_tokens = max(max(row) for row in hourly_matrix) if hourly_matrix else 1
            if max_hourly_tokens == 0:
                max_hourly_tokens = 1

            return {
                "calendar": {
                    "data": calendar_data,
                    "max_tokens": max_daily_tokens,
                },
                "hourly": {
                    "matrix": hourly_matrix,
                    "max_tokens": max_hourly_tokens,
                },
                "months": months,
            }

    def _row_to_record(self, row) -> TokenUsageRecord:
        """Convert database row to TokenUsageRecord."""
        return TokenUsageRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            provider_name=row["provider_name"],
            model_id=row["model_id"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cached_tokens=row.get("cached_tokens", 0),
            cache_creation_tokens=row.get("cache_creation_tokens", 0) or 0,
            total_tokens=row["total_tokens"],
            request_type=row["request_type"],
            response_time_ms=row.get("response_time_ms"),
            cost_usd=row.get("cost_usd"),
            tool_calls_count=row.get("tool_calls_count", 0) or 0,
            is_error=bool(row.get("is_error", 0)),
            error_type=row.get("error_type"),
            parent_instance_id=row.get("parent_instance_id"),
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
            ),
        )

    def _row_to_summary(self, row) -> TokenUsageSummary:
        """Convert database row to TokenUsageSummary."""
        return TokenUsageSummary(
            total_prompt_tokens=row["total_prompt_tokens"] if row["total_prompt_tokens"] else 0,
            total_completion_tokens=(
                row["total_completion_tokens"] if row["total_completion_tokens"] else 0
            ),
            total_cached_tokens=(
                row["total_cached_tokens"]
                if "total_cached_tokens" in row and row["total_cached_tokens"]
                else 0
            ),
            total_cache_creation_tokens=(
                row["total_cache_creation_tokens"]
                if "total_cache_creation_tokens" in row and row["total_cache_creation_tokens"]
                else 0
            ),
            total_tokens=row["total_tokens"] if row["total_tokens"] else 0,
            total_cost_usd=(
                row["total_cost_usd"] if "total_cost_usd" in row and row["total_cost_usd"] else 0
            ),
            request_count=row["request_count"] if row["request_count"] else 0,
            avg_response_time_ms=(
                row["avg_response_time_ms"]
                if "avg_response_time_ms" in row and row["avg_response_time_ms"]
                else None
            ),
        )
