"""Workflow Design Chat service for session and message management."""

import contextlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.data.database import Database


@dataclass
class WorkflowDesignSession:
    id: str
    workflow_id: str
    user_id: str | None
    agent_config_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class WorkflowDesignMessage:
    id: str
    session_id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    metadata: dict[str, Any]
    created_at: datetime | None


@dataclass
class WorkflowDesignOperation:
    id: str
    session_id: str
    operation_type: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    created_at: datetime | None


class WorkflowDesignChatService:
    """Service for workflow design chat session and message operations."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    # ── Sessions ──

    def list_sessions(self, workflow_id: str | None = None) -> list[WorkflowDesignSession]:
        """List sessions for a given workflow."""
        with self.db._get_connection() as conn:
            if workflow_id is not None:
                rows = conn.execute(
                    "SELECT * FROM workflow_design_sessions WHERE workflow_id = ? ORDER BY updated_at DESC",
                    (workflow_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workflow_design_sessions ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_session(row) for row in rows]

    def get_session(self, session_id: str) -> WorkflowDesignSession | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_design_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None

    def create_session(
        self, workflow_id: str, user_id: str | None = None, agent_config_id: int | None = None
    ) -> WorkflowDesignSession:
        session_id = str(uuid.uuid4())
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_design_sessions (id, workflow_id, user_id, agent_config_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (session_id, workflow_id, user_id, agent_config_id),
            )
            row = conn.execute(
                "SELECT * FROM workflow_design_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row)

    def touch_session(self, session_id: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE workflow_design_sessions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (session_id,),
            )

    def delete_session(self, session_id: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM workflow_design_sessions WHERE id = ?", (session_id,))

    # ── Messages ──

    def list_messages(self, session_id: str) -> list[WorkflowDesignMessage]:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_design_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            return [self._row_to_message(row) for row in rows]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowDesignMessage:
        msg_id = str(uuid.uuid4())
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_design_messages
                (id, session_id, role, content, tool_calls, tool_call_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                """,
                (
                    msg_id,
                    session_id,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    tool_call_id,
                    json.dumps(metadata or {}),
                ),
            )
            self.touch_session(session_id)
            row = conn.execute(
                "SELECT * FROM workflow_design_messages WHERE id = ?", (msg_id,)
            ).fetchone()
            return self._row_to_message(row)

    def delete_message(self, message_id: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM workflow_design_messages WHERE id = ?", (message_id,))

    # ── Operations (for undo/redo) ──

    def add_operation(
        self,
        session_id: str,
        operation_type: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> WorkflowDesignOperation:
        op_id = str(uuid.uuid4())
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_design_operations (id, session_id, operation_type, before_state, after_state, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                """,
                (
                    op_id,
                    session_id,
                    operation_type,
                    json.dumps(before_state) if before_state is not None else None,
                    json.dumps(after_state) if after_state is not None else None,
                ),
            )
            row = conn.execute(
                "SELECT * FROM workflow_design_operations WHERE id = ?", (op_id,)
            ).fetchone()
            return self._row_to_operation(row)

    def list_operations(self, session_id: str) -> list[WorkflowDesignOperation]:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_design_operations WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            return [self._row_to_operation(row) for row in rows]

    def get_last_operation(self, session_id: str) -> WorkflowDesignOperation | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_design_operations WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            return self._row_to_operation(row) if row else None

    # ── Workflow definition helpers ──

    def get_workflow_definition(self, workflow_id: str) -> dict[str, Any]:
        """Load current workflow definition (nodes, edges, variables) for AI context."""
        from backend.services.workflow.store import WorkflowStore

        store = WorkflowStore(self.db)
        workflow = store.get_workflow(workflow_id)
        if not workflow:
            return {"workflow_id": workflow_id, "nodes": [], "edges": [], "variables": []}

        version = store.get_latest_version(workflow_id)
        if not version:
            return {
                "workflow_id": workflow_id,
                "name": workflow.name,
                "nodes": [],
                "edges": [],
                "variables": [],
            }

        nodes = store.list_nodes(version.id)
        edges = store.list_edges(version.id)
        variables = store.list_variables(version.id)

        return {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "version_id": version.id,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "label": n.label,
                    "position": {"x": n.position_x, "y": n.position_y},
                    "config": n.config,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "source": e.source_node_id,
                    "target": e.target_node_id,
                    "source_handle": e.source_handle,
                    "target_handle": e.target_handle,
                    "condition": e.condition,
                }
                for e in edges
            ],
            "variables": [
                {
                    "name": v.name,
                    "type": v.type,
                    "default_value": v.default_value,
                    "required": v.required,
                }
                for v in variables
            ],
        }

    # ── Helpers ──

    def _row_to_session(self, row) -> WorkflowDesignSession:
        return WorkflowDesignSession(
            id=row["id"],
            workflow_id=row["workflow_id"],
            user_id=row["user_id"],
            agent_config_id=row["agent_config_id"],
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(str(row["updated_at"])) if row["updated_at"] else None
            ),
        )

    def _row_to_message(self, row) -> WorkflowDesignMessage:
        meta = {}
        with contextlib.suppress(Exception):
            meta = json.loads(row["metadata"] or "{}")
        tool_calls = None
        try:
            raw = row["tool_calls"]
            if raw is not None and raw != "":
                tool_calls = json.loads(raw)
        except Exception:
            pass
        return WorkflowDesignMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            tool_calls=tool_calls,
            tool_call_id=row["tool_call_id"] if row["tool_call_id"] else None,
            metadata=meta,
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
        )

    def _row_to_operation(self, row) -> WorkflowDesignOperation:
        before_state = None
        after_state = None
        try:
            if row["before_state"]:
                before_state = json.loads(row["before_state"])
        except Exception:
            pass
        try:
            if row["after_state"]:
                after_state = json.loads(row["after_state"])
        except Exception:
            pass
        return WorkflowDesignOperation(
            id=row["id"],
            session_id=row["session_id"],
            operation_type=row["operation_type"],
            before_state=before_state,
            after_state=after_state,
            created_at=(
                datetime.fromisoformat(str(row["created_at"])) if row["created_at"] else None
            ),
        )
