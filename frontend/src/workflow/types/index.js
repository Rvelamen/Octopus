/**
 * 工作流类型定义入口
 */

export * from './node';
export * from './edge';
export * from './io';

// 工作流模板基础类型
export const createWorkflowTemplateBasicType = (data = {}) => ({
  nodes: data.nodes || [],
  edges: data.edges || [],
  chatConfig: data.chatConfig
});

// 工作流模板类型
export const createWorkflowTemplateType = (data = {}) => ({
  id: data.id,
  parentId: data.parentId,
  isFolder: data.isFolder,
  avatar: data.avatar,
  name: data.name || '未命名工作流',
  intro: data.intro,
  toolDescription: data.toolDescription,
  author: data.author,
  courseUrl: data.courseUrl,
  weight: data.weight,
  version: data.version,
  workflow: createWorkflowTemplateBasicType(data.workflow)
});

// 模板市场项类型
export const createTemplateMarketItemType = (data = {}) => ({
  ...createWorkflowTemplateType(data),
  tags: data.tags || [],
  type: data.type
});

// 模板市场列表项类型
export const createTemplateMarketListItemType = (data = {}) => ({
  id: data.id,
  name: data.name || '未命名',
  intro: data.intro,
  author: data.author,
  tags: data.tags || [],
  type: data.type,
  avatar: data.avatar
});
