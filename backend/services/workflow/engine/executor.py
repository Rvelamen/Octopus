"""Node executor implementations."""

from __future__ import annotations

import ast
import re
import json
import httpx
from typing import Any

from backend.services.workflow.models import WorkflowNodeRecord
from backend.services.workflow.engine.context import WorkflowContext


class NodeExecutor:
    """Executor for workflow nodes.

    Args:
        engine: Optional WorkflowEngine instance for sub-workflow execution
                (loop/parallel nodes). Enables recursive node execution.
    """

    def __init__(self, engine: Optional[Any] = None):
        self._engine = engine

    async def execute_workflow_start(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute workflow start node.

        Supports dynamic input variables configured in node.config.inputs.
        Returns all input variables as node outputs so downstream nodes
        can reference them via {{nodeId.variableKey}}.
        """
        result = {}

        # Get configured input variables from node config
        node_config = node.config or {}
        configured_inputs = node_config.get("inputs", [])

        if configured_inputs and isinstance(configured_inputs, list):
            # Use dynamically configured input variables
            for input_def in configured_inputs:
                key = (input_def.get("name") or input_def.get("key")) if isinstance(input_def, dict) else input_def
                if key:
                    result[key] = inputs.get(key, "")
        else:
            # Fallback to legacy defaults for backward compatibility
            result = {
                "userChatInput": inputs.get("userChatInput", ""),
                "userFiles": inputs.get("userFiles", []),
            }

        # Include any other input variables (e.g. custom keys from RunInputModal)
        for key, value in inputs.items():
            if key not in result:
                result[key] = value

        return result

    async def execute_chat(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute AI chat node."""
        from backend.services.llm_service import LLMService

        # Use provider/model from node config if available
        node_config = node.config or {}
        provider_id = node_config.get("providerId")
        model_id = node_config.get("modelId")

        model = inputs.get("model", "")
        if model_id:
            model = model_id
        elif not model:
            model = "gpt-4o-mini"

        # Read prompts from node config (not inputs dict) and resolve variable references
        system_prompt = context.resolve_value(node_config.get("systemPrompt", ""))
        user_message = context.resolve_value(node_config.get("userPrompt", ""))

        # Fallback: if userPrompt is empty or still contains unresolved placeholders,
        # try to use input variable values as the message
        has_unresolved = bool(re.search(r'\{\{.+?\}\}', user_message))
        if (not user_message or has_unresolved) and inputs:
            input_values = [
                str(v) for v in inputs.values()
                if v is not None and isinstance(v, (str, int, float, bool))
            ]
            if input_values:
                user_message = "\n".join(input_values)

        temperature = float(node_config.get("temperature", 0.7))
        max_tokens = int(node_config.get("maxToken", 2000))

        # Get chat history if available
        history = inputs.get("history", [])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add history
        for msg in history:
            messages.append(msg)

        # Add user message
        if user_message:
            messages.append({"role": "user", "content": user_message})

        try:
            llm_service = LLMService()
            response = await llm_service.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_id=provider_id,
            )

            content = response.get("content", "")
            reasoning = response.get("reasoning", "")
            return {
                # Primary output key matching frontend default output name
                "output": content,
                # Legacy keys for backward compatibility
                "answerText": content,
                "reasoningText": reasoning,
            }
        except Exception as e:
            raise RuntimeError(f"Error calling LLM: {e}") from e

    async def execute_dataset_search(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute dataset search node."""
        from backend.services.knowledge_service import KnowledgeService

        datasets = inputs.get("datasets", [])
        query = inputs.get("userChatInput", "")
        similarity = float(inputs.get("similarity", 0.7))
        limit = int(inputs.get("limit", 5))

        if not datasets or not query:
            return {"quoteQA": []}

        try:
            knowledge_service = KnowledgeService()
            results = await knowledge_service.search(
                dataset_ids=datasets,
                query=query,
                top_k=limit,
                score_threshold=similarity,
            )

            return {"quoteQA": results}
        except Exception as e:
            return {"quoteQA": [], "error": str(e)}

    async def execute_http(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute HTTP request node."""
        url = inputs.get("system_httpReqUrl", "")
        method = inputs.get("system_httpMethod", "GET").upper()
        headers = inputs.get("system_httpHeader", [])
        params = inputs.get("system_httpParams", [])
        body = inputs.get("system_httpJsonBody", "")
        timeout = int(inputs.get("system_httpTimeout", 60))

        if not url:
            return {"error": "URL is required"}

        try:
            # Convert headers and params to dict
            headers_dict = {h["key"]: h["value"] for h in headers if "key" in h and "value" in h}
            params_dict = {p["key"]: p["value"] for p in params if "key" in p and "value" in p}

            # Parse body if it's JSON
            json_body = None
            if body and method in ["POST", "PUT", "PATCH"]:
                try:
                    json_body = json.loads(body)
                except json.JSONDecodeError:
                    pass

            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers_dict, params=params_dict)
                elif method == "POST":
                    response = await client.post(
                        url,
                        headers=headers_dict,
                        params=params_dict,
                        json=json_body,
                    )
                elif method == "PUT":
                    response = await client.put(
                        url,
                        headers=headers_dict,
                        params=params_dict,
                        json=json_body,
                    )
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers_dict, params=params_dict)
                elif method == "PATCH":
                    response = await client.patch(
                        url,
                        headers=headers_dict,
                        params=params_dict,
                        json=json_body,
                    )
                else:
                    return {"error": f"Unsupported HTTP method: {method}"}

                response_text = response.text
                try:
                    response_json = response.json()
                except json.JSONDecodeError:
                    response_json = None

                return {
                    "httpRawResponse": {
                        "status": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_json if response_json is not None else response_text,
                    },
                    "system_text": response_text,
                }

        except Exception as e:
            return {
                "error": str(e),
                "system_text": "",
            }

    async def execute_code(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute Python code in a restricted environment using AST analysis.

        Only pure expression evaluation is allowed (no statements like assignment,
        loops, imports, or function definitions). Results are captured via the
        `result` variable.

        Supported builtins: len, range, enumerate, zip, map, filter, sum, min,
        max, abs, round, sorted, reversed, str, int, float, bool, list, dict,
        set, tuple, slice, open, print, json, re, math, datetime, timedelta.
        """
        code = inputs.get("code", "")
        code_type = inputs.get("codeType", "python")

        if not code:
            return {"system_text": "", "error": "Code is required"}

        try:
            if code_type == "python":
                return self._execute_safe_python(code, inputs, context)
            else:
                return {"system_text": "", "error": f"Unsupported code type: {code_type}"}
        except Exception as e:
            return {"system_text": "", "error": str(e)}

    def _execute_safe_python(
        self,
        code: str,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute Python code safely using AST parsing and eval."""
        import math
        from datetime import datetime, timedelta

        # Parse the code into an AST
        try:
            tree = ast.parse(code.strip())
        except SyntaxError as e:
            return {"system_text": "", "error": f"Syntax error: {e}"}

        # Only allow a single expression (no statements)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            return {
                "system_text": "",
                "error": "Only a single expression is allowed. "
                         "Use expressions like: len(items) + 1, "
                         "[x * 2 for x in data], etc. "
                         "Assignment and statements are not permitted.",
            }

        expr = tree.body[0].value

        # Allowed builtin names
        safe_builtins = {
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "reversed": reversed,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "slice": slice,
            "open": open,
            "print": print,
            "json": json,
            "re": re,
            "math": math,
            "datetime": datetime,
            "timedelta": timedelta,
        }

        # Provide inputs as a top-level variable
        safe_globals = {
            "__builtins__": safe_builtins,
            "inputs": inputs,
            "context": context.to_dict(),
        }

        result = eval(compile(tree, filename="<workflow>", mode="eval"), safe_globals)

        return {"system_text": str(result) if result is not None else ""}

    async def execute_if_else(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute if-else node."""
        condition = inputs.get("condition", "")

        if not condition:
            return {"system_resultTrue": False, "system_resultFalse": True}

        try:
            # Evaluate condition
            # Support simple conditions like: {{var}} == "value", {{var}} > 10, etc.
            result = self._evaluate_condition(condition, context)

            return {
                "system_resultTrue": result,
                "system_resultFalse": not result,
            }
        except Exception as e:
            return {
                "system_resultTrue": False,
                "system_resultFalse": True,
                "error": str(e),
            }

    def _evaluate_condition(self, condition: str, context: WorkflowContext) -> bool:
        """Evaluate a condition string."""
        # Resolve variable references
        condition = context.resolve_value(condition)

        # If condition is already a boolean, return it
        if isinstance(condition, bool):
            return condition

        # If condition is a string, try to evaluate it
        if isinstance(condition, str):
            # Simple string comparisons
            condition = condition.strip()

            # Check for comparison operators
            if "==" in condition:
                parts = condition.split("==", 1)
                left = parts[0].strip().strip('"\'')
                right = parts[1].strip().strip('"\'')
                return left == right

            if "!=" in condition:
                parts = condition.split("!=", 1)
                left = parts[0].strip().strip('"\'')
                right = parts[1].strip().strip('"\'')
                return left != right

            # Check for truthy values
            return bool(condition) and condition.lower() not in ("false", "0", "", "none", "null")

        # For other types, check truthiness
        return bool(condition)

    async def execute_answer(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute answer node."""
        text = inputs.get("text", "")

        return {
            "answerText": text,
        }

    async def execute_workflow_end(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute workflow end node.

        Supports two return modes:
        1. 'variables' mode: Returns configured output variables with resolved values
        2. 'text' mode: Returns the configured text content
        """
        node_config = node.config or {}
        return_mode = node_config.get("returnMode", "variables")

        if return_mode == "text":
            # Text mode: return the configured text with variable references resolved
            return_text = node_config.get("returnText", "")
            resolved_text = context.resolve_value(return_text) if return_text else ""
            return {
                "finalOutput": resolved_text,
            }

        # Variables mode (default)
        configured_outputs = node_config.get("outputs", [])
        result = {}

        if configured_outputs and isinstance(configured_outputs, list):
            for output_def in configured_outputs:
                if isinstance(output_def, dict):
                    key = output_def.get("name") or output_def.get("key")
                    value_expr = output_def.get("value", "")
                    if key:
                        result[key] = context.resolve_value(value_expr) if value_expr else ""
        else:
            result = {
                "finalOutput": inputs.get("result", ""),
            }

        for key, value in inputs.items():
            if key not in result and key != "result":
                result[key] = value

        return result

    async def execute_classify_question(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute classify question node (placeholder)."""
        content = inputs.get("content", "")
        categories = inputs.get("categories", "")

        # Simple keyword-based classification as placeholder
        category_list = [c.strip() for c in str(categories).split(",") if c.strip()]
        if not category_list:
            category_list = ["其他"]

        # Default to first category
        result = category_list[0]

        # Simple keyword matching
        content_lower = str(content).lower()
        for cat in category_list:
            if cat.lower() in content_lower:
                result = cat
                break

        return {
            "cqResult": result,
        }

    async def execute_content_extract(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute content extract node (placeholder)."""
        content = inputs.get("content", "")
        extract_fields = inputs.get("extractFields", "")

        fields = [f.strip() for f in str(extract_fields).split(",") if f.strip()]
        if not fields:
            fields = ["result"]

        return {
            "fields": {f: f"extracted_{f}" for f in fields},
            "system_text": str(content)[:500],
        }

    async def execute_variable_update(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute variable update node."""
        update_list = inputs.get("updateList", [])

        for item in update_list:
            var_name = item.get("variable")
            value = item.get("value")
            if var_name:
                context.set_variable(var_name, value)

        return {
            "updated": True,
            "variables": context.to_dict()["variables"],
        }

    async def execute_read_files(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute read files node (placeholder)."""
        file_urls = inputs.get("fileUrlList", [])

        if isinstance(file_urls, str):
            file_urls = [file_urls]

        return {
            "fileTitle": [f"Content of {url}" for url in file_urls],
            "fileContent": [f"Placeholder content for {url}" for url in file_urls],
        }

    async def execute_json_serialize(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute JSON serialize node.

        Converts any input value to a JSON string.
        Handles non-serializable types gracefully.
        """
        value = inputs.get("input")

        if value is None:
            return {"output": "null"}

        try:
            result = json.dumps(value, ensure_ascii=False, default=str)
            return {"output": result}
        except (TypeError, ValueError) as e:
            return {"output": "", "error": f"JSON serialization failed: {e}"}

    async def execute_loop(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute loop node.

        Iterates over an input array, executing the sub-workflow (child nodes)
        for each item, and collects all results.

        Config:
            - loopInputArray: the array to iterate over
            - loopMaxIterations: max number of iterations (default 100)
            - loopItemVariable: variable name for each item (default "item")
        """
        loop_input = inputs.get("loopInputArray", [])
        max_iterations = int(inputs.get("loopMaxIterations", 100))

        if isinstance(loop_input, str):
            try:
                loop_input = json.loads(loop_input)
            except json.JSONDecodeError:
                loop_input = [loop_input]

        if not isinstance(loop_input, (list, tuple, range)):
            loop_input = [loop_input]

        loop_input = list(loop_input)[:max_iterations]
        results = []
        engine = getattr(self, "_engine", None)

        # 获取循环体内部的子节点和边
        version_id = context._version_id
        child_nodes = []
        child_edges = []
        if engine and version_id:
            all_nodes = engine._store.list_nodes(version_id)
            all_edges = engine._store.list_edges(version_id)
            child_nodes = [n for n in all_nodes if n.parent_id == node.id]
            child_node_ids = {n.id for n in child_nodes}
            child_edges = [
                e for e in all_edges
                if e.source_node_id in child_node_ids and e.target_node_id in child_node_ids
            ]

        item_var = inputs.get("loopItemVariable", "item")

        for idx, item in enumerate(loop_input):

            if engine and child_nodes:
                try:
                    # 将当前元素和索引注入上下文
                    context.set_variable(item_var, item)
                    context.set_variable("loopIndex", idx)

                    # 构建循环体内部的执行顺序
                    execution_order = self._build_sub_execution_order(child_nodes, child_edges)

                    # 执行循环体内部的子节点
                    iteration_outputs = {}
                    for child_node_id in execution_order:
                        child_node = next((n for n in child_nodes if n.id == child_node_id), None)
                        if not child_node:
                            continue

                        # 解析子节点的输入（使用当前上下文）
                        child_inputs = self._resolve_node_inputs(child_node, context)

                        # 执行子节点
                        child_result = await engine._execute_node(child_node, context, child_edges)

                        # 将子节点输出存入上下文
                        for key, value in child_result.items():
                            context.set_node_output(child_node_id, key, value)

                        iteration_outputs[child_node_id] = child_result

                    # 收集本次迭代的结果：取最后一个执行节点的输出作为迭代结果
                    if execution_order:
                        last_node_id = execution_order[-1]
                        last_result = context.get_node_output(last_node_id, "output") or \
                                      context.get_node_output(last_node_id, "answerText") or \
                                      iteration_outputs.get(last_node_id, {})
                        results.append(last_result if isinstance(last_result, dict) else {"output": last_result})
                    else:
                        results.append({item_var: item})

                except Exception as e:
                    results.append({"error": str(e)})
            else:
                results.append({item_var: item})

        # 清理循环变量
        context._variables.pop(item_var, None)
        context._variables.pop("loopIndex", None)

        result = {
            "loopArray": results,
            "loopCount": len(results),
            "loopItems": loop_input,
            "loopResult": results,
        }

        # 将输入变量也作为循环节点的输出，供下游节点引用
        for key, value in inputs.items():
            if key not in result and not key.startswith("_"):
                result[key] = value

        # 解析用户自定义的输出变量，供下游节点引用
        outputs_config = node.config.get("outputs", [])
        if isinstance(outputs_config, list):
            for output_def in outputs_config:
                name = output_def.get("name")
                value_expr = output_def.get("value")
                if name and value_expr:
                    result[name] = context.resolve_value(value_expr)

        return result

    def _build_sub_execution_order(
        self,
        nodes: list[WorkflowNodeRecord],
        edges: list[WorkflowEdgeRecord],
    ) -> list[str]:
        """Build execution order for sub-workflow inside loop/parallel nodes."""
        from collections import deque

        node_ids = {n.id for n in nodes}
        graph: dict[str, list[str]] = {n.id: [] for n in nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in nodes}

        for edge in edges:
            if edge.source_node_id in node_ids and edge.target_node_id in node_ids:
                graph[edge.source_node_id].append(edge.target_node_id)
                in_degree[edge.target_node_id] += 1

        queue: deque[str] = deque(sorted(
            (n_id for n_id, degree in in_degree.items() if degree == 0),
            key=lambda x: x,
        ))
        result: list[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for neighbor in sorted(graph[node_id]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _resolve_node_inputs(
        self,
        node: WorkflowNodeRecord,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Resolve inputs for a node using the current context."""
        inputs_config = node.config.get("inputs", [])
        inputs: dict[str, Any] = {}

        if isinstance(inputs_config, list):
            for input_item in inputs_config:
                key = input_item.get("name") or input_item.get("key")
                value = input_item.get("value")
                if key is not None:
                    inputs[key] = context.resolve_value(value)
        elif isinstance(inputs_config, dict):
            inputs = context.resolve_inputs(inputs_config)

        return inputs

    async def execute_parallel_run(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute parallel run node.

        Runs multiple items concurrently with a configurable max concurrency.

        Config:
            - loopInputArray: items to process in parallel
            - parallelRunMaxConcurrency: max concurrent tasks (default 5)
        """
        import asyncio

        loop_input = inputs.get("loopInputArray", [])
        max_concurrency = int(inputs.get("parallelRunMaxConcurrency", 5))

        if isinstance(loop_input, str):
            try:
                loop_input = json.loads(loop_input)
            except json.JSONDecodeError:
                loop_input = [loop_input]

        if not isinstance(loop_input, (list, tuple)):
            loop_input = [loop_input]

        engine = getattr(self, "_engine", None)
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_one(idx: int, item: Any) -> dict[str, Any]:
            async with semaphore:
                item_var = inputs.get("parallelItemVariable", "item")
                if engine:
                    try:
                        return await engine._execute_node_internal(
                            node_id=node.id,
                            inputs={**inputs, item_var: item, "parallelIndex": idx},
                            context=context,
                        )
                    except Exception as e:
                        return {"error": str(e)}
                return {item_var: item, "index": idx}

        tasks = [run_one(idx, item) for idx, item in enumerate(loop_input)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successful and failed results
        success_results = []
        full_results = []
        for r in results:
            if isinstance(r, Exception):
                success_results.append({"error": str(r)})
                full_results.append({"error": str(r)})
            else:
                success_results.append(r)
                full_results.append(r)

        return {
            "parallelSuccessResults": success_results,
            "parallelFullResults": full_results,
            "parallelCount": len(full_results),
        }

    async def execute_agent(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute agent node (placeholder)."""
        return {
            "agentResponse": "Agent execution placeholder",
            "toolCalls": [],
        }

    async def execute_sub_workflow(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute sub-workflow node (placeholder)."""
        return {
            "subWorkflowResult": "Sub-workflow execution placeholder",
        }

    async def execute_json_deserialize(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute JSON deserialize node."""
        json_str = inputs.get("jsonStr", "")

        if not json_str:
            return {"output": None, "error": "JSON string is required"}

        try:
            result = json.loads(json_str)
            return {"output": result}
        except json.JSONDecodeError as e:
            return {"output": None, "error": f"JSON parse error: {e}"}
        except Exception as e:
            return {"output": None, "error": str(e)}
