/**
 * 工作流边类型定义
 */

// 存储边项类型
export const createStoreEdgeItemType = (data = {}) => ({
  source: data.source,
  sourceHandle: data.sourceHandle,
  target: data.target,
  targetHandle: data.targetHandle
});

// 运行时边项类型
export const createRuntimeEdgeItemType = (data = {}) => ({
  ...createStoreEdgeItemType(data),
  status: data.status || 'waiting' // 'waiting' | 'active' | 'skipped'
});
