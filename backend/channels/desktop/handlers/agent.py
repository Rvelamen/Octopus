"""WebSocket message handlers for agent management."""

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


def _get_workspace_system_dir() -> Path:
    """Get the workspace root directory (system files are stored at workspace root).

    Returns:
        Path to workspace directory.
    """
    from backend.utils.helpers import get_workspace_path
    workspace = get_workspace_path()
    return workspace


class AgentGetListHandler(MessageHandler):
    """Handle get agent list requests from database."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of all agents from database."""
        try:
            from backend.data.subagent_store import SubagentRepository

            agents = []

            try:
                repo = SubagentRepository(self.db)
                db_agents = repo.get_subagents_with_details()
                for agent in db_agents:
                    agents.append({
                        "id": agent["id"],
                        "name": agent["name"],
                        "description": agent["description"],
                        "providerName": agent.get("providerName"),
                        "modelName": agent.get("modelName"),
                        "tools": agent.get("tools", []),
                        "extensions": agent.get("extensions", []),
                        "maxIterations": agent.get("maxIterations", 30),
                        "temperature": agent.get("temperature", 0.7),
                        "enabled": agent.get("enabled", True),
                    })
            except Exception as e:
                logger.warning(f"Failed to load agents from database: {e}")

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


class AgentGetSoulHandler(MessageHandler):
    """Handle get agent configuration from database."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return agent configuration from database."""
        try:
            from backend.data.subagent_store import SubagentRepository

            agent_id = message.data.get("id")
            agent_name = message.data.get("name")

            repo = SubagentRepository(self.db)
            record = None

            if agent_id:
                record = repo.get_subagent_by_id(agent_id)
            elif agent_name:
                record = repo.get_subagent_by_name(agent_name)

            if record:
                await self.send_response(websocket, WSMessage(
                    type=MessageType.AGENT_SOUL,
                    request_id=message.request_id,
                    data={
                        "id": record.id,
                        "name": record.name,
                        "description": record.description,
                        "providerId": record.provider_id,
                        "modelId": record.model_id,
                        "tools": record.tools,
                        "extensions": record.extensions,
                        "maxIterations": record.max_iterations,
                        "temperature": record.temperature,
                        "systemPrompt": record.system_prompt,
                        "enabled": record.enabled,
                    }
                ))
                return

            await self._send_error(websocket, message.request_id, f"Agent '{agent_name or agent_id}' not found")
        except Exception as e:
            logger.error(f"Failed to get agent: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get agent: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentSaveSoulHandler(MessageHandler):
    """Handle save agent requests to database."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save agent configuration to database."""
        try:
            from backend.data.subagent_store import SubagentRepository

            repo = SubagentRepository(self.db)

            agent_id = message.data.get("id")
            name = message.data.get("name")
            description = message.data.get("description", "")
            provider_id = message.data.get("providerId")
            model_id = message.data.get("modelId")
            tools = message.data.get("tools", [])
            extensions = message.data.get("extensions", [])
            max_iterations = message.data.get("maxIterations", 30)
            temperature = message.data.get("temperature", 0.7)
            system_prompt = message.data.get("systemPrompt", "")
            enabled = message.data.get("enabled", True)

            if not name:
                await self._send_error(websocket, message.request_id, "Agent name is required")
                return

            if provider_id is not None:
                provider_id = int(provider_id)
            if model_id is not None:
                model_id = int(model_id)

            if agent_id:
                success = repo.update_subagent(
                    subagent_id=int(agent_id),
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
                if success:
                    logger.info(f"Updated subagent in database: {name}")
                    await self.send_response(websocket, WSMessage(
                        type=MessageType.ACK,
                        request_id=message.request_id,
                        data={"id": agent_id, "name": name, "status": "updated"}
                    ))
                else:
                    await self._send_error(websocket, message.request_id, "Failed to update agent")
            else:
                record = repo.create_subagent(
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
                logger.info(f"Created subagent in database: {name}")
                await self.send_response(websocket, WSMessage(
                    type=MessageType.ACK,
                    request_id=message.request_id,
                    data={"id": record.id, "name": name, "status": "created"}
                ))
        except Exception as e:
            logger.error(f"Failed to save agent: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to save agent: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class AgentDeleteHandler(MessageHandler):
    """Handle delete agent requests from database."""

    def __init__(self, bus: MessageBus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete an agent from database."""
        try:
            from backend.data.subagent_store import SubagentRepository

            agent_id = message.data.get("id")
            agent_name = message.data.get("name")

            repo = SubagentRepository(self.db)

            if agent_id:
                success = repo.delete_subagent(int(agent_id))
                if success:
                    logger.info(f"Deleted subagent from database: id={agent_id}")
                    await self.send_response(websocket, WSMessage(
                        type=MessageType.AGENT_DELETED,
                        request_id=message.request_id,
                        data={"id": agent_id, "status": "deleted"}
                    ))
                    return
                else:
                    await self._send_error(websocket, message.request_id, f"Agent with id '{agent_id}' not found")
                    return

            if agent_name:
                record = repo.get_subagent_by_name(agent_name)
                if record:
                    success = repo.delete_subagent(record.id)
                    if success:
                        logger.info(f"Deleted subagent from database: {agent_name}")
                        await self.send_response(websocket, WSMessage(
                            type=MessageType.AGENT_DELETED,
                            request_id=message.request_id,
                            data={"id": record.id, "name": agent_name, "status": "deleted"}
                        ))
                        return

            await self._send_error(websocket, message.request_id, f"Agent '{agent_name or agent_id}' not found")
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
        """Return list of all files in workspace/system directory."""
        try:
            system_dir = _get_workspace_system_dir()

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
        """Return content of a specific system agent file from workspace/system."""
        try:
            filename = message.data.get("filename")
            if not filename:
                await self._send_error(websocket, message.request_id, "Filename is required")
                return

            if not filename.endswith(".md"):
                await self._send_error(websocket, message.request_id, "Only .md files are allowed")
                return

            system_dir = _get_workspace_system_dir()
            file_path = system_dir / filename

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
        """Save content to a specific system agent file in workspace/system."""
        try:
            filename = message.data.get("filename")
            content = message.data.get("content")

            if not filename:
                await self._send_error(websocket, message.request_id, "Filename is required")
                return

            if content is None:
                await self._send_error(websocket, message.request_id, "Content is required")
                return

            if not filename.endswith(".md"):
                await self._send_error(websocket, message.request_id, "Only .md files are allowed")
                return

            system_dir = _get_workspace_system_dir()
            file_path = system_dir / filename

            try:
                file_path = file_path.resolve()
                system_dir = system_dir.resolve()
                if not str(file_path).startswith(str(system_dir)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside system directory")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            system_dir.mkdir(parents=True, exist_ok=True)

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
