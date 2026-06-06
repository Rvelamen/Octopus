/**
 * 工作流节点类型定义
 */

export interface NodeToolConfig {
  mcpToolSet?: string;
  mcpTool?: string;
  systemTool?: string;
  systemToolSet?: string;
  httpToolSet?: string;
  httpTool?: string;
}

export interface ToolData {
  diagram?: string;
  userGuide?: string;
  courseUrl?: string;
  name?: string;
  avatar?: string;
  error?: string;
  status?: string;
}

export interface FlowNodeCommon {
  parentNodeId?: string;
  flowNodeType?: string;
  abandon?: boolean;
  avatar?: string;
  avatarLinear?: string;
  colorSchema?: string;
  name: string;
  intro?: string;
  toolDescription?: string;
  showStatus?: boolean;
  version?: string;
  versionLabel?: string;
  isLatestVersion?: boolean;
  catchError?: boolean;
  inputs: Array<Record<string, unknown>>;
  outputs: Array<Record<string, unknown>>;
  pluginId?: string;
  isFolder?: boolean;
  pluginData?: Record<string, unknown>;
  toolConfig?: NodeToolConfig;
  currentCost?: number;
  systemKeyCost?: number;
  hasTokenFee?: boolean;
  hasSystemSecret?: boolean;
}

export interface FlowNodeTemplate extends FlowNodeCommon {
  id?: string;
  templateType?: string;
  status?: string;
  showSourceHandle?: boolean;
  showTargetHandle?: boolean;
  isTool?: boolean;
  forbidDelete?: boolean;
  unique?: boolean;
  diagram?: string;
  courseUrl?: string;
  userGuide?: string;
  tags?: string[];
}

export interface NodeTemplateListItem {
  id?: string;
  flowNodeType?: string;
  parentId?: string;
  isFolder?: boolean;
  templateType?: string;
  tags?: string[];
  avatar?: string;
  name: string;
  intro?: string;
  isTool?: boolean;
  authorAvatar?: string;
  author?: string;
  unique?: boolean;
  currentCost?: number;
  systemKeyCost?: number;
  hasTokenFee?: boolean;
  instructions?: string;
  courseUrl?: string;
  sourceMember?: string;
  toolSource?: string;
}

export interface FlowNodeItem extends FlowNodeTemplate {
  nodeId?: string;
  parentNodeId?: string;
  isError?: boolean;
  searchedText?: string;
  debugResult?: Record<string, unknown>;
  isFolded?: boolean;
}

export interface StoreNodeItem extends FlowNodeCommon {
  nodeId?: string;
  position: { x: number; y: number };
}

export const createNodeToolConfigType = (config: Partial<NodeToolConfig> = {}): NodeToolConfig => ({
  mcpToolSet: config.mcpToolSet,
  mcpTool: config.mcpTool,
  systemTool: config.systemTool,
  systemToolSet: config.systemToolSet,
  httpToolSet: config.httpToolSet,
  httpTool: config.httpTool,
});

export const createToolDataType = (data: Partial<ToolData> = {}): ToolData => ({
  diagram: data.diagram,
  userGuide: data.userGuide,
  courseUrl: data.courseUrl,
  name: data.name,
  avatar: data.avatar,
  error: data.error,
  status: data.status,
});

export const createFlowNodeCommonType = (data: Partial<FlowNodeCommon> = {}): FlowNodeCommon => ({
  parentNodeId: data.parentNodeId,
  flowNodeType: data.flowNodeType,
  abandon: data.abandon,
  avatar: data.avatar,
  avatarLinear: data.avatarLinear,
  colorSchema: data.colorSchema,
  name: data.name || "未命名节点",
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
  hasSystemSecret: data.hasSystemSecret,
});

export const createFlowNodeTemplateType = (data: Partial<FlowNodeTemplate> = {}): FlowNodeTemplate => ({
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
  tags: data.tags,
});

export const createNodeTemplateListItemType = (data: Partial<NodeTemplateListItem> = {}): NodeTemplateListItem => ({
  id: data.id,
  flowNodeType: data.flowNodeType,
  parentId: data.parentId,
  isFolder: data.isFolder,
  templateType: data.templateType,
  tags: data.tags,
  avatar: data.avatar,
  name: data.name || "未命名",
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
  toolSource: data.toolSource,
});

export const createFlowNodeItemType = (data: Partial<FlowNodeItem> = {}): FlowNodeItem => ({
  ...createFlowNodeTemplateType(data),
  nodeId: data.nodeId,
  parentNodeId: data.parentNodeId,
  isError: data.isError,
  searchedText: data.searchedText,
  debugResult: data.debugResult,
  isFolded: data.isFolded,
});

export const createStoreNodeItemType = (data: Partial<StoreNodeItem> = {}): StoreNodeItem => ({
  ...createFlowNodeCommonType(data),
  nodeId: data.nodeId,
  position: data.position || { x: 0, y: 0 },
});
