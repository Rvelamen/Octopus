"""WebSocket message handlers for Desktop channel."""

import asyncio
import json
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


class ChatHandler(MessageHandler):
    """Handle chat messages from clients."""

    def __init__(self, bus: MessageBus, pending_responses: dict[str, asyncio.Queue], image_service=None):
        super().__init__(bus)
        self.pending_responses = pending_responses
        self.image_service = image_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Process a chat message and forward to agent."""
        content = message.data.get("content", "")
        images = message.data.get("images", [])  # List of uploaded image paths

        # Get instance_id if provided (for continuing existing conversation)
        instance_id = message.data.get("instance_id")

        # Generate request_id if not provided
        request_id = message.request_id or str(uuid.uuid4())

        # Create response queue for this request
        response_queue = asyncio.Queue()
        self.pending_responses[request_id] = response_queue

        # Send acknowledgment
        await self.send_response(websocket, WSMessage(
            type=MessageType.ACK,
            request_id=request_id,
            data={"status": "received"}
        ))

        # Build metadata
        metadata = {
            "request_id": request_id,
            "websocket_client": id(websocket)
        }
        if instance_id:
            metadata["instance_id"] = instance_id
            logger.info(f"Chat message with instance_id: {instance_id}")

        # Build message content
        if images:
            # Multi-modal message: text + images
            content_items = []
            if content.strip():
                content_items.append(MessageContentItem(type="text", text=content))
            for img in images:
                img_path = img.get("path", "")
                if img_path:
                    content_items.append(MessageContentItem(type="image", image_path=img_path))
            processed_content = content_items
        else:
            # Text-only message
            processed_content = content

        # Forward to message bus
        msg = InboundMessage(
            channel="desktop",
            sender_id="user",
            chat_id="desktop_session",
            content=processed_content,
            metadata=metadata
        )

        try:
            await self.bus.publish_inbound(msg)
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            await self._send_error(websocket, request_id, f"Failed to process message: {e}")
            del self.pending_responses[request_id]

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


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


class GetModelsHandler(MessageHandler):
    """Handle get models requests."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()
        self.provider_repo = ProviderRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return available models for a provider."""
        provider_name = message.data.get("provider")

        if not provider_name:
            await self._send_error(websocket, message.request_id, "Provider name is required")
            return

        try:
            models = await self._fetch_models_from_provider(provider_name)
        except Exception as e:
            logger.error(f"Failed to fetch models for {provider_name}: {e}")
            models = []

        await self.send_response(websocket, WSMessage(
            type=MessageType.MODELS,
            request_id=message.request_id,
            data={
                "provider": provider_name,
                "models": models
            }
        ))

    async def _fetch_models_from_provider(self, provider_name: str) -> list[dict]:
        """Fetch models from provider's API using database config."""
        provider_record = self.provider_repo.get_provider_by_name(provider_name)
        if not provider_record:
            logger.warning(f"Provider not found: {provider_name}")
            return []

        api_key = provider_record.api_key
        api_base = provider_record.api_host
        provider_type = provider_record.provider_type

        if not api_key:
            logger.warning(f"No API key found for provider: {provider_name}")
            return []

        if provider_type == "anthropic":
            return await self._fetch_anthropic_models(api_key)
        elif provider_type == "openai":
            return await self._fetch_openai_models(api_key, api_base)
        elif provider_type == "deepseek":
            return await self._fetch_deepseek_models(api_key, api_base)
        elif provider_type == "openrouter":
            return await self._fetch_openrouter_models(api_key)
        elif provider_type == "groq":
            return await self._fetch_groq_models(api_key)
        elif provider_type == "zhipu":
            return await self._fetch_zhipu_models(api_key, api_base)
        elif provider_type == "gemini":
            return await self._fetch_gemini_models(api_key)
        elif provider_type == "minimax":
            return await self._fetch_minimax_models(api_key, api_base)
        elif provider_type == "minimax-coding-plan":
            return await self._fetch_minimax_coding_plan_models()
        elif provider_type == "kimi":
            return await self._fetch_kimi_models(api_key, api_base)
        else:
            logger.warning(f"Unknown provider type: {provider_type}")
            return []

    async def _fetch_anthropic_models(self, api_key: str) -> list[dict]:
        """Fetch models from Anthropic API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["display_name"] or m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Anthropic API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Anthropic models: {e}")
            return []

    async def _fetch_openai_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from OpenAI API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.openai.com/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                logger.info(f"OpenAI API response: {response.status_code} {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                        if "gpt" in m["id"].lower() or "o1" in m["id"].lower() or "o3" in m["id"].lower()
                    ]
                else:
                    logger.error(f"OpenAI API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch OpenAI models: {e}")
            return []

    async def _fetch_deepseek_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from DeepSeek API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.deepseek.com/v1"
            logger.info(f"DeepSeek API base URL: {base_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                logger.info(f"DeepSeek API response: {response.status_code} {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"DeepSeek API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch DeepSeek models: {e}")
            return []

    async def _fetch_openrouter_models(self, api_key: str) -> list[dict]:
        """Fetch models from OpenRouter API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": f"{m.get('name', m['id'])} (OpenRouter)"}
                        for m in data.get("data", [])[:50]
                    ]
                else:
                    logger.error(f"OpenRouter API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            return []

    async def _fetch_groq_models(self, api_key: str) -> list[dict]:
        """Fetch models from Groq API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Groq API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Groq models: {e}")
            return []

    async def _fetch_zhipu_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from Zhipu (智谱) API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://open.bigmodel.cn/api/paas/v4"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("name", m["id"])}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Zhipu API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Zhipu models: {e}")
            return []

    async def _fetch_gemini_models(self, api_key: str) -> list[dict]:
        """Fetch models from Google Gemini API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["name"].split("/")[-1], "label": m.get("displayName", m["name"].split("/")[-1])}
                        for m in data.get("models", [])
                    ]
                else:
                    logger.error(f"Gemini API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Gemini models: {e}")
            return []

    async def _fetch_minimax_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from MiniMax API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.minimax.chat/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("name", m["id"])}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"MiniMax API error: {response.status_code} {response.text}")
                    return [

                    ]
        except Exception as e:
            logger.error(f"Failed to fetch MiniMax models: {e}")
            return []

    async def _fetch_minimax_coding_plan_models(self) -> list[dict]:
        """Return fixed models for MiniMax Coding Plan.

        Coding Plan supports the following text models:
        - MiniMax-M2.5
        - MiniMax-M2.1
        - MiniMax-M2
        - MiniMax-M2.5-highspeed (high-speed version)

        These models cannot be fetched via API, so we return them directly.
        """
        return [
            {"value": "MiniMax-M2.5", "label": "MiniMax-M2.5"},
            {"value": "MiniMax-M2.1", "label": "MiniMax-M2.1"},
            {"value": "MiniMax-M2", "label": "MiniMax-M2"},
            {"value": "MiniMax-M2.5-highspeed", "label": "MiniMax-M2.5-highspeed (极速版)"}
        ]

    async def _fetch_kimi_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from Kimi (Moonshot) API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.moonshot.cn/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("display_name", m["id"])}
                        for m in data.get("data", [])
                        # {"value": "k2p5", "label": "kimi-for-coding"}
                    ]
                else:
                    logger.error(f"Kimi API error: {response.status_code} {response.text}")
                    return [
                        {"value": "kimi-for-coding", "label": "kimi-for-coding"}
                    ]
        except Exception as e:
            logger.error(f"Failed to fetch Kimi models: {e}")
            return []

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPGetStatusHandler(MessageHandler):
    """Handle MCP get status requests."""

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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


# ========== System Handlers ==========

class RestartServiceHandler(MessageHandler):
    """Handle service restart requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Restart the backend service."""
        try:
            import os
            import sys
            import subprocess

            # Send acknowledgment first
            await self.send_response(websocket, WSMessage(
                type=MessageType.SERVICE_RESTARTING,
                request_id=message.request_id,
                data={"message": "Service is restarting..."}
            ))

            logger.info("Restarting service...")

            # Flush logs
            import logging
            for handler in logging.root.handlers:
                handler.flush()

            # Get the current Python executable
            python = sys.executable
            logger.info(f"Python executable: {python}")
            logger.info(f"sys.argv: {sys.argv}")
            logger.info(f"sys.path: {sys.path[:5]}...")

            # Determine the script/module to run
            # Try to find the server module path
            script_path = None
            for arg in sys.argv:
                if 'octopus' in arg and 'api' in arg:
                    script_path = arg
                    break

            if not script_path:
                # Fallback to module invocation
                script_path = "-m"
                logger.info("Using module invocation fallback")

            # Build command
            cmd = [python, "-m", "backend.api.server"]
            logger.info(f"Restart command: {' '.join(cmd)}")

            # Start new process and exit current one
            # Use subprocess for better compatibility
            if os.name == 'nt':
                # Windows
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=os.getcwd())
                os._exit(0)
            else:
                # Unix-like (macOS, Linux)
                # Change to original working directory before exec
                cwd = os.getcwd()
                os.chdir(cwd)
                os.execv(python, cmd)

        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to restart service: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class MCPGetServersHandler(MessageHandler):
    """Handle MCP get servers requests."""

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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
                env = config.get("env", {})

                # 检查连接状态
                connected = server.name in self.mcp_manager.connections

                # 根据协议类型构建返回数据
                if server.protocol == "stdio":
                    command = config.get("command", server.url.split()[0] if server.url else "")
                    args = config.get("args", server.url.split()[1:] if server.url and " " in server.url else [])
                    server_data = {
                        "name": server.name,
                        "protocol": server.protocol,
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
                    # HTTP/SSE/WebSocket 服务器
                    url = config.get("url", server.url)
                    headers = config.get("headers", {})
                    server_data = {
                        "name": server.name,
                        "protocol": server.protocol,
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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
                server_config_dict = {"command": command, "args": args, "env": env}
            else:
                server_config_dict = {"url": url, "headers": headers, "env": env}

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

            # Auto connect the server
            try:
                await self.mcp_manager.create_connection(server_config)
            except Exception as e:
                logger.warning(f"Failed to auto-connect server '{name}': {e}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.MCP_SERVER_ADDED,
                request_id=message.request_id,
                data={"success": True, "server": response_data}
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

            # If enabling/disabling, update config
            if "enabled" in updates and server_name in self.mcp_manager.config.servers:
                self.mcp_manager.config.servers[server_name].enabled = updates["enabled"]

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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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
                data={"server_name": server_name, "tools": tools}
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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
            server_config = MCPServerConfig(
                name=server.name,
                url=server.url,
                protocol=server.protocol,
                enabled=server.enabled,
                auto_connect=server.auto_connect,
                **server.config
            )

            connection = await self.mcp_manager.create_connection(server_config)
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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


class MCPCallToolHandler(MessageHandler):
    """Handle MCP call tool requests."""

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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

    def __init__(self, bus: MessageBus, mcp_manager: MCPManager):
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


# ========== Session History Handlers ==========

class SessionGetChannelsHandler(MessageHandler):
    """Handle get channels requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all unique channel names."""
        try:
            db = Database()
            rows = db.execute("SELECT DISTINCT channel FROM sessions ORDER BY channel")
            channels = [row["channel"] for row in rows]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNELS,
                request_id=message.request_id,
                data={"channels": channels}
            ))
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channels: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetChannelSessionsHandler(MessageHandler):
    """Handle get channel sessions requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all sessions for a specific channel."""
        try:
            channel = message.data.get("channel")
            if not channel:
                await self._send_error(websocket, message.request_id, "Channel name is required")
                return

            db = Database()
            rows = db.execute(
                "SELECT * FROM sessions WHERE channel = ? ORDER BY updated_at DESC",
                (channel,)
            )

            sessions = [
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "chat_id": row["chat_id"],
                    "session_key": row["session_key"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": {}
                }
                for row in rows
            ]

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CHANNEL_SESSIONS,
                request_id=message.request_id,
                data={"channel": channel, "sessions": sessions}
            ))
        except Exception as e:
            logger.error(f"Failed to get channel sessions: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get channel sessions: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetSessionDetailHandler(MessageHandler):
    """Handle get session detail requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return session detail with all instances."""
        try:
            channel = message.data.get("channel")
            chat_id = message.data.get("chat_id")

            if not channel or not chat_id:
                await self._send_error(websocket, message.request_id, "Channel and chat_id are required")
                return

            db = Database()
            repo = SessionRepository(db)

            session_key = f"{channel}:{chat_id}"
            session = repo.get_session(session_key)

            if not session:
                await self._send_error(websocket, message.request_id, "Session not found")
                return

            instances = repo.list_instances(session.id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_DETAIL,
                request_id=message.request_id,
                data={
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "metadata": session.metadata
                    },
                    "instances": [
                        {
                            "id": inst.id,
                            "session_id": inst.session_id,
                            "instance_name": inst.instance_name,
                            "is_active": inst.is_active,
                            "created_at": inst.created_at.isoformat(),
                            "updated_at": inst.updated_at.isoformat()
                        }
                        for inst in instances
                    ]
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get session detail: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get session detail: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionGetMessagesHandler(MessageHandler):
    """Handle get messages requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return messages for a specific session instance."""
        try:
            instance_id = message.data.get("instance_id")
            limit = message.data.get("limit", 100)
            offset = message.data.get("offset", 0)

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Verify instance exists
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            messages = repo.get_messages(instance_id, limit=limit, offset=offset)
            total = repo.get_message_count(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_MESSAGES,
                request_id=message.request_id,
                data={
                    "session_instance_id": instance_id,
                    "messages": [
                        {
                            "id": msg.id,
                            "session_instance_id": msg.session_instance_id,
                            "role": msg.role,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                            "metadata": msg.metadata
                        }
                        for msg in messages
                    ],
                    "total": total
                }
            ))
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get messages: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionDeleteInstanceHandler(MessageHandler):
    """Handle delete session instance requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete a session instance and all its messages."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance info before deletion for response
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Delete the instance (cascade will delete messages)
            success = repo.delete_instance(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_INSTANCE_DELETED,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "instance_name": instance.instance_name
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete instance: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionCreateHandler(MessageHandler):
    """Handle create session requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Create a new instance in the desktop session."""
        try:
            channel = message.data.get("channel", "desktop")
            # Use fixed chat_id for desktop channel - all instances in one session
            chat_id = "desktop_session"
            instance_name = message.data.get("instance_name", "New Chat")

            db = Database()
            repo = SessionRepository(db)

            # Get or create the single desktop session
            session = repo.get_or_create_session(channel, chat_id)
            logger.info(f"Session: {session.id}, chat_id: {session.chat_id}")

            # Create a new instance
            instance = repo.create_instance(session.id, instance_name)
            logger.info(f"Created instance: {instance.id}, is_active: {instance.is_active}")

            # Set the new instance as active
            result = repo.set_active_instance(session.id, instance.id)
            logger.info(f"set_active_instance result: {result}")

            # Refresh instance to get updated is_active
            instance = repo.get_instance_by_id(instance.id)
            logger.info(f"After refresh, instance {instance.id} is_active: {instance.is_active}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_CREATED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "session": {
                        "id": session.id,
                        "channel": session.channel,
                        "chat_id": session.chat_id,
                        "session_key": session.session_key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                    },
                    "instance": {
                        "id": instance.id,
                        "session_id": instance.session_id,
                        "instance_name": instance.instance_name,
                        "is_active": instance.is_active,
                        "created_at": instance.created_at.isoformat(),
                        "updated_at": instance.updated_at.isoformat(),
                    }
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create session: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SessionSetActiveHandler(MessageHandler):
    """Handle set active instance requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Set an instance as active for its session."""
        try:
            instance_id = message.data.get("instance_id")

            if not instance_id:
                await self._send_error(websocket, message.request_id, "Instance ID is required")
                return

            db = Database()
            repo = SessionRepository(db)

            # Get instance to find its session
            instance = repo.get_instance_by_id(instance_id)
            if not instance:
                await self._send_error(websocket, message.request_id, "Session instance not found")
                return

            # Set as active
            success = repo.set_active_instance(instance.session_id, instance_id)

            if success:
                # Get updated instance
                instance = repo.get_instance_by_id(instance_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.SESSION_ACTIVE_SET,
                request_id=message.request_id,
                data={
                    "success": success,
                    "instance_id": instance_id,
                    "session_id": instance.session_id,
                    "is_active": instance.is_active if instance else False
                }
            ))
        except Exception as e:
            logger.error(f"Failed to set active instance: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to set active instance: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


# ========== Workspace File System Handlers ==========

class WorkspaceGetRootHandler(MessageHandler):
    """Handle get workspace root path requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return the workspace root path."""
        try:
            # Get workspace path from helpers
            from backend.utils.helpers import get_workspace_path
            workspace_root = str(get_workspace_path())

            # Ensure workspace directory exists
            Path(workspace_root).mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_ROOT,
                request_id=message.request_id,
                data={"root": workspace_root}
            ))
        except Exception as e:
            logger.error(f"Failed to get workspace root: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get workspace root: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceListHandler(MessageHandler):
    """Handle list directory contents requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return directory listing."""
        try:
            path = message.data.get("path", ".")
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check: ensure path is within workspace
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            if not full_path.is_dir():
                await self._send_error(websocket, message.request_id, f"Path is not a directory: {path}")
                return

            items = []
            for item in full_path.iterdir():
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item.relative_to(workspace_root)),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime,
                })

            # Sort: directories first, then files
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "items": items,
                    "parent": str(Path(path).parent) if path != "." else None
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list directory: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceReadHandler(MessageHandler):
    """Handle read file requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return file content."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"File does not exist: {path}")
                return

            if not full_path.is_file():
                await self._send_error(websocket, message.request_id, f"Path is not a file: {path}")
                return

            # Read file content
            try:
                content = full_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Binary file
                content = full_path.read_bytes().hex()
                encoding = "hex"
            else:
                encoding = "utf-8"

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_READ_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "name": full_path.name,
                    "content": content,
                    "encoding": encoding,
                    "size": full_path.stat().st_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read file: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceWriteHandler(MessageHandler):
    """Handle write file requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Write content to file."""
        try:
            path = message.data.get("path")
            content = message.data.get("content", "")
            encoding = message.data.get("encoding", "utf-8")

            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            if encoding == "hex":
                full_path.write_bytes(bytes.fromhex(content))
            else:
                full_path.write_text(content, encoding='utf-8')

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_WRITE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True,
                    "size": full_path.stat().st_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write file: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceDeleteHandler(MessageHandler):
    """Handle delete file or directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete file or directory."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            recursive = message.data.get("recursive", False)
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            # Delete
            if full_path.is_dir():
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    try:
                        full_path.rmdir()
                    except OSError:
                        await self._send_error(websocket, message.request_id, "Directory not empty, use recursive=true")
                        return
            else:
                full_path.unlink()

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_DELETE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceMkdirHandler(MessageHandler):
    """Handle create directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Create directory."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Create directory
            full_path.mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_MKDIR_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create directory: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceRenameHandler(MessageHandler):
    """Handle rename file or directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Rename file or directory."""
        try:
            old_path = message.data.get("old_path")
            new_path = message.data.get("new_path")

            if not old_path or not new_path:
                await self._send_error(websocket, message.request_id, "Both old_path and new_path are required")
                return

            workspace_root = await self._get_workspace_root()
            full_old_path = Path(workspace_root) / old_path
            full_new_path = Path(workspace_root) / new_path

            # Security check
            try:
                full_old_path = full_old_path.resolve()
                full_new_path = full_new_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_old_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: old_path outside workspace")
                    return
                if not str(full_new_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: new_path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_old_path.exists():
                await self._send_error(websocket, message.request_id, f"Source does not exist: {old_path}")
                return

            if full_new_path.exists():
                await self._send_error(websocket, message.request_id, f"Destination already exists: {new_path}")
                return

            # Rename
            full_old_path.rename(full_new_path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_RENAME_RESULT,
                request_id=message.request_id,
                data={
                    "old_path": old_path,
                    "new_path": new_path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to rename: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to rename: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


# ========== Cron Job Handlers ==========

class CronGetJobsHandler(MessageHandler):
    """Handle get cron jobs requests."""

    def __init__(self, bus: MessageBus, cron_service=None):
        super().__init__(bus)
        self.cron_service = cron_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all cron jobs."""
        try:
            include_disabled = message.data.get("include_disabled", False)
            
            if self.cron_service:
                jobs = self.cron_service.list_jobs(include_disabled=include_disabled)
                jobs_data = [
                    {
                        "id": job.id,
                        "name": job.name,
                        "enabled": job.enabled,
                        "schedule": {
                            "kind": job.schedule.kind,
                            "at_ms": job.schedule.at_ms,
                            "every_ms": job.schedule.every_ms,
                            "expr": job.schedule.expr,
                            "tz": job.schedule.tz,
                        },
                        "payload": {
                            "message": job.payload.message,
                            "deliver": job.payload.deliver,
                            "channel": job.payload.channel,
                            "to": job.payload.to,
                        },
                        "created_at_ms": job.created_at_ms,
                        "updated_at_ms": job.updated_at_ms,
                        "delete_after_run": job.delete_after_run,
                        "next_run_at_ms": job.next_run_at_ms,
                        "last_run_at_ms": job.last_run_at_ms,
                    }
                    for job in jobs
                ]
            else:
                jobs_data = []

            await self.send_response(websocket, WSMessage(
                type=MessageType.CRON_JOBS,
                request_id=message.request_id,
                data={"jobs": jobs_data}
            ))
        except Exception as e:
            logger.error(f"Failed to get cron jobs: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get cron jobs: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class CronAddJobHandler(MessageHandler):
    """Handle add cron job requests."""

    def __init__(self, bus: MessageBus, cron_service=None):
        super().__init__(bus)
        self.cron_service = cron_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Add a new cron job."""
        try:
            if not self.cron_service:
                await self._send_error(websocket, message.request_id, "Cron service not available")
                return

            name = message.data.get("name")
            schedule_data = message.data.get("schedule")
            message_text = message.data.get("message", "")
            deliver = message.data.get("deliver", False)
            channel = message.data.get("channel")
            to = message.data.get("to")

            if not name:
                await self._send_error(websocket, message.request_id, "Job name is required")
                return

            if not schedule_data:
                await self._send_error(websocket, message.request_id, "Schedule is required")
                return

            # Build schedule
            from backend.services.cron.types import CronSchedule
            kind = schedule_data.get("kind", "every")
            if kind == "cron":
                schedule = CronSchedule(kind="cron", expr=schedule_data.get("expr"))
            elif kind == "every":
                schedule = CronSchedule(kind="every", every_ms=schedule_data.get("every_ms", 60000))
            elif kind == "at":
                schedule = CronSchedule(kind="at", at_ms=schedule_data.get("at_ms"))
            else:
                await self._send_error(websocket, message.request_id, f"Unknown schedule kind: {kind}")
                return

            job = self.cron_service.add_job(
                name=name,
                schedule=schedule,
                message=message_text,
                deliver=deliver,
                channel=channel,
                to=to,
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.CRON_JOB_ADDED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "job": {
                        "id": job.id,
                        "name": job.name,
                        "enabled": job.enabled,
                        "schedule": {
                            "kind": job.schedule.kind,
                            "at_ms": job.schedule.at_ms,
                            "every_ms": job.schedule.every_ms,
                            "expr": job.schedule.expr,
                        },
                        "next_run_at_ms": job.next_run_at_ms,
                    }
                }
            ))
        except Exception as e:
            logger.error(f"Failed to add cron job: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to add cron job: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class CronDeleteJobHandler(MessageHandler):
    """Handle delete cron job requests."""

    def __init__(self, bus: MessageBus, cron_service=None):
        super().__init__(bus)
        self.cron_service = cron_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete a cron job."""
        try:
            if not self.cron_service:
                await self._send_error(websocket, message.request_id, "Cron service not available")
                return

            job_id = message.data.get("job_id")
            if not job_id:
                await self._send_error(websocket, message.request_id, "Job ID is required")
                return

            success = self.cron_service.remove_job(job_id)

            await self.send_response(websocket, WSMessage(
                type=MessageType.CRON_JOB_DELETED,
                request_id=message.request_id,
                data={"success": success, "job_id": job_id}
            ))
        except Exception as e:
            logger.error(f"Failed to delete cron job: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete cron job: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class CronToggleJobHandler(MessageHandler):
    """Handle toggle cron job requests."""

    def __init__(self, bus: MessageBus, cron_service=None):
        super().__init__(bus)
        self.cron_service = cron_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Enable or disable a cron job."""
        try:
            if not self.cron_service:
                await self._send_error(websocket, message.request_id, "Cron service not available")
                return

            job_id = message.data.get("job_id")
            enabled = message.data.get("enabled", True)

            if not job_id:
                await self._send_error(websocket, message.request_id, "Job ID is required")
                return

            job = self.cron_service.enable_job(job_id, enabled)

            await self.send_response(websocket, WSMessage(
                type=MessageType.CRON_JOB_TOGGLED,
                request_id=message.request_id,
                data={
                    "success": job is not None,
                    "job_id": job_id,
                    "enabled": job.enabled if job else enabled,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to toggle cron job: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to toggle cron job: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class CronRunJobHandler(MessageHandler):
    """Handle run cron job requests."""

    def __init__(self, bus: MessageBus, cron_service=None):
        super().__init__(bus)
        self.cron_service = cron_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Manually run a cron job."""
        try:
            if not self.cron_service:
                await self._send_error(websocket, message.request_id, "Cron service not available")
                return

            job_id = message.data.get("job_id")
            if not job_id:
                await self._send_error(websocket, message.request_id, "Job ID is required")
                return

            success = await self.cron_service.run_job(job_id, force=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.CRON_JOB_RUN,
                request_id=message.request_id,
                data={"success": success, "job_id": job_id}
            ))
        except Exception as e:
            logger.error(f"Failed to run cron job: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to run cron job: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


def _get_agents_root_dir() -> Path:
    """Get the root agents directory (sibling to workspace).

    Returns:
        Path to agents directory.
    """
    from backend.utils.helpers import get_workspace_path
    workspace = get_workspace_path()
    return workspace.parent / "agents"


class AgentGetListHandler(MessageHandler):
    """Handle get agent list requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of all agents (excluding system)."""
        try:
            agents_root = _get_agents_root_dir()

            agents = []

            # Load from new location (agents/ sibling to workspace)
            if agents_root.exists():
                for agent_dir in sorted(agents_root.iterdir()):
                    if agent_dir.is_dir() and not agent_dir.name.startswith(".") and agent_dir.name != "system":
                        soul_file = agent_dir / "SOUL.md"
                        if soul_file.exists():
                            try:
                                content = soul_file.read_text(encoding="utf-8")
                                # Parse YAML frontmatter to get name and description
                                name = agent_dir.name
                                description = ""
                                if content.startswith("---"):
                                    import re
                                    import yaml
                                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                                    if match:
                                        try:
                                            metadata = yaml.safe_load(match.group(1)) or {}
                                            name = metadata.get("name", agent_dir.name)
                                            description = metadata.get("description", "")
                                        except Exception:
                                            pass
                                agents.append({"name": name, "description": description, "dir": agent_dir.name})
                            except Exception as e:
                                logger.warning(f"Failed to read SOUL.md from {agent_dir}: {e}")

            # Fall back to old location for backward compatibility
            from backend.utils.helpers import get_workspace_path
            workspace = get_workspace_path()
            old_agents_dir = workspace / "agents"
            if old_agents_dir.exists() and old_agents_dir != agents_root:
                for agent_dir in sorted(old_agents_dir.iterdir()):
                    if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                        # Skip if already loaded from new location
                        if any(a["dir"] == agent_dir.name for a in agents):
                            continue
                        soul_file = agent_dir / "SOUL.md"
                        if soul_file.exists():
                            try:
                                content = soul_file.read_text(encoding="utf-8")
                                name = agent_dir.name
                                description = ""
                                if content.startswith("---"):
                                    import re
                                    import yaml
                                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                                    if match:
                                        try:
                                            metadata = yaml.safe_load(match.group(1)) or {}
                                            name = metadata.get("name", agent_dir.name)
                                            description = metadata.get("description", "")
                                        except Exception:
                                            pass
                                agents.append({"name": name, "description": description, "dir": agent_dir.name})
                            except Exception as e:
                                logger.warning(f"Failed to read SOUL.md from {agent_dir}: {e}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_LIST,
                request_id=message.request_id,
                data={"agents": agents}
            ))
        except Exception as e:
            logger.error(f"Failed to get agent list: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get agent list: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


def _find_agent_directory(agent_name: str) -> Path | None:
    """Find agent directory by agent name (from SOUL.md metadata or directory name).

    Args:
        agent_name: Agent name from SOUL.md metadata or directory name

    Returns:
        Path to agent directory or None if not found
    """
    import yaml

    agents_root = _get_agents_root_dir()

    # Try new location first (agents/ sibling to workspace)
    if agents_root.exists():
        for agent_dir in agents_root.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith(".") and agent_dir.name != "system":
                soul_file = agent_dir / "SOUL.md"
                if soul_file.exists():
                    content = soul_file.read_text(encoding="utf-8")
                    # Parse YAML frontmatter to check name
                    if content.startswith("---"):
                        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                        if match:
                            try:
                                metadata = yaml.safe_load(match.group(1)) or {}
                                if metadata.get("name") == agent_name:
                                    return agent_dir
                            except Exception:
                                pass
                    # Also check directory name match as fallback
                    if agent_dir.name == agent_name:
                        return agent_dir

    # Fall back to old location for backward compatibility
    from backend.utils.helpers import get_workspace_path
    workspace = get_workspace_path()
    old_agents_dir = workspace / "agents"
    if old_agents_dir.exists() and old_agents_dir != agents_root:
        for agent_dir in old_agents_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                soul_file = agent_dir / "SOUL.md"
                if soul_file.exists():
                    content = soul_file.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                        if match:
                            try:
                                metadata = yaml.safe_load(match.group(1)) or {}
                                if metadata.get("name") == agent_name:
                                    return agent_dir
                            except Exception:
                                pass
                    if agent_dir.name == agent_name:
                        return agent_dir
    return None


class AgentGetSoulHandler(MessageHandler):
    """Handle get agent SOUL.md content requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return SOUL.md content for a specific agent."""
        try:
            agent_name = message.data.get("name")
            if not agent_name:
                await self._send_error(websocket, message.request_id, "Agent name is required")
                return

            agent_dir = _find_agent_directory(agent_name)
            if not agent_dir:
                await self._send_error(websocket, message.request_id, f"Agent '{agent_name}' not found")
                return

            soul_file = agent_dir / "SOUL.md"
            content = soul_file.read_text(encoding="utf-8")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_SOUL,
                request_id=message.request_id,
                data={"name": agent_name, "content": content}
            ))
        except Exception as e:
            logger.error(f"Failed to get agent SOUL.md: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get agent SOUL.md: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentSaveSoulHandler(MessageHandler):
    """Handle save agent SOUL.md content requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save SOUL.md content for a specific agent."""
        try:
            import yaml

            agent_name = message.data.get("name")
            content = message.data.get("content")

            if not agent_name:
                await self._send_error(websocket, message.request_id, "Agent name is required")
                return

            if content is None:
                await self._send_error(websocket, message.request_id, "Content is required")
                return

            agents_root = _get_agents_root_dir()

            # Try to find existing agent directory
            agent_dir = _find_agent_directory(agent_name)

            if agent_dir:
                # Update existing agent
                soul_file = agent_dir / "SOUL.md"
            else:
                # Create new agent - use agent_name as directory name
                # But first check if content has a name field
                dir_name = agent_name
                if content.startswith("---"):
                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                    if match:
                        try:
                            metadata = yaml.safe_load(match.group(1)) or {}
                            if metadata.get("name"):
                                # Use the name from content for directory
                                # Ensure it's a string (YAML may parse numeric names as int)
                                dir_name = str(metadata.get("name"))
                        except Exception:
                            pass
                agent_dir = agents_root / dir_name
                agent_dir.mkdir(parents=True, exist_ok=True)
                soul_file = agent_dir / "SOUL.md"

            # Write content to file
            soul_file.write_text(content, encoding="utf-8")

            logger.info(f"Saved SOUL.md for agent: {agent_name}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_SAVED,
                request_id=message.request_id,
                data={"name": agent_name, "status": "saved"}
            ))
        except Exception as e:
            logger.error(f"Failed to save agent SOUL.md: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to save agent SOUL.md: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentDeleteHandler(MessageHandler):
    """Handle delete agent requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete an agent directory."""
        try:
            import shutil

            agent_name = message.data.get("name")
            if not agent_name:
                await self._send_error(websocket, message.request_id, "Agent name is required")
                return

            # Find the agent directory by name
            agent_dir = _find_agent_directory(agent_name)

            if not agent_dir:
                await self._send_error(websocket, message.request_id, f"Agent '{agent_name}' not found")
                return

            # Remove the entire agent directory
            shutil.rmtree(agent_dir)

            logger.info(f"Deleted agent: {agent_name}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_DELETED,
                request_id=message.request_id,
                data={"name": agent_name, "status": "deleted"}
            ))
        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete agent: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentGetSystemFilesHandler(MessageHandler):
    """Handle get system agent file list requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of all files in agents/system directory."""
        try:
            agents_root = _get_agents_root_dir()
            system_dir = agents_root / "system"

            files = []
            if system_dir.exists():
                for file_path in sorted(system_dir.iterdir()):
                    if file_path.is_file() and file_path.suffix == ".md":
                        stat = file_path.stat()
                        files.append({
                            "name": file_path.name,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        })

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_SYSTEM_FILES,
                request_id=message.request_id,
                data={"files": files}
            ))
        except Exception as e:
            logger.error(f"Failed to get system files: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get system files: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentGetSystemFileHandler(MessageHandler):
    """Handle get system agent file content requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return content of a specific system agent file."""
        try:
            filename = message.data.get("filename")
            if not filename:
                await self._send_error(websocket, message.request_id, "Filename is required")
                return

            # Security check: only allow .md files
            if not filename.endswith(".md"):
                await self._send_error(websocket, message.request_id, "Only .md files are allowed")
                return

            agents_root = _get_agents_root_dir()
            system_dir = agents_root / "system"
            file_path = system_dir / filename

            # Security check: ensure file is within system directory
            try:
                file_path = file_path.resolve()
                system_dir = system_dir.resolve()
                if not str(file_path).startswith(str(system_dir)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside system directory")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not file_path.exists():
                await self._send_error(websocket, message.request_id, f"File not found: {filename}")
                return

            content = file_path.read_text(encoding="utf-8")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_SYSTEM_FILE,
                request_id=message.request_id,
                data={"filename": filename, "content": content}
            ))
        except Exception as e:
            logger.error(f"Failed to get system file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get system file: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentSaveSystemFileHandler(MessageHandler):
    """Handle save system agent file content requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save content to a specific system agent file."""
        try:
            filename = message.data.get("filename")
            content = message.data.get("content")

            if not filename:
                await self._send_error(websocket, message.request_id, "Filename is required")
                return

            if content is None:
                await self._send_error(websocket, message.request_id, "Content is required")
                return

            # Security check: only allow .md files
            if not filename.endswith(".md"):
                await self._send_error(websocket, message.request_id, "Only .md files are allowed")
                return

            agents_root = _get_agents_root_dir()
            system_dir = agents_root / "system"
            file_path = system_dir / filename

            # Security check: ensure file is within system directory
            try:
                file_path = file_path.resolve()
                system_dir = system_dir.resolve()
                if not str(file_path).startswith(str(system_dir)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside system directory")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Ensure system directory exists
            system_dir.mkdir(parents=True, exist_ok=True)

            # Write content to file
            file_path.write_text(content, encoding="utf-8")

            logger.info(f"Saved system file: {filename}")

            await self.send_response(websocket, WSMessage(
                type=MessageType.AGENT_SYSTEM_FILE_SAVED,
                request_id=message.request_id,
                data={"filename": filename, "status": "saved"}
            ))
        except Exception as e:
            logger.error(f"Failed to save system file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to save system file: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class TokenUsageHandler(MessageHandler):
    """Handle token usage queries."""

    def __init__(self, bus: MessageBus, db=None):
        super().__init__(bus)
        from backend.data import Database
        self.db = db or Database()
        from backend.data.token_store import TokenUsageRepository
        self.token_repo = TokenUsageRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return token usage statistics."""
        scope = message.data.get("scope", "global")
        scope_id = message.data.get("scope_id")
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


class HandlerRegistry:
    """Registry for message handlers."""

    def __init__(self, bus: MessageBus, pending_responses: dict[str, asyncio.Queue], mcp_manager: MCPManager | None = None, cron_service=None, db=None):
        from backend.data import Database
        self.mcp_manager = mcp_manager
        self.cron_service = cron_service
        self.db = db or Database()

        from backend.data.provider_store import ProviderRepository, ModelRepository, SettingsRepository
        self.provider_handler_db = self.db
        self.model_handler_db = self.db
        self.settings_handler_db = self.db

        self.handlers: dict[MessageType, MessageHandler] = {
            MessageType.CHAT: ChatHandler(bus, pending_responses),
            MessageType.GET_CONFIG: GetConfigHandler(bus, self.db),
            MessageType.SAVE_CONFIG: SaveConfigHandler(bus),
            MessageType.PING: PingHandler(bus),
            MessageType.GET_MODELS: GetModelsHandler(bus, self.db),
        }

        # Register MCP handlers if manager is available
        if mcp_manager:
            self.handlers.update({
                MessageType.MCP_GET_STATUS: MCPGetStatusHandler(bus, mcp_manager),
                MessageType.MCP_GET_SERVERS: MCPGetServersHandler(bus, mcp_manager),
                MessageType.MCP_GET_SERVER_TOOLS: MCPGetServerToolsHandler(bus, mcp_manager),
                MessageType.MCP_ADD_SERVER: MCPAddServerHandler(bus, mcp_manager),
                MessageType.MCP_DELETE_SERVER: MCPDeleteServerHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_SERVER: MCPUpdateServerHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_TOOL: MCPUpdateToolHandler(bus, mcp_manager),
                MessageType.MCP_DISCOVER_TOOLS: MCPDiscoverToolsHandler(bus, mcp_manager),
                MessageType.MCP_CONNECT_SERVER: MCPConnectServerHandler(bus, mcp_manager),
                MessageType.MCP_DISCONNECT_SERVER: MCPDisconnectServerHandler(bus, mcp_manager),
                MessageType.MCP_CALL_TOOL: MCPCallToolHandler(bus, mcp_manager),
                MessageType.MCP_GET_CONFIG: MCPGetConfigHandler(bus, mcp_manager),
                MessageType.MCP_UPDATE_CONFIG: MCPUpdateConfigHandler(bus, mcp_manager),
                MessageType.PROVIDER_GET_ALL: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_GET: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_ADD: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_UPDATE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_DELETE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.PROVIDER_ENABLE: ProviderHandler(bus, self.provider_handler_db),
                MessageType.MODEL_GET_ALL: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_ADD: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_UPDATE: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_DELETE: ModelHandler(bus, self.model_handler_db),
                MessageType.MODEL_SET_DEFAULT: ModelHandler(bus, self.model_handler_db),
                MessageType.SETTINGS_GET: SettingsHandler(bus, self.settings_handler_db),
                MessageType.SETTINGS_SET: SettingsHandler(bus, self.settings_handler_db),
                MessageType.AGENT_DEFAULTS_GET: AgentDefaultsHandler(bus, self.db),
                MessageType.AGENT_DEFAULTS_UPDATE: AgentDefaultsHandler(bus, self.db),
                MessageType.GET_ENABLED_MODELS: AgentDefaultsHandler(bus, self.db),
                MessageType.CHANNEL_GET_LIST: ChannelConfigHandler(bus, self.db),
                MessageType.CHANNEL_UPDATE: ChannelConfigHandler(bus, self.db),
                MessageType.CHANNEL_DELETE: ChannelConfigHandler(bus, self.db),
                MessageType.TOOL_GET_CONFIG: ToolConfigHandler(bus, self.db),
                MessageType.TOOL_UPDATE_CONFIG: ToolConfigHandler(bus, self.db),
                MessageType.IMAGE_GET_PROVIDERS: ImageProviderConfigHandler(bus, self.db),
                MessageType.IMAGE_SET_DEFAULT_PROVIDER: ImageProviderConfigHandler(bus, self.db),
                MessageType.TOKEN_GET_USAGE: TokenUsageHandler(bus, self.db),
            })

        # Register Extension handlers (unified)
        self.handlers.update({
            MessageType.EXTENSION_GET_LIST: ExtensionGetListHandler(bus),
            MessageType.EXTENSION_INSTALL: ExtensionInstallHandler(bus, pending_responses),
            MessageType.EXTENSION_UNINSTALL: ExtensionUninstallHandler(bus),
            MessageType.EXTENSION_RUN: ExtensionRunHandler(bus, pending_responses),
            MessageType.EXTENSION_CONFIG: ExtensionConfigHandler(bus),
        })

        # Register Session History handlers
        self.handlers.update({
            MessageType.SESSION_GET_CHANNELS: SessionGetChannelsHandler(bus),
            MessageType.SESSION_GET_CHANNEL_SESSIONS: SessionGetChannelSessionsHandler(bus),
            MessageType.SESSION_GET_SESSION_DETAIL: SessionGetSessionDetailHandler(bus),
            MessageType.SESSION_GET_MESSAGES: SessionGetMessagesHandler(bus),
            MessageType.SESSION_DELETE_INSTANCE: SessionDeleteInstanceHandler(bus),
            MessageType.SESSION_CREATE: SessionCreateHandler(bus),
            MessageType.SESSION_SET_ACTIVE: SessionSetActiveHandler(bus),
        })

        # Register Workspace File System handlers
        self.handlers.update({
            MessageType.WORKSPACE_GET_ROOT: WorkspaceGetRootHandler(bus),
            MessageType.WORKSPACE_LIST: WorkspaceListHandler(bus),
            MessageType.WORKSPACE_READ: WorkspaceReadHandler(bus),
            MessageType.WORKSPACE_WRITE: WorkspaceWriteHandler(bus),
            MessageType.WORKSPACE_DELETE: WorkspaceDeleteHandler(bus),
            MessageType.WORKSPACE_MKDIR: WorkspaceMkdirHandler(bus),
            MessageType.WORKSPACE_RENAME: WorkspaceRenameHandler(bus),
        })

        # Register Cron Job handlers
        self.handlers.update({
            MessageType.CRON_GET_JOBS: CronGetJobsHandler(bus, cron_service),
            MessageType.CRON_ADD_JOB: CronAddJobHandler(bus, cron_service),
            MessageType.CRON_DELETE_JOB: CronDeleteJobHandler(bus, cron_service),
            MessageType.CRON_TOGGLE_JOB: CronToggleJobHandler(bus, cron_service),
            MessageType.CRON_RUN_JOB: CronRunJobHandler(bus, cron_service),
        })

        # Register Agent handlers
        self.handlers.update({
            MessageType.AGENT_GET_LIST: AgentGetListHandler(bus),
            MessageType.AGENT_GET_SOUL: AgentGetSoulHandler(bus),
            MessageType.AGENT_SAVE_SOUL: AgentSaveSoulHandler(bus),
            MessageType.AGENT_DELETE: AgentDeleteHandler(bus),
            MessageType.AGENT_GET_SYSTEM_FILES: AgentGetSystemFilesHandler(bus),
            MessageType.AGENT_GET_SYSTEM_FILE: AgentGetSystemFileHandler(bus),
            MessageType.AGENT_SAVE_SYSTEM_FILE: AgentSaveSystemFileHandler(bus),
        })

        # Register Image handlers
        self.handlers.update({
            MessageType.IMAGE_UPLOAD: ImageUploadHandler(bus),
            MessageType.IMAGE_ANALYZE: ImageAnalyzeHandler(bus),
            MessageType.IMAGE_GENERATE: ImageGenerateHandler(bus),
            MessageType.IMAGE_GET_UNDERSTANDING_PROVIDERS: ImageGetUnderstandingProvidersHandler(bus),
            MessageType.IMAGE_GET_GENERATION_PROVIDERS: ImageGetGenerationProvidersHandler(bus),
        })

        # Register System handlers
        self.handlers.update({
            MessageType.RESTART_SERVICE: RestartServiceHandler(bus),
        })

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Route message to appropriate handler."""
        handler = self.handlers.get(message.type)
        if handler:
            try:
                await handler.handle(websocket, message)
            except Exception as e:
                logger.error(f"Handler error for {message.type}: {e}")
                await websocket.send_json(WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": f"Internal error: {str(e)}"}
                ).to_dict())
        else:
            logger.warning(f"No handler for message type: {message.type}")
            await websocket.send_json(WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={"error": f"Unknown message type: {message.type}"}
            ).to_dict())


# ========== Image Handlers ==========

class ImageUploadHandler(MessageHandler):
    """Handle image upload requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save uploaded image to workspace."""
        try:
            image_data = message.data.get("image_data")  # base64 encoded
            file_name = message.data.get("file_name", "uploaded_image.png")
            mime_type = message.data.get("mime_type", "image/png")
            session_instance_id = message.data.get("session_instance_id")

            if not image_data:
                await self._send_error(websocket, message.request_id, "Image data is required")
                return

            # Get workspace path
            from backend.utils.helpers import get_workspace_path
            workspace = get_workspace_path()

            # Create images directory
            images_dir = workspace / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            import uuid
            ext = file_name.split(".")[-1] if "." in file_name else "png"
            unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
            file_path = images_dir / unique_name

            # Save image
            import base64
            image_bytes = base64.b64decode(image_data.split(",")[-1] if "," in image_data else image_data)
            file_path.write_bytes(image_bytes)

            # Get relative path
            rel_path = file_path.relative_to(workspace)

            # Save to database if session_instance_id provided
            if session_instance_id:
                from backend.data.database import Database
                db = Database()
                db.execute(
                    """INSERT INTO images
                        (session_instance_id, image_type, source, file_path, file_name, mime_type, file_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_instance_id, "upload", "user", str(rel_path), unique_name, mime_type, len(image_bytes))
                )

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_UPLOADED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "file_name": unique_name,
                    "file_path": str(rel_path),
                    "full_path": str(file_path),
                    "size": len(image_bytes)
                }
            ))

        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to upload image: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageAnalyzeHandler(MessageHandler):
    """Handle image analysis requests."""

    def __init__(self, bus: MessageBus):
        super().__init__(bus)
        self.image_service = None

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Analyze image using vision model."""
        try:
            from backend.services.image_service import ImageService

            if self.image_service is None:
                self.image_service = ImageService()

            image_path = message.data.get("image_path")
            question = message.data.get("question", "")
            provider_name = message.data.get("provider_name")  # Use provider name instead of ID

            if not image_path:
                await self._send_error(websocket, message.request_id, "Image path is required")
                return

            # Resolve path
            from backend.utils.helpers import get_workspace_path
            full_path = get_workspace_path() / image_path
            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Image not found: {image_path}")
                return

            # Analyze
            result = await self.image_service.understand_image(
                image_path=str(full_path),
                question=question,
                provider_name=provider_name
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_ANALYSIS_RESULT,
                request_id=message.request_id,
                data={
                    "success": True,
                    "result": result,
                    "image_path": image_path
                }
            ))

        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to analyze image: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGenerateHandler(MessageHandler):
    """Handle image generation requests."""

    def __init__(self, bus: MessageBus):
        super().__init__(bus)
        self.image_service = None

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Generate image using AI model."""
        try:
            from backend.services.image_service import ImageService

            if self.image_service is None:
                self.image_service = ImageService()

            prompt = message.data.get("prompt")
            size = message.data.get("size")
            quality = message.data.get("quality")
            provider_name = message.data.get("provider_name")  # Use provider name instead of ID

            if not prompt:
                await self._send_error(websocket, message.request_id, "Prompt is required")
                return

            # Send progress
            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATION_PROGRESS,
                request_id=message.request_id,
                data={"status": "generating", "message": "正在生成图片..."}
            ))

            # Generate
            result = await self.image_service.generate_image(
                prompt=prompt,
                size=size,
                quality=quality,
                provider_name=provider_name
            )

            # Save image
            from backend.utils.helpers import get_workspace_path
            import uuid
            output_dir = get_workspace_path() / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_{uuid.uuid4().hex[:8]}.png"

            if "image_data" in result:
                output_path.write_bytes(result["image_data"])
            elif "url" in result:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(result["url"], timeout=60.0)
                    response.raise_for_status()
                    output_path.write_bytes(response.content)

            rel_path = output_path.relative_to(get_workspace_path())

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "file_path": str(rel_path),
                    "full_path": str(output_path),
                    "prompt": result.get("revised_prompt", prompt)
                }
            ))

        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to generate image: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGetUnderstandingProvidersHandler(MessageHandler):
    """Handle get understanding providers requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all image understanding providers from AI providers."""
        try:
            from backend.services.image_service import ImageService

            image_service = ImageService()
            providers = image_service.get_understanding_providers()

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_UNDERSTANDING_PROVIDERS,
                request_id=message.request_id,
                data={
                    "providers": [
                        {
                            "name": p.name,
                            "provider_type": p.provider_type,
                            "model": p.model,
                            "api_base": p.api_base,
                            "is_default": p.is_default,
                            "enabled": p.enabled,
                        }
                        for p in providers
                    ]
                }
            ))

        except Exception as e:
            logger.error(f"Failed to get understanding providers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get providers: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGetGenerationProvidersHandler(MessageHandler):
    """Handle get generation providers requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all image generation providers from AI providers."""
        try:
            from backend.services.image_service import ImageService

            image_service = ImageService()
            providers = image_service.get_generation_providers()

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATION_PROVIDERS,
                request_id=message.request_id,
                data={
                    "providers": [
                        {
                            "name": p.name,
                            "provider_type": p.provider_type,
                            "model": p.model,
                            "api_base": p.api_base,
                            "is_default": p.is_default,
                            "enabled": p.enabled,
                        }
                        for p in providers
                    ]
                }
            ))

        except Exception as e:
            logger.error(f"Failed to get generation providers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get providers: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
