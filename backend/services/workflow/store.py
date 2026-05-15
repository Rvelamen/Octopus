"""Workflow data store."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from backend.data.database import Database
from backend.services.workflow.models import (
    WorkflowRecord,
    WorkflowVersionRecord,
    WorkflowNodeRecord,
    WorkflowEdgeRecord,
    WorkflowVariableRecord,
    WorkflowTriggerRecord,
    WorkflowRunRecord,
    WorkflowRunNodeRecord,
    WorkflowStatus,
    NodeType,
    VariableType,
    TriggerType,
)


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse datetime from SQLite string or return as-is if already a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # SQLite datetime format: "YYYY-MM-DD HH:MM:SS"
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
    return None


# Map legacy node type names to canonical names used by the backend.
_LEGACY_NODE_TYPE_MAP = {
    "start": "workflowStart",
    "llm": "chatNode",
    "end": "workflowEnd",
}


def _normalize_node_type(node_type: str) -> str:
    """Normalize a node type string to its canonical form."""
    return _LEGACY_NODE_TYPE_MAP.get(node_type, node_type)


class WorkflowStore:
    """Workflow data store."""

    def __init__(self, db: Database):
        self._db = db

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    # Workflow CRUD
    def create_workflow(
        self,
        name: str,
        description: str = "",
        category: str = "general",
    ) -> WorkflowRecord:
        """Create a new workflow."""
        workflow_id = self._generate_id()
        now = datetime.now()
        
        with self._db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflows (id, name, description, category, status, current_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (workflow_id, name, description, category, WorkflowStatus.DRAFT.value, 1, now, now),
            )
            conn.commit()

        return WorkflowRecord(
            id=workflow_id,
            name=name,
            description=description,
            category=category,
            status=WorkflowStatus.DRAFT,
            current_version=1,
            created_at=now,
            updated_at=now,
        )

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """Get a workflow by ID."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflows WHERE id = ?",
                (workflow_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return WorkflowRecord(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                status=WorkflowStatus(row["status"]),
                current_version=row["current_version"],
                created_at=_parse_dt(row["created_at"]),
                updated_at=_parse_dt(row["updated_at"]),
            )

    def list_workflows(
        self,
        category: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
    ) -> list[WorkflowRecord]:
        """List workflows with optional filters."""
        query = "SELECT * FROM workflows WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY updated_at DESC"

        with self._db._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                WorkflowRecord(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    category=row["category"],
                    status=WorkflowStatus(row["status"]),
                    current_version=row["current_version"],
                    created_at=_parse_dt(row["created_at"]),
                    updated_at=_parse_dt(row["updated_at"]),
                )
                for row in rows
            ]

    def delete_run(self, run_id: str) -> bool:
        """Delete a single run."""
        with self._db._get_connection() as conn:
            # Delete run nodes first
            conn.execute("DELETE FROM workflow_run_nodes WHERE run_id = ?", (run_id,))
            cursor = conn.execute("DELETE FROM workflow_runs WHERE id = ?", (run_id,))
            return cursor.rowcount > 0

    def delete_workflow_runs(self, workflow_id: str) -> int:
        """Delete all runs for a workflow."""
        with self._db._get_connection() as conn:
            run_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM workflow_runs WHERE workflow_id = ?", (workflow_id,)
                ).fetchall()
            ]
            for rid in run_ids:
                conn.execute("DELETE FROM workflow_run_nodes WHERE run_id = ?", (rid,))
            cursor = conn.execute("DELETE FROM workflow_runs WHERE workflow_id = ?", (workflow_id,))
            return cursor.rowcount

    def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        current_version: Optional[int] = None,
    ) -> Optional[WorkflowRecord]:
        """Update a workflow."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if current_version is not None:
            updates.append("current_version = ?")
            params.append(current_version)

        if not updates:
            return self.get_workflow(workflow_id)

        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.append(workflow_id)

        with self._db._get_connection() as conn:
            conn.execute(
                f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        return self.get_workflow(workflow_id)

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow and all related data atomically."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM workflows WHERE id = ?",
                (workflow_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    # Version management
    def create_version(
        self,
        workflow_id: str,
        version: int,
        name: str,
        description: str = "",
        definition: Optional[dict] = None,
    ) -> WorkflowVersionRecord:
        """Create a new workflow version."""
        version_id = self._generate_id()
        now = datetime.now()

        with self._db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_versions (id, workflow_id, version, name, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (version_id, workflow_id, version, name, description, WorkflowStatus.DRAFT.value, now),
            )
            conn.commit()

        return WorkflowVersionRecord(
            id=version_id,
            workflow_id=workflow_id,
            version=version,
            name=name,
            description=description,
            status=WorkflowStatus.DRAFT,
            created_at=now,
        )

    def get_version(self, version_id: str) -> Optional[WorkflowVersionRecord]:
        """Get a version by ID."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE id = ?",
                (version_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return WorkflowVersionRecord(
                id=row["id"],
                workflow_id=row["workflow_id"],
                version=row["version"],
                name=row["name"],
                description=row["description"],
                status=WorkflowStatus(row["status"]),
                published_at=_parse_dt(row["published_at"]),
                created_at=_parse_dt(row["created_at"]),
            )

    def list_versions(self, workflow_id: str) -> list[WorkflowVersionRecord]:
        """List all versions of a workflow."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version DESC",
                (workflow_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowVersionRecord(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    version=row["version"],
                    name=row["name"],
                    description=row["description"],
                    status=WorkflowStatus(row["status"]),
                    published_at=_parse_dt(row["published_at"]),
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    def get_latest_version(self, workflow_id: str) -> Optional[WorkflowVersionRecord]:
        """Get the latest version of a workflow."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version DESC LIMIT 1",
                (workflow_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return WorkflowVersionRecord(
                id=row["id"],
                workflow_id=row["workflow_id"],
                version=row["version"],
                name=row["name"],
                description=row["description"],
                status=WorkflowStatus(row["status"]),
                published_at=_parse_dt(row["published_at"]),
                created_at=_parse_dt(row["created_at"]),
            )

    def publish_version(self, version_id: str) -> Optional[WorkflowVersionRecord]:
        """Publish a version."""
        now = datetime.now()
        with self._db._get_connection() as conn:
            conn.execute(
                "UPDATE workflow_versions SET status = ?, published_at = ? WHERE id = ?",
                (WorkflowStatus.PUBLISHED.value, now, version_id),
            )
            conn.commit()
        return self.get_version(version_id)

    # Node management
    def save_nodes(
        self,
        version_id: str,
        nodes_data: list[dict[str, Any]],
    ) -> list[WorkflowNodeRecord]:
        """Save nodes for a version (replaces existing nodes)."""
        with self._db._get_connection() as conn:
            # Delete existing nodes
            conn.execute(
                "DELETE FROM workflow_nodes WHERE version_id = ?",
                (version_id,),
            )

            records = []
            for node_data in nodes_data:
                node_id = node_data.get("id") or self._generate_id()
                now = datetime.now()

                conn.execute(
                    """
                    INSERT INTO workflow_nodes
                    (id, version_id, type, label, position_x, position_y, width, height, config, timeout_seconds, max_retries, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        version_id,
                        _normalize_node_type(node_data.get("type", "emptyNode")),
                        node_data.get("label", "Node"),
                        node_data.get("position", {}).get("x", 0),
                        node_data.get("position", {}).get("y", 0),
                        node_data.get("width", 240),
                        node_data.get("height", 120),
                        json.dumps(node_data.get("config", {})),
                        node_data.get("timeout_seconds", 60),
                        node_data.get("max_retries", 0),
                        now,
                    ),
                )

                records.append(WorkflowNodeRecord(
                    id=node_id,
                    version_id=version_id,
                    type=NodeType(_normalize_node_type(node_data.get("type", "emptyNode"))),
                    label=node_data.get("label", "Node"),
                    position_x=node_data.get("position", {}).get("x", 0),
                    position_y=node_data.get("position", {}).get("y", 0),
                    width=node_data.get("width", 240),
                    height=node_data.get("height", 120),
                    config=node_data.get("config", {}),
                    timeout_seconds=node_data.get("timeout_seconds", 60),
                    max_retries=node_data.get("max_retries", 0),
                    created_at=now,
                ))

            conn.commit()
            return records

    def list_nodes(self, version_id: str) -> list[WorkflowNodeRecord]:
        """List all nodes for a version."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_nodes WHERE version_id = ?",
                (version_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowNodeRecord(
                    id=row["id"],
                    version_id=row["version_id"],
                    type=NodeType(_normalize_node_type(row["type"])),
                    label=row["label"],
                    position_x=row["position_x"],
                    position_y=row["position_y"],
                    width=row["width"],
                    height=row["height"],
                    config=json.loads(row["config"]) if row["config"] else {},
                    timeout_seconds=row["timeout_seconds"],
                    max_retries=row["max_retries"],
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    # Edge management
    def save_edges(
        self,
        version_id: str,
        edges_data: list[dict[str, Any]],
    ) -> list[WorkflowEdgeRecord]:
        """Save edges for a version (replaces existing edges)."""
        with self._db._get_connection() as conn:
            # Delete existing edges
            conn.execute(
                "DELETE FROM workflow_edges WHERE version_id = ?",
                (version_id,),
            )

            records = []
            for edge_data in edges_data:
                edge_id = edge_data.get("id") or self._generate_id()
                now = datetime.now()

                conn.execute(
                    """
                    INSERT INTO workflow_edges
                    (id, version_id, source_node_id, target_node_id, label, condition, source_handle, target_handle, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        version_id,
                        edge_data.get("source"),
                        edge_data.get("target"),
                        edge_data.get("label"),
                        edge_data.get("condition"),
                        edge_data.get("sourceHandle"),
                        edge_data.get("targetHandle"),
                        now,
                    ),
                )

                records.append(WorkflowEdgeRecord(
                    id=edge_id,
                    version_id=version_id,
                    source_node_id=edge_data.get("source"),
                    target_node_id=edge_data.get("target"),
                    label=edge_data.get("label"),
                    condition=edge_data.get("condition"),
                    source_handle=edge_data.get("sourceHandle"),
                    target_handle=edge_data.get("targetHandle"),
                    created_at=now,
                ))

            conn.commit()
            return records

    def list_edges(self, version_id: str) -> list[WorkflowEdgeRecord]:
        """List all edges for a version."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_edges WHERE version_id = ?",
                (version_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowEdgeRecord(
                    id=row["id"],
                    version_id=row["version_id"],
                    source_node_id=row["source_node_id"],
                    target_node_id=row["target_node_id"],
                    label=row["label"],
                    condition=row["condition"],
                    source_handle=row["source_handle"],
                    target_handle=row["target_handle"],
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    # Variable management
    def save_variables(
        self,
        version_id: str,
        variables_data: list[dict[str, Any]],
    ) -> list[WorkflowVariableRecord]:
        """Save variables for a version (replaces existing variables)."""
        with self._db._get_connection() as conn:
            # Delete existing variables
            conn.execute(
                "DELETE FROM workflow_variables WHERE version_id = ?",
                (version_id,),
            )

            records = []
            for var_data in variables_data:
                var_id = var_data.get("id") or self._generate_id()
                now = datetime.now()

                conn.execute(
                    """
                    INSERT INTO workflow_variables
                    (id, version_id, name, type, default_value, description, required, is_input, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        var_id,
                        version_id,
                        var_data.get("name"),
                        var_data.get("type", "string"),
                        json.dumps(var_data.get("default_value")),
                        var_data.get("description", ""),
                        var_data.get("required", False),
                        var_data.get("is_input", True),
                        now,
                    ),
                )

                records.append(WorkflowVariableRecord(
                    id=var_id,
                    version_id=version_id,
                    name=var_data.get("name"),
                    type=VariableType(var_data.get("type", "string")),
                    default_value=var_data.get("default_value"),
                    description=var_data.get("description", ""),
                    required=var_data.get("required", False),
                    is_input=var_data.get("is_input", True),
                    created_at=now,
                ))

            conn.commit()
            return records

    def list_variables(self, version_id: str) -> list[WorkflowVariableRecord]:
        """List all variables for a version."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_variables WHERE version_id = ?",
                (version_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowVariableRecord(
                    id=row["id"],
                    version_id=row["version_id"],
                    name=row["name"],
                    type=VariableType(row["type"]),
                    default_value=json.loads(row["default_value"]) if row["default_value"] else None,
                    description=row["description"],
                    required=row["required"],
                    is_input=row["is_input"],
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    # Trigger management
    def create_trigger(
        self,
        workflow_id: str,
        trigger_type: TriggerType,
        config: dict[str, Any],
        enabled: bool = True,
    ) -> WorkflowTriggerRecord:
        """Create a new trigger."""
        trigger_id = self._generate_id()
        now = datetime.now()

        with self._db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_triggers (id, workflow_id, trigger_type, config, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (trigger_id, workflow_id, trigger_type.value, json.dumps(config), enabled, now),
            )
            conn.commit()

        return WorkflowTriggerRecord(
            id=trigger_id,
            workflow_id=workflow_id,
            trigger_type=trigger_type,
            config=config,
            enabled=enabled,
            created_at=now,
        )

    def list_triggers(self, workflow_id: str) -> list[WorkflowTriggerRecord]:
        """List all triggers for a workflow."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_triggers WHERE workflow_id = ?",
                (workflow_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowTriggerRecord(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    trigger_type=TriggerType(row["trigger_type"]),
                    config=json.loads(row["config"]) if row["config"] else {},
                    enabled=row["enabled"],
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    # Save complete definition
    def save_definition(
        self,
        version_id: str,
        nodes_data: list[dict[str, Any]],
        edges_data: list[dict[str, Any]],
        variables_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Save complete workflow definition."""
        nodes = self.save_nodes(version_id, nodes_data)
        edges = self.save_edges(version_id, edges_data)
        variables = self.save_variables(version_id, variables_data)

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "variable_count": len(variables),
        }


class WorkflowRunStore:
    """Workflow run data store."""

    def __init__(self, db: Database):
        self._db = db

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    def create_run(
        self,
        workflow_id: str,
        version_id: str,
        trigger_type: str = "manual",
        input_variables: Optional[dict[str, Any]] = None,
    ) -> WorkflowRunRecord:
        """Create a new workflow run."""
        run_id = self._generate_id()
        now = datetime.now()

        with self._db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs
                (id, workflow_id, version_id, status, trigger_type, input_variables, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workflow_id,
                    version_id,
                    "pending",
                    trigger_type,
                    json.dumps(input_variables or {}),
                    now,
                    now,
                ),
            )
            conn.commit()

        return WorkflowRunRecord(
            id=run_id,
            workflow_id=workflow_id,
            version_id=version_id,
            status="pending",
            trigger_type=trigger_type,
            input_variables=input_variables or {},
            started_at=now,
            created_at=now,
        )

    def get_run(self, run_id: str) -> Optional[WorkflowRunRecord]:
        """Get a run by ID."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_runs WHERE id = ?",
                (run_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return WorkflowRunRecord(
                id=row["id"],
                workflow_id=row["workflow_id"],
                version_id=row["version_id"],
                status=row["status"],
                trigger_type=row["trigger_type"],
                input_variables=json.loads(row["input_variables"]) if row["input_variables"] else {},
                output_result=json.loads(row["output_result"]) if row["output_result"] else None,
                error_message=row["error_message"],
                current_node_id=row["current_node_id"],
                started_at=_parse_dt(row["started_at"]),
                completed_at=_parse_dt(row["completed_at"]),
                created_at=_parse_dt(row["created_at"]),
            )

    def update_run_status(
        self,
        run_id: str,
        status: str,
        output_result: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        current_node_id: Optional[str] = None,
    ) -> Optional[WorkflowRunRecord]:
        """Update run status."""
        updates = ["status = ?"]
        params = [status]

        if output_result is not None:
            updates.append("output_result = ?")
            params.append(json.dumps(output_result))
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if current_node_id is not None:
            updates.append("current_node_id = ?")
            params.append(current_node_id)

        if status in ("completed", "failed", "cancelled"):
            updates.append("completed_at = ?")
            params.append(datetime.now())

        params.append(run_id)

        with self._db._get_connection() as conn:
            conn.execute(
                f"UPDATE workflow_runs SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        return self.get_run(run_id)

    def list_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowRunRecord]:
        """List workflow runs."""
        query = "SELECT * FROM workflow_runs WHERE 1=1"
        params = []

        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._db._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                WorkflowRunRecord(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    version_id=row["version_id"],
                    status=row["status"],
                    trigger_type=row["trigger_type"],
                    input_variables=json.loads(row["input_variables"]) if row["input_variables"] else {},
                    output_result=json.loads(row["output_result"]) if row["output_result"] else None,
                    error_message=row["error_message"],
                    current_node_id=row["current_node_id"],
                    started_at=_parse_dt(row["started_at"]),
                    completed_at=_parse_dt(row["completed_at"]),
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

    # Run node management
    def create_run_node(
        self,
        run_id: str,
        node_id: str,
        input_data: Optional[dict[str, Any]] = None,
    ) -> WorkflowRunNodeRecord:
        """Create a run node record."""
        run_node_id = self._generate_id()
        now = datetime.now()

        with self._db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_run_nodes
                (id, run_id, node_id, status, input_data, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_node_id,
                    run_id,
                    node_id,
                    "running",
                    json.dumps(input_data or {}),
                    now,
                    now,
                ),
            )
            conn.commit()

        return WorkflowRunNodeRecord(
            id=run_node_id,
            run_id=run_id,
            node_id=node_id,
            status="running",
            input_data=input_data or {},
            started_at=now,
            created_at=now,
        )

    def update_run_node(
        self,
        run_node_id: str,
        status: str,
        output_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[WorkflowRunNodeRecord]:
        """Update run node status."""
        updates = ["status = ?"]
        params = [status]

        if output_data is not None:
            updates.append("output_data = ?")
            params.append(json.dumps(output_data))
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if status in ("completed", "failed", "skipped"):
            updates.append("completed_at = ?")
            params.append(datetime.now())

        params.append(run_node_id)

        with self._db._get_connection() as conn:
            conn.execute(
                f"UPDATE workflow_run_nodes SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        return self.get_run_node(run_node_id)

    def update_run_node_status_by_node_id(
        self,
        run_id: str,
        node_id: str,
        status: str,
    ) -> None:
        """Update run node status by run_id and node_id (first match only)."""
        with self._db._get_connection() as conn:
            updates = ["status = ?"]
            params: list[Any] = [status]

            if status in ("completed", "failed", "skipped"):
                updates.append("completed_at = ?")
                params.append(datetime.now())

            params.extend([run_id, node_id])

            conn.execute(
                f"UPDATE workflow_run_nodes SET {', '.join(updates)} "
                "WHERE run_id = ? AND node_id = ? ORDER BY created_at ASC LIMIT 1",
                params,
            )
            conn.commit()

    def get_run_node(self, run_node_id: str) -> Optional[WorkflowRunNodeRecord]:
        """Get a run node by ID."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_run_nodes WHERE id = ?",
                (run_node_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return WorkflowRunNodeRecord(
                id=row["id"],
                run_id=row["run_id"],
                node_id=row["node_id"],
                status=row["status"],
                input_data=json.loads(row["input_data"]) if row["input_data"] else {},
                output_data=json.loads(row["output_data"]) if row["output_data"] else {},
                error_message=row["error_message"],
                started_at=_parse_dt(row["started_at"]),
                completed_at=_parse_dt(row["completed_at"]),
                retry_count=row["retry_count"],
                created_at=_parse_dt(row["created_at"]),
            )

    def list_run_nodes(self, run_id: str) -> list[WorkflowRunNodeRecord]:
        """List all run nodes for a run."""
        with self._db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_run_nodes WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            )
            rows = cursor.fetchall()

            return [
                WorkflowRunNodeRecord(
                    id=row["id"],
                    run_id=row["run_id"],
                    node_id=row["node_id"],
                    status=row["status"],
                    input_data=json.loads(row["input_data"]) if row["input_data"] else {},
                    output_data=json.loads(row["output_data"]) if row["output_data"] else {},
                    error_message=row["error_message"],
                    started_at=_parse_dt(row["started_at"]),
                    completed_at=_parse_dt(row["completed_at"]),
                    retry_count=row["retry_count"],
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]
