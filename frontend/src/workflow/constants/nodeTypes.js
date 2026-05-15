export const NODE_TYPE_INFO = {
  workflowStart: { icon: '🚀', color: '#3b82f6', name: '工作流开始', category: '基础节点' },
  answerNode: { icon: '💬', color: '#22c55e', name: '直接回复', category: '基础节点' },
  workflowEnd: { icon: '🔚', color: '#ef4444', name: '工作流结束', category: '基础节点' },
  llm: { icon: '🤖', color: '#8b5cf6', name: '大模型', category: 'AI 节点' },
  classifyQuestion: { icon: '📊', color: '#f97316', name: '问题分类', category: 'AI 节点' },
  contentExtract: { icon: '🔍', color: '#14b8a6', name: '内容提取', category: 'AI 节点' },
  httpRequest468: { icon: '🌐', color: '#06b6d4', name: 'HTTP 请求', category: '工具节点' },
  http: { icon: '🌐', color: '#3b82f6', name: 'HTTP 请求', category: '工具节点' },
  code: { icon: '💻', color: '#6b7280', name: '代码执行', category: '工具节点' },
  readFiles: { icon: '📄', color: '#eab308', name: '读取文件', category: '工具节点' },
  jsonSerialize: { icon: '🧊', color: '#06b6d4', name: 'JSON 序列化', category: '工具节点' },
  ifElseNode: { icon: '🔀', color: '#ec4899', name: '条件分支', category: '逻辑控制' },
  variableUpdate: { icon: '📝', color: '#84cc16', name: '变量更新', category: '逻辑控制' },
  loop: { icon: '🔄', color: '#7c3aed', name: '循环', category: '逻辑控制' },
  parallelRun: { icon: '⚡', color: '#ef4444', name: '并行执行', category: '逻辑控制' },
  userSelect: { icon: '👆', color: '#f59e0b', name: '用户选择', category: '交互节点' },
  formInput: { icon: '📝', color: '#14b8a6', name: '表单输入', category: '交互节点' },
  inputNode: { icon: '⬅️', color: '#6366f1', name: '输入', category: '交互节点' },
  pluginOutput: { icon: '➡️', color: '#6366f1', name: '输出', category: '交互节点' },
  textEditor: { icon: '📝', color: '#6366f1', name: '文本处理', category: '工具节点' },
  agentNode: { icon: '🤖', color: '#8b5cf6', name: 'Agent', category: 'Agent' },
  subWorkflowNode: { icon: '📦', color: '#6366f1', name: '子工作流', category: 'Agent' },
  jsonDeserialize: { icon: '🧩', color: '#6366f1', name: 'JSON 反序列化', category: '工具节点' },
};

export const DEFAULT_NODE_TYPE_INFO = { icon: '📦', color: '#6b7280', name: '节点', category: '其他' };

export const TYPE_COLORS = {
  string: '#3b82f6',
  number: '#22c55e',
  boolean: '#f97316',
  object: '#a855f7',
  array: '#ec4899',
  arrayString: '#06b6d4',
  arrayNumber: '#14b8a6',
  arrayObject: '#8b5cf6',
};

export const TYPE_LABELS = {
  string: '字符串',
  number: '数字',
  boolean: '布尔',
  object: '对象',
  array: '数组',
  arrayString: '字符串数组',
  arrayNumber: '数字数组',
  arrayObject: '对象数组',
};

export const TYPE_LABELS_EN = {
  string: 'String',
  number: 'Number',
  boolean: 'Boolean',
  object: 'Object',
  arrayString: 'Array<String>',
  arrayNumber: 'Array<Number>',
  arrayObject: 'Array<Object>',
};
