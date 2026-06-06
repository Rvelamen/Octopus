"""Subagent handlers for Desktop channel."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.schemas import (
    SubagentGetAvailableExtensionsRequest,
    SubagentGetAvailableToolsRequest,
    SubagentGetProviderModelsRequest,
)
from backend.core.events.bus import MessageBus
from backend.data import Database
from backend.data.subagent_seeder import DEFAULT_AVAILABLE_TOOLS


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
                    tools.append(
                        {
                            "id": tool.id,
                            "name": tool.name,
                            "description": tool.description,
                            "category": tool.category,
                            "source": "database",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load tools from database: {e}")

            # Also load built-in tools that may not yet be in the database
            try:
                for (
                    name,
                    display_name,
                    description,
                    category,
                    _sort_order,
                ) in DEFAULT_AVAILABLE_TOOLS:
                    if not any(t["name"] == name for t in tools):
                        tools.append(
                            {
                                "name": name,
                                "display_name": display_name,
                                "description": description,
                                "category": category,
                                "source": "builtin",
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to load built-in tools: {e}")

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_AVAILABLE_TOOLS,
                    request_id=message.request_id,
                    data={"tools": tools},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get available tools: {e}"
            )

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: SubagentGetAvailableToolsRequest
    ) -> None:
        """Return list of available tools from database and system."""
        try:
            from backend.data.subagent_store import AvailableToolRepository

            tools = []

            # Load from database
            try:
                repo = AvailableToolRepository(self.db)
                db_tools = repo.get_all_tools()
                for tool in db_tools:
                    tools.append(
                        {
                            "id": tool.id,
                            "name": tool.name,
                            "description": tool.description,
                            "category": tool.category,
                            "source": "database",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load tools from database: {e}")

            # Also load built-in tools that may not yet be in the database
            try:
                for (
                    name,
                    display_name,
                    description,
                    category,
                    _sort_order,
                ) in DEFAULT_AVAILABLE_TOOLS:
                    if not any(t["name"] == name for t in tools):
                        tools.append(
                            {
                                "name": name,
                                "display_name": display_name,
                                "description": description,
                                "category": category,
                                "source": "builtin",
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to load built-in tools: {e}")

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_AVAILABLE_TOOLS,
                    request_id=message.request_id,
                    data={"tools": tools},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get available tools: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


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
                    extensions.append(
                        {
                            "id": ext.id,
                            "name": ext.name,
                            "description": ext.description,
                            "source": "database",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load extensions from database: {e}")

            # Also load from extension registry
            try:
                from backend.extensions.registry import ExtensionRegistry

                registry = ExtensionRegistry()
                for ext in registry.list_all():
                    if not any(e["name"] == ext.name for e in extensions):
                        extensions.append(
                            {
                                "name": ext.name,
                                "description": (
                                    ext.description if hasattr(ext, "description") else ""
                                ),
                                "source": "registry",
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to load extensions from registry: {e}")

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_AVAILABLE_EXTENSIONS,
                    request_id=message.request_id,
                    data={"extensions": extensions},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get available extensions: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get available extensions: {e}"
            )

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: SubagentGetAvailableExtensionsRequest,
    ) -> None:
        """Return list of available extensions from database and system."""
        try:
            from backend.data.subagent_store import AvailableExtensionRepository

            extensions = []

            # Load from database
            try:
                repo = AvailableExtensionRepository(self.db)
                db_extensions = repo.get_all_extensions()
                for ext in db_extensions:
                    extensions.append(
                        {
                            "id": ext.id,
                            "name": ext.name,
                            "description": ext.description,
                            "source": "database",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load extensions from database: {e}")

            # Also load from extension registry
            try:
                from backend.extensions.registry import ExtensionRegistry

                registry = ExtensionRegistry()
                for ext in registry.list_all():
                    if not any(e["name"] == ext.name for e in extensions):
                        extensions.append(
                            {
                                "name": ext.name,
                                "description": (
                                    ext.description if hasattr(ext, "description") else ""
                                ),
                                "source": "registry",
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to load extensions from registry: {e}")

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_AVAILABLE_EXTENSIONS,
                    request_id=message.request_id,
                    data={"extensions": extensions},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get available extensions: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get available extensions: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


class SubagentGetProviderModelsHandler(MessageHandler):
    """Handle get providers and models for subagent configuration."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of providers with their models."""
        try:
            from backend.data.provider_store import ModelRepository, ProviderRepository

            provider_repo = ProviderRepository(self.db)
            model_repo = ModelRepository(self.db)

            providers = []
            provider_records = provider_repo.get_all_providers()

            for provider in provider_records:
                models = model_repo.get_models_by_provider(provider.id)
                providers.append(
                    {
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
                                "enabled": m.enabled,
                            }
                            for m in models
                        ],
                    }
                )

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_PROVIDER_MODELS,
                    request_id=message.request_id,
                    data={"providers": providers},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get providers and models: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get providers and models: {e}"
            )

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: SubagentGetProviderModelsRequest
    ) -> None:
        """Return list of providers with their models."""
        try:
            from backend.data.provider_store import ModelRepository, ProviderRepository

            provider_repo = ProviderRepository(self.db)
            model_repo = ModelRepository(self.db)

            providers = []
            provider_records = provider_repo.get_all_providers()

            for provider in provider_records:
                models = model_repo.get_models_by_provider(provider.id)
                providers.append(
                    {
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
                                "enabled": m.enabled,
                            }
                            for m in models
                        ],
                    }
                )

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SUBAGENT_PROVIDER_MODELS,
                    request_id=message.request_id,
                    data={"providers": providers},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get providers and models: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get providers and models: {e}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )


# ═══════════════════════════════════════════════════════════════════
# Subagent CRUD handlers (added for PDF Chat Agent configuration)
# ═══════════════════════════════════════════════════════════════════


class SubagentListHandler(MessageHandler):
    """List all subagents."""

    def __init__(self, bus, db=None):
        super().__init__(bus)
        from backend.data.database import Database

        self.db = db or Database()
        from backend.data.subagent_store import SubagentRepository

        self.repo = SubagentRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            records = self.repo.get_all_subagents()
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.CHAT_RESPONSE,
                    request_id=message.request_id,
                    data={
                        "subagents": [
                            {
                                "id": r.id,
                                "name": r.name,
                                "description": r.description,
                                "provider_id": r.provider_id,
                                "model_id": r.model_id,
                                "tools": r.tools,
                                "extensions": r.extensions,
                                "max_iterations": r.max_iterations,
                                "temperature": r.temperature,
                                "system_prompt": r.system_prompt,
                                "enabled": r.enabled,
                                "is_builtin": r.is_builtin,
                                "created_at": r.created_at.isoformat() if r.created_at else None,
                                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                            }
                            for r in records
                        ]
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to list subagents: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": str(e)},
                ),
            )


class SubagentSaveHandler(MessageHandler):
    """Create or update a subagent."""

    def __init__(self, bus, db=None):
        super().__init__(bus)
        from backend.data.database import Database

        self.db = db or Database()
        from backend.data.subagent_store import SubagentRepository

        self.repo = SubagentRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data
            subagent_id = data.get("id")
            name = data.get("name", "")
            description = data.get("description", "")
            provider_id = data.get("provider_id")
            model_id = data.get("model_id")
            tools = data.get("tools", [])
            extensions = data.get("extensions", [])
            max_iterations = data.get("max_iterations", 30)
            temperature = data.get("temperature", 0.7)
            system_prompt = data.get("system_prompt", "")
            enabled = data.get("enabled", True)

            if subagent_id:
                self.repo.update_subagent(
                    subagent_id=subagent_id,
                    name=name,
                    description=description,
                    provider_id=provider_id,
                    model_id=model_id,
                    tools=tools,
                    extensions=extensions,
                    max_iterations=max_iterations,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    enabled=enabled,
                )
                record = self.repo.get_subagent_by_id(subagent_id)
            else:
                record = self.repo.create_subagent(
                    name=name,
                    description=description,
                    provider_id=provider_id,
                    model_id=model_id,
                    tools=tools,
                    extensions=extensions,
                    max_iterations=max_iterations,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    enabled=enabled,
                )

            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.CHAT_RESPONSE,
                    request_id=message.request_id,
                    data={
                        "subagent": {
                            "id": record.id,
                            "name": record.name,
                            "description": record.description,
                            "provider_id": record.provider_id,
                            "model_id": record.model_id,
                            "tools": record.tools,
                            "extensions": record.extensions,
                            "max_iterations": record.max_iterations,
                            "temperature": record.temperature,
                            "system_prompt": record.system_prompt,
                            "enabled": record.enabled,
                            "created_at": (
                                record.created_at.isoformat() if record.created_at else None
                            ),
                            "updated_at": (
                                record.updated_at.isoformat() if record.updated_at else None
                            ),
                        }
                    },
                ),
            )
        except Exception as e:
            logger.error(f"Failed to save subagent: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": str(e)},
                ),
            )


class SubagentDeleteHandler(MessageHandler):
    """Delete a subagent."""

    def __init__(self, bus, db=None):
        super().__init__(bus)
        from backend.data.database import Database

        self.db = db or Database()
        from backend.data.subagent_store import SubagentRepository

        self.repo = SubagentRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            subagent_id = message.data.get("id")
            if subagent_id:
                success = self.repo.delete_subagent(subagent_id)
                if not success:
                    await self.send_response(
                        websocket,
                        WSMessage(
                            type=MessageType.ERROR,
                            request_id=message.request_id,
                            data={"error": "Built-in subagents cannot be deleted"},
                        ),
                    )
                    return
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.CHAT_RESPONSE,
                    request_id=message.request_id,
                    data={"success": True},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete subagent: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": str(e)},
                ),
            )
