"""Subagent task group aggregator for multi-subagent result collection."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from backend.core.events.types import InboundMessage
from backend.core.events.bus import MessageBus


@dataclass
class TaskGroup:
    """A group of subagent tasks that should be aggregated together."""
    
    id: str
    expected_count: int
    timeout: float
    origin_channel: str
    origin_chat_id: str
    session_instance_id: int
    created_at: datetime = field(default_factory=datetime.now)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed: bool = False
    
    def add_result(self, subagent_id: str, label: str, task: str, result: str, status: str) -> None:
        """Add a subagent result to the group."""
        self.results[subagent_id] = {
            "label": label,
            "task": task,
            "result": result,
            "status": status,
            "completed_at": datetime.now().isoformat(),
        }
        logger.info(f"[TaskGroup:{self.id}] Added result from {subagent_id} ({label}), "
                   f"progress: {len(self.results)}/{self.expected_count}")
    
    def is_complete(self) -> bool:
        """Check if all subagents have completed."""
        return len(self.results) >= self.expected_count
    
    def format_results(self) -> str:
        """Format all results for LLM summary."""
        parts = []
        for subagent_id, data in self.results.items():
            status_icon = "✅" if data["status"] == "ok" else "❌"
            parts.append(f"""
{status_icon} **{data['label']}** (ID: {subagent_id})
Task: {data['task']}
Result:
{data['result']}
""")
        return "\n---\n".join(parts)
    
    def get_summary_prompt(self) -> str:
        """Generate the summary prompt for the main agent."""
        return f"""以下 {len(self.results)} 个子任务已完成，请综合所有结果生成最终报告：

{self.format_results()}

请提供：
1. 关键发现总结
2. 优先级建议  
3. 后续行动项

请用简洁的语言总结，不要提及技术细节如 subagent ID 等。"""


class SubagentAggregator:
    """
    Aggregates results from multiple subagents and triggers summary when all complete.
    
    This solves the problem of scattered subagent notifications by:
    1. Grouping related subagent tasks
    2. Collecting results as they complete
    3. Triggering a unified summary when all tasks are done
    """
    
    def __init__(self, bus: MessageBus | None = None):
        self._task_groups: dict[str, TaskGroup] = {}
        self._subagent_to_group: dict[str, str] = {}  # Map subagent_id to group_id
        self._bus = bus
        self._running_tasks: dict[str, asyncio.Task] = {}
    
    def set_bus(self, bus: MessageBus) -> None:
        """Set the message bus for publishing aggregate results."""
        self._bus = bus
    
    async def create_group(
        self,
        expected_count: int,
        origin_channel: str,
        origin_chat_id: str,
        session_instance_id: int,
        timeout: float = 300.0,
    ) -> TaskGroup:
        """
        Create a new task group for aggregating subagent results.
        
        Args:
            expected_count: Number of subagents expected to complete
            origin_channel: Channel to send the summary to
            origin_chat_id: Chat ID to send the summary to
            session_instance_id: Session instance ID for precise routing
            timeout: Maximum time to wait for all subagents (seconds)
            
        Returns:
            The created TaskGroup
        """
        group_id = str(uuid.uuid4())[:8]
        group = TaskGroup(
            id=group_id,
            expected_count=expected_count,
            timeout=timeout,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            session_instance_id=session_instance_id,
        )
        self._task_groups[group_id] = group
        
        # Start timeout watchdog
        watchdog_task = asyncio.create_task(
            self._group_timeout_watchdog(group_id, timeout)
        )
        self._running_tasks[group_id] = watchdog_task
        
        logger.info(f"[SubagentAggregator] Created task group {group_id} "
                   f"expecting {expected_count} subagents, timeout={timeout}s")
        return group
    
    async def join_group(self, group_id: str, subagent_id: str) -> bool:
        """
        Register a subagent as part of a task group.
        
        Args:
            group_id: The task group ID
            subagent_id: The subagent task ID
            
        Returns:
            True if successfully joined, False if group not found
        """
        if group_id not in self._task_groups:
            logger.warning(f"[SubagentAggregator] Group {group_id} not found for subagent {subagent_id}")
            return False
        
        self._subagent_to_group[subagent_id] = group_id
        logger.info(f"[SubagentAggregator] Subagent {subagent_id} joined group {group_id}")
        return True
    
    async def submit_result(
        self,
        subagent_id: str,
        label: str,
        task: str,
        result: str,
        status: str,
    ) -> tuple[bool, bool]:
        """
        Submit a subagent result.
        
        Args:
            subagent_id: The subagent task ID
            label: Human-readable label for the task
            task: The original task description
            result: The task result
            status: "ok" or "error"
            
        Returns:
            Tuple of (is_grouped, is_complete):
            - is_grouped: Whether this subagent belongs to a group
            - is_complete: Whether all subagents in the group are now complete
        """
        # Check if this subagent belongs to a group
        group_id = self._subagent_to_group.get(subagent_id)
        if not group_id:
            # Not part of a group, handle as individual result
            logger.info(f"[SubagentAggregator] Subagent {subagent_id} is not part of any group")
            return False, False
        
        group = self._task_groups.get(group_id)
        if not group:
            logger.warning(f"[SubagentAggregator] Group {group_id} not found for subagent {subagent_id}")
            return False, False
        
        # Add result to group
        group.add_result(subagent_id, label, task, result, status)
        
        # Check if all subagents are complete
        if group.is_complete() and not group.completed:
            group.completed = True
            await self._trigger_summarize(group)
            return True, True
        
        return True, False
    
    async def _trigger_summarize(self, group: TaskGroup) -> None:
        """Trigger the main agent to summarize all results."""
        if not self._bus:
            logger.error(f"[SubagentAggregator] No message bus set, cannot trigger summary")
            return
        
        # Cancel the watchdog task
        if group.id in self._running_tasks:
            self._running_tasks[group.id].cancel()
            del self._running_tasks[group.id]
        
        summary_content = group.get_summary_prompt()
        
        # Create aggregate summary message
        msg = InboundMessage(
            channel="system",
            sender_id="aggregator",
            chat_id=f"{group.origin_channel}:{group.origin_chat_id}",
            content=summary_content,
            metadata={
                "type": "aggregate_summary",
                "group_id": group.id,
                "session_instance_id": group.session_instance_id,
                "subagent_count": len(group.results),
            }
        )
        
        try:
            await self._bus.publish_inbound(msg)
            logger.info(f"[SubagentAggregator] Published aggregate summary for group {group.id}")
        except Exception as e:
            logger.error(f"[SubagentAggregator] Failed to publish summary: {e}")
        
        # Cleanup
        self._cleanup_group(group.id)
    
    async def _group_timeout_watchdog(self, group_id: str, timeout: float) -> None:
        """Watchdog task to handle group timeout."""
        try:
            await asyncio.sleep(timeout)
            
            group = self._task_groups.get(group_id)
            if not group or group.completed:
                return
            
            # Timeout reached, trigger summary with partial results
            logger.warning(f"[SubagentAggregator] Group {group_id} timeout after {timeout}s, "
                          f"received {len(group.results)}/{group.expected_count} results")
            
            # Mark as complete and trigger summary
            group.completed = True
            await self._trigger_summarize(group)
            
        except asyncio.CancelledError:
            # Normal cancellation when group completes
            pass
        except Exception as e:
            logger.error(f"[SubagentAggregator] Watchdog error for group {group_id}: {e}")
    
    def _cleanup_group(self, group_id: str) -> None:
        """Clean up a completed group."""
        group = self._task_groups.pop(group_id, None)
        if group:
            # Remove subagent mappings
            for subagent_id in list(self._subagent_to_group.keys()):
                if self._subagent_to_group[subagent_id] == group_id:
                    del self._subagent_to_group[subagent_id]
        
        # Remove watchdog task
        if group_id in self._running_tasks:
            task = self._running_tasks.pop(group_id)
            if not task.done():
                task.cancel()
        
        logger.info(f"[SubagentAggregator] Cleaned up group {group_id}")
    
    def get_group_status(self, group_id: str) -> dict[str, Any] | None:
        """Get the status of a task group."""
        group = self._task_groups.get(group_id)
        if not group:
            return None
        
        return {
            "id": group.id,
            "expected_count": group.expected_count,
            "completed_count": len(group.results),
            "is_complete": group.is_complete(),
            "completed": group.completed,
            "created_at": group.created_at.isoformat(),
            "results": list(group.results.keys()),
        }
    
    def list_active_groups(self) -> list[dict[str, Any]]:
        """List all active task groups."""
        return [self.get_group_status(gid) for gid in self._task_groups.keys()]
