/**
 * 工作流常量定义
 */

import { MarkerType } from '@xyflow/react';

export * from './node';

// 工作流IO值类型枚举
export const WorkflowIOValueTypeEnum = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
  object: 'object',
  arrayString: 'arrayString',
  arrayNumber: 'arrayNumber',
  arrayBoolean: 'arrayBoolean',
  arrayObject: 'arrayObject',
  arrayAny: 'arrayAny',
  any: 'any',
  chatHistory: 'chatHistory',
  datasetQuote: 'datasetQuote',
  dynamic: 'dynamic',
  selectDataset: 'selectDataset',
  selectApp: 'selectApp'
};

// 工具值类型列表
export const toolValueTypeList = [
  {
    label: 'string',
    value: WorkflowIOValueTypeEnum.string,
    jsonSchema: { type: 'string' }
  },
  {
    label: 'number',
    value: WorkflowIOValueTypeEnum.number,
    jsonSchema: { type: 'number' }
  },
  {
    label: 'boolean',
    value: WorkflowIOValueTypeEnum.boolean,
    jsonSchema: { type: 'boolean' }
  },
  {
    label: 'array<string>',
    value: WorkflowIOValueTypeEnum.arrayString,
    jsonSchema: { type: 'array', items: { type: 'string' } }
  },
  {
    label: 'array<number>',
    value: WorkflowIOValueTypeEnum.arrayNumber,
    jsonSchema: { type: 'array', items: { type: 'number' } }
  },
  {
    label: 'array<boolean>',
    value: WorkflowIOValueTypeEnum.arrayBoolean,
    jsonSchema: { type: 'array', items: { type: 'boolean' } }
  },
  {
    label: 'object',
    value: WorkflowIOValueTypeEnum.object,
    jsonSchema: { type: 'object' }
  }
];

// 值类型 JSON Schema 映射
export const valueTypeJsonSchemaMap = toolValueTypeList.reduce((acc, item) => {
  acc[item.value] = item.jsonSchema;
  return acc;
}, {});

// 节点输入键枚举
export const NodeInputKeyEnum = {
  // 旧版
  welcomeText: 'welcomeText',
  switch: 'switch',
  history: 'history',
  answerText: 'text',

  // 系统配置
  questionGuide: 'questionGuide',
  tts: 'tts',
  whisper: 'whisper',
  variables: 'variables',
  scheduleTrigger: 'scheduleTrigger',
  chatInputGuide: 'chatInputGuide',
  autoExecute: 'autoExecute',

  // 插件配置
  instruction: 'instruction',

  // 入口
  userChatInput: 'userChatInput',
  inputFiles: 'inputFiles',
  agents: 'agents',

  // 通用
  aiModel: 'model',
  aiSystemPrompt: 'systemPrompt',
  description: 'description',
  anyInput: 'system_anyInput',
  textareaInput: 'system_textareaInput',
  addInputParam: 'system_addInputParam',
  forbidStream: 'system_forbid_stream',
  headerSecret: 'system_header_secret',
  systemInputConfig: 'system_input_config',

  // 历史记录
  historyMaxAmount: 'maxContext',

  // AI对话
  aiChatTemperature: 'temperature',
  aiChatMaxToken: 'maxToken',
  aiChatSettingModal: 'aiSettings',
  aiChatIsResponseText: 'isResponseAnswerText',
  aiChatQuoteRole: 'aiChatQuoteRole',
  aiChatQuoteTemplate: 'quoteTemplate',
  aiChatQuotePrompt: 'quotePrompt',
  aiChatDatasetQuote: 'quoteQA',
  aiChatVision: 'aiChatVision',
  stringQuoteText: 'stringQuoteText',
  aiChatReasoning: 'aiChatReasoning',
  aiChatTopP: 'aiChatTopP',
  aiChatStopSign: 'aiChatStopSign',
  aiChatResponseFormat: 'aiChatResponseFormat',
  aiChatJsonSchema: 'aiChatJsonSchema',

  // Agent
  selectedTools: 'agent_selectedTools',
  datasetParams: 'agent_datasetParams',
  skills: 'skills',
  useAgentSandbox: 'useAgentSandbox',
  useEditDebugSandbox: 'useEditDebugSandbox',

  // 知识库
  datasetSelectList: 'datasets',
  datasetSimilarity: 'similarity',
  datasetMaxTokens: 'limit',
  datasetSearchMode: 'searchMode',
  datasetSearchEmbeddingWeight: 'embeddingWeight',
  datasetSearchUsingReRank: 'usingReRank',
  datasetSearchRerankWeight: 'rerankWeight',
  datasetSearchRerankModel: 'rerankModel',
  datasetSearchUsingExtensionQuery: 'datasetSearchUsingExtensionQuery',
  datasetSearchExtensionModel: 'datasetSearchExtensionModel',
  datasetSearchExtensionBg: 'datasetSearchExtensionBg',
  collectionFilterMatch: 'collectionFilterMatch',
  authTmbId: 'authTmbId',
  datasetDeepSearch: 'datasetDeepSearch',
  datasetDeepSearchModel: 'datasetDeepSearchModel',
  datasetDeepSearchMaxTimes: 'datasetDeepSearchMaxTimes',
  datasetDeepSearchBg: 'datasetDeepSearchBg',

  // 知识库合并
  datasetQuoteList: 'system_datasetQuoteList',

  // 上下文提取
  contextExtractInput: 'content',
  extractKeys: 'extractKeys',

  // HTTP
  httpReqUrl: 'system_httpReqUrl',
  httpHeaders: 'system_httpHeader',
  httpMethod: 'system_httpMethod',
  httpParams: 'system_httpParams',
  httpJsonBody: 'system_httpJsonBody',
  httpFormBody: 'system_httpFormBody',
  httpContentType: 'system_httpContentType',
  httpTimeout: 'system_httpTimeout',
  abandon_httpUrl: 'url',

  // 应用
  runAppSelectApp: 'app',

  // 插件
  pluginId: 'pluginId',
  pluginStart: 'pluginStart',

  // 条件分支
  condition: 'condition',
  ifElseList: 'ifElseList',

  // 变量更新
  updateList: 'updateList',

  // 代码
  code: 'code',
  codeType: 'codeType',

  // 读取文件
  fileUrlList: 'fileUrlList',

  // 用户选择
  userSelectOptions: 'userSelectOptions',

  // 嵌套容器
  nestedInputArray: 'loopInputArray',
  childrenNodeIdList: 'childrenNodeIdList',
  nodeWidth: 'nodeWidth',
  nodeHeight: 'nodeHeight',
  nestedNodeInputHeight: 'loopNodeInputHeight',
  nestedStartInput: 'loopStartInput',
  nestedStartIndex: 'loopStartIndex',
  nestedEndInput: 'loopEndInput',
  parallelRunMaxConcurrency: 'parallelRunMaxConcurrency',
  parallelRunMaxRetryTimes: 'parallelRunMaxRetryTimes',

  // 表单输入
  userInputForms: 'userInputForms',

  // 注释
  commentText: 'commentText',
  commentSize: 'commentSize',

  // 工具
  toolData: 'system_toolData',
  toolSetData: 'system_toolSetData'
};

// 节点输出键枚举
export const NodeOutputKeyEnum = {
  // 通用
  userChatInput: 'userChatInput',
  history: 'history',
  answerText: 'answerText',
  reasoningText: 'reasoningText',
  success: 'success',
  failed: 'failed',
  text: 'system_text',
  addOutputParam: 'system_addOutputParam',
  rawResponse: 'system_rawResponse',
  systemError: 'system_error',
  errorText: 'system_error_text',

  // 开始节点
  userFiles: 'userFiles',

  // 知识库
  datasetQuoteQA: 'quoteQA',

  // 分类
  cqResult: 'cqResult',

  // 上下文提取
  contextExtractFields: 'fields',

  // 条件分支
  resultTrue: 'system_resultTrue',
  resultFalse: 'system_resultFalse',

  // 工具
  selectedTools: 'selectedTools',

  // HTTP
  httpRawResponse: 'httpRawResponse',

  // 插件
  pluginStart: 'pluginStart',

  // 条件分支结果
  ifElseResult: 'ifElseResult',

  // 用户选择
  selectResult: 'selectResult',

  // 嵌套容器结果
  nestedArrayResult: 'loopArray',
  nestedStartInput: 'loopStartInput',
  nestedStartIndex: 'loopStartIndex',

  // 并行运行输出
  parallelSuccessResults: 'parallelSuccessResults',
  parallelFullResults: 'parallelFullResults',
  parallelStatus: 'parallelStatus',

  // 表单输入
  formInputResult: 'formInputResult',

  // 文件
  fileTitle: 'fileTitle',

  // 已弃用
  error: 'error'
};

// 并行运行状态枚举
export const ParallelRunStatusEnum = {
  success: 'success',
  partial_success: 'partial_success',
  failed: 'failed'
};

// 变量输入类型枚举
export const VariableInputEnum = {
  input: 'input',
  textarea: 'textarea',
  numberInput: 'numberInput',
  select: 'select',
  multipleSelect: 'multipleSelect',
  timePointSelect: 'timePointSelect',
  timeRangeSelect: 'timeRangeSelect',
  switch: 'switch',
  password: 'password',
  file: 'file',
  llmSelect: 'llmSelect',
  datasetSelect: 'datasetSelect',
  custom: 'custom',
  internal: 'internal'
};

// HTTP 内容类型
export const ContentTypes = {
  none: 'none',
  formData: 'form-data',
  xWwwFormUrlencoded: 'x-www-form-urlencoded',
  json: 'json',
  xml: 'xml',
  raw: 'raw-text'
};

export const contentTypeMap = {
  [ContentTypes.none]: '',
  [ContentTypes.formData]: '',
  [ContentTypes.xWwwFormUrlencoded]: 'application/x-www-form-urlencoded',
  [ContentTypes.json]: 'application/json',
  [ContentTypes.xml]: 'application/xml',
  [ContentTypes.raw]: 'text/plain'
};

// HTTP 请求方法
export const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

// 数组类型映射
export const ArrayTypeMap = {
  [WorkflowIOValueTypeEnum.string]: WorkflowIOValueTypeEnum.arrayString,
  [WorkflowIOValueTypeEnum.number]: WorkflowIOValueTypeEnum.arrayNumber,
  [WorkflowIOValueTypeEnum.boolean]: WorkflowIOValueTypeEnum.arrayBoolean,
  [WorkflowIOValueTypeEnum.object]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.arrayString]: WorkflowIOValueTypeEnum.arrayString,
  [WorkflowIOValueTypeEnum.arrayNumber]: WorkflowIOValueTypeEnum.arrayNumber,
  [WorkflowIOValueTypeEnum.arrayBoolean]: WorkflowIOValueTypeEnum.arrayBoolean,
  [WorkflowIOValueTypeEnum.arrayObject]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.chatHistory]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.datasetQuote]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.dynamic]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.selectDataset]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.selectApp]: WorkflowIOValueTypeEnum.arrayObject,
  [WorkflowIOValueTypeEnum.arrayAny]: WorkflowIOValueTypeEnum.arrayAny,
  [WorkflowIOValueTypeEnum.any]: WorkflowIOValueTypeEnum.arrayAny
};

// 特殊变量
export const VARIABLE_NODE_ID = 'VARIABLE_NODE_ID';
export const DYNAMIC_INPUT_REFERENCE_KEY = 'DYNAMIC_INPUT_REFERENCE_KEY';

// 值类型描述
export const chatHistoryValueDesc = `{\n  obj: System | Human | AI;\n  value: string;\n}[]`;

export const datasetQuoteValueDesc = `{\n  id: string;\n  datasetId: string;\n  collectionId: string;\n  sourceName: string;\n  sourceId?: string;\n  q: string;\n  a: string\n}[]`;

// 工作流模板类型枚举
export const FlowNodeTemplateTypeEnum = {
  systemInput: 'systemInput',
  ai: 'ai',
  interactive: 'interactive',
  tools: 'tools',
  other: 'other',
  teamApp: 'teamApp'
};

// 画布默认配置
export const defaultEdgeOptions = {
  type: 'default',
  animated: true,
  style: { stroke: '#999', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#999' }
};

export const minZoom = 0.1;
export const maxZoom = 2;
