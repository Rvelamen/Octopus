"""Workflow node registry.

Manages available node types and their configurations.
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from dataclasses import dataclass, field


# 配置 Schema 类型枚举
class ConfigSchemaType:
    INPUT = "input"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SLIDER = "slider"
    SWITCH = "switch"
    SELECT = "select"
    MULTIPLE_SELECT = "multipleSelect"
    JSON_EDITOR = "JSONEditor"
    SELECT_LLM_MODEL = "selectLLMModel"
    SELECT_DATASET = "selectDataset"
    REFERENCE = "reference"
    CUSTOM = "custom"


@dataclass
class NodeTypeInfo:
    """Node type information."""
    type: str
    name: str
    description: str
    category: str
    icon: str = ""
    color: str = "blue"
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    executor: Optional[Callable] = None


class NodeRegistry:
    """Registry for workflow node types."""

    _instance: Optional[NodeRegistry] = None
    _nodes: dict[str, NodeTypeInfo]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._nodes = {}
            cls._instance._register_default_nodes()
        return cls._instance

    def _register_default_nodes(self):
        """Register default node types."""
        # System nodes
        self.register(NodeTypeInfo(
            type="workflowStart",
            name="工作流开始",
            description="接收用户输入，启动工作流",
            category="基础节点",
            icon="🚀",
            color="blue",
            config_schema={
                "inputs": {
                    "type": "custom",
                    "label": "输入变量",
                    "description": "定义工作流的入口参数",
                    "default": [
                        {"key": "input", "label": "input", "type": "string", "required": False},
                    ],
                },
            },
            outputs=[],  # Outputs are dynamically determined by configured inputs
        ))

        self.register(NodeTypeInfo(
            type="answerNode",
            name="直接回复",
            description="直接回复指定内容",
            category="基础节点",
            icon="💬",
            color="green",
            inputs=[
                {"key": "text", "label": "回复内容", "type": "string", "required": True},
            ],
            config_schema={
                "text": {
                    "type": "textarea",
                    "label": "回复内容",
                    "required": True,
                    "placeholder": "输入要回复的固定内容...",
                    "rows": 4,
                    "maxLength": 4000,
                },
                "delaySeconds": {
                    "type": "number",
                    "label": "延迟回复（秒）",
                    "description": "回复前的延迟时间，用于模拟打字效果",
                    "min": 0,
                    "max": 60,
                    "default": 0,
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="jsonDeserialize",
            name="JSON 反序列化",
            description="用于把 JSON 字符串转化为变量",
            category="工具节点",
            icon="🧩",
            color="indigo",
            inputs=[
                {"key": "jsonStr", "label": "JSON 字符串", "type": "string", "required": True},
            ],
            outputs=[
                {"key": "output", "label": "输出", "type": "any"},
            ],
            config_schema={
                "jsonStr": {
                    "type": "reference",
                    "label": "JSON 字符串",
                    "required": True,
                    "description": "输入或引用 JSON 字符串",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="workflowEnd",
            name="工作流结束",
            description="终止工作流并输出最终结果",
            category="基础节点",
            icon="🔚",
            color="red",
            config_schema={
                "returnMode": {
                    "type": "select",
                    "label": "返回模式",
                    "options": [
                        {"value": "variables", "label": "返回变量"},
                        {"value": "text", "label": "返回文本"},
                    ],
                    "default": "variables",
                },
                "outputs": {
                    "type": "custom",
                    "label": "输出变量",
                    "description": "定义工作流的输出结果变量",
                    "default": [
                        {"key": "type", "label": "type", "type": "string", "value": ""},
                        {"key": "url", "label": "url", "type": "string", "value": ""},
                    ],
                },
                "returnText": {
                    "type": "textarea",
                    "label": "返回文本",
                    "description": "要返回的文本内容，支持变量引用",
                    "placeholder": "输入要返回的文本...",
                    "rows": 4,
                },
            },
            inputs=[],  # Inputs are dynamically determined by configured output values
        ))

        # AI nodes - 大模型节点（带完整 Schema）
        self.register(NodeTypeInfo(
            type="chatNode",
            name="大模型",
            description="与大语言模型进行对话",
            category="AI 节点",
            icon="🤖",
            color="purple",
            inputs=[
                {"key": "model", "label": "模型", "type": "string", "required": True},
                {"key": "systemPrompt", "label": "系统提示词", "type": "string"},
                {"key": "temperature", "label": "温度", "type": "number", "default": 0.7},
                {"key": "maxToken", "label": "最大 Token", "type": "number", "default": 2000},
            ],
            outputs=[
                {"key": "answerText", "label": "AI 回复", "type": "string"},
                {"key": "reasoningText", "label": "推理过程", "type": "string"},
            ],
            config_schema={
                "model": {
                    "type": "selectLLMModel",
                    "label": "选择模型",
                    "required": True,
                    "placeholder": "选择或搜索模型...",
                },
                "systemPrompt": {
                    "type": "textarea",
                    "label": "系统提示词",
                    "placeholder": "定义 AI 的角色和行为...",
                    "rows": 4,
                    "maxLength": 4000,
                },
                "temperature": {
                    "type": "slider",
                    "label": "温度参数",
                    "description": "控制输出的随机性。较低的值使输出更确定性，较高的值使输出更有创造性",
                    "min": 0,
                    "max": 2,
                    "step": 0.1,
                    "default": 0.7,
                },
                "maxToken": {
                    "type": "number",
                    "label": "最大 Token 数",
                    "description": "生成的最大 token 数量",
                    "min": 1,
                    "max": 32000,
                    "default": 2000,
                },
                "responseFormat": {
                    "type": "select",
                    "label": "响应格式",
                    "options": [
                        {"value": "text", "label": "文本"},
                        {"value": "json", "label": "JSON"},
                    ],
                    "default": "text",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="classifyQuestion",
            name="问题分类",
            description="将问题分类到不同类别",
            category="AI 节点",
            icon="📊",
            color="orange",
            inputs=[
                {"key": "content", "label": "问题内容", "type": "string", "required": True},
                {"key": "categories", "label": "分类选项", "type": "arrayString", "required": True},
            ],
            outputs=[
                {"key": "cqResult", "label": "分类结果", "type": "string"},
                {"key": "confidence", "label": "置信度", "type": "number"},
            ],
            config_schema={
                "categories": {
                    "type": "custom",
                    "label": "分类选项",
                    "required": True,
                    "description": "定义分类选项，每个选项包含名称和描述",
                },
                "prompt": {
                    "type": "textarea",
                    "label": "分类提示词",
                    "description": "指导模型如何进行分类的额外提示",
                    "placeholder": "根据用户的问题，将其分类到最合适的类别中...",
                    "rows": 3,
                },
                "threshold": {
                    "type": "slider",
                    "label": "置信度阈值",
                    "description": "只返回置信度大于此值的分类结果",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                    "default": 0.5,
                },
                "returnAllMatches": {
                    "type": "switch",
                    "label": "返回所有匹配",
                    "description": "是否返回所有匹配项，而不仅仅是最高置信度的项",
                    "default": False,
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="contentExtract",
            name="内容提取",
            description="从文本中提取结构化信息",
            category="AI 节点",
            icon="🔍",
            color="teal",
            inputs=[
                {"key": "content", "label": "输入内容", "type": "string", "required": True},
                {"key": "extractKeys", "label": "提取字段", "type": "arrayObject", "required": True},
            ],
            outputs=[
                {"key": "fields", "label": "提取字段", "type": "object"},
            ],
            config_schema={
                "extractSchema": {
                    "type": "textarea",
                    "label": "提取 Schema",
                    "required": True,
                    "description": "定义要提取的字段，使用 JSON Schema 格式",
                    "placeholder": '{\n  "字段名1": "字段描述1",\n  "字段名2": "字段描述2"\n}',
                    "rows": 6,
                    "fontFamily": "mono",
                },
                "prompt": {
                    "type": "textarea",
                    "label": "提取提示词",
                    "description": "额外的提取指导",
                    "placeholder": "请从文本中提取相关信息...",
                    "rows": 3,
                },
                "model": {
                    "type": "selectLLMModel",
                    "label": "使用的模型",
                    "required": True,
                },
            },
        ))

        # Tool nodes - HTTP 请求（带完整 Schema）
        self.register(NodeTypeInfo(
            type="httpRequest468",
            name="HTTP 请求",
            description="发送 HTTP 请求",
            category="工具节点",
            icon="🌐",
            color="cyan",
            inputs=[
                {"key": "system_httpReqUrl", "label": "URL", "type": "string", "required": True},
                {"key": "system_httpMethod", "label": "方法", "type": "string", "default": "GET"},
                {"key": "system_httpHeader", "label": "请求头", "type": "arrayObject"},
                {"key": "system_httpParams", "label": "查询参数", "type": "arrayObject"},
                {"key": "system_httpJsonBody", "label": "JSON 请求体", "type": "string"},
                {"key": "system_httpTimeout", "label": "超时时间", "type": "number", "default": 60},
            ],
            outputs=[
                {"key": "httpRawResponse", "label": "原始响应", "type": "any"},
                {"key": "system_text", "label": "响应文本", "type": "string"},
            ],
            config_schema={
                "system_httpReqUrl": {
                    "type": "input",
                    "label": "请求 URL",
                    "required": True,
                    "placeholder": "https://api.example.com/endpoint",
                },
                "system_httpMethod": {
                    "type": "select",
                    "label": "请求方法",
                    "options": [
                        {"value": "GET", "label": "GET"},
                        {"value": "POST", "label": "POST"},
                        {"value": "PUT", "label": "PUT"},
                        {"value": "DELETE", "label": "DELETE"},
                        {"value": "PATCH", "label": "PATCH"},
                    ],
                    "default": "GET",
                },
                "system_httpHeader": {
                    "type": "jsonEditor",
                    "label": "请求头",
                    "description": "JSON 格式的请求头，如 {\"Content-Type\": \"application/json\"}",
                    "placeholder": '{"Content-Type": "application/json"}',
                },
                "system_httpParams": {
                    "type": "jsonEditor",
                    "label": "查询参数",
                    "description": "JSON 格式的查询参数",
                    "placeholder": '{"page": 1, "limit": 10}',
                },
                "system_httpJsonBody": {
                    "type": "textarea",
                    "label": "请求体",
                    "description": "JSON 格式的请求体",
                    "rows": 4,
                    "placeholder": '{"key": "value"}',
                },
                "system_httpTimeout": {
                    "type": "number",
                    "label": "超时时间（秒）",
                    "min": 1,
                    "max": 300,
                    "default": 60,
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="code",
            name="代码执行",
            description="执行自定义代码",
            category="工具节点",
            icon="💻",
            color="gray",
            inputs=[
                {"key": "code", "label": "代码", "type": "string", "required": True},
                {"key": "codeType", "label": "代码类型", "type": "string", "default": "python"},
            ],
            outputs=[
                {"key": "system_text", "label": "执行结果", "type": "any"},
            ],
        ))

        self.register(NodeTypeInfo(
            type="readFiles",
            name="读取文件",
            description="读取文件内容",
            category="工具节点",
            icon="📄",
            color="yellow",
            inputs=[
                {"key": "fileUrlList", "label": "文件 URL 列表", "type": "arrayString", "required": True},
            ],
            outputs=[
                {"key": "fileTitle", "label": "文件内容", "type": "string"},
            ],
            config_schema={
                "fileUrlList": {
                    "type": "reference",
                    "label": "文件 URL 列表",
                    "required": True,
                    "description": "要读取的文件 URL 列表",
                },
                "encoding": {
                    "type": "select",
                    "label": "文件编码",
                    "options": [
                        {"value": "utf-8", "label": "UTF-8"},
                        {"value": "gbk", "label": "GBK"},
                        {"value": "gb2312", "label": "GB2312"},
                        {"value": "auto", "label": "自动检测"},
                    ],
                    "default": "utf-8",
                },
                "maxFileSize": {
                    "type": "number",
                    "label": "最大文件大小（MB）",
                    "description": "限制单个文件的最大大小",
                    "min": 0.1,
                    "max": 100,
                    "default": 10,
                },
                "concatContent": {
                    "type": "switch",
                    "label": "合并内容",
                    "description": "是否将多个文件的内容合并为一个输出",
                    "default": True,
                },
                "separator": {
                    "type": "input",
                    "label": "内容分隔符",
                    "description": "合并多个文件时使用的分隔符",
                    "default": "\n\n--- 文件分隔 ---\n\n",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="jsonSerialize",
            name="JSON 序列化",
            description="用于把变量转化为 JSON 字符串",
            category="工具节点",
            icon="🧊",
            color="cyan",
            inputs=[
                {"key": "input", "label": "输入", "type": "any", "required": True},
            ],
            outputs=[
                {"key": "output", "label": "输出", "type": "string"},
            ],
            config_schema={
                "input": {
                    "type": "reference",
                    "label": "输入",
                    "required": True,
                    "description": "输入或引用参数值",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="textEditor",
            name="文本处理",
            description="用于处理多个字符串类型变量的格式，支持字符串拼接、替换、截取、正则等操作",
            category="工具节点",
            icon="📝",
            color="indigo",
            inputs=[
                {"key": "var1", "label": "输入变量 1", "type": "string", "required": True},
                {"key": "var2", "label": "输入变量 2", "type": "string"},
            ],
            outputs=[
                {"key": "output", "label": "输出", "type": "string"},
            ],
            config_schema={
                "operation": {
                    "type": "select",
                    "label": "操作类型",
                    "required": True,
                    "options": [
                        {"value": "concat", "label": "字符串拼接"},
                        {"value": "replace", "label": "文本替换"},
                        {"value": "substring", "label": "文本截取"},
                        {"value": "regex", "label": "正则匹配"},
                        {"value": "split", "label": "文本分割"},
                        {"value": "trim", "label": "去除空白"},
                        {"value": "uppercase", "label": "转大写"},
                        {"value": "lowercase", "label": "转小写"},
                    ],
                    "default": "concat",
                },
                "inputs": {
                    "type": "custom",
                    "label": "输入变量",
                    "required": True,
                    "description": "定义输入变量，支持引用上游节点输出",
                },
            },
        ))

        # Logic nodes - 条件分支（带完整 Schema）
        self.register(NodeTypeInfo(
            type="ifElseNode",
            name="条件分支",
            description="根据条件执行不同分支",
            category="逻辑控制",
            icon="🔀",
            color="pink",
            inputs=[
                {"key": "condition", "label": "条件表达式", "type": "string", "required": True},
            ],
            outputs=[
                {"key": "system_resultTrue", "label": "真分支", "type": "boolean"},
                {"key": "system_resultFalse", "label": "假分支", "type": "boolean"},
            ],
            config_schema={
                "condition": {
                    "type": "input",
                    "label": "条件表达式",
                    "required": True,
                    "description": "支持变量引用，如 {{node1.value}} > 10",
                    "placeholder": "输入条件表达式，如 {{input.value}} == 'success'",
                },
                "logicType": {
                    "type": "select",
                    "label": "逻辑运算",
                    "options": [
                        {"value": "and", "label": "AND（所有条件满足）"},
                        {"value": "or", "label": "OR（任一条件满足）"},
                    ],
                    "default": "and",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="variableUpdate",
            name="变量更新",
            description="更新变量值",
            category="逻辑控制",
            icon="📝",
            color="lime",
            inputs=[
                {"key": "updateList", "label": "更新列表", "type": "arrayObject", "required": True},
            ],
            config_schema={
                "updateList": {
                    "type": "custom",
                    "label": "变量更新列表",
                    "required": True,
                    "description": "定义要更新的变量及其新值",
                },
            },
        ))

        # Logic nodes - 循环（带完整 Schema）
        self.register(NodeTypeInfo(
            type="loop",
            name="循环",
            description="循环执行子工作流",
            category="逻辑控制",
            icon="🔄",
            color="violet",
            inputs=[
                {"key": "loopInputArray", "label": "输入数组", "type": "arrayAny", "required": True},
            ],
            outputs=[
                {"key": "loopArray", "label": "循环结果", "type": "arrayAny"},
            ],
            config_schema={
                "loopInputArray": {
                    "type": "reference",
                    "label": "输入数组",
                    "required": True,
                    "description": "要遍历的数组变量",
                },
                "maxIterations": {
                    "type": "number",
                    "label": "最大迭代次数",
                    "description": "防止无限循环的最大迭代次数",
                    "min": 1,
                    "max": 1000,
                    "default": 100,
                },
                "continueOnError": {
                    "type": "switch",
                    "label": "出错时继续",
                    "description": "单个迭代出错时是否继续执行剩余迭代",
                    "default": False,
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="parallelRun",
            name="并行执行",
            description="并行执行多个子工作流",
            category="逻辑控制",
            icon="⚡",
            color="red",
            inputs=[
                {"key": "loopInputArray", "label": "输入数组", "type": "arrayAny", "required": True},
                {"key": "parallelRunMaxConcurrency", "label": "最大并发数", "type": "number", "default": 5},
            ],
            outputs=[
                {"key": "parallelSuccessResults", "label": "成功结果", "type": "arrayAny"},
                {"key": "parallelFullResults", "label": "全部结果", "type": "arrayAny"},
            ],
            config_schema={
                "loopInputArray": {
                    "type": "reference",
                    "label": "输入数组",
                    "required": True,
                    "description": "要并行处理的数组",
                },
                "parallelRunMaxConcurrency": {
                    "type": "number",
                    "label": "最大并发数",
                    "description": "同时执行的最大任务数",
                    "min": 1,
                    "max": 20,
                    "default": 5,
                },
                "continueOnError": {
                    "type": "switch",
                    "label": "出错时继续",
                    "description": "某个任务出错时是否继续执行其他任务",
                    "default": True,
                },
            },
        ))

        # Interactive nodes
        self.register(NodeTypeInfo(
            type="userSelect",
            name="用户选择",
            description="等待用户选择",
            category="交互节点",
            icon="👆",
            color="amber",
            inputs=[
                {"key": "userSelectOptions", "label": "选项", "type": "arrayObject", "required": True},
            ],
            outputs=[
                {"key": "selectResult", "label": "选择结果", "type": "string"},
                {"key": "selectIndex", "label": "选择索引", "type": "number"},
            ],
            config_schema={
                "userSelectOptions": {
                    "type": "custom",
                    "label": "选项配置",
                    "required": True,
                    "description": "定义用户可选的选项列表",
                },
                "allowMultiSelect": {
                    "type": "switch",
                    "label": "允许多选",
                    "description": "是否允许用户选择多个选项",
                    "default": False,
                },
                "timeout": {
                    "type": "number",
                    "label": "超时时间（秒）",
                    "description": "等待用户选择的超时时间，0 表示不限制",
                    "min": 0,
                    "max": 3600,
                    "default": 0,
                },
                "defaultOption": {
                    "type": "input",
                    "label": "超时默认选项",
                    "description": "超时后使用的默认选项值",
                },
            },
        ))

        self.register(NodeTypeInfo(
            type="formInput",
            name="表单输入",
            description="等待用户填写表单",
            category="交互节点",
            icon="📝",
            color="teal",
            inputs=[
                {"key": "userInputForms", "label": "表单字段", "type": "arrayObject", "required": True},
            ],
            outputs=[
                {"key": "formInputResult", "label": "表单结果", "type": "object"},
            ],
            config_schema={
                "userInputForms": {
                    "type": "custom",
                    "label": "表单字段配置",
                    "required": True,
                    "description": "定义表单字段列表，包括字段名称、类型、验证规则等",
                },
                "allowSkip": {
                    "type": "switch",
                    "label": "允许跳过",
                    "description": "是否允许用户跳过表单填写",
                    "default": False,
                },
                "timeout": {
                    "type": "number",
                    "label": "超时时间（秒）",
                    "description": "等待用户填写的超时时间，0 表示不限制",
                    "min": 0,
                    "max": 3600,
                    "default": 0,
                },
                "submitText": {
                    "type": "input",
                    "label": "提交按钮文本",
                    "default": "提交",
                },
                "skipText": {
                    "type": "input",
                    "label": "跳过按钮文本",
                    "default": "跳过",
                },
            },
        ))

    def register(self, node_info: NodeTypeInfo) -> None:
        """Register a node type."""
        self._nodes[node_info.type] = node_info

    def get(self, node_type: str) -> Optional[NodeTypeInfo]:
        """Get a node type by type string."""
        return self._nodes.get(node_type)

    def list_all(self) -> list[NodeTypeInfo]:
        """List all registered node types."""
        return list(self._nodes.values())

    def list_by_category(self, category: str) -> list[NodeTypeInfo]:
        """List node types by category."""
        return [n for n in self._nodes.values() if n.category == category]

    def get_categories(self) -> list[str]:
        """Get all categories."""
        return sorted(set(n.category for n in self._nodes.values()))


def get_node_types_dict() -> dict[str, dict[str, Any]]:
    """Get all node types as a dictionary."""
    registry = NodeRegistry()
    return {
        node_type.type: {
            "type": node_type.type,
            "name": node_type.name,
            "description": node_type.description,
            "category": node_type.category,
            "icon": node_type.icon,
            "color": node_type.color,
            "inputs": node_type.inputs,
            "outputs": node_type.outputs,
            "configSchema": node_type.config_schema,
        }
        for node_type in registry.list_all()
    }
