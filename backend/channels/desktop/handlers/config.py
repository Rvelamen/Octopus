"""WebSocket message handlers for configuration management."""

import asyncio
import json
import uuid
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.schemas import (
    GetConfigRequest,
    SaveConfigRequest,
    PingRequest,
    StopAgentsRequest,
)
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

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: GetConfigRequest) -> None:
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

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: SaveConfigRequest) -> None:
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

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: PingRequest) -> None:
        """Respond with pong."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.PONG,
            request_id=message.request_id,
            data={"timestamp": validated.timestamp}
        ))


class StopAgentsHandler(MessageHandler):
    """Handle stop agents requests."""

    def __init__(self, bus: MessageBus, agent_loop=None, subagent_manager=None):
        super().__init__(bus)
        self.agent_loop = agent_loop
        self.subagent_manager = subagent_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Stop running agents and subagents for a specific instance, or all if no instance specified."""
        # 从消息中获取 instance_id，如果为空则停止所有
        instance_id = message.data.get("instance_id") if message.data else None
        
        stopped_count = 0
        main_agent_stopped = False

        # Stop main agent current task (optionally by instance_id)
        if self.agent_loop:
            if instance_id:
                self.agent_loop.stop_instance_task(instance_id)
                logger.info(f"[StopAgentsHandler] Main agent task stop signal sent for instance: {instance_id}")
            else:
                self.agent_loop.stop_current_task()
                logger.info("[StopAgentsHandler] Main agent task stop signal sent (all instances)")
            main_agent_stopped = True

        # Stop subagents (optionally by instance_id)
        if self.subagent_manager:
            if instance_id:
                stopped_count = self.subagent_manager.stop_by_instance(instance_id)
                logger.info(f"[StopAgentsHandler] Stopped {stopped_count} subagents for instance: {instance_id}")
            else:
                stopped_count = self.subagent_manager.stop_all()
                logger.info(f"[StopAgentsHandler] Stopped {stopped_count} subagents (all instances)")

        message_text = f"已暂停主Agent任务和 {stopped_count} 个子Agent任务"
        if instance_id:
            message_text = f"已暂停实例 {instance_id} 的主Agent任务和 {stopped_count} 个子Agent任务"

        await self.send_response(websocket, WSMessage(
            type=MessageType.AGENTS_STOPPED,
            request_id=message.request_id,
            data={
                "status": "stopped",
                "main_agent_stopped": main_agent_stopped,
                "subagents_stopped": stopped_count,
                "instance_id": instance_id,
                "message": message_text
            }
        ))

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: StopAgentsRequest) -> None:
        """Stop running agents and subagents for a specific instance, or all if no instance specified."""
        instance_id = validated.instance_id
        
        stopped_count = 0
        main_agent_stopped = False

        # Stop main agent current task (optionally by instance_id)
        if self.agent_loop:
            if instance_id:
                self.agent_loop.stop_instance_task(instance_id)
                logger.info(f"[StopAgentsHandler] Main agent task stop signal sent for instance: {instance_id}")
            else:
                self.agent_loop.stop_current_task()
                logger.info("[StopAgentsHandler] Main agent task stop signal sent (all instances)")
            main_agent_stopped = True

        # Stop subagents (optionally by instance_id)
        if self.subagent_manager:
            if instance_id:
                stopped_count = self.subagent_manager.stop_by_instance(instance_id)
                logger.info(f"[StopAgentsHandler] Stopped {stopped_count} subagents for instance: {instance_id}")
            else:
                stopped_count = self.subagent_manager.stop_all()
                logger.info(f"[StopAgentsHandler] Stopped {stopped_count} subagents (all instances)")

        message_text = f"已暂停主Agent任务和 {stopped_count} 个子Agent任务"
        if instance_id:
            message_text = f"已暂停实例 {instance_id} 的主Agent任务和 {stopped_count} 个子Agent任务"

        await self.send_response(websocket, WSMessage(
            type=MessageType.AGENTS_STOPPED,
            request_id=message.request_id,
            data={
                "status": "stopped",
                "main_agent_stopped": main_agent_stopped,
                "subagents_stopped": stopped_count,
                "instance_id": instance_id,
                "message": message_text
            }
        ))
