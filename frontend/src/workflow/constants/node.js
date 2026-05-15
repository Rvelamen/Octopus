/**
 * 工作流节点常量定义
 * 从 FastGPT 迁移并适配为原生 JavaScript
 */

// 节点输入类型枚举
export const FlowNodeInputTypeEnum = {
  reference: 'reference', // 引用其他节点输出
  input: 'input', // 单行输入
  textarea: 'textarea',
  numberInput: 'numberInput',
  switch: 'switch', // 开关
  select: 'select',
  multipleSelect: 'multipleSelect',
  JSONEditor: 'JSONEditor',
  addInputParam: 'addInputParam', // 动态参数输入
  customVariable: 'customVariable', // 外部变量
  selectApp: 'selectApp',
  selectLLMModel: 'selectLLMModel',
  settingLLMModel: 'settingLLMModel',
  selectDataset: 'selectDataset',
  selectDatasetParamsModal: 'selectDatasetParamsModal',
  settingDatasetQuotePrompt: 'settingDatasetQuotePrompt',
  hidden: 'hidden',
  custom: 'custom', // 自定义渲染
  selectSkill: 'selectSkill',
  selectTool: 'selectTool',
  fileSelect: 'fileSelect',
  timePointSelect: 'timePointSelect',
  timeRangeSelect: 'timeRangeSelect',
  password: 'password'
};

// 节点输入类型图标映射
export const FlowNodeInputMap = {
  [FlowNodeInputTypeEnum.reference]: { icon: 'core/workflow/inputType/reference' },
  [FlowNodeInputTypeEnum.numberInput]: { icon: 'core/workflow/inputType/numberInput' },
  [FlowNodeInputTypeEnum.select]: { icon: 'core/workflow/inputType/option' },
  [FlowNodeInputTypeEnum.multipleSelect]: { icon: 'core/workflow/inputType/multipleSelect' },
  [FlowNodeInputTypeEnum.switch]: { icon: 'core/workflow/inputType/switch' },
  [FlowNodeInputTypeEnum.JSONEditor]: { icon: 'core/workflow/inputType/jsonEditor' },
  [FlowNodeInputTypeEnum.addInputParam]: { icon: 'core/workflow/inputType/dynamic' },
  [FlowNodeInputTypeEnum.selectApp]: { icon: 'core/workflow/inputType/selectApp' },
  [FlowNodeInputTypeEnum.selectLLMModel]: { icon: 'core/workflow/inputType/selectLLM' },
  [FlowNodeInputTypeEnum.settingLLMModel]: { icon: 'core/workflow/inputType/selectLLM' },
  [FlowNodeInputTypeEnum.selectDataset]: { icon: 'core/workflow/inputType/selectDataset' },
  [FlowNodeInputTypeEnum.selectDatasetParamsModal]: { icon: 'core/workflow/inputType/selectDataset' },
  [FlowNodeInputTypeEnum.settingDatasetQuotePrompt]: { icon: 'core/workflow/inputType/selectDataset' },
  [FlowNodeInputTypeEnum.hidden]: { icon: 'core/workflow/inputType/internal' },
  [FlowNodeInputTypeEnum.customVariable]: { icon: 'core/workflow/inputType/customVariable' },
  [FlowNodeInputTypeEnum.custom]: { icon: 'core/workflow/inputType/custom' },
  [FlowNodeInputTypeEnum.selectSkill]: { icon: 'core/workflow/inputType/selectDataset' },
  [FlowNodeInputTypeEnum.selectTool]: { icon: 'core/workflow/inputType/selectDataset' },
  [FlowNodeInputTypeEnum.input]: { icon: 'core/workflow/inputType/input' },
  [FlowNodeInputTypeEnum.textarea]: { icon: 'core/workflow/inputType/textarea' },
  [FlowNodeInputTypeEnum.fileSelect]: { icon: 'core/workflow/inputType/file' },
  [FlowNodeInputTypeEnum.timePointSelect]: { icon: 'core/workflow/inputType/timePointSelect' },
  [FlowNodeInputTypeEnum.timeRangeSelect]: { icon: 'core/workflow/inputType/timeRangeSelect' },
  [FlowNodeInputTypeEnum.password]: { icon: 'core/workflow/inputType/password' }
};

// 节点输出类型枚举
export const FlowNodeOutputTypeEnum = {
  hidden: 'hidden',
  error: 'error',
  source: 'source',
  static: 'static',
  dynamic: 'dynamic'
};

// 节点类型枚举
export const FlowNodeTypeEnum = {
  emptyNode: 'emptyNode',
  systemConfig: 'userGuide',
  pluginConfig: 'pluginConfig',
  globalVariable: 'globalVariable',
  comment: 'comment',
  workflowStart: 'workflowStart',
  chatNode: 'chatNode',
  answerNode: 'answerNode',
  classifyQuestion: 'classifyQuestion',
  contentExtract: 'contentExtract',
  httpRequest468: 'httpRequest468',
  pluginInput: 'pluginInput',
  pluginOutput: 'pluginOutput',
  queryExtension: 'cfr',
  agent: 'agent',
  toolCall: 'tools',
  stopTool: 'stopTool',
  toolParams: 'toolParams',
  lafModule: 'lafModule',
  ifElseNode: 'ifElseNode',
  variableUpdate: 'variableUpdate',
  code: 'code',
  textEditor: 'textEditor',
  customFeedback: 'customFeedback',
  readFiles: 'readFiles',
  userSelect: 'userSelect',
  loop: 'loop',
  nestedStart: 'loopStart',
  nestedEnd: 'loopEnd',
  parallelRun: 'parallelRun',
  formInput: 'formInput',
  inputNode: 'inputNode',
  tool: 'tool',
  toolSet: 'toolSet',
  appModule: 'appModule',
  pluginModule: 'pluginModule',
  runApp: 'app',
  workflowEnd: 'workflowEnd',
  llm: 'llm',
  http: 'http',
  jsonSerialize: 'jsonSerialize',
  jsonDeserialize: 'jsonDeserialize',
};

// 节点颜色主题
export const NodeGradients = {
  pink: 'linear-gradient(180deg, rgba(255, 161, 206, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  blue: 'linear-gradient(180deg, rgba(104, 192, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  blueLight: 'linear-gradient(180deg, rgba(85, 184, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  blueDark: 'linear-gradient(180deg, rgba(125, 153, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  orange: 'linear-gradient(180deg, rgba(255, 199, 90, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  purple: 'linear-gradient(180deg, rgba(235, 120, 254, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  teal: 'linear-gradient(180deg, rgba(97, 210, 196, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  green: 'linear-gradient(180deg, rgba(62, 217, 170, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  greenLight: 'linear-gradient(180deg, rgba(94, 209, 128, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  indigo: 'linear-gradient(180deg, rgba(120, 147, 254, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  coral: 'linear-gradient(180deg, rgba(252, 162, 143, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  lime: 'linear-gradient(0deg, rgba(255, 255, 255, 0.00) 0%, rgba(92, 216, 201, 0.25) 100%)',
  violet: 'linear-gradient(180deg, rgba(155, 142, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  violetDeep: 'linear-gradient(180deg, rgba(212, 117, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  yellowGreen: 'linear-gradient(180deg, rgba(166, 218, 114, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  lafTeal: 'linear-gradient(180deg, rgba(72, 213, 186, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  skyBlue: 'linear-gradient(180deg, rgba(137, 229, 255, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  salmon: 'linear-gradient(180deg, rgba(255, 160, 160, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  gray: 'linear-gradient(180deg, rgba(136, 136, 136, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)',
  emerald: 'linear-gradient(180deg, rgba(20, 168, 70, 0.20) 0%, rgba(255, 255, 255, 0.00) 100%)'
};

export const NodeBorderColors = {
  pink: 'rgba(255, 161, 206, 0.6)',
  blue: 'rgba(104, 192, 255, 0.6)',
  blueLight: 'rgba(85, 184, 255, 0.6)',
  blueDark: 'rgba(125, 153, 255, 0.6)',
  orange: 'rgba(255, 199, 90, 0.6)',
  purple: 'rgba(235, 120, 254, 0.6)',
  teal: 'rgba(97, 210, 196, 0.6)',
  green: 'rgba(62, 217, 170, 0.6)',
  greenLight: 'rgba(94, 209, 128, 0.6)',
  indigo: 'rgba(120, 147, 254, 0.6)',
  coral: 'rgba(252, 162, 143, 0.6)',
  lime: 'rgba(92, 216, 201, 0.6)',
  violet: 'rgba(155, 142, 255, 0.6)',
  violetDeep: 'rgba(212, 117, 255, 0.6)',
  yellowGreen: 'rgba(166, 218, 114, 0.6)',
  lafTeal: 'rgba(72, 213, 186, 0.6)',
  skyBlue: 'rgba(137, 229, 255, 0.6)',
  salmon: 'rgba(255, 160, 160, 0.6)',
  gray: 'rgba(136, 136, 136, 0.6)',
  emerald: 'rgba(20, 168, 70, 0.6)'
};

export const NodeColorSchemaEnum = [
  'pink', 'blue', 'blueLight', 'blueDark', 'orange', 'purple', 'teal', 'green',
  'greenLight', 'indigo', 'coral', 'lime', 'violet', 'violetDeep', 'yellowGreen',
  'lafTeal', 'skyBlue', 'salmon', 'gray', 'emerald'
];

// 边类型
export const EDGE_TYPE = 'default';

// 判断是否为嵌套父容器节点
export const isNestedParentNodeType = (flowNodeType) =>
  flowNodeType === FlowNodeTypeEnum.loop || flowNodeType === FlowNodeTypeEnum.parallelRun;

// 交互类节点类型集合
export const INTERACTIVE_NODE_TYPES = new Set([
  FlowNodeTypeEnum.userSelect,
  FlowNodeTypeEnum.formInput
]);

// 判断是否为交互类节点
export const isInteractiveNodeType = (flowNodeType) =>
  INTERACTIVE_NODE_TYPES.has(flowNodeType);

// 应用节点映射
export const AppNodeFlowNodeTypeMap = {
  [FlowNodeTypeEnum.pluginModule]: true,
  [FlowNodeTypeEnum.appModule]: true,
  [FlowNodeTypeEnum.tool]: true,
  [FlowNodeTypeEnum.toolSet]: true
};
