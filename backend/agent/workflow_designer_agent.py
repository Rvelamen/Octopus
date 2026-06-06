"""Workflow Designer Agent — an AI assistant for creating and modifying workflows.

Built on top of PdfChatAgent patterns but specialized for visual workflow authoring.
"""

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from backend.agent.config_service import AgentConfigService
from backend.agent.loader import SubAgentConfig, SubAgentLoader
from backend.core.config.schema import AgentDefaults, ProviderConfig
from backend.core.providers.factory import create_provider
from backend.data import Database
from backend.data.provider_store import ModelRepository, ProviderRepository
from backend.extensions.loader import SkillsLoader
from backend.services.workflow_design_chat_service import (
    WorkflowDesignChatService,
)
from backend.tools.registry import ToolRegistry
from backend.tools.workflow_designer import (
    WorkflowAddInputTool,
    WorkflowAddNodeTool,
    WorkflowAddOutputTool,
    WorkflowAutoLayoutTool,
    WorkflowConnectNodesTool,
    WorkflowGetNodeIOTool,
    WorkflowGetNodesTool,
    WorkflowGetVariableContextTool,
    WorkflowListDatabaseTablesTool,
    WorkflowRemoveNodeTool,
    WorkflowRemoveVariableTool,
    WorkflowRunTestTool,
    WorkflowSetVariableTool,
    WorkflowUpdateNodeTool,
    WorkflowValidateTool,
    _WorkflowToolBase,
)


class WorkflowDesignerAgent:
    """Independent agent for workflow design with configurable tools, model, and system prompt."""

    def __init__(self, workspace: Path, db: Database | None = None):
        self.workspace = workspace
        self.db = db or Database()
        self.design_service = WorkflowDesignChatService(self.db)
        self._config_service = AgentConfigService(self.db)
        self._skills = SkillsLoader(workspace)
        self._agent_loader = SubAgentLoader(workspace, self.db)

    async def chat(
        self,
        session_id: str,
        workflow_id: str,
        user_content: str,
        selected_nodes: list[dict] | None = None,
        agent_config_id: int | None = None,
        on_token: Callable[[str], Any] | None = None,
        on_tool_start: Callable[[dict], Any] | None = None,
        on_tool_result: Callable[[dict], Any] | None = None,
    ) -> str:
        """Process a user message in a workflow design session.

        Args:
            session_id: The design chat session ID.
            workflow_id: The workflow being designed.
            user_content: User's instruction/message.
            selected_nodes: Optional list of currently selected nodes on canvas.
            on_token: Callback for each streaming token.
            on_tool_start: Callback when a tool call starts.
            on_tool_result: Callback when a tool call completes.

        Returns:
            The full assistant response text.
        """
        session = self.design_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Save user message
        self.design_service.add_message(
            session_id=session_id,
            role="user",
            content=user_content,
        )

        # Load agent config (default to "workflow-designer" role)
        agent_config = self._load_agent_config(agent_config_id)

        # Get provider, model, tools
        provider, model, provider_type, max_tokens, temperature = self._get_provider_for_config(
            agent_config
        )
        tools = self._build_tools_for_config(agent_config)

        # Inject workflow_id into all workflow tools (AI does not need to pass it)
        for tool_name in tools.tool_names:
            tool = tools.get(tool_name)
            if isinstance(tool, _WorkflowToolBase):
                tool.set_workflow_id(workflow_id)

        # Run LLM with tool support
        final_content = ""
        accumulated_reasoning = ""
        iteration = 0
        max_iterations = agent_config.max_iterations if agent_config else 15

        # Build initial messages
        definition = self.design_service.get_workflow_definition(workflow_id)
        canvas_context = self._build_canvas_context(workflow_id, definition)
        system_prompt = self._build_system_prompt(
            agent_config, canvas_context, workflow_id, definition, selected_nodes
        )
        messages = self._build_messages(
            session_id, system_prompt, user_content, workflow_id, selected_nodes
        )

        while iteration < max_iterations:
            iteration += 1
            full_content = ""
            accumulated_reasoning = ""
            tool_calls_buffer: dict[str, dict] = {}

            # Refresh canvas context in system prompt for each iteration
            # so the LLM sees the latest canvas state after tool modifications
            definition = self.design_service.get_workflow_definition(workflow_id)
            canvas_context = self._build_canvas_context(workflow_id, definition)
            system_prompt = self._build_system_prompt(
                agent_config, canvas_context, workflow_id, definition, selected_nodes
            )
            messages[0] = {"role": "system", "content": system_prompt}

            try:
                async for chunk in provider.chat_stream(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ):
                    if chunk.content:
                        full_content += chunk.content
                        if on_token:
                            with contextlib.suppress(Exception):
                                on_token(chunk.content)

                    if chunk.reasoning_content:
                        accumulated_reasoning += chunk.reasoning_content

                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            if tc.id not in tool_calls_buffer:
                                tool_calls_buffer[tc.id] = {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "arguments": tc.arguments,
                                }
                                if on_tool_start:
                                    with contextlib.suppress(Exception):
                                        on_tool_start(
                                            {
                                                "tool": tc.name,
                                                "args": tc.arguments,
                                                "tool_call_id": tc.id,
                                            }
                                        )
                            else:
                                tool_calls_buffer[tc.id]["arguments"].update(tc.arguments)

            except Exception as e:
                logger.error(f"[WorkflowDesignerAgent] LLM call failed: {e}")
                raise

            if tool_calls_buffer:
                tool_calls_list = []
                for tc_data in tool_calls_buffer.values():
                    tool_calls_list.append(
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": json.dumps(tc_data["arguments"], ensure_ascii=False),
                            },
                        }
                    )
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": tool_calls_list,
                }
                if accumulated_reasoning:
                    assistant_msg["reasoning_content"] = accumulated_reasoning
                messages.append(assistant_msg)
                if full_content:
                    final_content = full_content

                # Persist assistant message
                self.design_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content or "",
                    tool_calls=tool_calls_list,
                )
            else:
                if full_content:
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": full_content,
                    }
                    if accumulated_reasoning:
                        assistant_msg["reasoning_content"] = accumulated_reasoning
                    messages.append(assistant_msg)
                    final_content = full_content

                self.design_service.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_content or "",
                )
                break

            # Execute tools and persist results
            for tc_data in tool_calls_buffer.values():
                tool_args = dict(tc_data.get("arguments", {}))
                try:
                    result = await tools.execute(tc_data["name"], tool_args)
                except Exception as e:
                    logger.error(f"[WorkflowDesignerAgent] Tool {tc_data['name']} failed: {e}")
                    result = f"Error: {e}"

                if on_tool_result:
                    with contextlib.suppress(Exception):
                        on_tool_result(
                            {
                                "tool": tc_data["name"],
                                "result": result,
                                "tool_call_id": tc_data["id"],
                            }
                        )

                messages.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tc_data["id"],
                    }
                )

                # Serialize result for metadata storage
                result_for_meta = result
                if not isinstance(result, (str, int, float, bool, list, dict, type(None))):
                    result_for_meta = str(result)

                self.design_service.add_message(
                    session_id=session_id,
                    role="tool",
                    content=str(result),
                    tool_call_id=tc_data["id"],
                    metadata={
                        "tool": tc_data["name"],
                        "args": tc_data["arguments"],
                        "result": result_for_meta,
                    },
                )

        return final_content

    # ── Configuration ──

    def _load_agent_config(self, agent_config_id: int | None = None) -> SubAgentConfig | None:
        """Load agent config. Fallback to default if not found."""
        if agent_config_id:
            from backend.data.subagent_store import SubagentRepository

            repo = SubagentRepository(self.db)
            record = repo.get_subagent_by_id(agent_config_id)
            if record:
                return SubAgentConfig(
                    name=record.name,
                    description=record.description,
                    provider_id=record.provider_id,
                    model_id=record.model_id,
                    tools=record.tools,
                    extensions=record.extensions,
                    max_iterations=record.max_iterations,
                    temperature=record.temperature,
                    system_prompt=record.system_prompt,
                )

        # Try to load "workflow-designer" role from database
        config = self._agent_loader.get("workflow-designer", reload=False)
        if config:
            return config

        # Default fallback
        return SubAgentConfig(
            name="workflow-designer",
            description="Workflow design assistant",
            tools=[
                "add_node",
                "connect_nodes",
                "set_variable",
                "remove_node",
                "update_node",
                "auto_layout",
                "validate_workflow",
                "run_test",
                "get_variable_context",
                "get_node_io",
                "get_nodes",
                "list_database_tables",
                "add_input_variable",
                "add_output_variable",
                "remove_variable",
            ],
            max_iterations=15,
            temperature=0.3,
            system_prompt=self._default_system_prompt(),
        )

    def _get_provider_for_config(self, config: SubAgentConfig | None):
        """Get provider and model for the agent config."""
        defaults = self._config_service._get_agent_defaults_repo().get_or_create_defaults()
        max_tokens = getattr(defaults, "max_tokens", 8192) or 8192
        temperature = getattr(defaults, "temperature", 0.7) or 0.7

        if config and config.provider_id and config.model_id:
            provider_repo = ProviderRepository(self.db)
            model_repo = ModelRepository(self.db)
            provider_record = provider_repo.get_provider_by_id(config.provider_id)
            model_record = model_repo.get_model_by_id(config.model_id)

            if provider_record and model_record:
                provider_config = ProviderConfig(
                    type=provider_record.provider_type,
                    api_key=provider_record.api_key,
                    api_base=provider_record.api_host,
                )
                agent_defaults = AgentDefaults(
                    provider=provider_record.name,
                    model=model_record.model_id,
                    max_tokens=max_tokens,
                    temperature=config.temperature if config else temperature,
                    llm_max_retries=getattr(defaults, "llm_max_retries", 3) or 3,
                    llm_retry_base_delay=getattr(defaults, "llm_retry_base_delay", 1.0) or 1.0,
                    llm_retry_max_delay=getattr(defaults, "llm_max_retry_max_delay", 30.0) or 30.0,
                )
                providers_dict = {provider_record.name: provider_config}
                provider = create_provider(providers_dict, agent_defaults)
                return (
                    provider,
                    model_record.model_id,
                    provider_record.provider_type,
                    max_tokens,
                    config.temperature,
                )

        return self._config_service.get_default_provider_and_model()

    def _build_tools_for_config(self, config: SubAgentConfig | None) -> ToolRegistry:
        """Build tool registry with workflow-specific tools."""
        tools = ToolRegistry()
        db = self.db

        # Workflow-specific tools (injected with workflow_id via closure)
        tool_mapping = {
            "add_node": lambda: WorkflowAddNodeTool(db),
            "connect_nodes": lambda: WorkflowConnectNodesTool(db),
            "set_variable": lambda: WorkflowSetVariableTool(db),
            "add_input_variable": lambda: WorkflowAddInputTool(db),
            "add_output_variable": lambda: WorkflowAddOutputTool(db),
            "remove_variable": lambda: WorkflowRemoveVariableTool(db),
            "get_node_io": lambda: WorkflowGetNodeIOTool(db),
            "get_nodes": lambda: WorkflowGetNodesTool(db),
            "list_database_tables": lambda: WorkflowListDatabaseTablesTool(db),
            "remove_node": lambda: WorkflowRemoveNodeTool(db),
            "update_node": lambda: WorkflowUpdateNodeTool(db),
            "auto_layout": lambda: WorkflowAutoLayoutTool(db),
            "validate_workflow": lambda: WorkflowValidateTool(db),
            "run_test": lambda: WorkflowRunTestTool(db),
            "get_variable_context": lambda: WorkflowGetVariableContextTool(db),
        }

        tool_names = config.tools if config else []
        for tool_name in tool_names:
            tool_name_lower = tool_name.lower()
            if tool_name_lower in tool_mapping:
                try:
                    tool = tool_mapping[tool_name_lower]()
                    tools.register(tool)
                except Exception as e:
                    logger.warning(
                        f"[WorkflowDesignerAgent] Failed to register tool '{tool_name}': {e}"
                    )
            else:
                logger.warning(f"[WorkflowDesignerAgent] Unknown tool '{tool_name}'")

        return tools

    def _build_system_prompt(
        self,
        config: SubAgentConfig | None,
        canvas_context: str,
        workflow_id: str,
        definition: dict,
        selected_nodes: list[dict] | None,
    ) -> str:
        """Build system prompt for the workflow designer agent."""
        base_prompt = config.system_prompt if config else self._default_system_prompt()
        workflow_name = definition.get("name", "未命名")
        node_count = len(definition.get("nodes", []))

        selected_section = ""
        if selected_nodes:
            lines = ["\n\n## 当前选中的节点"]
            for n in selected_nodes:
                lines.append(f"- {n.get('id')} ({n.get('type')}): {n.get('label', '')}")
            selected_section = "\n".join(lines)

        return (
            f"# {config.display_name if config else 'Workflow Design Agent'}\n\n"
            f"{base_prompt}\n\n"
            f"## 当前工作流上下文\n"
            f"- workflow_id: `{workflow_id}`\n"
            f"- 名称: {workflow_name}\n"
            f"- 状态: {'空白画布（请从头创建）' if node_count == 0 else f'已有 {node_count} 个节点'}\n\n"
            f"{canvas_context}{selected_section}\n\n"
            f"## ⚠️ 核心约束\n"
            f"1. **禁止使用 read / write / list / exec 等文件系统工具**\n"
            f"2. **只使用 workflow-designer 专用工具**\n"
            f"3. 如果画布为空，必须从 workflowStart → llm → workflowEnd 开始创建\n"
            f"4. **禁止重复添加已存在的节点** — 每次调用工具前检查画布中是否已有该节点\n"
            f"5. **每次添加/删除/连接/更新节点后，必须先调用 validate_workflow 验证，再调用 auto_layout 整理布局**\n"
            f"6. 修改现有节点配置时，必须使用 update_node，禁止 remove + add_node\n"
            f"7. 如果用户要求修改节点但你不确定当前配置，先用 get_node_io 查看\n"
            f"8. **节点类型选择**: 数据库操作(INSERT/UPDATE/DELETE/QUERY)用 database 节点; HTTP/REST API 调用用 httpRequest468; 大模型推理用 chatNode; 代码执行用 code\n"
            f"9. **配置 database 节点前**，先调用 list_database_tables 查看可用表和字段\n"
            f"10. **你不需要传入 workflow_id，系统会自动处理**"
        )

    def _default_system_prompt(self) -> str:
        from backend.services.workflow.node_registry import NodeRegistry

        registry = NodeRegistry()
        # Build node config guide for key node types
        key_nodes = [
            ("workflowStart", "工作流开始"),
            ("workflowEnd", "工作流结束"),
            ("chatNode", "大模型（LLM）"),
            ("classifyQuestion", "问题分类"),
            ("contentExtract", "内容提取"),
            ("httpRequest468", "HTTP 请求"),
            ("code", "代码执行"),
            ("ifElseNode", "条件分支"),
            ("textEditor", "文本处理"),
            ("database", "数据库"),
            ("loop", "循环"),
            ("answerNode", "直接回复"),
            ("readFiles", "读取文件"),
            ("jsonSerialize", "JSON 序列化"),
            ("jsonDeserialize", "JSON 反序列化"),
            ("variableUpdate", "变量更新"),
            ("parallelRun", "并行执行"),
            ("userSelect", "用户选择"),
            ("formInput", "表单输入"),
        ]
        node_guide_lines = []
        for nt, cn_name in key_nodes:
            info = registry.get(nt)
            if not info:
                continue
            lines = [f"- {nt}（{cn_name}）: {info.description}"]
            # Config schema
            if info.config_schema:
                lines.append("  config 参数:")
                for key, schema in info.config_schema.items():
                    label = schema.get("label", key)
                    desc = schema.get("description", "")
                    default = schema.get("default")
                    options = schema.get("options")
                    parts = [label]
                    if desc:
                        parts.append(desc)
                    if default is not None:
                        parts.append(f"默认: {default}")
                    if options:
                        opts = ", ".join(
                            f"{o.get('value')}={o.get('label', o.get('value'))}" for o in options
                        )
                        parts.append(f"可选: {opts}")
                    lines.append(f"    - {key}: {'; '.join(parts)}")
            # Inputs / outputs
            if info.inputs:
                lines.append("  输入:")
                for inp in info.inputs:
                    lines.append(
                        f"    - {inp.get('key')} ({inp.get('label', '')}) [{inp.get('type', 'string')}]"
                    )
            if info.outputs:
                lines.append("  输出:")
                for out in info.outputs:
                    lines.append(
                        f"    - {out.get('key')} ({out.get('label', '')}) [{out.get('type', 'string')}]"
                    )
            node_guide_lines.append("\n".join(lines))

        node_guide = "\n\n".join(node_guide_lines)

        return (
            "You are a workflow design expert for the Octopus platform.\n\n"
            "Your job is to help users create and modify visual workflows by calling tools.\n\n"
            "## Available Tools\n"
            "- add_node — Add a new node to the canvas\n"
            "- connect_nodes — Connect two nodes with an edge\n"
            "- set_variable — Bind a node's input to an upstream output\n"
            "- remove_node — Remove a node\n"
            "- update_node — Update an existing node's config (prompts, model, URL, code, etc.)\n"
            "- get_node_io — Get detailed input/output definitions for a node\n"
            "- get_nodes — Get all nodes with their full configurations (prompts, URLs, code, etc.)\n"
            "- list_database_tables — List available database tables and their column schemas\n"
            "- add_input_variable — Add a new input slot to a node\n"
            "- add_output_variable — Add a new output slot to a node\n"
            "- remove_variable — Remove an input or output variable from a node\n"
            "- auto_layout — Rearrange nodes neatly\n"
            "- validate_workflow — Check for structural errors\n"
            "- run_test — Execute the workflow in test mode\n"
            "- get_variable_context — List all available variables\n\n"
            "## Node Types & Configuration Guide\n"
            "When calling add_node, use these exact node_type values and config parameters:\n\n"
            f"{node_guide}\n\n"
            "## Design Rules\n"
            "1. Every workflow MUST have a workflowStart and workflowEnd node\n"
            '2. Use Chinese node names (e.g. "智能回复", "问题分类")\n'
            "3. Prefer linear structures; use branches only when necessary\n"
            "4. After adding nodes, auto-bind variables and run validate_workflow\n"
            "5. If validate finds errors, fix them before reporting success\n"
            "6. Use auto_layout after making structural changes\n"
            "7. When modifying an existing node (changing prompts, model, URL, code, etc.), use update_node — do NOT remove and re-add\n"
            "8. Before modifying a node, you may call get_node_io to inspect its current inputs/outputs\n"
            "9. After any add, remove, connect, or update operation, call validate_workflow, then auto_layout\n"
            "10. **Node type selection**: database operations (INSERT/UPDATE/DELETE/QUERY) MUST use the 'database' node; HTTP/REST API calls MUST use 'httpRequest468'; LLM inference MUST use 'chatNode'; code execution MUST use 'code'\n"
            "11. **Before configuring a database node**, call list_database_tables to see available tables and columns. Then use the exact table name and column names in fieldMappings.\n"
            '12. **database node config format**: fieldMappings MUST be an array of objects: [{"name":"column","value":"{{nodeId.output}}"}]. Do NOT put column names as top-level config keys.\n\n'
            "## Variable Binding\n"
            "- Syntax: {{nodeId.outputKey}}\n"
            "- Example: {{workflowStart-1.input}}, {{chatNode-1.answerText}}\n"
            "- If unsure, the system will auto-bind common patterns\n"
            "- For uncertain bindings, use {{?}} placeholder\n\n"
            "## Response Style\n"
            "1. Explain your design plan in natural language first\n"
            "2. Then call the necessary tools\n"
            "3. Report the final result to the user"
        )

    def _build_messages(
        self,
        session_id: str,
        system_prompt: str,
        user_content: str,
        workflow_id: str,
        selected_nodes: list[dict] | None,
    ) -> list[dict[str, Any]]:
        """Build message list for LLM call, restoring full tool call context."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Load history
        history = self.design_service.list_messages(session_id)
        # Exclude the last user message (just added)
        for msg in history[:-1]:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            messages.append(entry)

        # Build current user message with context
        context_parts = []
        context_parts.append(f"当前工作流ID: {workflow_id}")
        if selected_nodes:
            context_parts.append(f"选中节点: {', '.join(n.get('id', '') for n in selected_nodes)}")

        full_content = "\n\n".join(context_parts) + f"\n\n用户指令: {user_content}"

        messages.append({"role": "user", "content": full_content})
        return messages

    def _extract_node_key_config(self, node: dict) -> list[str]:
        """Extract human-readable key configuration for a node based on its type."""
        config = node.get("config", {}) if isinstance(node.get("config"), dict) else {}
        node_type = node.get("type", "")
        items: list[str] = []

        def _trunc(val: Any, max_len: int = 60) -> str:
            s = str(val) if val is not None else ""
            return s if len(s) <= max_len else s[:max_len] + "..."

        if node_type in ("chatNode", "llm"):
            if config.get("providerId"):
                items.append(f"provider={config['providerId']}")
            if config.get("modelId"):
                items.append(f"model={config['modelId']}")
            if config.get("systemPrompt"):
                items.append(f"systemPrompt=({_trunc(config['systemPrompt'])})")
            if config.get("userPrompt"):
                items.append(f"userPrompt=({_trunc(config['userPrompt'])})")
            if config.get("temperature") is not None:
                items.append(f"temperature={config['temperature']}")
            if config.get("maxToken"):
                items.append(f"maxToken={config['maxToken']}")

        elif node_type == "httpRequest468":
            if config.get("system_httpReqUrl"):
                items.append(f"url={_trunc(config['system_httpReqUrl'])}")
            if config.get("system_httpMethod"):
                items.append(f"method={config['system_httpMethod']}")
            if config.get("system_httpReqHeader"):
                items.append("hasHeader=True")
            if config.get("system_httpReqBody"):
                items.append("hasBody=True")

        elif node_type == "code":
            if config.get("code"):
                items.append(f"code=({_trunc(config['code'], 40)})")
            if config.get("codeType"):
                items.append(f"lang={config['codeType']}")

        elif node_type == "ifElseNode":
            if config.get("system_ifelse"):
                items.append(f"condition=({_trunc(config['system_ifelse'])})")

        elif node_type == "textEditor":
            if config.get("system_text"):
                items.append(f"text=({_trunc(config['system_text'])})")

        elif node_type == "database":
            if config.get("tableName"):
                items.append(f"table={config['tableName']}")
            if config.get("operation"):
                items.append(f"op={config['operation']}")
            fm = config.get("fieldMappings", [])
            if fm:
                items.append(f"fields={len(fm)}项")
            if config.get("whereCondition"):
                items.append(f"where=({_trunc(config['whereCondition'])})")
            if config.get("orderBy"):
                items.append(f"order={_trunc(config['orderBy'])}")

        elif node_type == "classifyQuestion":
            if config.get("system_classify"):
                items.append(f"classify=({_trunc(config['system_classify'])})")

        elif node_type == "contentExtract":
            if config.get("system_content"):
                items.append(f"extract=({_trunc(config['system_content'])})")

        elif node_type == "answerNode":
            if config.get("text"):
                items.append(f"text=({_trunc(config['text'])})")
            if config.get("delaySeconds") is not None:
                items.append(f"delay={config['delaySeconds']}s")

        elif node_type == "readFiles":
            if config.get("encoding"):
                items.append(f"encoding={config['encoding']}")
            if config.get("concatContent") is not None:
                items.append(f"concat={config['concatContent']}")
            if config.get("maxFileSize"):
                items.append(f"maxSize={config['maxFileSize']}MB")

        elif node_type == "jsonSerialize":
            if config.get("input"):
                items.append(f"inputRef={_trunc(config['input'])}")

        elif node_type == "jsonDeserialize":
            if config.get("jsonStr"):
                items.append(f"jsonStr={_trunc(config['jsonStr'])}")

        elif node_type == "variableUpdate":
            if config.get("updateList"):
                items.append(f"updates={len(config['updateList'])}项")

        elif node_type == "loop":
            if config.get("maxIterations"):
                items.append(f"maxIter={config['maxIterations']}")
            if config.get("continueOnError") is not None:
                items.append(f"continueOnError={config['continueOnError']}")

        elif node_type == "parallelRun":
            if config.get("parallelRunMaxConcurrency"):
                items.append(f"concurrency={config['parallelRunMaxConcurrency']}")
            if config.get("continueOnError") is not None:
                items.append(f"continueOnError={config['continueOnError']}")

        elif node_type == "userSelect":
            if config.get("allowMultiSelect") is not None:
                items.append(f"multiSelect={config['allowMultiSelect']}")
            if config.get("timeout"):
                items.append(f"timeout={config['timeout']}s")

        elif node_type == "formInput":
            if config.get("allowSkip") is not None:
                items.append(f"allowSkip={config['allowSkip']}")
            if config.get("timeout"):
                items.append(f"timeout={config['timeout']}s")
            if config.get("submitText"):
                items.append(f"submitBtn={config['submitText']}")

        elif node_type == "workflowStart":
            start_inputs = config.get("inputs", [])
            if start_inputs:
                items.append(f"inputs={', '.join(i.get('key', '') for i in start_inputs)}")

        elif node_type == "workflowEnd":
            if config.get("returnMode"):
                items.append(f"returnMode={config['returnMode']}")
            if config.get("returnText"):
                items.append(f"returnText=({_trunc(config['returnText'])})")

        # Generic: show any other non-system, non-input/output config keys
        for k, v in config.items():
            if k in (
                "inputs",
                "outputs",
                "name",
                "intro",
                "showTargetHandle",
                "showSourceHandle",
                "forbidDelete",
                "avatar",
                "colorSchema",
            ):
                continue
            if k.startswith("system_") and k not in (
                "systemPrompt",
                "userPrompt",
                "system_httpReqUrl",
                "system_httpMethod",
                "system_httpReqHeader",
                "system_httpReqBody",
                "system_code",
                "system_codeLanguage",
                "system_ifelse",
                "system_text",
                "system_database",
                "system_databaseSql",
                "system_classify",
                "system_content",
            ):
                items.append(f"{k}={_trunc(v)}")

        return items

    def _build_canvas_context(self, workflow_id: str, definition: dict | None = None) -> str:
        """Build canvas context from current workflow definition."""
        if definition is None:
            definition = self.design_service.get_workflow_definition(workflow_id)
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])

        if not nodes:
            return "## 当前画布\n（画布为空，请从头开始设计）"

        lines = ["## 当前画布", ""]
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("label", node_id)
            config = node.get("config", {})
            inputs = config.get("inputs", []) if isinstance(config, dict) else []
            outputs = config.get("outputs", []) if isinstance(config, dict) else []

            lines.append(f"- {node_id} ({node_type}, 名称: {label})")
            if outputs:
                lines.append(
                    f"  输出: {', '.join(o.get('key', '') + '[' + o.get('type', 'string') + ']' for o in outputs)}"
                )
            if inputs:
                bound = [
                    f"{i.get('key', '')}={i.get('value', '')}" for i in inputs if i.get("value")
                ]
                if bound:
                    lines.append(f"  输入绑定: {', '.join(bound)}")
            # 关键配置
            key_cfg = self._extract_node_key_config(node)
            if key_cfg:
                lines.append(f"  配置: {', '.join(key_cfg)}")

        lines.append("")
        lines.append("## 连线")
        for edge in edges:
            lines.append(f"- {edge.get('source')} → {edge.get('target')}")

        return "\n".join(lines)
