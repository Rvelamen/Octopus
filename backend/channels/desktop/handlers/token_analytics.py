"""Token usage analytics handlers for Desktop channel."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.schemas import (
    TokenGetCacheAnalyticsRequest,
    TokenGetCostTrendRequest,
    TokenGetEfficiencyRequest,
    TokenGetModelComparisonRequest,
    TokenGetSessionWaterfallRequest,
)
from backend.core.events.bus import MessageBus
from backend.data import Database
from backend.data.token_store import TokenUsageRepository


class TokenEfficiencyHandler(MessageHandler):
    """Handle efficiency metrics queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: TokenGetEfficiencyRequest
    ) -> None:
        try:
            metrics = self.token_repo.get_efficiency_metrics(days=validated.days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_EFFICIENCY, request_id=message.request_id, data=metrics
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get efficiency metrics: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get efficiency metrics: {e}"
            )

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        days = message.data.get("days", 7)
        try:
            metrics = self.token_repo.get_efficiency_metrics(days=days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_EFFICIENCY, request_id=message.request_id, data=metrics
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get efficiency metrics: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get efficiency metrics: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


class TokenCostTrendHandler(MessageHandler):
    """Handle cost trend queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: TokenGetCostTrendRequest
    ) -> None:
        try:
            trend = self.token_repo.get_cost_trend(
                days=validated.days, granularity=validated.granularity
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_COST_TREND,
                    request_id=message.request_id,
                    data={
                        "days": validated.days,
                        "granularity": validated.granularity,
                        "trend": trend,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get cost trend: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get cost trend: {e}")

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        days = message.data.get("days", 30)
        granularity = message.data.get("granularity", "daily")
        try:
            trend = self.token_repo.get_cost_trend(days=days, granularity=granularity)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_COST_TREND,
                    request_id=message.request_id,
                    data={
                        "days": days,
                        "granularity": granularity,
                        "trend": trend,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get cost trend: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get cost trend: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


class TokenSessionWaterfallHandler(MessageHandler):
    """Handle session waterfall queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: TokenGetSessionWaterfallRequest
    ) -> None:
        try:
            waterfall = self.token_repo.get_session_waterfall(instance_id=validated.instance_id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_SESSION_WATERFALL,
                    request_id=message.request_id,
                    data={
                        "instance_id": validated.instance_id,
                        "calls": waterfall,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get session waterfall: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get session waterfall: {e}"
            )

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        instance_id = message.data.get("instance_id")
        if not instance_id:
            await self._send_error(websocket, message.request_id, "instance_id is required")
            return
        try:
            waterfall = self.token_repo.get_session_waterfall(instance_id=int(instance_id))
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_SESSION_WATERFALL,
                    request_id=message.request_id,
                    data={
                        "instance_id": int(instance_id),
                        "calls": waterfall,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get session waterfall: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get session waterfall: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


class TokenCacheAnalyticsHandler(MessageHandler):
    """Handle cache analytics queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: TokenGetCacheAnalyticsRequest
    ) -> None:
        try:
            analytics = self.token_repo.get_cache_analytics(days=validated.days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_CACHE_ANALYTICS,
                    request_id=message.request_id,
                    data=analytics,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get cache analytics: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get cache analytics: {e}"
            )

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        days = message.data.get("days", 7)
        try:
            analytics = self.token_repo.get_cache_analytics(days=days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_CACHE_ANALYTICS,
                    request_id=message.request_id,
                    data=analytics,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get cache analytics: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get cache analytics: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


class TokenModelComparisonHandler(MessageHandler):
    """Handle model comparison queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: TokenGetModelComparisonRequest
    ) -> None:
        try:
            comparison = self.token_repo.get_model_comparison(days=validated.days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_MODEL_COMPARISON,
                    request_id=message.request_id,
                    data={
                        "days": validated.days,
                        "models": comparison,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get model comparison: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get model comparison: {e}"
            )

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        days = message.data.get("days", 30)
        try:
            comparison = self.token_repo.get_model_comparison(days=days)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.TOKEN_MODEL_COMPARISON,
                    request_id=message.request_id,
                    data={
                        "days": days,
                        "models": comparison,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get model comparison: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get model comparison: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )
