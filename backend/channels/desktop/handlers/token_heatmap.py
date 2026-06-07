"""Token usage heatmap handler for Desktop channel."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.schemas import TokenGetHeatmapRequest
from backend.core.events.bus import MessageBus
from backend.data import Database
from backend.data.token_store import TokenUsageRepository


class TokenHeatmapHandler(MessageHandler):
    """Handle heatmap data queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: TokenGetHeatmapRequest) -> None:
        try:
            heatmap = self.token_repo.get_heatmap(months=validated.months)
            await self.send_response(websocket, WSMessage(
                type=MessageType.TOKEN_HEATMAP,
                request_id=message.request_id,
                data=heatmap
            ))
        except Exception as e:
            logger.error(f"Failed to get heatmap: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get heatmap: {e}")

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        months = message.data.get("months", 6)
        try:
            heatmap = self.token_repo.get_heatmap(months=months)
            await self.send_response(websocket, WSMessage(
                type=MessageType.TOKEN_HEATMAP,
                request_id=message.request_id,
                data=heatmap
            ))
        except Exception as e:
            logger.error(f"Failed to get heatmap: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get heatmap: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
