"""SQLite-based task queue for knowledge distillation jobs."""

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.services.knowledge_migrations import run_distill_queue_migrations


@dataclass
class DistillTask:
    id: int
    request_id: str
    source_path: str
    prompt: str
    output_path: Optional[str]
    template: str
    status: str
    stage: str
    message: str
    progress: float
    result_path: Optional[str]
    error: Optional[str]
    created_at: str
    updated_at: str


class KnowledgeTaskQueue:
    """Lightweight SQLite queue for distillation tasks."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        run_distill_queue_migrations(self.db_path)

    def enqueue(
        self,
        request_id: str,
        source_path: str,
        prompt: str,
        output_path: Optional[str] = None,
        template: str = "custom",
    ) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge_distill_tasks
                (request_id, source_path, prompt, output_path, template, status, stage, message, progress)
                VALUES (?, ?, ?, ?, ?, 'pending', 'pending', 'Waiting in queue...', 0.0)
                """,
                (request_id, source_path, prompt, output_path, template),
            )
            conn.commit()
            logger.info(f"Enqueued distill task {request_id} for {source_path}")
            return cursor.lastrowid

    def dequeue_for_run(self) -> Optional[DistillTask]:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM knowledge_distill_tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            task = self._row_to_task(row)
            conn.execute(
                """
                UPDATE knowledge_distill_tasks
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'pending'
                """,
                (task.id,),
            )
            conn.commit()
            if conn.total_changes == 0:
                return None
            return task

    def update_status(
        self,
        task_id: int,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        result_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = CURRENT_TIMESTAMP"]
        values: list = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if stage is not None:
            fields.append("stage = ?")
            values.append(stage)
        if message is not None:
            fields.append("message = ?")
            values.append(message)
        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if result_path is not None:
            fields.append("result_path = ?")
            values.append(result_path)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        if len(fields) == 1:
            return
        values.append(task_id)
        sql = f"UPDATE knowledge_distill_tasks SET {', '.join(fields)} WHERE id = ?"
        with self._connection() as conn:
            conn.execute(sql, values)
            conn.commit()

    def list_recent(self, limit: int = 20) -> list[DistillTask]:
        """Deprecated: Use list_tasks instead for pagination support."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM knowledge_distill_tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def list_tasks(self, limit: int = 20, offset: int = 0) -> tuple[list[DistillTask], int]:
        """List tasks with pagination support.

        Args:
            limit: Number of tasks per page
            offset: Number of tasks to skip

        Returns:
            Tuple of (tasks list, total count)
        """
        with self._connection() as conn:
            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) FROM knowledge_distill_tasks"
            ).fetchone()[0]

            # Get paginated data
            cursor = conn.execute(
                """
                SELECT * FROM knowledge_distill_tasks
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            tasks = [self._row_to_task(row) for row in cursor.fetchall()]
            return tasks, total

    def get_by_request_id(self, request_id: str) -> Optional[DistillTask]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM knowledge_distill_tasks WHERE request_id = ?",
                (request_id,),
            )
            row = cursor.fetchone()
            return self._row_to_task(row) if row else None

    def save_iterations(self, task_id: int, iterations: list[dict]) -> None:
        """Save ReAct flow iterations to database (replaces any existing)."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM knowledge_distill_task_iterations WHERE task_id = ?",
                (task_id,),
            )
            for iter_data in iterations:
                conn.execute(
                    """INSERT INTO knowledge_distill_task_iterations
                       (task_id, iteration_num, reasoning, tools, token_usage, duration)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        iter_data.get("iteration"),
                        iter_data.get("reasoning"),
                        json.dumps(iter_data.get("tools", [])),
                        json.dumps(iter_data.get("token_usage")) if iter_data.get("token_usage") else None,
                        iter_data.get("duration"),
                    )
                )
            conn.commit()

    def append_iteration(self, task_id: int, iter_data: dict) -> None:
        """Upsert a single iteration so running tasks can stream their ReAct flow."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM knowledge_distill_task_iterations WHERE task_id = ? AND iteration_num = ?",
                (task_id, iter_data.get("iteration")),
            )
            conn.execute(
                """INSERT INTO knowledge_distill_task_iterations
                   (task_id, iteration_num, reasoning, tools, token_usage, duration)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    iter_data.get("iteration"),
                    iter_data.get("reasoning"),
                    json.dumps(iter_data.get("tools", [])),
                    json.dumps(iter_data.get("token_usage")) if iter_data.get("token_usage") else None,
                    iter_data.get("duration"),
                )
            )
            conn.commit()

    def get_task_with_iterations(self, task_id: int) -> Optional[dict]:
        """Get task with its iterations for detail view."""
        with self._connection() as conn:
            task_row = conn.execute(
                "SELECT * FROM knowledge_distill_tasks WHERE id = ?",
                (task_id,)
            ).fetchone()

            if not task_row:
                return None

            iter_rows = conn.execute(
                "SELECT * FROM knowledge_distill_task_iterations WHERE task_id = ? ORDER BY iteration_num",
                (task_id,)
            ).fetchall()

            return {
                "id": task_row["id"],
                "request_id": task_row["request_id"],
                "source_path": task_row["source_path"],
                "prompt": task_row["prompt"],
                "status": task_row["status"],
                "stage": task_row["stage"],
                "message": task_row["message"],
                "progress": task_row["progress"],
                "result_path": task_row["result_path"],
                "error": task_row["error"],
                "created_at": task_row["created_at"],
                "updated_at": task_row["updated_at"],
                "iterations": [
                    {
                        "iteration": row["iteration_num"],
                        "reasoning": row["reasoning"],
                        "tools": json.loads(row["tools"]),
                        "token_usage": json.loads(row["token_usage"]) if row["token_usage"] else None,
                        "duration": row["duration"],
                    }
                    for row in iter_rows
                ]
            }

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> DistillTask:
        return DistillTask(
            id=row["id"],
            request_id=row["request_id"],
            source_path=row["source_path"],
            prompt=row["prompt"],
            output_path=row["output_path"],
            template=row["template"] if row["template"] is not None else "custom",
            status=row["status"],
            stage=row["stage"],
            message=row["message"],
            progress=row["progress"],
            result_path=row["result_path"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
