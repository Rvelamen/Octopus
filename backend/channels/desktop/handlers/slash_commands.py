"""WebSocket handler for slash commands."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.extensions.registry import get_registry


class GetSlashCommandsHandler(MessageHandler):
    """Handle get_slash_commands requests from clients."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return available slash commands including built-ins and skills."""
        request_id = message.request_id

        slash_commands = [
            {"name": "new", "description": "Create a new chat", "aliases": ["n"]},
            {
                "name": "clear",
                "description": "Clear current conversation",
                "aliases": ["cls", "clean"],
            },
            {
                "name": "compress",
                "description": "Compress conversation context",
                "aliases": ["zip"],
            },
            {"name": "image", "description": "Generate an image", "aliases": ["img", "pic"]},
        ]

        try:
            registry = get_registry()
            skills = registry.list_skills()
            for skill in skills:
                slash_commands.append(
                    {
                        "name": f"skill:{skill.name}",
                        "description": skill.description or f"Use {skill.name} skill",
                        "aliases": [],
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to load skills for slash commands: {e}")

        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.ACK, request_id=request_id, data={"slash_commands": slash_commands}
            ),
        )
