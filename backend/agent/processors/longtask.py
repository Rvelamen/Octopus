"""Longtask message processor."""
from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage
from .base import MessageProcessor


class LongtaskMessageProcessor(MessageProcessor):
    """Processor for longtask auth and completion messages."""

    def can_process(self, msg: InboundMessage) -> bool:
        # Only intercept longtask_auth; longtask_complete is handled inside _prepare_session_and_context
        return msg.message_type == "longtask_auth"

    async def process(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """Process a longtask message (auth request or completion notification)."""
        logger.info(f"Processing longtask message: {msg.message_type}")

        # Get session and save the message for context
        session = self.agent_loop.sessions.get_or_create(msg.session_key)

        # For auth requests, we need to ask the user for authorization
        if msg.message_type == "longtask_auth":
            content = f"🔔 {msg.content}"
            # Save to session for context
            session.add_message("assistant", content, message_type="longtask_auth")
            self.agent_loop.sessions.save(session)
            logger.info(f"[_process_longtask_message] Saved longtask_auth message to session {session.key}")
            instance_id = session.active_instance.id if session.active_instance else None
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
                metadata={"session_instance_id": instance_id} if instance_id else {}
            )

        # For completion notifications, just notify the user
        elif msg.message_type == "longtask_complete":
            content = f"✅ {msg.content}"
            # Save to session for context
            session.add_message("assistant", content, message_type="longtask_complete")
            self.agent_loop.sessions.save(session)
            logger.info(f"[_process_longtask_message] Saved longtask_complete message to session {session.key}")
            instance_id = session.active_instance.id if session.active_instance else None
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
                metadata={"session_instance_id": instance_id} if instance_id else {}
            )

        return None
