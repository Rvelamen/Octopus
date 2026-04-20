"""Email channel implementation using IMAP + SMTP."""

import asyncio
import email as email_lib
import imaplib
import smtplib
from collections import OrderedDict
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel


class EmailChannel(BaseChannel):
    """Email channel using IMAP polling and SMTP replies."""

    name = "email"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._imap_host = (
            getattr(self.config.config, "imap_host", "imap.gmail.com")
            or "imap.gmail.com"
        )
        self._imap_port = getattr(self.config.config, "imap_port", 993) or 993
        self._smtp_host = (
            getattr(self.config.config, "smtp_host", "smtp.gmail.com")
            or "smtp.gmail.com"
        )
        self._smtp_port = getattr(self.config.config, "smtp_port", 587) or 587
        self._address = getattr(self.config.config, "address", "") or ""
        self._password = getattr(self.config.config, "password", "") or ""
        self._poll_interval = (
            getattr(self.config.config, "poll_interval", 15) or 15
        )
        self._seen_uids: OrderedDict[str, None] = OrderedDict()
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start email polling loop."""
        if not self._address or not self._password:
            logger.error("Email address and password not configured")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Email channel started")

    async def stop(self) -> None:
        """Stop email polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Email channel stopped")

    async def _poll_loop(self) -> None:
        """Periodically check inbox for new messages."""
        while self._running:
            try:
                await self._check_inbox()
            except Exception as e:
                logger.error(f"Email poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _check_inbox(self) -> None:
        """Fetch unseen emails via IMAP."""
        loop = asyncio.get_running_loop()

        def _fetch():
            try:
                mail = imaplib.IMAP4_SSL(self._imap_host, self._imap_port)
                mail.login(self._address, self._password)
                mail.select("inbox")

                status, messages = mail.search(None, "UNSEEN")
                if status != "OK":
                    mail.logout()
                    return []

                uids = messages[0].split()
                results = []
                for uid in uids:
                    uid_str = uid.decode()
                    if uid_str in self._seen_uids:
                        continue
                    self._seen_uids[uid_str] = None

                    status, msg_data = mail.fetch(uid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    from_header = msg.get("From", "")
                    sender_match = email_lib.utils.parseaddr(from_header)[1]

                    if any(
                        k in sender_match.lower()
                        for k in ("noreply", "no-reply", "mailer-daemon")
                    ):
                        continue
                    if sender_match.lower() == self._address.lower():
                        continue

                    subject = ""
                    subj_raw = msg.get("Subject", "")
                    if subj_raw:
                        decoded = decode_header(subj_raw)
                        parts = []
                        for part, charset in decoded:
                            if isinstance(part, bytes):
                                parts.append(
                                    part.decode(charset or "utf-8", errors="replace")
                                )
                            else:
                                parts.append(part)
                        subject = "".join(parts)

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            if ctype == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or "utf-8"
                                    body = payload.decode(charset, errors="replace")
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            charset = msg.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")

                    if body:
                        results.append(
                            {
                                "uid": uid_str,
                                "sender": sender_match,
                                "subject": subject,
                                "body": body.strip(),
                                "message_id": msg.get("Message-ID", uid_str),
                            }
                        )

                mail.logout()
                return results
            except Exception as e:
                logger.error(f"IMAP fetch error: {e}")
                return []

        emails = await loop.run_in_executor(None, _fetch)

        while len(self._seen_uids) > 2000:
            self._seen_uids.popitem(last=False)

        for item in emails:
            content = f"Subject: {item['subject']}\n\n{item['body']}"
            await self._handle_message(
                sender_id=item["sender"],
                chat_id=item["sender"],
                content=content,
                metadata={
                    "email_uid": item["uid"],
                    "message_id": item["message_id"],
                    "subject": item["subject"],
                },
            )

    async def send(self, msg: OutboundMessage) -> None:
        """Send email reply via SMTP."""
        if not self._address or not self._password:
            logger.warning("Email not configured")
            return

        loop = asyncio.get_running_loop()

        def _send():
            try:
                server = smtplib.SMTP(self._smtp_host, self._smtp_port)
                server.starttls()
                server.login(self._address, self._password)

                mime_msg = MIMEMultipart()
                mime_msg["From"] = self._address
                mime_msg["To"] = msg.chat_id
                subject = "Re: Octopus"
                if msg.metadata and msg.metadata.get("subject"):
                    subject = f"Re: {msg.metadata['subject']}"
                mime_msg["Subject"] = subject

                if msg.metadata and msg.metadata.get("message_id"):
                    mime_msg["In-Reply-To"] = msg.metadata["message_id"]
                    mime_msg["References"] = msg.metadata["message_id"]

                mime_msg.attach(MIMEText(msg.content, "plain", "utf-8"))
                server.send_message(mime_msg)
                server.quit()
                logger.debug(f"Email reply sent to {msg.chat_id}")
            except Exception as e:
                logger.error(f"SMTP send error: {e}")

        await loop.run_in_executor(None, _send)
