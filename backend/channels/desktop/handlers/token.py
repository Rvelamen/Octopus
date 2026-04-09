"""Token usage handler for Desktop channel."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.core.events.bus import MessageBus
from backend.data import Database
from backend.data.token_store import TokenUsageRepository


class TokenUsageHandler(MessageHandler):
    """Handle token usage queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        self.db = db or Database()
        self.token_repo = TokenUsageRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return token usage statistics."""
        scope = message.data.get("scope", "global")
        scope_id = (
            message.data.get("scope_id")
            or message.data.get("instance_id")
            or message.data.get("session_instance_id")
        )
        days = message.data.get("days", 7)

        try:
            result = {}

            if scope == "global":
                summary = self.token_repo.get_global_summary()
                result = {
                    "scope": "global",
                    "summary": summary.to_dict(),
                    "by_provider": self.token_repo.get_usage_by_provider(days),
                    "by_model": self.token_repo.get_usage_by_model(days),
                    "daily": self.token_repo.get_daily_usage(days),
                }
            elif scope == "instance" and scope_id:
                summary = self.token_repo.get_instance_summary(int(scope_id))
                result = {
                    "scope": "instance",
                    "scope_id": scope_id,
                    "summary": summary.to_dict(),
                    "recent": [
                        {
                            "provider_name": r.provider_name,
                            "model_id": r.model_id,
                            "prompt_tokens": r.prompt_tokens,
                            "completion_tokens": r.completion_tokens,
                            "total_tokens": r.total_tokens,
                            "request_type": r.request_type,
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in self.token_repo.get_instance_recent_usage(int(scope_id))
                    ],
                }
            elif scope == "session" and scope_id:
                summary = self.token_repo.get_session_summary(scope_id)
                result = {
                    "scope": "session",
                    "scope_id": scope_id,
                    "summary": summary.to_dict(),
                }
            elif scope == "provider" and scope_id:
                summary = self.token_repo.get_provider_summary(scope_id)
                result = {
                    "scope": "provider",
                    "scope_id": scope_id,
                    "summary": summary.to_dict(),
                }
            elif scope == "model" and scope_id:
                summary = self.token_repo.get_model_summary(scope_id)
                result = {
                    "scope": "model",
                    "scope_id": scope_id,
                    "summary": summary.to_dict(),
                }
            elif scope == "daily":
                result = {
                    "scope": "daily",
                    "daily": self.token_repo.get_daily_usage(days),
                }
            else:
                await self._send_error(websocket, message.request_id, f"Invalid scope or missing scope_id: {scope}")
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.TOKEN_USAGE,
                request_id=message.request_id,
                data=result
            ))
        except Exception as e:
            logger.error(f"Failed to get token usage: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get token usage: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
