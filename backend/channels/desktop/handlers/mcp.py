"""MCP handlers for Desktop channel.

This module contains all MCP-related handlers for managing MCP servers,
tools, and connections.
"""

import asyncio
import json
import uuid
import time
import base64
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.mcp.manager import MCPManager, get_mcp_manager
from backend.mcp.config import MCPServerConfig
from backend.data import Database
from backend.data.provider_store import ProviderRepository


class MCPGetStatusHandler(MessageHandler):
    """Handle MCP get status requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return MCP system status."""
        try:
            status = self.mcp_manager.get_status()
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_STATUS,
                request_id=message.request_id,
                data=status
            ))
        except Exception as e:
            logger.error(f"Failed to get MCP status: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get MCP status: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class TTSHandler(MessageHandler):
    """Handle TTS related requests."""

    def __init__(self, bus, db=None):
        super().__init__(bus)
        from backend.data import Database
        self.db = db or Database()
        self._tts_repo = None
        self._session_db = None

    @property
    def tts_repo(self):
        """Lazy load TTS config repository."""
        if self._tts_repo is None:
            from backend.data.provider_store import TTSServiceConfigRepository
            self._tts_repo = TTSServiceConfigRepository(self.db)
        return self._tts_repo

    @property
    def session_db(self):
        """Lazy load session database."""
        if self._session_db is None:
            from backend.data.session_db import SessionDatabase
            from backend.utils.helpers import get_data_path
            self._session_db = SessionDatabase(get_data_path() / "sessions.db")
        return self._session_db

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Route TTS message to appropriate handler."""
        msg_type = message.type.value if hasattr(message.type, 'value') else message.type

        if msg_type == "tts_get_instance_config":
            await self._get_instance_config(websocket, message)
        elif msg_type == "tts_update_instance_config":
            await self._update_instance_config(websocket, message)
        elif msg_type == "tts_get_defaults":
            await self._get_defaults(websocket, message)
        elif msg_type == "tts_set_defaults":
            await self._set_defaults(websocket, message)
        elif msg_type == "tts_synthesize":
            await self._synthesize(websocket, message)
        elif msg_type == "tts_get_voices":
            await self._get_voices(websocket, message)
        elif msg_type == "tts_get_providers":
            await self._get_providers(websocket, message)
        elif msg_type == "tts_get_styles":
            await self._get_styles(websocket, message)
        else:
            await self._send_error(websocket, message.request_id, f"Unknown TTS message type: {msg_type}")

    async def _get_instance_config(self, websocket: WebSocket, message: WSMessage) -> None:
        """Get TTS config for a session instance."""
        try:
            instance_id = message.data.get("instance_id")
            if not instance_id:
                await self._send_error(websocket, message.request_id, "instance_id is required")
                return

            instance = self.session_db.get_instance(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_CONFIG,
                request_id=message.request_id,
                data={
                    "instanceId": instance_id,
                    "enabled": instance.tts_enabled if instance else False,
                    "config": instance.tts_config if instance else {}
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get TTS config: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get TTS config: {e}")

    async def _update_instance_config(self, websocket: WebSocket, message: WSMessage) -> None:
        """Update TTS config for a session instance."""
        try:
            instance_id = message.data.get("instance_id")
            enabled = message.data.get("enabled")
            config = message.data.get("config", {})

            if not instance_id:
                await self._send_error(websocket, message.request_id, "instance_id is required")
                return

            success = self.session_db.update_instance_tts_config(
                instance_id,
                enabled=enabled,
                config=config
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_CONFIG,
                request_id=message.request_id,
                data={"success": success, "instanceId": instance_id}
            ))
        except Exception as e:
            logger.error(f"Failed to update TTS config: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to update TTS config: {e}")

    async def _get_defaults(self, websocket: WebSocket, message: WSMessage) -> None:
        """Get global default TTS config and available models."""
        try:
            available_models = self.tts_repo.get_available_models()
            default_model = self.tts_repo.get_default_model()

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_DEFAULTS,
                request_id=message.request_id,
                data={
                    "availableModels": available_models,
                    "defaultModel": default_model,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get TTS defaults: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get TTS defaults: {e}")

    async def _set_defaults(self, websocket: WebSocket, message: WSMessage) -> None:
        """Set global default TTS config."""
        try:
            model_id = message.data.get("modelId")
            default_voice = message.data.get("defaultVoice")
            default_format = message.data.get("defaultFormat")

            success = self.tts_repo.update_config(
                default_model_id=model_id,
                default_voice=default_voice,
                default_format=default_format,
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_DEFAULTS,
                request_id=message.request_id,
                data={"success": success}
            ))
        except Exception as e:
            logger.error(f"Failed to set TTS defaults: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to set TTS defaults: {e}")

    async def _synthesize(self, websocket: WebSocket, message: WSMessage) -> None:
        """Synthesize text to speech."""
        try:
            text = message.data.get("text")
            model_id = message.data.get("modelId")
            voice = message.data.get("voice")

            if not text:
                await self._send_error(websocket, message.request_id, "text is required")
                return

            from backend.services.tts.factory import TTSFactory
            from backend.data.provider_store import ProviderRepository

            provider_repo = ProviderRepository(self.db)

            model = None
            if model_id:
                models = provider_repo.get_models_by_ids([model_id])
                if models:
                    model = models[0]

            if not model:
                default_config = self.tts_repo.get_default_model()
                if default_config:
                    model_id = default_config.get("modelDbId")
                    models = provider_repo.get_models_by_ids([model_id])
                    if models:
                        model = models[0]

            if not model:
                await self._send_error(websocket, message.request_id, "No TTS model available")
                return

            provider = provider_repo.get_provider_by_id(model.get("provider_id") if isinstance(model, dict) else model.provider_id)

            tts_provider = TTSFactory.create("openai", provider)

            result = await tts_provider.synthesize(
                text=text,
                voice=voice or "alloy"
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_AUDIO,
                request_id=message.request_id,
                data={
                    "audio": base64.b64encode(result.audio_data).decode(),
                    "format": result.format,
                    "duration_ms": result.duration_ms
                }
            ))
        except Exception as e:
            logger.error(f"Failed to synthesize TTS: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to synthesize TTS: {e}")

    async def _get_voices(self, websocket: WebSocket, message: WSMessage) -> None:
        """Get available voices for a provider type."""
        try:
            provider_type = message.data.get("provider", "openai")

            if provider_type == "mimo":
                from backend.services.tts.mimo_tts import MiMoTTS
                voices = MiMoTTS.VOICES
            else:
                from backend.services.tts.openai_tts import OpenAITTS
                voices = OpenAITTS.VOICES

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_VOICES,
                request_id=message.request_id,
                data={
                    "voices": [
                        {"id": v.id, "name": v.name, "gender": v.gender, "language": getattr(v, 'language', 'en')}
                        for v in voices
                    ]
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get TTS voices: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get TTS voices: {e}")

    async def _get_providers(self, websocket: WebSocket, message: WSMessage) -> None:
        """Get available TTS models from enabled providers."""
        try:
            available_models = self.tts_repo.get_available_models()
            default_model = self.tts_repo.get_default_model()

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_PROVIDERS,
                request_id=message.request_id,
                data={
                    "availableModels": available_models,
                    "defaultModel": default_model
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get TTS providers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get TTS providers: {e}")

    async def _get_styles(self, websocket: WebSocket, message: WSMessage) -> None:
        """Get available styles for a provider type."""
        try:
            provider_type = message.data.get("provider", "openai")

            if provider_type == "mimo":
                from backend.services.tts.mimo_tts import MiMoTTS
                styles = MiMoTTS.SUPPORTED_STYLES
            else:
                styles = []

            await self.send_response(websocket, WSMessage(
                type=MessageType.TTS_STYLES,
                request_id=message.request_id,
                data={"styles": styles}
            ))
        except Exception as e:
            logger.error(f"Failed to get TTS styles: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get TTS styles: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPGetServersHandler(MessageHandler):
    """Handle MCP get servers requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all MCP servers with their tools in standard MCP format."""
        try:
            enabled_only = message.data.get("enabled_only", False)
            servers_data = self.mcp_manager.db.get_all_servers_with_tools(enabled_only=enabled_only)

            result = []
            for item in servers_data:
                server = item["server"]
                tools = item["tools"]

                # 从 config 中提取标准 MCP 格式字段
                config = server.config or {}
                env = config.get("env_vars", {})

                # 检查连接状态
                connected = server.name in self.mcp_manager.connections

                # 根据协议类型构建返回数据
                if server.protocol == "stdio":
                    command = config.get("command", server.url.split()[0] if server.url else "")
                    args = config.get("args", server.url.split()[1:] if server.url and " " in server.url else [])
                    server_data = {
                        "name": server.name,
                        "protocol": server.protocol,
                        "enabled": server.enabled,
                        "command": command,
                        "args": args,
                        "env": env,
                        "connected": connected,
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "enabled": tool.enabled,
                            }
                            for tool in tools
                        ]
                    }
                else:
                    url = config.get("url", server.url)
                    headers = config.get("headers", {})
                    server_data = {
                        "name": server.name,
                        "protocol": server.protocol,
                        "enabled": server.enabled,
                        "url": url,
                        "headers": headers,
                        "env": env,
                        "connected": connected,
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "enabled": tool.enabled,
                            }
                            for tool in tools
                        ]
                    }

                result.append(server_data)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVERS,
                request_id=message.request_id,
                data={"servers": result}
            ))
        except Exception as e:
            logger.error(f"Failed to get MCP servers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get MCP servers: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPGetServerToolsHandler(MessageHandler):
    """Handle MCP get server tools requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return tools for a specific server."""
        try:
            server_name = message.data.get("server_name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            server, tools = self.mcp_manager.db.get_server_with_tools(server_name)
            if not server:
                await self._send_error(websocket, message.request_id, f"Server '{server_name}' not found")
                return

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_TOOLS,
                request_id=message.request_id,
                data={
                    "server": {
                        "name": server.name,
                        "enabled": server.enabled,
                    },
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "enabled": tool.enabled,
                            "parameters": tool.parameters,
                        }
                        for tool in tools
                    ]
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get MCP server tools: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get MCP server tools: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPAddServerHandler(MessageHandler):
    """Handle MCP add server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Add a new MCP server using standard MCP format.

        Supports two types of servers:
        1. stdio servers: { name, command, args, env }
        2. HTTP/SSE/WebSocket servers: { name, url, protocol, headers, env }
        """
        try:
            name = message.data.get("name")
            # stdio protocol fields
            command = message.data.get("command")
            args = message.data.get("args", [])
            env = message.data.get("env", {})
            # HTTP protocol fields
            url = message.data.get("url")
            protocol = message.data.get("protocol", "stdio")
            headers = message.data.get("headers", {})

            if not name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            # Determine server type and validate required fields
            if protocol == "stdio":
                if not command:
                    await self._send_error(websocket, message.request_id, "Command required for stdio servers")
                    return
                # Build URL from command and args for stdio protocol
                url = command
                if args:
                    url = f"{command} {' '.join(args)}"
            else:
                # HTTP/SSE/WebSocket protocol
                if not url:
                    await self._send_error(websocket, message.request_id, f"URL required for {protocol} servers")
                    return
                if protocol not in ("sse", "websocket"):
                    await self._send_error(websocket, message.request_id, f"Unsupported protocol: {protocol}")
                    return

            # Check if server already exists
            existing = self.mcp_manager.db.get_server(name)
            if existing:
                await self._send_error(websocket, message.request_id, f"Server '{name}' already exists")
                return

            # Prepare config based on server type
            if protocol == "stdio":
                server_config_dict = {"command": command, "args": args, "env_vars": env}
            else:
                server_config_dict = {"url": url, "headers": headers, "env_vars": env}

            # Create server in database
            server = self.mcp_manager.db.get_or_create_server(
                name=name,
                url=url,
                protocol=protocol,
                enabled=True,
                auto_connect=True,
                config=server_config_dict
            )

            # Add to config
            from backend.mcp.config import MCPServerConfig
            if protocol == "stdio":
                server_config = MCPServerConfig(
                    name=name,
                    url=url,
                    protocol=protocol,
                    enabled=True,
                    auto_connect=True,
                    command=command,
                    args=args,
                    env_vars=env
                )
                response_data = {"name": server.name, "command": command, "args": args, "protocol": protocol}
            else:
                server_config = MCPServerConfig(
                    name=name,
                    url=url,
                    protocol=protocol,
                    enabled=True,
                    auto_connect=True,
                    headers=headers,
                    env_vars=env
                )
                response_data = {"name": server.name, "url": url, "protocol": protocol}

            self.mcp_manager.config.servers[name] = server_config

            # Auto connect the server and discover tools
            connection = None
            discovered_tools = []
            try:
                connection = await self.mcp_manager.create_connection(server_config)
                if connection and connection.is_available:
                    # Discover tools after successful connection
                    discovered_tools = await self.mcp_manager.discover_tools(name)
            except Exception as e:
                logger.warning(f"Failed to auto-connect server '{name}': {e}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_ADDED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "server": response_data,
                    "connected": connection is not None and connection.is_available,
                    "tools": discovered_tools,
                    "discovered_count": len(discovered_tools)
                }
            ))
        except Exception as e:
            logger.error(f"Failed to add MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to add MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPDeleteServerHandler(MessageHandler):
    """Handle MCP delete server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete an MCP server."""
        try:
            name = message.data.get("name")
            if not name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            # Get tools associated with this server before deletion
            server_tools = self.mcp_manager.db.get_tools_by_server(name)
            tool_names = [tool.name for tool in server_tools]

            # Disconnect if connected
            if name in self.mcp_manager.connections:
                await self.mcp_manager.remove_connection(name)

            # Unregister tools from tool_registry
            for tool_name in tool_names:
                await self.mcp_manager.tool_registry.unregister_tool(tool_name)

            # Delete from database (this will cascade delete tools due to FK constraint)
            success = self.mcp_manager.db.delete_server(name)

            # Remove from config
            if name in self.mcp_manager.config.servers:
                del self.mcp_manager.config.servers[name]

            # Remove tools from config.tools
            for tool_name in tool_names:
                if tool_name in self.mcp_manager.config.tools:
                    del self.mcp_manager.config.tools[tool_name]

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_DELETED,
                request_id=message.request_id,
                data={"success": success, "name": name}
            ))
        except Exception as e:
            logger.error(f"Failed to delete MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPUpdateServerHandler(MessageHandler):
    """Handle MCP update server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Update server configuration."""
        try:
            server_name = message.data.get("name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            updates = {k: v for k, v in message.data.items() if k != "name" and v is not None}
            success = self.mcp_manager.db.update_server(server_name, **updates)

            if "enabled" in updates:
                if server_name in self.mcp_manager.config.servers:
                    self.mcp_manager.config.servers[server_name].enabled = updates["enabled"]

                if not updates["enabled"]:
                    if server_name in self.mcp_manager.connections:
                        logger.info(f"Disabling server '{server_name}', disconnecting...")
                        await self.mcp_manager.remove_connection(server_name)
                else:
                    if server_name not in self.mcp_manager.connections:
                        server = self.mcp_manager.db.get_server(server_name)
                        if server:
                            server_config = MCPServerConfig(
                                name=server.name,
                                url=server.url,
                                protocol=server.protocol,
                                enabled=server.enabled,
                                auto_connect=False,
                                **server.config
                            )
                            logger.info(f"Enabling server '{server_name}', connecting...")
                            connection = await self.mcp_manager.create_connection(server_config)
                            if connection and connection.is_available:
                                await self.mcp_manager.discover_tools(server_name)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_UPDATED,
                request_id=message.request_id,
                data={"success": success, "name": server_name}
            ))
        except Exception as e:
            logger.error(f"Failed to update MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to update MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPUpdateToolHandler(MessageHandler):
    """Handle MCP update tool requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Update tool configuration."""
        try:
            tool_name = message.data.get("name")
            server_name = message.data.get("server_name")

            if not tool_name:
                await self._send_error(websocket, message.request_id, "Tool name required")
                return

            # Get server_id if server_name provided
            server_id = None
            if server_name:
                server = self.mcp_manager.db.get_server(server_name)
                if server:
                    server_id = server.id

            # Get current tool state
            tool = self.mcp_manager.db.get_tool(tool_name, server_id=server_id)
            if not tool:
                await self._send_error(websocket, message.request_id, f"Tool '{tool_name}' not found")
                return

            # Update in database
            updates = {k: v for k, v in message.data.items()
                       if k not in {"name", "server_name"} and v is not None}
            success = self.mcp_manager.db.update_tool(tool_name, server_id=server_id, **updates)

            # Sync with registry if enabled state changed
            if "enabled" in updates:
                if updates["enabled"]:
                    await self.mcp_manager.tool_registry.enable_tool(tool_name)
                else:
                    await self.mcp_manager.tool_registry.disable_tool(tool_name)

                # Update config
                if tool_name in self.mcp_manager.config.tools:
                    self.mcp_manager.config.tools[tool_name].enabled = updates["enabled"]

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_TOOL_UPDATED,
                request_id=message.request_id,
                data={"success": success, "name": tool_name}
            ))
        except Exception as e:
            logger.error(f"Failed to update MCP tool: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to update MCP tool: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPDiscoverToolsHandler(MessageHandler):
    """Handle MCP discover tools requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Discover tools from a server."""
        try:
            server_name = message.data.get("server_name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            tools = await self.mcp_manager.discover_tools(server_name)
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_TOOLS_DISCOVERED,
                request_id=message.request_id,
                data={
                    "server_name": server_name,
                    "tools": tools,
                    "discovered_count": len(tools) if tools else 0
                }
            ))
        except Exception as e:
            logger.error(f"Failed to discover MCP tools: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to discover MCP tools: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPConnectServerHandler(MessageHandler):
    """Handle MCP connect server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Connect to an MCP server."""
        try:
            server_name = message.data.get("name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            server = self.mcp_manager.db.get_server(server_name)
            if not server:
                await self._send_error(websocket, message.request_id, f"Server '{server_name}' not found")
                return

            # Create server config from database record
            # Handle backward compatibility: convert "env" to "env_vars" if needed
            server_config_dict = server.config.copy() if server.config else {}
            if "env" in server_config_dict and "env_vars" not in server_config_dict:
                server_config_dict["env_vars"] = server_config_dict.pop("env")

            server_config = MCPServerConfig(
                name=server.name,
                url=server.url,
                protocol=server.protocol,
                enabled=server.enabled,
                auto_connect=server.auto_connect,
                **server_config_dict
            )

            connection = await self.mcp_manager.create_connection(server_config)
            if connection and connection.is_available:
                await self.mcp_manager.discover_tools(server_name)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_CONNECTED,
                request_id=message.request_id,
                data={
                    "success": connection is not None,
                    "connection": connection.get_info() if connection else None,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to connect MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to connect MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPDisconnectServerHandler(MessageHandler):
    """Handle MCP disconnect server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Disconnect from an MCP server."""
        try:
            server_name = message.data.get("name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            success = await self.mcp_manager.remove_connection(server_name)
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_DISCONNECTED,
                request_id=message.request_id,
                data={"success": success, "name": server_name}
            ))
        except Exception as e:
            logger.error(f"Failed to disconnect MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to disconnect MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPReconnectServerHandler(MessageHandler):
    """Handle MCP reconnect server requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Reconnect to an MCP server."""
        try:
            server_name = message.data.get("name")
            if not server_name:
                await self._send_error(websocket, message.request_id, "Server name required")
                return

            server = self.mcp_manager.db.get_server(server_name)
            if not server:
                await self._send_error(websocket, message.request_id, f"Server '{server_name}' not found")
                return

            await self.mcp_manager.remove_connection(server_name)

            # Handle backward compatibility: convert "env" to "env_vars" if needed
            server_config_dict = server.config.copy() if server.config else {}
            if "env" in server_config_dict and "env_vars" not in server_config_dict:
                server_config_dict["env_vars"] = server_config_dict.pop("env")

            server_config = MCPServerConfig(
                name=server.name,
                url=server.url,
                protocol=server.protocol,
                enabled=server.enabled,
                auto_connect=server.auto_connect,
                **server_config_dict
            )

            connection = await self.mcp_manager.create_connection(server_config)
            if connection and connection.is_available:
                await self.mcp_manager.discover_tools(server_name)

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_CONNECTED,
                request_id=message.request_id,
                data={
                    "success": connection is not None,
                    "connection": connection.get_info() if connection else None,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to reconnect MCP server: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to reconnect MCP server: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPCallToolHandler(MessageHandler):
    """Handle MCP call tool requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Call an MCP tool."""
        try:
            tool_name = message.data.get("name")
            params = message.data.get("params", {})
            server_name = message.data.get("server_name")

            if not tool_name:
                await self._send_error(websocket, message.request_id, "Tool name required")
                return

            result = await self.mcp_manager.call_tool(tool_name, params, server_name)
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_TOOL_RESULT,
                request_id=message.request_id,
                data={"result": result}
            ))
        except Exception as e:
            logger.error(f"Failed to call MCP tool: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to call MCP tool: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPGetConfigHandler(MessageHandler):
    """Handle MCP get config requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return MCP configuration."""
        try:
            config = self.mcp_manager.get_config_dict()
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_CONFIG,
                request_id=message.request_id,
                data=config
            ))
        except Exception as e:
            logger.error(f"Failed to get MCP config: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get MCP config: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPUpdateConfigHandler(MessageHandler):
    """Handle MCP update config requests."""

    def __init__(self, bus, mcp_manager: MCPManager):
        super().__init__(bus)
        self.mcp_manager = mcp_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Update MCP configuration."""
        try:
            config_data = message.data.get("config")
            if config_data is None:
                await self._send_error(websocket, message.request_id, "Config data is required")
                return

            success = await self.mcp_manager.update_config(config_data)
            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_CONFIG_UPDATED,
                request_id=message.request_id,
                data={"success": success, "config": self.mcp_manager.get_config_dict()}
            ))
        except Exception as e:
            logger.error(f"Failed to update MCP config: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to update MCP config: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


# Export all handlers
__all__ = [
    "MCPGetStatusHandler",
    "TTSHandler",
    "MCPGetServersHandler",
    "MCPGetServerToolsHandler",
    "MCPAddServerHandler",
    "MCPDeleteServerHandler",
    "MCPUpdateServerHandler",
    "MCPUpdateToolHandler",
    "MCPDiscoverToolsHandler",
    "MCPConnectServerHandler",
    "MCPDisconnectServerHandler",
    "MCPReconnectServerHandler",
    "MCPCallToolHandler",
    "MCPGetConfigHandler",
    "MCPUpdateConfigHandler",
]
