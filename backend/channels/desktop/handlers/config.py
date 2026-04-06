"""WebSocket message handlers for configuration management."""

import asyncio
import json
import uuid
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.core.events.bus import MessageBus
from backend.data import Database


class GetConfigHandler(MessageHandler):
    """Handle configuration retrieval requests."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return current configuration (now stored in database)."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.CONFIG,
            request_id=message.request_id,
            data={}
        ))

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SaveConfigHandler(MessageHandler):
    """Handle configuration save requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Configuration is now stored in database, not in config file."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ACK,
            request_id=message.request_id,
            data={"status": "deprecated", "message": "Config is now stored in database"}
        ))

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class PingHandler(MessageHandler):
    """Handle ping messages for keep-alive."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Respond with pong."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.PONG,
            request_id=message.request_id,
            data={"timestamp": message.data.get("timestamp")}
        ))


class StopAgentsHandler(MessageHandler):
    """Handle stop agents requests."""

    def __init__(self, bus: MessageBus, agent_loop=None, subagent_manager=None):
        super().__init__(bus)
        self.agent_loop = agent_loop
        self.subagent_manager = subagent_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Stop all running agents and subagents."""
        stopped_count = 0

        # Stop main agent current task
        if self.agent_loop:
            self.agent_loop.stop_current_task()
            logger.info("[StopAgentsHandler] Main agent task stop signal sent")

        # Stop all subagents
        if self.subagent_manager:
            stopped_count = self.subagent_manager.stop_all()
            logger.info(f"[StopAgentsHandler] Stopped {stopped_count} subagents")

        await self.send_response(websocket, WSMessage(
            type=MessageType.AGENTS_STOPPED,
            request_id=message.request_id,
            data={
                "status": "stopped",
                "subagents_stopped": stopped_count,
                "message": f"已暂停主Agent任务和 {stopped_count} 个子Agent任务"
            }
        ))
