"""Subagent handlers for Desktop channel."""

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


class SubagentGetAvailableToolsHandler(MessageHandler):
    """Handle get available tools for subagent configuration."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of available tools from database and system."""
        try:
            from backend.data.subagent_store import AvailableToolRepository

            tools = []

            # Load from database
            try:
                repo = AvailableToolRepository(self.db)
                db_tools = repo.get_all_tools()
                for tool in db_tools:
                    tools.append({
                        "id": tool.id,
                        "name": tool.name,
                        "description": tool.description,
                        "category": tool.category,
                        "source": "database"
                    })
            except Exception as e:
                logger.warning(f"Failed to load tools from database: {e}")

            # Also load from tool registry
            try:
                from backend.tools.registry import ToolRegistry
                registry = ToolRegistry()
                for tool_name in registry.tool_names:
                    if not any(t["name"] == tool_name for t in tools):
                        tool = registry.get(tool_name)
                        tools.append({
                            "name": tool_name,
                            "description": tool.description if tool else "",
                            "source": "registry"
                        })
            except Exception as e:
                logger.warning(f"Failed to load tools from registry: {e}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.SUBAGENT_AVAILABLE_TOOLS,
                request_id=message.request_id,
                data={"tools": tools}
            ))
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get available tools: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SubagentGetAvailableExtensionsHandler(MessageHandler):
    """Handle get available extensions for subagent configuration."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of available extensions from database and system."""
        try:
            from backend.data.subagent_store import AvailableExtensionRepository

            extensions = []

            # Load from database
            try:
                repo = AvailableExtensionRepository(self.db)
                db_extensions = repo.get_all_extensions()
                for ext in db_extensions:
                    extensions.append({
                        "id": ext.id,
                        "name": ext.name,
                        "description": ext.description,
                        "source": "database"
                    })
            except Exception as e:
                logger.warning(f"Failed to load extensions from database: {e}")

            # Also load from extension registry
            try:
                from backend.extensions.registry import ExtensionRegistry
                registry = ExtensionRegistry()
                for ext in registry.list_all():
                    if not any(e["name"] == ext.name for e in extensions):
                        extensions.append({
                            "name": ext.name,
                            "description": ext.description if hasattr(ext, 'description') else "",
                            "source": "registry"
                        })
            except Exception as e:
                logger.warning(f"Failed to load extensions from registry: {e}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.SUBAGENT_AVAILABLE_EXTENSIONS,
                request_id=message.request_id,
                data={"extensions": extensions}
            ))
        except Exception as e:
            logger.error(f"Failed to get available extensions: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get available extensions: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SubagentGetProviderModelsHandler(MessageHandler):
    """Handle get providers and models for subagent configuration."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of providers with their models."""
        try:
            from backend.data.provider_store import ProviderRepository, ModelRepository

            provider_repo = ProviderRepository(self.db)
            model_repo = ModelRepository(self.db)

            providers = []
            provider_records = provider_repo.get_all_providers()

            for provider in provider_records:
                models = model_repo.get_models_by_provider(provider.id)
                providers.append({
                    "id": provider.id,
                    "name": provider.name,
                    "displayName": provider.display_name or provider.name,
                    "type": provider.provider_type,
                    "enabled": provider.enabled,
                    "models": [
                        {
                            "id": m.id,
                            "name": m.model_id,
                            "displayName": m.display_name or m.model_id,
                            "enabled": m.enabled
                        }
                        for m in models
                    ]
                })

            await self.send_response(websocket, WSMessage(
                type=MessageType.SUBAGENT_PROVIDER_MODELS,
                request_id=message.request_id,
                data={"providers": providers}
            ))
        except Exception as e:
            logger.error(f"Failed to get providers and models: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get providers and models: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
