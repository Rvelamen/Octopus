/**
 * 工作流边类型定义
 */

export interface StoreEdgeItem {
  source?: string;
  sourceHandle?: string;
  target?: string;
  targetHandle?: string;
}

export interface RuntimeEdgeItem extends StoreEdgeItem {
  status: "waiting" | "active" | "skipped";
}

export const createStoreEdgeItemType = (data: Partial<StoreEdgeItem> = {}): StoreEdgeItem => ({
  source: data.source,
  sourceHandle: data.sourceHandle,
  target: data.target,
  targetHandle: data.targetHandle,
});

export const createRuntimeEdgeItemType = (data: Partial<RuntimeEdgeItem> = {}): RuntimeEdgeItem => ({
  ...createStoreEdgeItemType(data),
  status: data.status || "waiting",
});
