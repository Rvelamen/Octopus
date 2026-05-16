"""Workflow execution engine."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional, Callable
from uuid import uuid4

from backend.services.workflow.store import WorkflowStore, WorkflowRunStore
from backend.services.workflow.models import (
    WorkflowNodeRecord,
    WorkflowEdgeRecord,
    WorkflowRunRecord,
    WorkflowRunNodeRecord,
    NodeType,
)
from backend.services.workflow.engine.context import WorkflowContext
from backend.services.workflow.engine.executor import NodeExecutor
from backend.data.database import Database
from loguru import logger


class WorkflowExecutionError(Exception):
    """Raised when a workflow node execution fails."""
    pass


class WorkflowCancelledError(Exception):
    """Raised when a workflow run is cancelled."""
    pass


class WorkflowEngine:
    """Workflow execution engine."""

    def __init__(self, db: Database, executor: Optional[NodeExecutor] = None):
        """Initialize the engine.

        Args:
            db: Database instance.
            executor: Optional NodeExecutor for dependency injection / testing.
        """
        self._db = db
        self._store = WorkflowStore(db)
        self._run_store = WorkflowRunStore(db)
        self._executor = executor or NodeExecutor()
        # Allow executor to call back into the engine for sub-workflow execution
        self._executor._engine = self
        # Track running tasks for cancellation
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def execute(
        self,
        workflow_id: str,
        version_id: Optional[str] = None,
        input_variables: Optional[dict[str, Any]] = None,
        trigger_type: str = "manual",
        on_node_update: Optional[Callable] = None,
        test_mode: bool = False,
    ) -> WorkflowRunRecord:
        """Execute a workflow.

        Args:
            workflow_id: ID of the workflow to execute.
            version_id: Optional specific version to run.
            input_variables: Input variables for the workflow.
            trigger_type: How the workflow was triggered.
            on_node_update: Optional callback for real-time node status updates.
            test_mode: If True, execute without persisting run history.
        """
        # Resolve version_id if not provided
        if not version_id:
            versions = self._store.list_versions(workflow_id)
            published = [v for v in versions if v.status.value == "published"]
            if published:
                version_id = published[0].id
            elif versions:
                version_id = versions[0].id
            else:
                raise ValueError("No versions found for workflow")

        # Create run record (in-memory only for test mode)
        now = datetime.now()
        if test_mode:
            run = WorkflowRunRecord(
                id=f"test-{uuid4().hex[:12]}",
                workflow_id=workflow_id,
                version_id=version_id,
                status="pending",
                trigger_type=trigger_type,
                input_variables=input_variables or {},
                started_at=now,
                created_at=now,
            )
        else:
            run = self._run_store.create_run(
                workflow_id=workflow_id,
                version_id=version_id,
                trigger_type=trigger_type,
                input_variables=input_variables,
            )

        # Register the running task for cancellation support
        if not test_mode:
            current_task = asyncio.current_task()
            if current_task:
                self._running_tasks[run.id] = current_task

        try:
            nodes = self._store.list_nodes(version_id)
            edges = self._store.list_edges(version_id)
            variables = self._store.list_variables(version_id)

            context = WorkflowContext(input_variables or {}, version_id=version_id)

            for var in variables:
                if var.default_value is not None:
                    context.set_variable(var.name, var.default_value)

            execution_order = self._build_execution_order(nodes, edges)

            if not test_mode:
                self._run_store.update_run_status(run.id, "running")

            if on_node_update:
                await on_node_update(run.id, None, "running", {})

            for node_id in execution_order:
                # Check for cancellation before each node
                if not test_mode:
                    self._check_cancellation(run.id)

                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue

                if not self._should_execute_node(node_id, edges, nodes, context):
                    if not test_mode:
                        self._run_store.update_run_node_status_by_node_id(
                            run.id, node_id, "skipped"
                        )
                    context.update_node_trace(node_id, status="skipped")
                    continue

                if not test_mode:
                    self._run_store.update_run_status(run.id, "running", current_node_id=node_id)

                if on_node_update:
                    await on_node_update(run.id, node_id, "running", {})

                # Start node trace
                context.start_node_trace(node_id)

                if test_mode:
                    run_node = WorkflowRunNodeRecord(
                        id=f"test-node-{uuid4().hex[:12]}",
                        run_id=run.id,
                        node_id=node_id,
                        status="running",
                        started_at=datetime.now(),
                        created_at=datetime.now(),
                    )
                else:
                    run_node = self._run_store.create_run_node(run.id, node_id)

                try:
                    result = await self._execute_node(node, context, edges)

                    for key, value in result.items():
                        context.set_node_output(node_id, key, value)

                    # Update trace with output snapshot
                    context.update_node_trace(
                        node_id,
                        status="completed",
                        output_snapshot=result,
                    )

                    if not test_mode:
                        self._run_store.update_run_node(
                            run_node.id,
                            "completed",
                            output_data=result,
                        )

                    if on_node_update:
                        trace = context.get_node_trace(node_id)
                        trace_dict = trace.to_dict() if trace else None
                        await on_node_update(run.id, node_id, "completed", {
                            "result": result,
                            "trace": trace_dict,
                            "duration_ms": trace_dict.get("duration_ms") if trace_dict else None,
                        })

                except WorkflowCancelledError:
                    context.update_node_trace(node_id, status="skipped")
                    if not test_mode:
                        self._run_store.update_run_node(
                            run_node.id, "skipped", error_message="Run cancelled"
                        )
                    raise  # Re-raise to propagate

                except Exception as e:
                    context.update_node_trace(
                        node_id,
                        status="failed",
                        error_detail={"message": str(e), "type": type(e).__name__},
                    )

                    if not test_mode:
                        self._run_store.update_run_node(
                            run_node.id,
                            "failed",
                            error_message=str(e),
                        )

                        self._run_store.update_run_status(
                            run.id,
                            "failed",
                            error_message=str(e),
                        )

                    if on_node_update:
                        trace = context.get_node_trace(node_id)
                        trace_dict = trace.to_dict() if trace else None
                        await on_node_update(run.id, node_id, "failed", {
                            "error": str(e),
                            "trace": trace_dict,
                            "duration_ms": trace_dict.get("duration_ms") if trace_dict else None,
                        })

                    if not test_mode:
                        return self._run_store.get_run(run.id)
                    else:
                        run.status = "failed"
                        run.error_message = str(e)
                        run.completed_at = datetime.now()
                        return run

            final_outputs = self._collect_end_node_outputs(nodes, context)

            if not test_mode:
                self._run_store.update_run_status(
                    run.id,
                    "completed",
                    output_result=final_outputs,
                )

            if on_node_update:
                await on_node_update(run.id, None, "completed", {
                    "result": final_outputs,
                    "all_traces": context.get_all_traces(),
                })

        except WorkflowCancelledError:
            # Already handled above, just re-raise
            raise

        except Exception as e:
            if not test_mode:
                self._run_store.update_run_status(
                    run.id,
                    "failed",
                    error_message=str(e),
                )

            if on_node_update:
                await on_node_update(run.id, None, "failed", {"error": str(e)})

        finally:
            if not test_mode:
                self._running_tasks.pop(run.id, None)

        if test_mode:
            run.status = "completed"
            run.completed_at = datetime.now()
            return run
        else:
            return self._run_store.get_run(run.id)

    def _check_cancellation(self, run_id: str) -> None:
        """Check if the run has been cancelled and raise if so."""
        run = self._run_store.get_run(run_id)
        if run and run.status == "cancelled":
            raise WorkflowCancelledError(f"Run {run_id} was cancelled")

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            run_id: ID of the run to cancel.

        Returns:
            True if the run was found and cancelled, False otherwise.
        """
        run = self._run_store.get_run(run_id)
        if not run:
            return False

        if run.status not in ("pending", "running"):
            return False  # Can only cancel pending or running runs

        self._run_store.update_run_status(run_id, "cancelled")
        return True

    def _build_execution_order(
        self,
        nodes: list[WorkflowNodeRecord],
        edges: list[WorkflowEdgeRecord],
    ) -> list[str]:
        """Build execution order using Kahn's algorithm (topological sort).

        ⭐ 改进版：支持循环节点（Loop Node），将其视为超级节点，忽略内部连接

        Uses a stable queue (collections.deque) for predictable ordering
        when multiple nodes have the same in-degree.
        """
        from collections import deque

        # 1️⃣ 识别 Loop 节点和它们的子节点
        logger.info(f"[_build_execution_order] Total nodes: {len(nodes)}, Total edges: {len(edges)}")
        for n in nodes:
            node_type_val = n.type.value if hasattr(n.type, 'value') else n.type
            logger.info(f"  Node: id={n.id}, type={node_type_val}, parent_id={n.parent_id}")
        for e in edges:
            logger.info(f"  Edge: {e.source_node_id} -> {e.target_node_id}, handles: {e.source_handle}/{e.target_handle}")
        
        loop_node_ids = {
            n.id for n in nodes
            if (n.type.value if hasattr(n.type, 'value') else n.type) == "loop"
        }
        logger.info(f"[_build_execution_order] Loop nodes found: {loop_node_ids}")
        
        child_node_ids = {
            n.id for n in nodes
            if n.parent_id and n.parent_id in loop_node_ids
        }
        logger.info(f"[_build_execution_order] Child nodes found: {child_node_ids}")

        # 2️⃣ 过滤出需要参与拓扑排序的"有效节点"
        #    - 所有非子节点的普通节点
        #    - Loop 节点本身（作为超级节点代表整个循环体）
        effective_nodes = [n for n in nodes if n.id not in child_node_ids]

        # 3️⃣ 过滤出"有效边"
        #    排除以下类型的边：
        #    a) 涉及子节点的边（循环体内部连接）
        #    b) 涉及 body-start / body-end handles 的边（循环体入口/出口）
        def is_loop_internal_edge(edge: WorkflowEdgeRecord) -> bool:
            # 如果 source 或 target 是子节点，这是内部连接
            if edge.source_node_id in child_node_ids or edge.target_node_id in child_node_ids:
                return True
            
            # 如果涉及 body-start 或 body-end handle，这是循环体的入口/出口连接
            source_handle = edge.source_handle or ""
            target_handle = edge.target_handle or ""
            
            if (
                "body-start" in source_handle or "body-start" in target_handle or
                "body-end" in source_handle or "body-end" in target_handle
            ):
                return True
            
            return False

        effective_edges = [e for e in edges if not is_loop_internal_edge(e)]

        # 4️⃣ 使用过滤后的节点和边构建图进行拓扑排序
        graph: dict[str, list[str]] = {n.id: [] for n in effective_nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in effective_nodes}

        for edge in effective_edges:
            if edge.source_node_id in graph and edge.target_node_id in graph:
                graph[edge.source_node_id].append(edge.target_node_id)
                in_degree[edge.target_node_id] += 1

        # Use deque for O(1) popleft instead of O(n) list.pop(0)
        queue: deque[str] = deque(sorted(
            (n_id for n_id, degree in in_degree.items() if degree == 0),
            key=lambda x: x  # Stable sort by node ID for determinism
        ))
        result: list[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for neighbor in sorted(graph[node_id]):  # Sort for deterministic order
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有环（基于有效节点的数量）
        if len(result) != len(effective_nodes):
            raise ValueError("Workflow contains cycles")

        return result

    async def _execute_node(
        self,
        node: WorkflowNodeRecord,
        context: WorkflowContext,
        edges: list[WorkflowEdgeRecord],
    ) -> dict[str, Any]:
        """Execute a single node."""
        context.set_current_node(node.id)

        inputs_config = node.config.get("inputs", [])
        inputs: dict[str, Any] = {}

        node_type = node.type.value if isinstance(node.type, NodeType) else node_type

        # workflowStart inputs are self-referential ({{workflowStart.var_1}}),
        # resolve them from context._variables (runtime input) instead
        if node_type in ("workflowStart", "start"):
            if isinstance(inputs_config, list):
                for input_item in inputs_config:
                    key = input_item.get("name") or input_item.get("key")
                    if key is not None:
                        inputs[key] = context._variables.get(key, "")
            elif isinstance(inputs_config, dict):
                for key in inputs_config:
                    inputs[key] = context._variables.get(key, "")
            inputs = {**inputs, **context._variables}
        elif isinstance(inputs_config, list):
            for input_item in inputs_config:
                key = input_item.get("name") or input_item.get("key")
                value = input_item.get("value")
                if key is not None:
                    inputs[key] = context.resolve_value(value)
        elif isinstance(inputs_config, dict):
            inputs = context.resolve_inputs(inputs_config)

        # Translate loopConfig/parallelConfig into inputs format
        if node_type in ("loop", "parallelRun"):
            loop_config = node.config.get("loopConfig") or node.config.get("parallelConfig") or {}
            loop_type = loop_config.get("loopType", "array")

            if loop_type == "array":
                loop_array = loop_config.get("loopArray", {})
                var_value = loop_array.get("varValue", "")
                if var_value:
                    resolved = context.resolve_value(var_value)
                    inputs["loopInputArray"] = resolved
                var_name = loop_array.get("varName")
                if var_name:
                    inputs["loopItemVariable"] = var_name
            elif loop_type == "count":
                loop_count_cfg = loop_config.get("loopCount", {})
                count = int(loop_count_cfg.get("value", 10))
                inputs["loopInputArray"] = list(range(count))
                inputs["loopMaxIterations"] = count
            else:
                loop_count_cfg = loop_config.get("loopCount", {})
                count = int(loop_count_cfg.get("value", 10))
                inputs["loopInputArray"] = list(range(count))
                inputs["loopMaxIterations"] = count

        # Allow input_variables to override node inputs (for testing and runtime injection)
        for key in list(inputs.keys()):
            if key in context._variables:
                inputs[key] = context._variables[key]

        # Record resolved inputs into the trace so the outer loop can reference them
        context.update_node_trace(node.id, input_snapshot=inputs)

        executor_map = {
            "workflowStart": self._executor.execute_workflow_start,
            "start": self._executor.execute_workflow_start,
            "chatNode": self._executor.execute_chat,
            "llm": self._executor.execute_chat,
            "httpRequest468": self._executor.execute_http,
            "code": self._executor.execute_code,
            "ifElseNode": self._executor.execute_if_else,
            "answerNode": self._executor.execute_answer,
            "workflowEnd": self._executor.execute_workflow_end,
            "end": self._executor.execute_workflow_end,
            "classifyQuestion": self._executor.execute_classify_question,
            "contentExtract": self._executor.execute_content_extract,
            "variableUpdate": self._executor.execute_variable_update,
            "loop": self._executor.execute_loop,
            "parallelRun": self._executor.execute_parallel_run,
            "agentNode": self._executor.execute_agent,
            "subWorkflowNode": self._executor.execute_sub_workflow,
            "readFiles": self._executor.execute_read_files,
            "jsonSerialize": self._executor.execute_json_serialize,
            "jsonDeserialize": self._executor.execute_json_deserialize,
        }

        executor = executor_map.get(node_type)
        if executor:
            return await executor(node, inputs, context)

        return {"result": inputs}

    async def execute_step(
        self,
        run_id: str,
        node_id: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single step for debugging."""
        run = self._run_store.get_run(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        nodes = self._store.list_nodes(run.version_id)
        node = next((n for n in nodes if n.id == node_id), None)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        context = WorkflowContext(run.input_variables)
        edges = self._store.list_edges(run.version_id)
        return await self._execute_node(node, context, edges)

    async def _execute_node_internal(
        self,
        node_id: str,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Internal node execution used by loop/parallel nodes.

        Looks up the node definition by ID from the current version and
        executes it with the provided inputs.
        """
        version_id = context._version_id
        if not version_id:
            return {"error": "No version_id in context for sub-workflow execution"}

        nodes = self._store.list_nodes(version_id)
        node = next((n for n in nodes if n.id == node_id), None)
        if not node:
            return {"error": f"Node not found: {node_id}"}

        edges = self._store.list_edges(version_id)
        return await self._execute_node(node, context, edges)

    def _is_edge_active(
        self,
        edge: WorkflowEdgeRecord,
        nodes: list[WorkflowNodeRecord],
        context: WorkflowContext,
    ) -> bool:
        """Check if an edge is active (for conditional branches)."""
        source_node = next((n for n in nodes if n.id == edge.source_node_id), None)
        if not source_node:
            return True

        source_type = (
            source_node.type.value
            if hasattr(source_node.type, "value")
            else source_node.type
        )
        if source_type != "ifElseNode":
            return True

        result_true = context.get_node_output(source_node.id, "system_resultTrue")

        source_handle = edge.source_handle or ""
        prefix = f"{source_node.id}-source-"
        key = source_handle[len(prefix):] if source_handle.startswith(prefix) else source_handle

        if key == "system_resultTrue":
            return bool(result_true)
        elif key == "system_resultFalse":
            return not bool(result_true)

        return True

    def _collect_end_node_outputs(
        self,
        nodes: list[WorkflowNodeRecord],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Collect outputs only from the WorkflowEnd node, with clean key names.

        Unlike get_all_outputs() which returns ALL node outputs with nodeId.key format,
        this only returns the end node's configured outputs without internal fields.
        """
        end_node = next((n for n in nodes if n.type == NodeType.WORKFLOW_END), None)
        if not end_node:
            return context.get_all_outputs()

        end_outputs = context._node_outputs.get(end_node.id, {})
        return {k: v for k, v in end_outputs.items() if not k.startswith("_")}

    def _should_execute_node(
        self,
        node_id: str,
        edges: list[WorkflowEdgeRecord],
        nodes: list[WorkflowNodeRecord],
        context: WorkflowContext,
    ) -> bool:
        """Check if a node should execute based on active incoming edges."""
        incoming_edges = [e for e in edges if e.target_node_id == node_id]
        if not incoming_edges:
            return True

        return any(
            self._is_edge_active(edge, nodes, context)
            for edge in incoming_edges
        )

    def get_run_status(self, run_id: str) -> Optional[dict[str, Any]]:
        """Get run status."""
        run = self._run_store.get_run(run_id)
        if not run:
            return None

        nodes = self._run_store.list_run_nodes(run_id)

        return {
            "id": run.id,
            "status": run.status,
            "current_node_id": run.current_node_id,
            "error_message": run.error_message,
            "input_variables": run.input_variables,
            "output_result": run.output_result,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "nodes": [
                {
                    "id": n.id,
                    "node_id": n.node_id,
                    "status": n.status,
                    "error_message": n.error_message,
                    "started_at": n.started_at.isoformat() if n.started_at else None,
                    "completed_at": n.completed_at.isoformat() if n.completed_at else None,
                }
                for n in nodes
            ],
        }
