"""Workflow execution engine."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from loguru import logger

from backend.data.database import Database
from backend.services.workflow.engine.context import WorkflowContext
from backend.services.workflow.engine.executor import NodeExecutor
from backend.services.workflow.models import (
    NodeType,
    WorkflowEdgeRecord,
    WorkflowNodeRecord,
    WorkflowRunNodeRecord,
    WorkflowRunRecord,
)
from backend.services.workflow.store import WorkflowRunStore, WorkflowStore


class WorkflowExecutionError(Exception):
    """Raised when a workflow node execution fails."""

    pass


class WorkflowCancelledError(Exception):
    """Raised when a workflow run is cancelled."""

    pass


class WorkflowEngine:
    """Workflow execution engine."""

    def __init__(self, db: Database, executor: NodeExecutor | None = None):
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
        version_id: str | None = None,
        input_variables: dict[str, Any] | None = None,
        trigger_type: str = "manual",
        on_node_update: Callable | None = None,
        test_mode: bool = False,
        timeout: float | None = None,
    ) -> WorkflowRunRecord:
        """Execute a workflow.

        Args:
            workflow_id: ID of the workflow to execute.
            version_id: Optional specific version to run.
            input_variables: Input variables for the workflow.
            trigger_type: How the workflow was triggered.
            on_node_update: Optional callback for real-time node status updates.
            test_mode: If True, execute without persisting run history.
            timeout: Maximum execution time in seconds (default 300s for test, None for normal).
        """
        # Resolve version_id if not provided
        if not version_id:
            versions = self._store.list_versions(workflow_id)
            published = [v for v in versions if v.status.value == "published"]
            if published:
                version_id = published[0].id
            else:
                raise ValueError(
                    "No published version found for this workflow. "
                    "Please publish a version before executing."
                )
        else:
            # Validate that the explicitly requested version is not archived
            version = self._store.get_version(version_id)
            if version and version.status.value == "archived":
                raise ValueError(
                    "Cannot execute an archived version. "
                    "Please provide a published or draft version_id, or omit it to use the published version."
                )

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

        # Register the running task for cancellation support (always, including test_mode)
        current_task = asyncio.current_task()
        if current_task:
            self._running_tasks[run.id] = current_task

        # Default timeout: 300s for test mode, no default for normal runs
        exec_timeout = timeout if timeout is not None else (300.0 if test_mode else None)

        try:
            nodes = self._store.list_nodes(version_id)
            edges = self._store.list_edges(version_id)
            variables = self._store.list_variables(version_id)

            # Validate required input variables (engine-level guard)
            input_vars = input_variables or {}
            required_missing = [
                v.name for v in variables if v.is_input and v.required and v.name not in input_vars
            ]
            if required_missing:
                raise ValueError(
                    f"Missing required input variables: {', '.join(required_missing)}. "
                    f"Provide them in input_variables."
                )

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
                # Check for cancellation before each node (always, including test_mode)
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
                    # Per-node timeout: use global timeout if set, else 120s default
                    node_timeout = exec_timeout if exec_timeout else 120.0
                    result = await asyncio.wait_for(
                        self._execute_node(node, context, edges),
                        timeout=node_timeout,
                    )

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
                        await on_node_update(
                            run.id,
                            node_id,
                            "completed",
                            {
                                "result": result,
                                "trace": trace_dict,
                                "duration_ms": (
                                    trace_dict.get("duration_ms") if trace_dict else None
                                ),
                            },
                        )

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
                        await on_node_update(
                            run.id,
                            node_id,
                            "failed",
                            {
                                "error": str(e),
                                "trace": trace_dict,
                                "duration_ms": (
                                    trace_dict.get("duration_ms") if trace_dict else None
                                ),
                            },
                        )

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
                await on_node_update(
                    run.id,
                    None,
                    "completed",
                    {
                        "result": final_outputs,
                        "all_traces": context.get_all_traces(),
                    },
                )

        except asyncio.TimeoutError:
            error_msg = (
                f"Workflow execution timed out after {exec_timeout}s"
                if exec_timeout
                else "Workflow execution timed out"
            )
            logger.warning(error_msg)
            if not test_mode:
                self._run_store.update_run_status(run.id, "failed", error_message=error_msg)
            else:
                run.status = "failed"
                run.error_message = error_msg
                run.completed_at = datetime.now()
            if on_node_update:
                await on_node_update(run.id, None, "failed", {"error": error_msg})
            return run if test_mode else self._run_store.get_run(run.id)

        except asyncio.CancelledError:
            # Task was cancelled (e.g. via cancel_run) - treat as workflow cancellation
            logger.info(f"Workflow run {run.id} was cancelled via task cancellation")
            if not test_mode:
                self._run_store.update_run_status(run.id, "cancelled")
            else:
                run.status = "cancelled"
                run.completed_at = datetime.now()
            if on_node_update:
                await on_node_update(run.id, None, "cancelled", {})
            raise WorkflowCancelledError(f"Run {run.id} was cancelled") from None

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
            # Always clean up running task tracking
            self._running_tasks.pop(run.id, None)

        if test_mode:
            run.status = "completed"
            run.completed_at = datetime.now()
            return run
        else:
            return self._run_store.get_run(run.id)

    def _check_cancellation(self, run_id: str) -> None:
        """Check if the run has been cancelled and raise if so."""
        # Check DB for normal runs
        run = self._run_store.get_run(run_id)
        if run and run.status == "cancelled":
            raise WorkflowCancelledError(f"Run {run_id} was cancelled")
        # Check task directly for test_mode or immediate cancellation
        task = self._running_tasks.get(run_id)
        if task and task.cancelled():
            raise WorkflowCancelledError(f"Run {run_id} was cancelled")

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            run_id: ID of the run to cancel.

        Returns:
            True if the run was found and cancelled, False otherwise.
        """
        cancelled = False

        # Update DB status for normal runs
        run = self._run_store.get_run(run_id)
        if run:
            if run.status not in ("pending", "running"):
                return False
            self._run_store.update_run_status(run_id, "cancelled")
            cancelled = True

        # Directly cancel the asyncio task (works for both normal and test_mode)
        task = self._running_tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            cancelled = True

        return cancelled

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
        logger.info(
            f"[_build_execution_order] Total nodes: {len(nodes)}, Total edges: {len(edges)}"
        )
        for n in nodes:
            node_type_val = n.type.value if hasattr(n.type, "value") else n.type
            logger.info(f"  Node: id={n.id}, type={node_type_val}, parent_id={n.parent_id}")
        for e in edges:
            logger.info(
                f"  Edge: {e.source_node_id} -> {e.target_node_id}, handles: {e.source_handle}/{e.target_handle}"
            )

        loop_node_ids = {
            n.id for n in nodes if (n.type.value if hasattr(n.type, "value") else n.type) == "loop"
        }
        logger.info(f"[_build_execution_order] Loop nodes found: {loop_node_ids}")

        child_node_ids = {n.id for n in nodes if n.parent_id and n.parent_id in loop_node_ids}
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

            return bool(
                "body-start" in source_handle
                or "body-start" in target_handle
                or "body-end" in source_handle
                or "body-end" in target_handle
            )

        effective_edges = [e for e in edges if not is_loop_internal_edge(e)]

        # 4️⃣ 使用过滤后的节点和边构建图进行拓扑排序
        graph: dict[str, list[str]] = {n.id: [] for n in effective_nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in effective_nodes}

        for edge in effective_edges:
            if edge.source_node_id in graph and edge.target_node_id in graph:
                graph[edge.source_node_id].append(edge.target_node_id)
                in_degree[edge.target_node_id] += 1

        # 4️⃣.5️⃣ 扫描节点 config 中的变量引用，添加隐式依赖边
        # 例如 database 节点的 fieldMappings.value = {{codeNode.result}}
        # 需要确保 codeNode 在 database 之前执行
        for node in effective_nodes:
            config = node.config or {}
            for cfg_value in config.values():
                refs = self._extract_node_refs_from_value(cfg_value)
                for ref_node_id in refs:
                    if ref_node_id in graph and ref_node_id != node.id and node.id not in graph[ref_node_id]:
                            graph[ref_node_id].append(node.id)
                            in_degree[node.id] += 1
                            logger.info(
                                f"[_build_execution_order] implicit edge: {ref_node_id} -> {node.id}"
                            )

        # Use deque for O(1) popleft instead of O(n) list.pop(0)
        queue: deque[str] = deque(
            sorted(
                (n_id for n_id, degree in in_degree.items() if degree == 0),
                key=lambda x: x,  # Stable sort by node ID for determinism
            )
        )
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

    def _extract_node_refs_from_value(self, value: Any) -> set[str]:
        """Extract {{nodeId.outputKey}} node IDs from a config value recursively."""
        import re

        refs: set[str] = set()
        if isinstance(value, str):
            for m in re.finditer(r"\{\{(.+?)\}\}", value):
                ref = m.group(1)
                if "." in ref:
                    refs.add(ref.split(".", 1)[0])
        elif isinstance(value, dict):
            for v in value.values():
                refs.update(self._extract_node_refs_from_value(v))
        elif isinstance(value, list):
            for item in value:
                refs.update(self._extract_node_refs_from_value(item))
        return refs

    async def _execute_node(
        self,
        node: WorkflowNodeRecord,
        context: WorkflowContext,
        edges: list[WorkflowEdgeRecord],
    ) -> dict[str, Any]:
        """Execute a single node."""
        context.set_current_node(node.id)
        context.clear_unresolved_refs(node.id)

        inputs_config = node.config.get("inputs", [])
        inputs: dict[str, Any] = {}

        node_type = node.type.value if isinstance(node.type, NodeType) else str(node.type)

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

        # 将解析后的 inputs 绑定到当前节点上下文，供 userPrompt / systemPrompt 中的
        # {{变量名}} 短引用使用（如 {{input}}）。只注入有效绑定的变量。
        valid_inputs = {}
        for key, value in inputs.items():
            if value is None or value == "" or value == "{{?}}":
                continue
            if isinstance(value, str) and value.startswith("[未解析"):
                continue
            valid_inputs[key] = value
        context._current_inputs = valid_inputs

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

        # Inject code/config fields for specific node types
        if node_type == "code":
            node_code = node.config.get("code", "")
            if node_code:
                inputs["code"] = node_code
            else:
                import logging

                logging.warning(
                    f"[CodeNode] code is empty for node {node.id}, config keys: {list(node.config.keys())}"
                )

        # Fallback: for nodes that store config directly in node.config (not in inputs list),
        # inject config values into inputs when inputs list is empty or values are missing.
        # This fixes nodes like database, http, etc. where frontend saves to node.data directly.
        # For values containing {{...}} variable refs, keep them as-is so the executor can
        # resolve them at execution time (after all dependencies have produced outputs).
        if node_type in ("database", "http", "httpRequest468", "readFiles"):
            logger.info(f"[_execute_node] fallback for {node_type}, inputs before: {inputs}")
            for key, value in (node.config or {}).items():
                if (
                    key not in ("inputs", "outputs", "_parentId", "__parentId")
                    and value is not None
                ) and (key not in inputs or inputs[key] is None or inputs[key] == ""):
                    # Only resolve values that don't contain variable references;
                    # leave {{...}} refs for the executor to resolve later.
                    if self._contains_var_ref(value):
                        inputs[key] = value
                        logger.info(
                            f"[_execute_node] fallback injected (raw ref): {key} = {value}"
                        )
                    else:
                        inputs[key] = context.resolve_value(value)
                        logger.info(
                            f"[_execute_node] fallback injected (resolved): {key} = {inputs[key]}"
                        )
            logger.info(f"[_execute_node] inputs after fallback: {inputs}")

        # Record resolved inputs into the trace so the outer loop can reference them
        context.update_node_trace(node.id, input_snapshot=inputs)

        # Check for unresolved variable references in this node's inputs
        unresolved = context.get_unresolved_refs(node.id)
        if unresolved:
            ref_messages = [f"{{{u['ref']}}}" for u in unresolved]
            error_detail = {
                "type": "unresolved_variables",
                "message": f"存在未解析的变量引用: {', '.join(ref_messages)}",
                "refs": unresolved,
            }
            context.update_node_trace(
                node.id,
                error_detail=error_detail,
            )
            logger.warning(
                "[Node %s] unresolved variable refs: %s",
                node.id,
                ref_messages,
            )

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
            "database": self._executor.execute_database,
        }

        executor = executor_map.get(node_type)
        if executor:
            return await executor(node, inputs, context)

        return {"result": inputs}

    def _contains_var_ref(self, value: Any) -> bool:
        """Check if a value contains {{...}} variable references."""
        import re

        if isinstance(value, str):
            return bool(re.search(r"\{\{(.+?)\}\}", value))
        elif isinstance(value, dict):
            return any(self._contains_var_ref(v) for v in value.values())
        elif isinstance(value, list):
            return any(self._contains_var_ref(item) for item in value)
        return False

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
            source_node.type.value if hasattr(source_node.type, "value") else source_node.type
        )
        if source_type != "ifElseNode":
            return True

        result_true = context.get_node_output(source_node.id, "system_resultTrue")

        source_handle = edge.source_handle or ""
        prefix = f"{source_node.id}-source-"
        key = source_handle[len(prefix) :] if source_handle.startswith(prefix) else source_handle

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

        return any(self._is_edge_active(edge, nodes, context) for edge in incoming_edges)

    def get_run_status(self, run_id: str) -> dict[str, Any] | None:
        """Get run status."""
        run = self._run_store.get_run(run_id)
        if not run:
            return None

        nodes = self._run_store.list_run_nodes(run_id)

        return {
            "id": run.id,
            "workflow_id": run.workflow_id,
            "version_id": run.version_id,
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
