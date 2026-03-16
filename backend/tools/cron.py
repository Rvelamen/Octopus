"""Cron tool for scheduling tasks."""

from typing import Any

from backend.tools.base import Tool
from backend.services.cron.service import CronService
from backend.services.cron.types import CronSchedule


class CronTool(Tool):
    """Tool to schedule tasks. All tasks are executed via SubAgent."""

    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._session_instance_id: int | None = None

    def set_context(self, channel: str, chat_id: str, session_instance_id: int | None = None) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
        self._session_instance_id = session_instance_id

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return """Schedule tasks to be executed at specific times. All tasks are executed by a subagent.

Actions: add, list, remove.

## Time Options
- `at`: One-time task at specific time (ISO format: '2026-02-11T16:30:00')
- `every_seconds`: Recurring task with interval in seconds
- `cron_expr`: Cron expression for complex schedules (e.g., '0 9 * * *' for daily at 9am)

## Examples
- `cron(action="add", message="发送文件给用户", at="2026-02-13T10:30:00")`
- `cron(action="add", message="检查服务器状态", every_seconds=3600)`
- `cron(action="add", message="每日报告", cron_expr="0 9 * * *")`
- `cron(action="list")`
- `cron(action="remove", job_id="abc123")`"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Task description - what the subagent should do (for add)"
                },
                "at": {
                    "type": "string",
                    "description": "Absolute time in ISO format like '2026-02-11T16:30:00' (for one-time tasks)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for daily/weekly scheduled tasks)"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
                }
            },
            "required": ["action"]
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        at: str | None = None,
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        job_id: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_job(message, at, every_seconds, cron_expr)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"

    def _add_job(
        self,
        message: str,
        at: str | None,
        every_seconds: int | None,
        cron_expr: str | None
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"

        # Build schedule
        schedule_count = sum(x is not None for x in [at, every_seconds, cron_expr])
        if schedule_count == 0:
            return "Error: one of 'at', 'every_seconds', or 'cron_expr' is required"
        if schedule_count > 1:
            return "Error: only one of 'at', 'every_seconds', or 'cron_expr' should be provided"

        if at:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(at.replace('Z', '+00:00'))
                at_ms = int(dt.timestamp() * 1000)
                schedule = CronSchedule(kind="at", at_ms=at_ms)
            except ValueError as e:
                return f"Error: invalid time format '{at}'. Use ISO format like '2026-02-11T16:30:00'"
        elif every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
        else:
            return "Error: no schedule specified"

        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=(at is not None),
            session_instance_id=self._session_instance_id,
        )

        if at:
            return f"Created one-time task '{job.name}' (id: {job.id}) for {at}"
        elif every_seconds:
            return f"Created recurring task '{job.name}' (id: {job.id}) every {every_seconds} seconds"
        else:
            return f"Created scheduled task '{job.name}' (id: {job.id}) with cron '{cron_expr}'"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = []
        for j in jobs:
            kind = j.schedule.kind
            if kind == "at" and j.schedule.at_ms:
                from datetime import datetime
                at_time = datetime.fromtimestamp(j.schedule.at_ms / 1000).strftime("%Y-%m-%d %H:%M")
                lines.append(f"- {j.name} (id: {j.id}, at {at_time})")
            elif kind == "every":
                lines.append(f"- {j.name} (id: {j.id}, every {j.schedule.every_ms // 1000}s)")
            else:
                lines.append(f"- {j.name} (id: {j.id}, cron: {j.schedule.expr})")
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
