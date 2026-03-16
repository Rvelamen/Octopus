"""Provider, Model and Settings handlers for WebSocket communication."""

import json
from typing import TYPE_CHECKING

from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data.provider_store import ProviderRepository, ModelRepository, SettingsRepository

if TYPE_CHECKING:
    from backend.data.database import Database


class ProviderHandler:
    """Handler for provider-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        self.provider_repo = ProviderRepository(db)
        self.model_repo = ModelRepository(db)
        self.event_bus = event_bus

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "provider_get_all":
                await self._get_all(websocket, msg_data, request_id)
            elif msg_type == "provider_get":
                await self._get(websocket, msg_data, request_id)
            elif msg_type == "provider_add":
                await self._add(websocket, msg_data, request_id)
            elif msg_type == "provider_update":
                await self._update(websocket, msg_data, request_id)
            elif msg_type == "provider_delete":
                await self._delete(websocket, msg_data, request_id)
            elif msg_type == "provider_enable":
                await self._enable(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"ProviderHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_all(self, websocket, data: dict, request_id: str = None):
        """Get all providers."""
        try:
            providers = self.provider_repo.get_all_providers()
            logger.debug(f"Got {len(providers)} providers from database")
            
            provider_list = []
            for p in providers:
                try:
                    models = self.model_repo.get_enabled_models_by_provider(p.id)
                    provider_list.append({
                        "id": p.id,
                        "name": p.name,
                        "displayName": p.display_name,
                        "providerType": p.provider_type,
                        "apiKey": p.api_key,
                        "apiHost": p.api_host,
                        "apiVersion": p.api_version,
                        "enabled": p.enabled,
                        "isSystem": p.is_system,
                        "sortOrder": p.sort_order,
                        "config": p.config_json,
                        "modelCount": len(models),
                    })
                except Exception as e:
                    logger.error(f"Error processing provider {p.id}: {e}")
                    raise
            
            response = {
                "type": MessageType.PROVIDERS.value,
                "request_id": request_id,
                "data": {"providers": provider_list}
            }
            logger.debug(f"Sending response with {len(provider_list)} providers")
            await websocket.send_json(response)
        except Exception as e:
            logger.error(f"Error in _get_all: {e}")
            raise

    async def _get(self, websocket, data: dict, request_id: str = None):
        """Get a single provider by ID."""
        provider_id = data.get("id")
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        provider = self.provider_repo.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")
        
        models = self.model_repo.get_models_by_provider(provider.id)
        model_list = [{
            "id": m.id,
            "modelId": m.model_id,
            "displayName": m.display_name,
            "modelType": m.model_type,
            "groupName": m.group_name,
            "maxTokens": m.max_tokens,
            "contextWindow": m.context_window,
            "supportsVision": m.supports_vision,
            "supportsFunctionCalling": m.supports_function_calling,
            "supportsStreaming": m.supports_streaming,
            "enabled": m.enabled,
            "isDefault": m.is_default,
        } for m in models]
        
        await websocket.send_json({
            "type": MessageType.PROVIDER.value,
            "request_id": request_id,
            "data": {
                "provider": {
                    "id": provider.id,
                    "name": provider.name,
                    "displayName": provider.display_name,
                    "providerType": provider.provider_type,
                    "apiKey": provider.api_key,
                    "apiHost": provider.api_host,
                    "apiVersion": provider.api_version,
                    "enabled": provider.enabled,
                    "isSystem": provider.is_system,
                },
                "models": model_list
            }
        })

    async def _add(self, websocket, data: dict, request_id: str = None):
        """Add a new provider."""
        provider = self.provider_repo.add_provider(
            name=data.get("name"),
            display_name=data.get("displayName", data.get("name")),
            provider_type=data.get("providerType"),
            api_key=data.get("apiKey", ""),
            api_host=data.get("apiHost", ""),
            api_version=data.get("apiVersion", ""),
            enabled=data.get("enabled", True),
            is_system=False
        )
        await websocket.send_json({
            "type": MessageType.PROVIDER_ADDED.value,
            "request_id": request_id,
            "data": {
                "id": provider.id,
                "name": provider.name,
                "displayName": provider.display_name,
                "providerType": provider.provider_type,
                "enabled": provider.enabled,
            }
        })

    async def _update(self, websocket, data: dict, request_id: str = None):
        """Update a provider."""
        provider_id = data.get("id")
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        success = self.provider_repo.update_provider(
            provider_id=provider_id,
            api_key=data.get("apiKey"),
            api_host=data.get("apiHost"),
            api_version=data.get("apiVersion"),
            enabled=data.get("enabled"),
            sort_order=data.get("sortOrder"),
            config_json=data.get("config"),
        )
        
        if success:
            await websocket.send_json({
                "type": MessageType.PROVIDER_UPDATED.value,
                "request_id": request_id,
                "data": {"id": provider_id}
            })
        else:
            raise ValueError(f"Provider {provider_id} not found")

    async def _delete(self, websocket, data: dict, request_id: str = None):
        """Delete a provider."""
        provider_id = data.get("id")
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        success = self.provider_repo.delete_provider(provider_id)
        if success:
            await websocket.send_json({
                "type": MessageType.PROVIDER_DELETED.value,
                "request_id": request_id,
                "data": {"id": provider_id}
            })
        else:
            raise ValueError(f"Provider {provider_id} not found")

    async def _enable(self, websocket, data: dict, request_id: str = None):
        """Enable/disable a provider."""
        provider_id = data.get("id")
        enabled = data.get("enabled", True)
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        success = self.provider_repo.update_provider(
            provider_id=provider_id,
            enabled=enabled,
        )
        
        if success:
            await websocket.send_json({
                "type": MessageType.PROVIDER_UPDATED.value,
                "request_id": request_id,
                "data": {"id": provider_id, "enabled": enabled}
            })
        else:
            raise ValueError(f"Provider {provider_id} not found")


class ModelHandler:
    """Handler for model-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        self.model_repo = ModelRepository(db)
        self.provider_repo = ProviderRepository(db)

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "model_get_all":
                await self._get_all(websocket, msg_data, request_id)
            elif msg_type == "model_add":
                await self._add(websocket, msg_data, request_id)
            elif msg_type == "model_update":
                await self._update(websocket, msg_data, request_id)
            elif msg_type == "model_delete":
                await self._delete(websocket, msg_data, request_id)
            elif msg_type == "model_set_default":
                await self._set_default(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"ModelHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_all(self, websocket, data: dict, request_id: str = None):
        """Get all models for a provider."""
        provider_id = data.get("providerId") or data.get("provider_id")
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        models = self.model_repo.get_models_by_provider(provider_id)
        model_list = [{
            "id": m.id,
            "modelId": m.model_id,
            "displayName": m.display_name,
            "modelTypes": m.model_types,
            "groupName": m.group_name,
            "maxTokens": m.max_tokens,
            "contextWindow": m.context_window,
            "supportsVision": m.supports_vision,
            "supportsFunctionCalling": m.supports_function_calling,
            "supportsStreaming": m.supports_streaming,
            "enabled": m.enabled,
            "isDefault": m.is_default,
            "description": m.description,
            "pricing": m.pricing_json,
        } for m in models]
        
        await websocket.send_json({
            "type": MessageType.MODELS_LIST.value,
            "request_id": request_id,
            "data": {"models": model_list, "providerId": provider_id}
        })

    async def _add(self, websocket, data: dict, request_id: str = None):
        """Add a new model."""
        provider_id = data.get("providerId") or data.get("provider_id")
        if not provider_id:
            raise ValueError("Provider ID is required")
        
        model = self.model_repo.add_model(
            provider_id=provider_id,
            model_id=data.get("modelId") or data.get("model_id"),
            display_name=data.get("displayName", data.get("modelId", "New Model")),
            model_types=data.get("modelTypes", ["chat"]),
            group_name=data.get("groupName", "Chat Models"),
            max_tokens=data.get("maxTokens", 4096),
            context_window=data.get("contextWindow", 128000),
            supports_vision=data.get("supportsVision", False),
            supports_function_calling=data.get("supportsFunctionCalling", True),
            supports_streaming=data.get("supportsStreaming", True),
            enabled=data.get("enabled", True),
            is_default=data.get("isDefault", False)
        )
        
        await websocket.send_json({
            "type": MessageType.MODEL_ADDED.value,
            "request_id": request_id,
            "data": {
                "id": model.id,
                "modelId": model.model_id,
                "displayName": model.display_name,
                "providerId": provider_id,
            }
        })

    async def _update(self, websocket, data: dict, request_id: str = None):
        """Update a model."""
        model_id = data.get("id")
        if not model_id:
            raise ValueError("Model ID is required")
        
        success = self.model_repo.update_model(
            model_id=model_id,
            display_name=data.get("displayName"),
            model_types=data.get("modelTypes"),
            group_name=data.get("groupName"),
            max_tokens=data.get("maxTokens"),
            context_window=data.get("contextWindow"),
            supports_vision=data.get("supportsVision"),
            supports_function_calling=data.get("supportsFunctionCalling"),
            supports_streaming=data.get("supportsStreaming"),
            enabled=data.get("enabled"),
            is_default=data.get("isDefault"),
            config_json=data.get("config"),
        )
        
        if success:
            await websocket.send_json({
                "type": MessageType.MODEL_UPDATED.value,
                "request_id": request_id,
                "data": {"id": model_id}
            })
        else:
            raise ValueError(f"Model {model_id} not found")

    async def _delete(self, websocket, data: dict, request_id: str = None):
        """Delete a model."""
        model_id = data.get("id")
        if not model_id:
            raise ValueError("Model ID is required")
        
        success = self.model_repo.delete_model(model_id)
        if success:
            await websocket.send_json({
                "type": MessageType.MODEL_DELETED.value,
                "request_id": request_id,
                "data": {"id": model_id}
            })
        else:
            raise ValueError(f"Model {model_id} not found")

    async def _set_default(self, websocket, data: dict, request_id: str = None):
        """Set default model for a provider."""
        model_id = data.get("id")
        if not model_id:
            raise ValueError("Model ID is required")
        
        model = self.model_repo.get_model_by_id(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        self.model_repo.update_model(model_id=model_id, is_default=True)
        
        await websocket.send_json({
            "type": MessageType.MODEL_UPDATED.value,
            "request_id": request_id,
            "data": {"id": model_id, "isDefault": True}
        })


class SettingsHandler:
    """Handler for settings-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        self.settings_repo = SettingsRepository(db)

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "settings_get":
                await self._get(websocket, msg_data, request_id)
            elif msg_type == "settings_set":
                await self._set(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"SettingsHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get(self, websocket, data: dict, request_id: str = None):
        """Get settings."""
        keys = data.get("keys", [])
        if keys:
            settings = {k: self.settings_repo.get_setting_typed(k) for k in keys}
        else:
            settings = self.settings_repo.get_all_settings()
        
        await websocket.send_json({
            "type": MessageType.SETTINGS.value,
            "request_id": request_id,
            "data": {"settings": settings}
        })

    async def _set(self, websocket, data: dict, request_id: str = None):
        """Set a setting."""
        key = data.get("key")
        value = data.get("value")
        value_type = data.get("valueType", "string")

        if not key:
            raise ValueError("Setting key is required")

        self.settings_repo.set_setting(key, value, value_type)

        await websocket.send_json({
            "type": MessageType.SETTINGS.value,
            "request_id": request_id,
            "data": {"key": key, "value": value}
        })


class AgentDefaultsHandler:
    """Handler for agent defaults-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        from backend.data.provider_store import AgentDefaultsRepository, ProviderRepository, ModelRepository
        self.agent_defaults_repo = AgentDefaultsRepository(db)
        self.provider_repo = ProviderRepository(db)
        self.model_repo = ModelRepository(db)
        self.event_bus = event_bus

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "agent_defaults_get":
                await self._get(websocket, msg_data, request_id)
            elif msg_type == "agent_defaults_update":
                await self._update(websocket, msg_data, request_id)
            elif msg_type == "get_enabled_models":
                await self._get_enabled_models(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"AgentDefaultsHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get(self, websocket, data: dict, request_id: str = None):
        """Get agent defaults with provider and model details."""
        defaults = self.agent_defaults_repo.get_or_create_defaults()

        # Get provider details
        provider_name = None
        provider_display_name = None
        if defaults.default_provider_id:
            provider = self.provider_repo.get_provider_by_id(defaults.default_provider_id)
            if provider:
                provider_name = provider.name
                provider_display_name = provider.display_name

        # Get model details
        model_name = None
        model_display_name = None
        if defaults.default_model_id:
            model = self.model_repo.get_model_by_id(defaults.default_model_id)
            if model:
                model_name = model.model_id
                model_display_name = model.display_name

        await websocket.send_json({
            "type": MessageType.AGENT_DEFAULTS.value,
            "request_id": request_id,
            "data": {
                "defaultProviderId": defaults.default_provider_id,
                "defaultProviderName": provider_name,
                "defaultProviderDisplayName": provider_display_name,
                "defaultModelId": defaults.default_model_id,
                "defaultModelName": model_name,
                "defaultModelDisplayName": model_display_name,
                "workspacePath": defaults.workspace_path,
                "maxTokens": defaults.max_tokens,
                "temperature": defaults.temperature,
                "maxIterations": defaults.max_iterations,
                "contextCompressionEnabled": defaults.context_compression_enabled,
                "contextCompressionTurns": defaults.context_compression_turns,
                "heartbeatEnabled": defaults.heartbeat_enabled,
                "heartbeatInterval": defaults.heartbeat_interval,
                "heartbeatChannel": defaults.heartbeat_channel,
                "config": defaults.config_json,
            }
        })

    async def _update(self, websocket, data: dict, request_id: str = None):
        """Update agent defaults."""
        success = self.agent_defaults_repo.update_agent_defaults(
            default_provider_id=data.get("defaultProviderId"),
            default_model_id=data.get("defaultModelId"),
            workspace_path=data.get("workspacePath"),
            max_tokens=data.get("maxTokens"),
            temperature=data.get("temperature"),
            max_iterations=data.get("maxIterations"),
            context_compression_enabled=data.get("contextCompressionEnabled"),
            context_compression_turns=data.get("contextCompressionTurns"),
            heartbeat_enabled=data.get("heartbeatEnabled"),
            heartbeat_interval=data.get("heartbeatInterval"),
            heartbeat_channel=data.get("heartbeatChannel"),
            config_json=data.get("config"),
        )

        if success:
            await websocket.send_json({
                "type": MessageType.AGENT_DEFAULTS_UPDATED.value,
                "request_id": request_id,
                "data": {"success": True}
            })
        else:
            raise ValueError("Failed to update agent defaults")

    async def _get_enabled_models(self, websocket, data: dict, request_id: str = None):
        """Get all enabled models from enabled providers for selection."""
        models = self.agent_defaults_repo.get_enabled_models_for_selection()

        await websocket.send_json({
            "type": MessageType.ENABLED_MODELS.value,
            "request_id": request_id,
            "data": {"models": models}
        })


class ChannelConfigHandler:
    """Handler for channel config-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        from backend.data.provider_store import ChannelConfigRepository
        self.channel_repo = ChannelConfigRepository(db)
        self.event_bus = event_bus

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "channel_get_list":
                await self._get_list(websocket, msg_data, request_id)
            elif msg_type == "channel_update":
                await self._update(websocket, msg_data, request_id)
            elif msg_type == "channel_delete":
                await self._delete(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"ChannelConfigHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_list(self, websocket, data: dict, request_id: str = None):
        """Get all channel configs."""
        channels = self.channel_repo.get_all_channel_configs()

        await websocket.send_json({
            "type": MessageType.CHANNEL_LIST.value,
            "request_id": request_id,
            "data": {
                "channels": [
                    {
                        "id": c.id,
                        "channelName": c.channel_name,
                        "channelType": c.channel_type,
                        "enabled": c.enabled,
                        "appId": c.app_id,
                        "appSecret": c.app_secret,
                        "encryptKey": c.encrypt_key,
                        "verificationToken": c.verification_token,
                        "allowFrom": c.allow_from,
                    }
                    for c in channels
                ]
            }
        })

    async def _update(self, websocket, data: dict, request_id: str = None):
        """Update channel config."""
        success = self.channel_repo.create_or_update_channel_config(
            channel_name=data.get("channelName"),
            channel_type=data.get("channelType", data.get("channelName")),
            enabled=data.get("enabled", False),
            app_id=data.get("appId", ""),
            app_secret=data.get("appSecret", ""),
            encrypt_key=data.get("encryptKey", ""),
            verification_token=data.get("verificationToken", ""),
            allow_from=data.get("allowFrom", []),
        )

        if success:
            await websocket.send_json({
                "type": MessageType.CHANNEL_UPDATED.value,
                "request_id": request_id,
                "data": {"success": True}
            })
        else:
            raise ValueError("Failed to update channel config")

    async def _delete(self, websocket, data: dict, request_id: str = None):
        """Delete channel config."""
        channel_name = data.get("channelName")
        if not channel_name:
            raise ValueError("channelName is required")

        success = self.channel_repo.delete_channel_config(channel_name)

        if success:
            await websocket.send_json({
                "type": MessageType.CHANNEL_DELETED.value,
                "request_id": request_id,
                "data": {"success": True, "channelName": channel_name}
            })
        else:
            raise ValueError(f"Channel {channel_name} not found")


class ToolConfigHandler:
    """Handler for tool config-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        from backend.data.provider_store import ToolConfigRepository
        self.tool_repo = ToolConfigRepository(db)
        self.event_bus = event_bus

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "tool_get_config":
                await self._get_config(websocket, msg_data, request_id)
            elif msg_type == "tool_update_config":
                await self._update_config(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"ToolConfigHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_config(self, websocket, data: dict, request_id: str = None):
        """Get all tool configs."""
        tools = self.tool_repo.get_all_tool_configs()

        await websocket.send_json({
            "type": MessageType.TOOL_CONFIG.value,
            "request_id": request_id,
            "data": {
                "tools": [
                    {
                        "id": t.id,
                        "toolName": t.tool_name,
                        "enabled": t.enabled,
                        "timeout": t.timeout,
                        "restrictToWorkspace": t.restrict_to_workspace,
                        "searchApiKey": t.search_api_key,
                        "searchMaxResults": t.search_max_results,
                    }
                    for t in tools
                ]
            }
        })

    async def _update_config(self, websocket, data: dict, request_id: str = None):
        """Update tool config."""
        success = self.tool_repo.create_or_update_tool_config(
            tool_name=data.get("toolName"),
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 60),
            restrict_to_workspace=data.get("restrictToWorkspace", True),
            search_api_key=data.get("searchApiKey", ""),
            search_max_results=data.get("searchMaxResults", 5),
        )

        if success:
            await websocket.send_json({
                "type": MessageType.TOOL_UPDATED.value,
                "request_id": request_id,
                "data": {"success": True}
            })
        else:
            raise ValueError("Failed to update tool config")


class ImageProviderConfigHandler:
    """Handler for image service config-related WebSocket messages."""

    def __init__(self, bus, db: "Database", event_bus=None):
        self.db = db
        from backend.data.provider_store import ImageServiceConfigRepository
        self.image_repo = ImageServiceConfigRepository(db)
        self.event_bus = event_bus

    async def handle(self, websocket, message: WSMessage) -> None:
        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        msg_data = message.data
        if isinstance(msg_data, str):
            try:
                msg_data = json.loads(msg_data) if msg_data else {}
            except:
                msg_data = {}
        elif not isinstance(msg_data, dict):
            msg_data = {}

        request_id = message.request_id

        try:
            if msg_type == "image_get_providers":
                await self._get_providers(websocket, msg_data, request_id)
            elif msg_type == "image_set_default_provider":
                await self._set_default_provider(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"ImageProviderConfigHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_providers(self, websocket, data: dict, request_id: str = None):
        """Get available models and default config for image services."""
        # Get available models for understanding and generation
        understanding_models = self.image_repo.get_available_models('understanding')
        generation_models = self.image_repo.get_available_models('generation')

        # Get default selections
        default_understanding = self.image_repo.get_default_model('understanding')
        default_generation = self.image_repo.get_default_model('generation')

        # Get config for sizes and quality
        understanding_config = self.image_repo.get_config('understanding')
        generation_config = self.image_repo.get_config('generation')

        await websocket.send_json({
            "type": MessageType.IMAGE_PROVIDERS.value,
            "request_id": request_id,
            "data": {
                "understanding": {
                    "availableModels": understanding_models,
                    "defaultModel": default_understanding,
                },
                "generation": {
                    "availableModels": generation_models,
                    "defaultModel": default_generation,
                    "defaultSize": generation_config.default_size if generation_config else "1024x1024",
                    "defaultQuality": generation_config.default_quality if generation_config else "standard",
                },
            }
        })

    async def _set_default_provider(self, websocket, data: dict, request_id: str = None):
        """Set default model for image service."""
        model_id = data.get("modelId")
        config_type = data.get("configType")  # 'understanding' or 'generation'

        if not model_id or not config_type:
            raise ValueError("modelId and configType are required")

        if config_type not in ["understanding", "generation"]:
            raise ValueError(f"Invalid configType: {config_type}")

        # Get additional config for generation
        default_size = data.get("defaultSize")
        default_quality = data.get("defaultQuality")

        success = self.image_repo.update_config(
            config_type=config_type,
            default_model_id=model_id,
            default_size=default_size,
            default_quality=default_quality,
        )

        if success:
            await websocket.send_json({
                "type": MessageType.IMAGE_DEFAULT_PROVIDER_UPDATED.value,
                "request_id": request_id,
                "data": {"success": True}
            })
        else:
            raise ValueError("Failed to set default image model")
