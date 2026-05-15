/**
 * 工作流节点类型定义
 */

// 工具配置类型
export const createNodeToolConfigType = (config = {}) => ({
  mcpToolSet: config.mcpToolSet,
  mcpTool: config.mcpTool,
  systemTool: config.systemTool,
  systemToolSet: config.systemToolSet,
  httpToolSet: config.httpToolSet,
  httpTool: config.httpTool
});

// 工具数据类型
export const createToolDataType = (data = {}) => ({
  diagram: data.diagram,
  userGuide: data.userGuide,
  courseUrl: data.courseUrl,
  name: data.name,
  avatar: data.avatar,
  error: data.error,
  status: data.status
});

// 流程节点通用类型
export const createFlowNodeCommonType = (data = {}) => ({
  parentNodeId: data.parentNodeId,
  flowNodeType: data.flowNodeType,
  abandon: data.abandon,
  avatar: data.avatar,
  avatarLinear: data.avatarLinear,
  colorSchema: data.colorSchema,
  name: data.name || '未命名节点',
  intro: data.intro,
  toolDescription: data.toolDescription,
  showStatus: data.showStatus,
  version: data.version,
  versionLabel: data.versionLabel,
  isLatestVersion: data.isLatestVersion,
  catchError: data.catchError,
  inputs: data.inputs || [],
  outputs: data.outputs || [],
  pluginId: data.pluginId,
  isFolder: data.isFolder,
  pluginData: data.pluginData,
  toolConfig: data.toolConfig,
  currentCost: data.currentCost,
  systemKeyCost: data.systemKeyCost,
  hasTokenFee: data.hasTokenFee,
  hasSystemSecret: data.hasSystemSecret
});

// 流程节点模板类型
export const createFlowNodeTemplateType = (data = {}) => ({
  ...createFlowNodeCommonType(data),
  id: data.id,
  templateType: data.templateType,
  status: data.status,
  showSourceHandle: data.showSourceHandle,
  showTargetHandle: data.showTargetHandle,
  isTool: data.isTool,
  forbidDelete: data.forbidDelete,
  unique: data.unique,
  diagram: data.diagram,
  courseUrl: data.courseUrl,
  userGuide: data.userGuide,
  tags: data.tags
});

// 节点模板列表项类型
export const createNodeTemplateListItemType = (data = {}) => ({
  id: data.id,
  flowNodeType: data.flowNodeType,
  parentId: data.parentId,
  isFolder: data.isFolder,
  templateType: data.templateType,
  tags: data.tags,
  avatar: data.avatar,
  name: data.name || '未命名',
  intro: data.intro,
  isTool: data.isTool,
  authorAvatar: data.authorAvatar,
  author: data.author,
  unique: data.unique,
  currentCost: data.currentCost,
  systemKeyCost: data.systemKeyCost,
  hasTokenFee: data.hasTokenFee,
  instructions: data.instructions,
  courseUrl: data.courseUrl,
  sourceMember: data.sourceMember,
  toolSource: data.toolSource
});

// React Flow 节点项类型
export const createFlowNodeItemType = (data = {}) => ({
  ...createFlowNodeTemplateType(data),
  nodeId: data.nodeId,
  parentNodeId: data.parentNodeId,
  isError: data.isError,
  searchedText: data.searchedText,
  debugResult: data.debugResult,
  isFolded: data.isFolded
});

// 存储节点项类型
export const createStoreNodeItemType = (data = {}) => ({
  ...createFlowNodeCommonType(data),
  nodeId: data.nodeId,
  position: data.position || { x: 0, y: 0 }
});
