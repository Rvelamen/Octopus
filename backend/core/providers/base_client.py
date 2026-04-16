"""Base provider with shared retry logic."""

import asyncio
from typing import Any

import httpx
from loguru import logger

from backend.core.providers.base import LLMProvider

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    ConnectionError,
    TimeoutError,
)


class RetryableProvider(LLMProvider):
    """Base LLM provider with retry/backoff support."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gpt-4",
        provider_type: str = "openai",
        api_version: str = "2024-02-01",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.provider_type = provider_type
        self.api_version = api_version
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        if isinstance(error, RETRYABLE_EXCEPTIONS):
            return True

        error_str = str(error).lower()
        retryable_keywords = [
            "timeout", "timed out", "connection", "network",
            "502", "503", "504", "429", "rate limit",
            "gateway", "service unavailable", "bad gateway"
        ]
        return any(kw in error_str for kw in retryable_keywords)

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry with exponential backoff and jitter."""
        import random

        delay = min(
            self.retry_base_delay * (2 ** attempt),
            self.retry_max_delay
        )
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

    async def _execute_with_retry(
        self,
        func,
        operation_name: str = "LLM call",
    ) -> Any:
        """Execute a function with retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func()
            except Exception as e:
                last_error = e

                if not self._is_retryable_error(e):
                    logger.error(f"[Provider] {operation_name} failed with non-retryable error: {e}")
                    raise

                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"[Provider] {operation_name} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[Provider] {operation_name} failed after {self.max_retries + 1} attempts: {e}"
                    )
                    raise

        raise last_error

    def get_default_model(self) -> str:
        return self.default_model
