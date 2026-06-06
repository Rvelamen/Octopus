"""Automatic variable binding for workflow nodes.

Provides rule-based auto-binding of node inputs to upstream node outputs,
reducing the manual work users need to do when building workflows.
"""

# ── Hard-coded binding rules for common patterns ──
# Each rule: (source_node_type, source_output_key, target_node_type, target_input_key)
AUTO_BINDING_RULES: list[tuple[str, str, str, str]] = [
    # Start → various consumers
    ("workflowStart", "userChatInput", "llm", "input"),
    ("workflowStart", "userChatInput", "chatNode", "input"),
    ("workflowStart", "userChatInput", "classifyQuestion", "input"),
    ("workflowStart", "userChatInput", "contentExtract", "input"),
    ("workflowStart", "userChatInput", "textEditor", "text"),
    # LLM outputs → downstream chatNodes
    ("llm", "output", "chatNode", "input"),
    ("chatNode", "output", "chatNode", "input"),
    # LLM outputs → downstream
    ("llm", "output", "workflowEnd", "result"),
    ("llm", "output", "ifElseNode", "condition"),
    ("llm", "output", "textEditor", "text"),
    ("llm", "output", "http", "body"),
    ("chatNode", "output", "workflowEnd", "result"),
    ("chatNode", "output", "ifElseNode", "condition"),
    # Classifier → router
    ("classifyQuestion", "cqResult", "ifElseNode", "condition"),
    # Extractor → LLM
    ("contentExtract", "extractResult", "llm", "input"),
    ("contentExtract", "extractResult", "chatNode", "input"),
    # HTTP → downstream
    ("http", "body", "llm", "input"),
    ("http", "body", "chatNode", "input"),
    ("http", "body", "jsonDeserialize", "json"),
    ("httpRequest468", "body", "llm", "input"),
    ("httpRequest468", "body", "chatNode", "input"),
    ("httpRequest468", "body", "jsonDeserialize", "json"),
    # JSON deserialize → downstream
    ("jsonDeserialize", "object", "llm", "input"),
    ("jsonDeserialize", "object", "chatNode", "input"),
    # Text editor → end
    ("textEditor", "result", "workflowEnd", "result"),
    # Code → end
    ("code", "result", "workflowEnd", "result"),
    ("code", "result", "llm", "input"),
    # Read files → downstream
    ("readFiles", "content", "llm", "input"),
    ("readFiles", "content", "chatNode", "input"),
    ("readFiles", "content", "textEditor", "text"),
    # Variable update → end
    ("variableUpdate", "updatedValue", "workflowEnd", "result"),
]

# Type compatibility for loose matching
# downstream_input_type -> acceptable upstream output types
TYPE_COMPATIBILITY: dict[str, list[str]] = {
    "string": ["string", "number", "integer", "boolean"],
    "number": ["number", "integer", "string"],
    "integer": ["integer", "number", "string"],
    "boolean": ["boolean", "string"],
    "object": ["object"],
    "array": ["array"],
    "arrayString": ["arrayString", "array"],
    "arrayNumber": ["arrayNumber", "array"],
    "arrayInteger": ["arrayInteger", "array"],
    "arrayBoolean": ["arrayBoolean", "array"],
    "arrayObject": ["arrayObject", "array"],
    "file": ["file", "arrayFile"],
}


def _get_upstream_nodes(node_id: str, existing_nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Get all nodes that have an edge pointing to the given node."""
    upstream_ids = {e["source"] for e in edges if e["target"] == node_id}
    return [n for n in existing_nodes if n.get("id") in upstream_ids]


def _extract_outputs(node: dict) -> list[dict]:
    """Extract output definitions from a node config."""
    outputs = []
    config = node.get("config", {})
    if isinstance(config, dict):
        # Try 'outputs' key first
        raw_outputs = config.get("outputs", [])
        if raw_outputs:
            for o in raw_outputs:
                if isinstance(o, dict):
                    outputs.append(
                        {
                            "key": o.get("key") or o.get("name") or o.get("id", "output"),
                            "name": o.get("name") or o.get("key") or o.get("id", "output"),
                            "type": o.get("type", "string"),
                            "label": o.get("label", ""),
                            "value": o.get("value", ""),
                        }
                    )
    # Fallback: known default outputs per node type
    if not outputs:
        node_type = node.get("type", "")
        if node_type in ("workflowStart", "start"):
            # workflowStart: inputs ARE outputs (entry point variables).
            # Read from config.inputs first; if empty, config.outputs is legacy fallback.
            inputs_list = _extract_inputs(node)
            if inputs_list:
                outputs = [
                    {
                        "key": i["key"],
                        "name": i["name"],
                        "type": i["type"],
                        "label": i.get("label", ""),
                        "value": i.get("value", ""),
                    }
                    for i in inputs_list
                ]
        elif node_type in ("llm", "chatNode"):
            outputs = [{"key": "output", "name": "output", "type": "string"}]
        elif node_type == "classifyQuestion":
            outputs = [{"key": "cqResult", "name": "cqResult", "type": "string"}]
        elif node_type == "contentExtract":
            outputs = [{"key": "extractResult", "name": "extractResult", "type": "string"}]
        elif node_type in ("http", "httpRequest468"):
            outputs = [
                {"key": "body", "name": "body", "type": "string"},
                {"key": "statusCode", "name": "statusCode", "type": "integer"},
                {"key": "headers", "name": "headers", "type": "object"},
            ]
        elif node_type == "code":
            outputs = [{"key": "result", "name": "result", "type": "string"}]
        elif node_type == "jsonDeserialize":
            outputs = [{"key": "object", "name": "object", "type": "object"}]
        elif node_type == "textEditor":
            outputs = [{"key": "result", "name": "result", "type": "string"}]
        elif node_type == "readFiles":
            outputs = [{"key": "content", "name": "content", "type": "string"}]
        elif node_type == "variableUpdate":
            outputs = [{"key": "updatedValue", "name": "updatedValue", "type": "string"}]
        elif node_type == "workflowEnd":
            outputs = [{"key": "result", "name": "result", "type": "string"}]
    return outputs


def _extract_inputs(node: dict) -> list[dict]:
    """Extract input definitions from a node config."""
    inputs_list = []
    config = node.get("config", {})
    if isinstance(config, dict):
        raw_inputs = config.get("inputs", [])
        if raw_inputs:
            for i in raw_inputs:
                if isinstance(i, dict):
                    inputs_list.append(
                        {
                            "key": i.get("key") or i.get("name") or i.get("id", "input"),
                            "name": i.get("name") or i.get("key") or i.get("id", "input"),
                            "type": i.get("type", "string"),
                            "value": i.get("value", ""),
                            "label": i.get("label", ""),
                        }
                    )
    # Fallback: known default inputs per node type
    if not inputs_list:
        node_type = node.get("type", "")
        if node_type in ("llm", "chatNode"):
            inputs_list = [
                {"key": "input", "name": "input", "type": "string", "value": "", "label": "输入"},
            ]
        elif node_type == "workflowEnd":
            inputs_list = [
                {
                    "key": "result",
                    "name": "result",
                    "type": "string",
                    "value": "",
                    "label": "最终结果",
                }
            ]
        elif node_type == "http":
            inputs_list = [
                {"key": "url", "name": "url", "type": "string", "value": "", "label": "URL"},
                {
                    "key": "method",
                    "name": "method",
                    "type": "string",
                    "value": "GET",
                    "label": "方法",
                },
            ]
    return inputs_list


def _type_matches(downstream_type: str, upstream_type: str) -> bool:
    """Check if upstream output type can feed into downstream input type."""
    if downstream_type == upstream_type:
        return True
    compatible = TYPE_COMPATIBILITY.get(downstream_type, [])
    return upstream_type in compatible


def find_binding_rule(
    source_node_type: str,
    source_output_key: str,
    target_node_type: str,
    target_input_key: str,
) -> tuple[str, str, str, str] | None:
    """Find a matching auto-binding rule."""
    for rule in AUTO_BINDING_RULES:
        if (
            rule[0] == source_node_type
            and rule[1] == source_output_key
            and rule[2] == target_node_type
            and rule[3] == target_input_key
        ):
            return rule
    return None


def auto_bind_variables(
    new_node: dict,
    existing_nodes: list[dict],
    edges: list[dict],
) -> list[tuple[str, str, str]]:
    """
    Auto-bind inputs of `new_node` to upstream outputs based on rules.

    Returns list of (input_key, bound_value, confidence) tuples.
    Confidence is "high" for rule match, "medium" for type-only match.
    """
    bindings: list[tuple[str, str, str]] = []
    node_id = new_node.get("id", "")
    node_type = new_node.get("type", "")

    inputs_list = _extract_inputs(new_node)
    upstream_nodes = _get_upstream_nodes(node_id, existing_nodes, edges)

    for input_def in inputs_list:
        input_key = input_def["key"]
        input_type = input_def.get("type", "string")
        current_value = input_def.get("value", "")

        # Skip if already has a value (AI or user already set it)
        if current_value and current_value not in ("", "{{?}}"):
            continue

        bound = False

        # 1. Try rule-based binding (highest confidence)
        for upstream in upstream_nodes:
            upstream_type = upstream.get("type", "")
            for output in _extract_outputs(upstream):
                rule = find_binding_rule(upstream_type, output["key"], node_type, input_key)
                if rule and _type_matches(input_type, output["type"]):
                    bindings.append(
                        (
                            input_key,
                            f"{{{{{upstream['id']}.{output['key']}}}}}",
                            "high",
                        )
                    )
                    bound = True
                    break
            if bound:
                break

        # 2. Fallback: type-compatible first upstream output (medium confidence)
        if not bound:
            for upstream in upstream_nodes:
                for output in _extract_outputs(upstream):
                    if _type_matches(input_type, output["type"]):
                        bindings.append(
                            (
                                input_key,
                                f"{{{{{upstream['id']}.{output['key']}}}}}",
                                "medium",
                            )
                        )
                        bound = True
                        break
                if bound:
                    break

        # 3. If still not bound, leave as placeholder (AI will handle or user fills in)
        if not bound:
            bindings.append((input_key, "{{?}}", "low"))

    return bindings


def build_variable_context(existing_nodes: list[dict], edges: list[dict]) -> str:
    """Build a markdown variable dictionary for AI system prompt."""
    lines = ["## 当前画布可用变量", ""]

    if not existing_nodes:
        lines.append("（画布为空，尚无节点）")
        return "\n".join(lines)

    for node in existing_nodes:
        node_id = node.get("id", "")
        node_type = node.get("type", "")
        label = node.get("label", node_id)
        outputs = _extract_outputs(node)

        if not outputs:
            continue

        lines.append(f"- {node_id} ({node_type}, 名称: {label}):")
        for o in outputs:
            lines.append(
                f"  - {o['key']} [{o['type']}]" + (f" — {o['label']}" if o.get("label") else "")
            )

    lines.append("")
    lines.append("## 变量引用语法")
    lines.append("使用 {{nodeId.outputKey}} 语法引用上游输出")
    lines.append("示例: {{start-1.userChatInput}}, {{llm-1.output}}")
    lines.append("如果不确定最佳匹配，使用 {{?}} 占位符")

    return "\n".join(lines)
