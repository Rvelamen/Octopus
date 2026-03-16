"""Cron service using APScheduler with SQLite backend."""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

from backend.services.cron.types import CronJob, CronSchedule, CronPayload


def _now_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)


# Global registry to store service instances for job execution
# This avoids pickling issues with instance methods
_service_registry: dict[str, "CronService"] = {}


def _execute_job_wrapper(service_id: str, job_id: str, **kwargs) -> None:
    """Global wrapper to execute job - called by APScheduler."""
    service = _service_registry.get(service_id)
    if not service:
        logger.error(f"Cron service {service_id} not found for job {job_id}")
        return

    # Run the async execution - APScheduler calls this from a thread
    try:
        # Try to get the running loop (for asyncio scheduler)
        loop = asyncio.get_running_loop()
        # Schedule the coroutine in the running loop
        asyncio.run_coroutine_threadsafe(
            service._do_execute(job_id, **kwargs),
            loop
        )
    except RuntimeError:
        # No running loop - create a new one
        try:
            asyncio.run(service._do_execute(job_id, **kwargs))
        except Exception as e:
            logger.error(f"Failed to execute job {job_id}: {e}")


async def default_on_cron_job(
    job: CronJob,
    publish_message: Callable[[str, str, str], Coroutine[Any, Any, None]],
    subagent_manager: Any = None
) -> None:
    """
    Default handler for cron job execution.
    All jobs are executed via SubAgent using common-worker role.

    Args:
        job: The cron job to execute
        publish_message: Async function to publish message (channel, chat_id, content)
        subagent_manager: SubagentManager for task execution
    """
    payload = job.payload

    if not payload.channel or not payload.to:
        logger.warning(f"Cron job '{job.name}' has no channel/to, skipping")
        return

    logger.info(f"Cron job executing: {payload.message[:50]}...")

    if subagent_manager:
        # Build task with context for the subagent
        task_with_context = f"""{payload.message}

## Context
- Target channel: {payload.channel}
- Target user chat_id: {payload.to}

When you need to send a message or file to the user, use the `channel` tool with these values."""
        # Spawn subagent with common-worker role to execute the task
        # Pass session_instance_id to ensure messages are saved to the correct instance
        await subagent_manager.spawn(
            task=task_with_context,
            label=f"Cron: {job.name}",
            origin_channel=payload.channel,
            origin_chat_id=payload.to,
            agent_role="common-worker",  # Use common-worker subagent for cron tasks
            session_instance_id=payload.session_instance_id,
        )
    else:
        # Fallback: just send notification
        logger.warning("No SubagentManager available, sending notification only")
        await publish_message(
            payload.channel,
            payload.to,
            f"🔔 定时任务: {payload.message}"
        )


class CronService:
    """Service for managing and executing scheduled jobs using APScheduler."""

    # Class-level constant service ID - stable across restarts
    # This ensures jobs stored in SQLite can always find the service
    _SERVICE_ID = "octopus-cron-service"

    def __init__(
        self,
        db: "Database | None" = None,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None,
        publish_message: Callable[[str, str, str], Coroutine[Any, Any, None]] | None = None,
        subagent_manager: Any = None,
    ):
        if db is None:
            from backend.data import Database
            db = Database()
        
        self._db = db
        self.db_path = db.db_path
        self.on_job = on_job
        self.publish_message = publish_message
        self.subagent_manager = subagent_manager
        self._scheduler = None
        self._running = False
        # Use stable service ID instead of random UUID
        self._service_id = self._SERVICE_ID

        # Register this service instance (may override previous registration)
        _service_registry[self._service_id] = self
    
    def _get_job_id(self, job_id: str) -> str:
        """Generate APScheduler job ID."""
        return f"cron_{job_id}"
    
    def _extract_job_id(self, scheduler_job_id: str) -> str:
        """Extract original job ID from APScheduler job ID."""
        return scheduler_job_id.replace("cron_", "", 1)
    
    def _build_trigger(self, schedule: CronSchedule):
        """Build APScheduler trigger from CronSchedule."""
        from apscheduler.triggers.date import DateTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
        from datetime import datetime, timezone
        
        if schedule.kind == "at":
            if not schedule.at_ms:
                raise ValueError("at_ms is required for 'at' schedule")
            run_date = datetime.fromtimestamp(schedule.at_ms / 1000, tz=timezone.utc)
            return DateTrigger(run_date=run_date)
        
        elif schedule.kind == "every":
            if not schedule.every_ms:
                raise ValueError("every_ms is required for 'every' schedule")
            seconds = schedule.every_ms / 1000
            return IntervalTrigger(seconds=seconds)
        
        elif schedule.kind == "cron":
            if not schedule.expr:
                raise ValueError("expr is required for 'cron' schedule")
            # Parse cron expression (e.g., "0 9 * * *")
            parts = schedule.expr.split()
            if len(parts) != 5:
                raise ValueError(f"Invalid cron expression: {schedule.expr}")
            minute, hour, day, month, day_of_week = parts
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=schedule.tz or "UTC"
            )
        
        else:
            raise ValueError(f"Unknown schedule kind: {schedule.kind}")
    
    async def start(self) -> None:
        """Start the cron service."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure job store with SQLite
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')
        }
        
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        self._scheduler.start()
        self._running = True
        
        logger.info(f"Cron service started with SQLite backend: {self.db_path}")
    
    def stop(self) -> None:
        """Stop the cron service."""
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None
        self._running = False
        
        # Unregister from global registry
        _service_registry.pop(self._service_id, None)
        
        logger.info("Cron service stopped")
    
    def _job_to_cron_job(self, job) -> CronJob:
        """Convert APScheduler job to CronJob."""
        job_id = self._extract_job_id(job.id)
        
        # Extract payload from job kwargs
        payload = CronPayload(
            message=job.kwargs.get('message', ''),
            deliver=job.kwargs.get('deliver', False),
            channel=job.kwargs.get('channel'),
            to=job.kwargs.get('to'),
            session_instance_id=job.kwargs.get('session_instance_id'),
        )
        
        # Determine schedule type from trigger
        trigger_type = type(job.trigger).__name__
        if trigger_type == "DateTrigger":
            schedule = CronSchedule(kind="at", at_ms=int(job.trigger.run_date.timestamp() * 1000))
        elif trigger_type == "IntervalTrigger":
            # Convert interval to milliseconds
            interval_s = job.trigger.interval.total_seconds()
            schedule = CronSchedule(kind="every", every_ms=int(interval_s * 1000))
        elif trigger_type == "CronTrigger":
            fields = job.trigger.fields
            expr = f"{fields[0]} {fields[1]} {fields[2]} {fields[3]} {fields[4]}"
            schedule = CronSchedule(kind="cron", expr=expr)
        else:
            schedule = CronSchedule(kind="every")
        
        # Get next run time
        next_run_at_ms = None
        if job.next_run_time:
            next_run_at_ms = int(job.next_run_time.timestamp() * 1000)
        
        return CronJob(
            id=job_id,
            name=job.kwargs.get('name', job_id),
            enabled=not job.kwargs.get('paused', False),
            schedule=schedule,
            payload=payload,
            created_at_ms=job.kwargs.get('created_at_ms', 0),
            updated_at_ms=job.kwargs.get('updated_at_ms', 0),
            delete_after_run=job.kwargs.get('delete_after_run', False),
            next_run_at_ms=next_run_at_ms,
        )
    
    async def _do_execute(self, job_id: str, **kwargs) -> None:
        """Actually execute the job (called by global wrapper)."""
        name = kwargs.get('name', job_id)
        delete_after_run = kwargs.get('delete_after_run', False)

        logger.info(f"Cron: executing job '{name}' ({job_id})")

        # Build CronJob for callback
        job = CronJob(
            id=job_id,
            name=name,
            payload=CronPayload(
                message=kwargs.get('message', ''),
                deliver=kwargs.get('deliver', False),
                channel=kwargs.get('channel'),
                to=kwargs.get('to'),
                session_instance_id=kwargs.get('session_instance_id'),
            ),
            created_at_ms=kwargs.get('created_at_ms', 0),
            updated_at_ms=kwargs.get('updated_at_ms', 0),
            delete_after_run=delete_after_run,
        )

        try:
            if self.on_job:
                # Use custom on_job handler
                await self.on_job(job)
            elif self.publish_message:
                # Use default handler with publish_message and subagent_manager
                await default_on_cron_job(job, self.publish_message, self.subagent_manager)
            else:
                logger.warning(f"No handler for job '{name}' - message: {job.payload.message}")
            logger.info(f"Cron: job '{name}' completed")
        except Exception as e:
            logger.error(f"Cron: job '{name}' failed: {e}")

        # Handle one-shot jobs (DateTrigger with delete_after_run)
        if delete_after_run:
            self.remove_job(job_id)
    
    # ========== Public API ==========
    
    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs."""
        if not self._scheduler:
            return []
        
        jobs = []
        for job in self._scheduler.get_jobs():
            # Skip non-cron jobs
            if not job.id.startswith("cron_"):
                continue
            
            cron_job = self._job_to_cron_job(job)
            
            # Filter out paused jobs unless include_disabled
            if not include_disabled and not cron_job.enabled:
                continue
            
            jobs.append(cron_job)
        
        # Sort by next run time
        jobs.sort(key=lambda j: j.next_run_at_ms or float('inf'))
        return jobs
    
    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
        session_instance_id: int | None = None,
    ) -> CronJob:
        """Add a new job."""
        if not self._scheduler:
            raise RuntimeError("Cron service not started")

        job_id = str(uuid.uuid4())[:8]
        scheduler_job_id = self._get_job_id(job_id)
        now = _now_ms()

        trigger = self._build_trigger(schedule)

        # Add job to scheduler using global wrapper function
        self._scheduler.add_job(
            func=_execute_job_wrapper,
            trigger=trigger,
            id=scheduler_job_id,
            kwargs={
                'service_id': self._service_id,
                'job_id': job_id,
                'name': name,
                'message': message,
                'deliver': deliver,
                'channel': channel,
                'to': to,
                'session_instance_id': session_instance_id,
                'created_at_ms': now,
                'updated_at_ms': now,
                'delete_after_run': delete_after_run,
            },
            replace_existing=True,
        )

        logger.info(f"Cron: added job '{name}' ({job_id})")

        return CronJob(
            id=job_id,
            name=name,
            schedule=schedule,
            payload=CronPayload(
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
                session_instance_id=session_instance_id,
            ),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        if not self._scheduler:
            return False
        
        scheduler_job_id = self._get_job_id(job_id)
        try:
            self._scheduler.remove_job(scheduler_job_id)
            logger.info(f"Cron: removed job {job_id}")
            return True
        except Exception:
            return False
    
    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job."""
        if not self._scheduler:
            return None
        
        scheduler_job_id = self._get_job_id(job_id)
        try:
            job = self._scheduler.get_job(scheduler_job_id)
            if not job:
                return None
            
            if enabled:
                self._scheduler.resume_job(scheduler_job_id)
            else:
                self._scheduler.pause_job(scheduler_job_id)
            
            # Update kwargs
            job.kwargs['paused'] = not enabled
            job.kwargs['updated_at_ms'] = _now_ms()
            
            logger.info(f"Cron: {'enabled' if enabled else 'disabled'} job {job_id}")
            return self._job_to_cron_job(job)
        except Exception:
            return None
    
    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job."""
        if not self._scheduler:
            return False
        
        scheduler_job_id = self._get_job_id(job_id)
        try:
            job = self._scheduler.get_job(scheduler_job_id)
            if not job:
                return False
            
            if not force and job.kwargs.get('paused'):
                return False
            
            # Execute immediately
            await self._do_execute(job_id, **job.kwargs)
            
            # For interval/cron jobs, reschedule next run
            if not job.kwargs.get('delete_after_run'):
                self._scheduler.reschedule_job(scheduler_job_id)
            
            return True
        except Exception as e:
            logger.error(f"Failed to run job {job_id}: {e}")
            return False
    
    def status(self) -> dict:
        """Get service status."""
        if not self._scheduler:
            return {"enabled": False, "jobs": 0, "next_wake_at_ms": None}
        
        jobs = self.list_jobs(include_disabled=True)
        next_wake = None
        
        for job in jobs:
            if job.enabled and job.next_run_at_ms:
                if next_wake is None or job.next_run_at_ms < next_wake:
                    next_wake = job.next_run_at_ms
        
        return {
            "enabled": self._running,
            "jobs": len(jobs),
            "next_wake_at_ms": next_wake,
        }
