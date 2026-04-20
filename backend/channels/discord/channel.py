"""Discord channel implementation using discord.py."""

import asyncio
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel

try:
    import discord
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = Any


class DiscordChannel(BaseChannel):
    """Discord channel using discord.py."""

    name = "discord"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._token = getattr(self.config.config, "token", "") or ""
        self._client: Any = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start Discord client."""
        if not DISCORD_AVAILABLE:
            logger.error("discord.py not installed. Run: pip install discord.py")
            return
        if not self._token:
            logger.error("Discord token not configured")
            return

        self._running = True
        intents = discord.Intents.default()
        intents.message_content = True

        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message):
            if message.author == self._client.user:
                return
            sender_id = str(message.author.id)
            chat_id = str(message.channel.id)
            content = message.content or ""
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "message_id": str(message.id),
                    "guild_id": str(message.guild.id) if message.guild else None,
                },
            )

        self._task = asyncio.create_task(self._client.start(self._token))
        logger.info("Discord channel started")

    async def stop(self) -> None:
        """Stop Discord client."""
        self._running = False
        if self._client:
            await self._client.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Discord channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Discord."""
        if not self._client:
            logger.warning("Discord client not initialized")
            return

        try:
            channel = self._client.get_channel(int(msg.chat_id))
            if channel:
                await channel.send(msg.content)
                logger.debug(f"Discord message sent to {msg.chat_id}")
            else:
                logger.warning(f"Discord channel {msg.chat_id} not found")
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
