"""Telegram channel implementation using python-telegram-bot."""

import asyncio
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel

try:
    from telegram import Update
    from telegram.ext import Application, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Update = Any
    ContextTypes = Any
    filters = None


class TelegramChannel(BaseChannel):
    """Telegram bot channel using long polling."""

    name = "telegram"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._app: Any = None

    async def start(self) -> None:
        """Start Telegram bot with polling."""
        if not TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return

        token = getattr(self.config.config, "token", None)
        if not token:
            logger.error("Telegram token not configured")
            return

        self._running = True
        self._app = Application.builder().token(token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        logger.info("Telegram channel started")

        while self._running:
            await asyncio.sleep(1)

        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    async def stop(self) -> None:
        """Stop Telegram bot."""
        self._running = False
        logger.info("Telegram channel stopped")

    async def _on_text(self, update: Update, context: Any) -> None:
        """Handle incoming text message."""
        if not update.message:
            return

        sender_id = str(update.message.from_user.id)
        chat_id = str(update.message.chat_id)
        content = update.message.text or ""

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={
                "message_id": str(update.message.message_id),
                "chat_type": update.message.chat.type if update.message.chat else "private",
            },
        )

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app or not self._app.bot:
            logger.warning("Telegram app not initialized")
            return

        try:
            await self._app.bot.send_message(chat_id=msg.chat_id, text=msg.content)
            logger.debug(f"Telegram message sent to {msg.chat_id}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
