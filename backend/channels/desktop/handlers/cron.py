"""Cron job handlers for Desktop channel."""

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
