/**
 * 工作流类型定义入口
 */

export * from "./node";
export * from "./edge";
export * from "./io";

export interface WorkflowTemplateBasic {
  nodes: unknown[];
  edges: unknown[];
  chatConfig?: unknown;
}

export interface WorkflowTemplate {
  id?: string;
  parentId?: string;
  isFolder?: boolean;
  avatar?: string;
  name: string;
  intro?: string;
  toolDescription?: string;
  author?: string;
  courseUrl?: string;
  weight?: number;
  version?: string;
  workflow: WorkflowTemplateBasic;
}

export interface TemplateMarketItem extends WorkflowTemplate {
  tags: string[];
  type?: string;
}

export interface TemplateMarketListItem {
  id?: string;
  name: string;
  intro?: string;
  author?: string;
  tags: string[];
  type?: string;
  avatar?: string;
}

export const createWorkflowTemplateBasicType = (data: Partial<WorkflowTemplateBasic> = {}): WorkflowTemplateBasic => ({
  nodes: data.nodes || [],
  edges: data.edges || [],
  chatConfig: data.chatConfig,
});

export const createWorkflowTemplateType = (data: Partial<WorkflowTemplate> = {}): WorkflowTemplate => ({
  id: data.id,
  parentId: data.parentId,
  isFolder: data.isFolder,
  avatar: data.avatar,
  name: data.name || "未命名工作流",
  intro: data.intro,
  toolDescription: data.toolDescription,
  author: data.author,
  courseUrl: data.courseUrl,
  weight: data.weight,
  version: data.version,
  workflow: createWorkflowTemplateBasicType(data.workflow),
});

export const createTemplateMarketItemType = (data: Partial<TemplateMarketItem> = {}): TemplateMarketItem => ({
  ...createWorkflowTemplateType(data),
  tags: data.tags || [],
  type: data.type,
});

export const createTemplateMarketListItemType = (data: Partial<TemplateMarketListItem> = {}): TemplateMarketListItem => ({
  id: data.id,
  name: data.name || "未命名",
  intro: data.intro,
  author: data.author,
  tags: data.tags || [],
  type: data.type,
  avatar: data.avatar,
});
