"""Node executor implementations."""

from __future__ import annotations

import ast
import contextlib
import json
import re
from typing import Any

import httpx

from backend.data.db_store import DBRepository
from backend.services.workflow.engine.context import WorkflowContext
from backend.services.workflow.models import WorkflowEdgeRecord, WorkflowNodeRecord


class NodeExecutor:
    """Executor for workflow nodes.

    Args:
        engine: Optional WorkflowEngine instance for sub-workflow execution
                (loop/parallel nodes). Enables recursive node execution.
    """

    def __init__(self, engine: Any | None = None):
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
                key = (
                    (input_def.get("name") or input_def.get("key"))
                    if isinstance(input_def, dict)
                    else input_def
                )
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

        # Fallback: only when userPrompt is truly empty, use input variable values as the message.
        # If userPrompt contains unresolved {{xxx}} placeholders, keep them as-is and let the LLM see the literal text.
        # Do NOT auto-correct user-written templates.
        if not user_message and inputs:
            input_values = [
                str(v)
                for v in inputs.values()
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
                with contextlib.suppress(json.JSONDecodeError):
                    json_body = json.loads(body)

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

    _SAFE_IMPORT_MODULES = {
        "math",
        "json",
        "re",
        "datetime",
        "random",
        "collections",
        "itertools",
        "statistics",
        "hashlib",
        "base64",
        "urllib",
        "time",
        "string",
        "copy",
        "functools",
        "decimal",
        "fractions",
        "numbers",
        "typing",
        "inspect",
        "textwrap",
        "html",
        "uuid",
        "pathlib",
        "dataclasses",
        "enum",
    }

    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Restricted __import__ for sandboxed Python execution."""
        top = name.split(".")[0]
        if top not in self._SAFE_IMPORT_MODULES:
            raise ImportError(f"Import of module '{name}' is not allowed in sandboxed execution")
        return __import__(name, globals, locals, fromlist, level)

    async def execute_code(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute Python code in a restricted environment using AST analysis.

        Supports multi-line Python code including imports, assignments, function
        definitions, and control flow. Results are captured via the `ret` or
        `result` variable, or by returning a dict from a `main()` function.

        Supported builtins: len, range, enumerate, zip, map, filter, sum, min,
        max, abs, round, sorted, reversed, str, int, float, bool, list, dict,
        set, tuple, slice, open, print, json, re, math, datetime, timedelta.
        Allowed imports: math, json, re, datetime, random, collections, itertools,
        statistics, hashlib, base64, urllib, time, string, copy, functools,
        decimal, fractions, numbers, typing, inspect, textwrap, html, uuid,
        pathlib, dataclasses, enum.
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
        """Execute Python code safely in a restricted environment.

        Supports multi-line Python code including function definitions,
        assignments, and control flow statements.
        The code can access inputs via the `params` variable and should
        return results via the `ret` variable.
        """
        import math
        from datetime import datetime, timedelta

        # Parse the code into an AST
        try:
            tree = ast.parse(code.strip())
        except SyntaxError as e:
            return {"system_text": "", "error": f"Syntax error: {e}"}

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
            "__import__": self._safe_import,
        }

        # Provide inputs as a top-level variable named `params`
        # Use the same dict for globals and locals so that imported modules
        # and function definitions are visible to each other within the sandbox.
        safe_globals = {
            "__builtins__": safe_builtins,
            "params": inputs,
            "context": context.to_dict(),
        }
        safe_locals = safe_globals

        try:
            exec(compile(tree, filename="<workflow>", mode="exec"), safe_globals, safe_locals)
        except Exception as e:
            return {"system_text": "", "error": str(e)}

        # If user defined a main() function, call it automatically
        main_func = safe_locals.get("main")
        if callable(main_func):
            try:
                import inspect

                sig = inspect.signature(main_func)
                param_count = len(sig.parameters)
                ret = main_func() if param_count == 0 else main_func(inputs)
                if ret is not None:
                    return {
                        "system_text": "",
                        **(ret if isinstance(ret, dict) else {"result": ret}),
                    }
            except Exception as e:
                return {"system_text": "", "error": str(e)}

        # Capture the `ret` variable if defined (preferred)
        ret = safe_locals.get("ret")
        if ret is not None:
            return {"system_text": "", **(ret if isinstance(ret, dict) else {"result": ret})}

        # Also capture `result` variable (common user convention)
        result = safe_locals.get("result")
        if result is not None:
            return {
                "system_text": "",
                **(result if isinstance(result, dict) else {"result": result}),
            }

        # Fallback: return the last evaluated expression or empty result
        return {"system_text": ""}

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
                left = parts[0].strip().strip("\"'")
                right = parts[1].strip().strip("\"'")
                return left == right

            if "!=" in condition:
                parts = condition.split("!=", 1)
                left = parts[0].strip().strip("\"'")
                right = parts[1].strip().strip("\"'")
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
        """Execute read files node.

        Downloads content from multiple URLs.
        Supports:
        - Multi-line URL string (split by newline)
        - Array of URLs
        - Configurable encoding, max file size, content concatenation
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        file_urls_raw = inputs.get("fileUrlList", "")
        encoding = inputs.get("encoding", "utf-8")
        max_file_size_mb = float(inputs.get("maxFileSize", 10))
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        concat_content = bool(inputs.get("concatContent", True))
        separator = inputs.get("separator", "\n\n--- 文件分隔 ---\n\n")

        # Parse URLs from multi-line string or array
        file_urls: list[str] = []
        if isinstance(file_urls_raw, str):
            file_urls = [u.strip() for u in file_urls_raw.split("\n") if u.strip()]
        elif isinstance(file_urls_raw, list):
            file_urls = [str(u).strip() for u in file_urls_raw if str(u).strip()]

        if not file_urls:
            return {
                "fileTitle": [],
                "fileContent": [],
                "error": "没有提供文件 URL",
            }

        results: list[dict[str, Any]] = []

        async def fetch_url(url: str) -> dict[str, Any]:
            """Download content from a single URL."""
            try:
                async with httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True,
                    max_redirects=5,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                    content_bytes = response.content
                    if len(content_bytes) > max_file_size_bytes:
                        return {
                            "url": url,
                            "title": url,
                            "content": "",
                            "error": f"文件大小超过限制 ({max_file_size_mb} MB)",
                            "size": len(content_bytes),
                        }

                    # Decode content
                    text = ""
                    if encoding == "auto":
                        # Try common encodings
                        for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
                            try:
                                text = content_bytes.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            text = content_bytes.decode("utf-8", errors="replace")
                    else:
                        try:
                            text = content_bytes.decode(encoding)
                        except UnicodeDecodeError:
                            text = content_bytes.decode("utf-8", errors="replace")

                    return {
                        "url": url,
                        "title": url,
                        "content": text,
                        "size": len(content_bytes),
                        "status_code": response.status_code,
                    }
            except httpx.TimeoutException:
                return {"url": url, "title": url, "content": "", "error": "下载超时"}
            except httpx.HTTPStatusError as e:
                return {
                    "url": url,
                    "title": url,
                    "content": "",
                    "error": f"HTTP {e.response.status_code}",
                }
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                return {"url": url, "title": url, "content": "", "error": str(e)}

        # Fetch all URLs concurrently
        fetch_tasks = [fetch_url(url) for url in file_urls]
        results = await asyncio.gather(*fetch_tasks)

        # Separate successes and failures
        successes = [r for r in results if not r.get("error")]
        failures = [r for r in results if r.get("error")]

        if concat_content:
            # Return concatenated content
            contents = [r["content"] for r in successes]
            titles = [r["title"] for r in successes]
            combined = separator.join(contents) if contents else ""
            return {
                "fileTitle": titles,
                "fileContent": combined,
                "fileCount": len(successes),
                "totalCount": len(file_urls),
                "failedUrls": [r["url"] for r in failures],
                "errors": [r["error"] for r in failures] if failures else None,
            }
        else:
            # Return array of contents
            return {
                "fileTitle": [r["title"] for r in successes],
                "fileContent": [r["content"] for r in successes],
                "fileCount": len(successes),
                "totalCount": len(file_urls),
                "failedUrls": [r["url"] for r in failures],
                "errors": [r["error"] for r in failures] if failures else None,
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
                e
                for e in all_edges
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
                        self._resolve_node_inputs(child_node, context)

                        # 执行子节点
                        child_result = await engine._execute_node(child_node, context, child_edges)

                        # 将子节点输出存入上下文
                        for key, value in child_result.items():
                            context.set_node_output(child_node_id, key, value)

                        iteration_outputs[child_node_id] = child_result

                    # 收集本次迭代的结果：取最后一个执行节点的输出作为迭代结果
                    if execution_order:
                        last_node_id = execution_order[-1]
                        last_result = (
                            context.get_node_output(last_node_id, "output")
                            or context.get_node_output(last_node_id, "answerText")
                            or iteration_outputs.get(last_node_id, {})
                        )
                        results.append(
                            last_result
                            if isinstance(last_result, dict)
                            else {"output": last_result}
                        )
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

        queue: deque[str] = deque(
            sorted(
                (n_id for n_id, degree in in_degree.items() if degree == 0),
                key=lambda x: x,
            )
        )
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

    async def execute_database(
        self,
        node: WorkflowNodeRecord,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute database operation node.

        Supports INSERT, UPDATE, DELETE, and QUERY operations on user-defined tables.
        """
        import logging

        from backend.data.db_store import DBRepository

        logger = logging.getLogger(__name__)

        # Primary: read from inputs; fallback: read directly from node.config
        node_config = node.config or {}
        table_name_raw = inputs.get("tableName") or node_config.get("tableName", "")
        operation = inputs.get("operation") or node_config.get("operation", "QUERY")
        field_mappings = inputs.get("fieldMappings") or node_config.get("fieldMappings", [])
        where_condition = inputs.get("whereCondition") or node_config.get("whereCondition", "")
        order_by = inputs.get("orderBy") or node_config.get("orderBy", "")
        limit_val = inputs.get("limit") or node_config.get("limit", 100)
        limit = int(limit_val) if limit_val is not None else 100

        logger.info(f"[DatabaseNode] inputs keys: {list(inputs.keys())}")
        logger.info(f"[DatabaseNode] tableName: {table_name_raw}")
        logger.info(f"[DatabaseNode] operation: {operation}")
        logger.info(f"[DatabaseNode] field_mappings: {field_mappings}")
        logger.info(
            f"[DatabaseNode] node.config keys: {list(node.config.keys()) if node.config else []}"
        )

        # Resolve table name (may contain variable references)
        table_name = context.resolve_value(table_name_raw)
        if not table_name:
            return {
                "result": None,
                "system_text": "",
                "error": "Table name is required",
                "_debug_inputs_keys": list(inputs.keys()),
                "_debug_config_keys": list(node.config.keys()) if node.config else [],
            }

        # Get database instance from engine
        engine = getattr(self, "_engine", None)
        if not engine:
            return {
                "result": None,
                "system_text": "",
                "error": "Engine not available",
                "_debug_inputs_keys": list(inputs.keys()),
            }

        db = getattr(engine, "_db", None)
        if not db:
            return {
                "result": None,
                "system_text": "",
                "error": "Database not available",
                "_debug_inputs_keys": list(inputs.keys()),
            }

        repo = DBRepository(db)

        # Check if table exists
        table = repo.get_table(table_name)
        if not table:
            return {
                "result": None,
                "system_text": "",
                "error": f"Table '{table_name}' not found",
                "_debug_inputs_keys": list(inputs.keys()),
            }

        try:
            if operation == "INSERT":
                return await self._execute_db_insert(repo, table_name, field_mappings, context)
            elif operation == "UPDATE":
                return await self._execute_db_update(
                    repo, table_name, field_mappings, where_condition, context
                )
            elif operation == "DELETE":
                return await self._execute_db_delete(repo, table_name, where_condition, context)
            elif operation == "QUERY":
                return await self._execute_db_query(
                    repo, table_name, where_condition, order_by, limit, context
                )
            else:
                return {
                    "result": None,
                    "system_text": "",
                    "error": f"Unsupported operation: {operation}",
                    "_debug_inputs_keys": list(inputs.keys()),
                }
        except Exception as e:
            return {
                "result": None,
                "system_text": "",
                "error": str(e),
                "_debug_inputs_keys": list(inputs.keys()),
            }

    def _resolve_db_field_value(
        self, field_value: str, field_name: str, context: WorkflowContext
    ) -> Any:
        """Resolve a field value, returning error if {{...}} ref remains unresolved."""
        import re

        resolved = context.resolve_value(field_value)
        # If the resolved value still contains {{...}}, the upstream node output is missing
        if isinstance(resolved, str) and re.search(r"\{\{(.+?)\}\}", resolved):
            # Try to extract the referenced node ID for a clearer error message
            match = re.search(r"\{\{([^}]+)\}\}", resolved)
            ref = match.group(1) if match else resolved
            raise ValueError(
                f"Field '{field_name}' references unresolved variable '{{{{{ref}}}}}'. "
                f"Make sure the upstream node has executed successfully and produced the required output."
            )
        return resolved

    async def _execute_db_insert(
        self,
        repo: DBRepository,
        table_name: str,
        field_mappings: list,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute INSERT operation."""
        import logging

        logger = logging.getLogger(__name__)
        data = {}
        logger.info(f"[DB_INSERT] field_mappings count: {len(field_mappings)}")
        for idx, mapping in enumerate(field_mappings):
            if isinstance(mapping, dict):
                field_name = mapping.get("name", "")
                field_value = mapping.get("value", "")
                logger.info(f"[DB_INSERT] mapping[{idx}]: name={field_name}, value={field_value}")
                if field_name:
                    try:
                        resolved = self._resolve_db_field_value(field_value, field_name, context)
                        data[field_name] = resolved
                        logger.info(f"[DB_INSERT] resolved: {field_name} = {resolved}")
                    except ValueError as e:
                        return {
                            "result": None,
                            "system_text": "",
                            "error": str(e),
                        }
            else:
                logger.warning(f"[DB_INSERT] mapping[{idx}] is not dict: {type(mapping)}")

        logger.info(f"[DB_INSERT] final data: {data}")
        table = repo.get_table(table_name)
        fields = []
        if table:
            fields = json.loads(table.fields_json or "[]")

        record = repo.create_record(table_name, data, fields)
        logger.info(f"[DB_INSERT] created record: id={record.id}, data={record.record_data}")
        return {
            "result": {"id": record.id, "data": record.record_data},
            "system_text": f"Inserted record #{record.id} into {table_name}",
        }

    async def _execute_db_update(
        self,
        repo: DBRepository,
        table_name: str,
        field_mappings: list,
        where_condition: str,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute UPDATE operation."""
        records = self._filter_db_records(repo, table_name, where_condition, context)
        updated = []
        for rec in records:
            data = {}
            for mapping in field_mappings:
                if isinstance(mapping, dict):
                    field_name = mapping.get("name", "")
                    field_value = mapping.get("value", "")
                    if field_name:
                        try:
                            data[field_name] = self._resolve_db_field_value(
                                field_value, field_name, context
                            )
                        except ValueError as e:
                            return {
                                "result": None,
                                "system_text": "",
                                "error": str(e),
                            }

            new_data = {**rec.record_data, **data}
            updated_record = repo.update_record(rec.id, new_data)
            if updated_record:
                updated.append({"id": updated_record.id, "data": updated_record.record_data})

        return {
            "result": {"updated": updated, "count": len(updated)},
            "system_text": f"Updated {len(updated)} records in {table_name}",
        }

    async def _execute_db_delete(
        self,
        repo: DBRepository,
        table_name: str,
        where_condition: str,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute DELETE operation."""
        records = self._filter_db_records(repo, table_name, where_condition, context)
        deleted_ids = []
        for rec in records:
            repo.delete_record(rec.id)
            deleted_ids.append(rec.id)

        return {
            "result": {"deleted_ids": deleted_ids, "count": len(deleted_ids)},
            "system_text": f"Deleted {len(deleted_ids)} records from {table_name}",
        }

    async def _execute_db_query(
        self,
        repo: DBRepository,
        table_name: str,
        where_condition: str,
        order_by: str,
        limit: int,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Execute QUERY operation."""
        result = repo.list_records(table_name, page=1, page_size=10000)
        records = result.get("records", [])

        # Apply WHERE filter
        if where_condition:
            conditions = self._parse_where_condition(where_condition, context)
            records = [r for r in records if self._match_db_record(r, conditions)]

        # Apply ORDER BY
        if order_by:
            records = self._sort_db_records(records, order_by)

        # Apply LIMIT
        records = records[:limit]

        record_data = [r.record_data for r in records]
        return {
            "result": {"records": record_data, "total": len(record_data)},
            "system_text": f"Queried {len(record_data)} records from {table_name}",
        }

    def _filter_db_records(
        self,
        repo: DBRepository,
        table_name: str,
        where_condition: str,
        context: WorkflowContext,
    ) -> list:
        """Get records matching WHERE condition."""
        if not where_condition:
            # No condition = match all
            result = repo.list_records(table_name, page=1, page_size=10000)
            return result.get("records", [])

        conditions = self._parse_where_condition(where_condition, context)
        result = repo.list_records(table_name, page=1, page_size=10000)
        records = result.get("records", [])
        return [r for r in records if self._match_db_record(r, conditions)]

    def _parse_where_condition(self, condition: str, context: WorkflowContext) -> dict:
        """Parse simple WHERE condition into key-value pairs.

        Supports:
            - key = "value"
            - key = 'value'
            - key = number
            - key = {{variable}}
        Multiple conditions joined by AND (case-insensitive).
        """
        if not condition:
            return {}

        # Resolve variable references first
        condition = context.resolve_value(condition)

        conditions = {}
        # Split by AND (case-insensitive)
        parts = re.split(r"\s+(?i:AND)\s+", condition)
        for part in parts:
            part = part.strip()
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                continue

            # Remove quotes
            if len(value) >= 2:
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                else:
                    # Try to parse as number
                    with contextlib.suppress(ValueError, TypeError):
                        value = float(value) if "." in value else int(value)

            conditions[key] = value

        return conditions

    def _match_db_record(self, record, conditions: dict) -> bool:
        """Check if a record matches all conditions."""
        data = record.record_data
        for key, expected in conditions.items():
            actual = data.get(key)
            # Loose comparison for numbers
            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                if actual != expected:
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    def _sort_db_records(self, records: list, order_by: str) -> list:
        """Sort records by order_by clause.

        Format: field ASC or field DESC
        """
        order_by = order_by.strip()
        if not order_by:
            return records

        parts = order_by.split()
        field = parts[0]
        reverse = len(parts) > 1 and parts[1].upper() == "DESC"

        def sort_key(r):
            val = r.record_data.get(field)
            if val is None:
                return ""
            return val

        return sorted(records, key=sort_key, reverse=reverse)
