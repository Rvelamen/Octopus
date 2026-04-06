"""WebSocket message handlers for Desktop channel."""

import asyncio
import json
import random
import time
import uuid
from pathlib import Path
from typing import Any
import re

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.provider_handlers import (
    ProviderHandler, ModelHandler, SettingsHandler, AgentDefaultsHandler,
    ChannelConfigHandler, ToolConfigHandler, ImageProviderConfigHandler
)
from backend.channels.desktop.wechat_handler import WechatConfigHandler
from backend.core.events.types import InboundMessage, AgentEvent, MessageContentItem
from backend.core.events.bus import MessageBus
from backend.mcp.manager import MCPManager, get_mcp_manager
from backend.mcp.config import MCPServerConfig
from backend.data import Database, SessionRepository
from backend.data.provider_store import (
    ProviderRepository, ModelRepository, AgentDefaultsRepository,
    SettingsRepository, ChannelConfigRepository, ToolConfigRepository
)

# Import handlers from extensions (unified extension system)
from backend.extensions.desktop_handlers import (
    ExtensionGetListHandler,
    ExtensionInstallHandler,
    ExtensionUninstallHandler,
    ExtensionRunHandler,
    ExtensionConfigHandler,
)


class MessageHandler:
    """Base class for message handlers."""

    def __init__(self, bus: MessageBus):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Handle a message. Must be implemented by subclasses."""
        raise NotImplementedError

    async def send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
