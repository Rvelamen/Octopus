/**
 * 工作流状态管理 - Zustand Store
 * 替代 FastGPT 中的 use-context-selector
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react';

// 生成唯一ID
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// ⭐ LoopNode header 区域的估算高度（包含图标、标题、参数预览等）
// 子节点的 y 坐标不应小于此值，以避免与 header 区域重叠
const LOOP_HEADER_OFFSET = 110; // 从140减小到110，减少顶部间距

// ⭐ 循环体容器框体在 LoopNode 内部的偏移量（对应 Node.jsx 中的 margin: 0 12px 12px）
const LOOP_BODY_MARGIN_LEFT = 12;
const LOOP_BODY_MARGIN_TOP = 0;
const LOOP_BODY_MARGIN_RIGHT = 12;
const LOOP_BODY_MARGIN_BOTTOM = 8; // 从12减小到8，减少底部间距

// ⭐ 子节点在循环体内的额外内边距
const CHILD_NODE_PADDING_TOP = 8;   // 顶部额外间距（从20减小到8）
const CHILD_NODE_PADDING_LEFT = 16;  // 左侧间距

// ⭐ 碰撞检测容错范围（像素），增加此值可以让用户更容易将节点拖入循环体
const COLLISION_PADDING = 30;

/**
 * ⭐ ReactFlow 12: 重新计算 loop 节点尺寸以容纳子节点
 * 必须同步更新 measured.width/height，因为 RF12 渲染使用 measured
 */
const recalcLoopDimensions = (nodes) => {
  const loopNodeIds = new Set(nodes.filter((n) => n.type === 'loop').map((n) => n.id));
  if (loopNodeIds.size === 0) return nodes;

  return nodes.map((node) => {
    if (node.type !== 'loop') return node;

    const children = nodes.filter((n) => n.parentId === node.id);
    if (children.length === 0) {
      const w = 400;
      const h = 280;
      return {
        ...node,
        width: w,
        height: h,
        measured: { width: w, height: h },
      };
    }

    let maxX = 0;
    let maxY = 0;
    for (const child of children) {
      // ⭐ 使用更大的默认值，确保 loop 有足够空间容纳子节点
      // 大多数节点（如 LLMNode）的实际高度约为 120-160px
      const w = child.measured?.width ?? child.width ?? 200;
      const h = child.measured?.height ?? child.height ?? 150;
      maxX = Math.max(maxX, (child.position?.x || 0) + w);
      maxY = Math.max(maxY, (child.position?.y || 0) + h);
    }

    const minWidth = Math.max(400, maxX + 40);
    const minHeight = Math.max(280, maxY + 80);

    return {
      ...node,
      width: minWidth,
      height: minHeight,
      measured: { width: minWidth, height: minHeight },
    };
  });
};

/**
 * 递归清理节点数据中引用被删除节点的变量引用
 * 变量引用格式: {{nodeId.variableKey}}
 */
const cleanNodeDataRefs = (data, deletedNodeId) => {
  if (!data || typeof data !== 'object') return data;

  const regex = new RegExp(`\\{\\{${deletedNodeId}\\.[^}]+\\}\\}`, 'g');

  const cleanValue = (value) => {
    if (typeof value === 'string') {
      return value.replace(regex, '');
    }
    if (Array.isArray(value)) {
      return value.map((item) => {
        if (typeof item === 'object' && item !== null) {
          const cleaned = {};
          for (const [k, v] of Object.entries(item)) {
            cleaned[k] = cleanValue(v);
          }
          return cleaned;
        }
        return cleanValue(item);
      });
    }
    if (typeof value === 'object' && value !== null) {
      const cleaned = {};
      for (const [k, v] of Object.entries(value)) {
        cleaned[k] = cleanValue(v);
      }
      return cleaned;
    }
    return value;
  };

  return cleanValue(data);
};

// 初始状态
const initialState = {
  // 节点和边数据
  nodes: [],
  edges: [],

  // 选中状态
  selectedNodeId: null,
  selectedEdgeId: null,

  // 循环体内部子节点选中状态
  selectedLoopChildNodeId: null,
  selectedLoopChildParentId: null,

  // 画布状态
  viewport: { x: 0, y: 0, zoom: 1 },

  // 调试状态
  isDebugging: false,
  debugNodeId: null,
  debugResults: {},

  // 执行状态
  isExecuting: false,
  executionRunId: null,
  executionStatus: {}, // { nodeId: { status, output, error } }
  executionLogs: [], // [{ timestamp, nodeId, status, message }]
  executionMode: null, // null | 'run' | 'test'
  testTargetNodeId: null,

  // UI状态
  showNodeTemplates: false,
  contextMenu: null,
  isTracePanelOpen: false,
  tracePanelTab: 'trace', // 'trace' | 'test'
  testTargetNodeId: null,
  configDrawerOpen: false,
  isTestResultOpen: false,

  // 历史记录（用于撤销/重做）
  history: [],
  historyIndex: -1,
  maxHistorySize: 50,

  // 未保存变更标记
  dirty: false,

  // 跨页通信：待打开的工作流运行详情（由 WorkflowStatusFold 设置，由 Workflow 页面消费）
  pendingOpenRun: null,

  // 节点注册表（从后端获取的节点类型信息，包含 Schema）
  nodeRegistry: {},

  // 当前工作流信息（用于节点测试等跨组件调用）
  workflowId: null,
  versionId: null,

  // 工作流基本信息（用于 TabTitle 显示）
  workflowName: null,
  updatedAt: null,
};

export const useWorkflowStore = create(
  devtools(
    (set, get) => ({
      ...initialState,

      // ========== 节点操作 ==========

      // 添加节点
      addNode: (nodeData) => {
        // 如果 nodeData 已经是完整的节点结构（包含 id, type, position, data）
        if (nodeData.id && nodeData.type && nodeData.data) {
          const newNode = {
            ...nodeData,
            data: {
              ...nodeData.data,
              flowNodeType: nodeData.data.flowNodeType || nodeData.type,
            }
          };

          set((state) => {
            const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
            const newNodes = [...currentNodes, newNode];
            get().saveToHistory({ nodes: newNodes, edges: state.edges });
            return { nodes: newNodes, dirty: true };
          });

          return newNode.id;
        }

        // 兼容旧格式：nodeData 是 data 对象
        const newNode = {
          id: generateId(),
          type: nodeData.flowNodeType || 'default',
          position: nodeData.position || { x: 100, y: 100 },
          data: nodeData,
        };

        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const newNodes = [...currentNodes, newNode];
          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });

        return newNode.id;
      },

      // 更新节点
      updateNode: (nodeId, updates) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const newNodes = currentNodes.map((node) =>
            node.id === nodeId ? { ...node, ...updates, data: { ...node.data, ...updates } } : node
          );
          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });
      },

      // 删除节点
      removeNode: (nodeId) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const currentEdges = Array.isArray(state.edges) ? state.edges : [];
          let newNodes = currentNodes
            .filter((node) => node.id !== nodeId)
            .map((node) => ({
              ...node,
              data: cleanNodeDataRefs(node.data, nodeId),
            }));
          // 同时删除相关的边
          const newEdges = currentEdges.filter(
            (edge) => edge.source !== nodeId && edge.target !== nodeId
          );
          // ⭐ 删除子节点后重新计算 loop 尺寸
          newNodes = recalcLoopDimensions(newNodes);
          get().saveToHistory({ nodes: newNodes, edges: newEdges });
          return {
            nodes: newNodes,
            edges: newEdges,
            selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
            dirty: true
          };
        });
      },

      // 设置节点位置
      setNodePosition: (nodeId, position) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const newNodes = currentNodes.map((node) =>
            node.id === nodeId ? { ...node, position } : node
          );
          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });
      },

      // 设置节点尺寸（resize 时不记录历史，仅在 drag stop 时记录）
      setNodeDimensions: (nodeId, dimensions) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const newNodes = currentNodes.map((node) =>
            node.id === nodeId
              ? { ...node, width: dimensions.width, height: dimensions.height }
              : node
          );
          return { nodes: newNodes, dirty: true };
        });
      },

      // ⭐ ReactFlow 12 parentId: 将子节点绑定到父节点
      setNodeParent: (childId, parentId) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const parentNode = currentNodes.find((n) => n.id === parentId);
          const childNode = currentNodes.find((n) => n.id === childId);
          if (!parentNode || !childNode) return state;

          // 如果已经在该 parent 下，跳过
          if (childNode.parentId === parentId) return state;

          // 将 child 的 position 从绝对坐标转为相对于 parent 的坐标
          let basePosition = childNode.position;
          if (childNode.parentId) {
            // 如果已经在另一个 parent 下，先转为绝对坐标
            const oldParent = currentNodes.find((n) => n.id === childNode.parentId);
            if (oldParent) {
              basePosition = {
                x: oldParent.position.x + childNode.position.x,
                y: oldParent.position.y + childNode.position.y,
              };
            }
          }

          // ⭐ 拖入时重置到 LoopNode 内部的默认位置，确保在左上角可见区域
          // 使用固定的相对坐标，避免依赖外部计算导致的偏移
          const newPosition = {
            x: CHILD_NODE_PADDING_LEFT, // 距离左边框 16px
            y: LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP, // 距离顶部 header 区域 8px
          };

          console.log('[setNodeParent] 设置子节点初始位置', {
            childId,
            parentId,
            relativePosition: newPosition,
            parentNodePosition: parentNode.position,
            parentNodeSize: {
              width: parentNode.measured?.width ?? parentNode.width ?? 400,
              height: parentNode.measured?.height ?? parentNode.height ?? 280,
            },
          });

          // ⭐ 计算画布绝对坐标（用于 positionAbsolute）
          const absolutePosition = {
            x: parentNode.position.x + newPosition.x,
            y: parentNode.position.y + newPosition.y,
          };

          // 从当前位置移除 child
          const filteredNodes = currentNodes.filter((n) => n.id !== childId);

          // 找到 parent 的索引
          const parentIndex = filteredNodes.findIndex((n) => n.id === parentId);
          if (parentIndex === -1) return state;

          // 在 parent 后面插入 child（RF12 要求 parent 在 children 前面）
          // ⭐ 关键修复：移除 extent: 'parent'，避免 ReactFlow 自动限制导致子节点卡在边缘
          // 改用手动计算的 positionAbsolute 来控制位置
          const newChildNode = {
            ...childNode,
            parentId,
            position: newPosition, // 相对于 parent 的坐标（仅用于数据记录）
            // ⭐ 不设置 extent: 'parent'，让子节点自由定位
            // extent: undefined,  // 不限制
            // expandParent: false,  // 不自动扩展
            internals: {
              ...childNode.internals,
              // ⭐ 关键：positionAbsolute 是画布绝对坐标，ReactFlow 用此来渲染实际位置
              positionAbsolute: absolutePosition,
            },
            // ⭐ 不设置额外的 style，让 ReactFlow 使用默认的绝对定位
          };

          const newNodes = [
            ...filteredNodes.slice(0, parentIndex + 1),
            newChildNode,
            ...filteredNodes.slice(parentIndex + 1),
          ];

          const recalced = recalcLoopDimensions(newNodes);
          get().saveToHistory({ nodes: recalced, edges: state.edges });
          return { nodes: recalced, dirty: true };
        });
      },

      // ⭐ ReactFlow 12 parentId: 解除子节点与父节点的绑定
      unsetNodeParent: (childId) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const childNode = currentNodes.find((n) => n.id === childId);
          if (!childNode || !childNode.parentId) return state;

          const parentNode = currentNodes.find((n) => n.id === childNode.parentId);

          // 将 position 从相对转为绝对
          const newPosition = parentNode
            ? {
                x: parentNode.position.x + childNode.position.x,
                y: parentNode.position.y + childNode.position.y,
              }
            : childNode.position;

          const newNodes = currentNodes.map((n) =>
            n.id === childId
              ? {
                  ...n,
                  position: newPosition,
                  parentId: undefined,
                  extent: undefined,
                  expandParent: undefined,
                  internals: {
                    ...n.internals,
                    positionAbsolute: newPosition,
                  },
                }
              : n
          );

          const recalced = recalcLoopDimensions(newNodes);
          get().saveToHistory({ nodes: recalced, edges: state.edges });
          return { nodes: recalced, dirty: true };
        });
      },

      // ========== 边操作 ==========

      // 添加边
      addEdge: (edgeData) => {
        const newEdge = {
          id: generateId(),
          source: edgeData.source,
          target: edgeData.target,
          sourceHandle: edgeData.sourceHandle || `${edgeData.source}-source`,
          targetHandle: edgeData.targetHandle || `${edgeData.target}-target`,
        };

        set((state) => {
          const currentEdges = Array.isArray(state.edges) ? state.edges : [];
          
          // 检查是否已存在完全相同的边
          const exists = currentEdges.some(
            (e) => e.source === newEdge.source && e.target === newEdge.target
          );

          if (exists) return state;

          const newEdges = [...currentEdges, newEdge];
          get().saveToHistory({ nodes: state.nodes, edges: newEdges });
          return { edges: newEdges, dirty: true };
        });

        return newEdge.id;
      },

      // 删除边
      removeEdge: (edgeId) => {
        set((state) => {
          const currentEdges = Array.isArray(state.edges) ? state.edges : [];
          const newEdges = currentEdges.filter((edge) => edge.id !== edgeId);
          get().saveToHistory({ nodes: state.nodes, edges: newEdges });
          return {
            edges: newEdges,
            selectedEdgeId: state.selectedEdgeId === edgeId ? null : state.selectedEdgeId,
            dirty: true
          };
        });
      },

      // 设置节点（由 ReactFlow 内部调用，用于同步拖拽等操作）
      setNodes: (nodes) => {
        set({ nodes: Array.isArray(nodes) ? nodes : [], dirty: true });
      },

      // 设置边（由 ReactFlow 内部调用）
      setEdges: (edges) => {
        set({ edges: Array.isArray(edges) ? edges : [], dirty: true });
      },

      // ========== 选中状态 ==========

      selectNode: (nodeId) => {
        set({ selectedNodeId: nodeId, selectedEdgeId: null, selectedLoopChildNodeId: null, selectedLoopChildParentId: null });
      },

      selectEdge: (edgeId) => {
        set({ selectedEdgeId: edgeId, selectedNodeId: null });
      },

      clearSelection: () => {
        set({ selectedNodeId: null, selectedEdgeId: null });
      },

      // ========== ReactFlow 变更处理 ==========

      // 处理节点变更（拖拽、选中、调整大小等）
      onNodesChange: (changes) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];

          // ⭐ 限制 parentId 子节点的左/上/右/下边界，确保在 LoopNode 循环体容器内
          const adjustedChanges = changes.map((change) => {
            if (change.type === 'position' && change.position) {
              const node = currentNodes.find((n) => n.id === change.id);
              if (node?.parentId) {
                const parentNode = currentNodes.find((n) => n.id === node.parentId);
                if (!parentNode) return change;

                const parentW = parentNode.measured?.width ?? parentNode.width ?? 400;
                const parentH = parentNode.measured?.height ?? parentNode.height ?? 280;
                const nodeW = node.measured?.width ?? node.width ?? 200;
                const nodeH = node.measured?.height ?? node.height ?? 120;

                // ⭐ 如果坐标跳跃很大且新坐标明显超出父节点范围，说明是残留的绝对坐标，应忽略
                if (change.dragging !== true) {
                  const dx = Math.abs(change.position.x - (node.position?.x || 0));
                  const dy = Math.abs(change.position.y - (node.position?.y || 0));
                  if ((dx > 100 || dy > 100) && (change.position.x > parentW + 50 || change.position.y > parentH + 50)) {
                    console.log('[Boundary] 忽略异常坐标跳跃', {
                      nodeId: node.id,
                      oldPos: node.position,
                      newPos: change.position,
                      parentSize: { w: parentW, h: parentH },
                    });
                    return { ...change, position: node.position };
                  }
                }

                // ⭐ 边界限制：确保子节点在循环体容器内
                // 左边界：最小 10px（避免与左边框重叠）
                const newX = Math.max(10, change.position.x);
                // 上边界：最小 LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP（避免与 header 重叠）
                const newY = Math.max(LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP, change.position.y);
                // ⭐ 右边界：节点右边缘不能超过父节点右边缘 - 24px（右边距）
                const maxX = Math.max(10, parentW - nodeW - 24); // 24 = 左右 margin 各 12px
                const clampedX = Math.min(newX, maxX);
                // ⭐ 下边界：节点下边缘不能超过父节点下边缘 - LOOP_BODY_MARGIN_BOTTOM
                const maxY = Math.max(LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP, parentH - nodeH - LOOP_BODY_MARGIN_BOTTOM);
                const clampedY = Math.min(newY, maxY);

                if (clampedX !== change.position.x || clampedY !== change.position.y) {
                  console.log('[Boundary] 限制子节点位置', {
                    nodeId: node.id,
                    original: change.position.x,
                    clamped: { x: clampedX, y: clampedY },
                    bounds: { minX: 10, maxX, minY: LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP, maxY },
                    parentSize: { w: parentW, h: parentH },
                    nodeSize: { w: nodeW, h: nodeH },
                  });
                  return { ...change, position: { x: clampedX, y: clampedY } };
                }
              }
            }
            return change;
          });

          let newNodes = applyNodeChanges(adjustedChanges, currentNodes);

          // ⭐ 自动移入循环体：在拖拽结束时检测碰撞（原子处理，避免 onNodeDragStop 竞态）
          // 改进：使用更宽松的碰撞检测，考虑循环体容器的实际位置和容错范围
          for (const change of changes) {
            if (change.type === 'position' && change.position && change.dragging !== true) {
              const node = newNodes.find((n) => n.id === change.id);
              if (!node || node.parentId) continue;

              for (const loopNode of newNodes) {
                if (loopNode.type !== 'loop' || loopNode.id === node.id) continue;

                const nodeW = node.measured?.width ?? node.width ?? 150;
                const nodeH = node.measured?.height ?? node.height ?? 44;

                // ⭐ 使用节点中心点进行碰撞检测（更直观）
                const nodeCenterX = change.position.x + nodeW / 2;
                const nodeCenterY = change.position.y + nodeH / 2;

                const loopW = loopNode.measured?.width ?? loopNode.width ?? 400;
                const loopH = loopNode.measured?.height ?? loopNode.height ?? 280;

                // ⭐ 计算循环体容器的实际可用区域（考虑 margin 偏移）
                // 循环体容器在 LoopNode 内部，有 margin: 0 12px 12px
                const bodyX = loopNode.position.x + LOOP_BODY_MARGIN_LEFT;
                const bodyY = loopNode.position.y + LOOP_HEADER_OFFSET + 40; // +40 为循环体标题栏高度
                const bodyW = loopW - LOOP_BODY_MARGIN_LEFT - LOOP_BODY_MARGIN_RIGHT;
                const bodyH = loopH - LOOP_HEADER_OFFSET - 40 - LOOP_BODY_MARGIN_BOTTOM;

                // ⭐ 改进的碰撞检测：使用带容错的循环体容器边界
                // 条件1：节点中心点在循环体容器范围内（带容错）
                const isInBodyArea =
                  nodeCenterX >= bodyX - COLLISION_PADDING &&
                  nodeCenterX <= bodyX + bodyW + COLLISION_PADDING &&
                  nodeCenterY >= bodyY - COLLISION_PADDING &&
                  nodeCenterY <= bodyY + bodyH + COLLISION_PADDING;

                // 条件2：节点与 LoopNode 有足够大的重叠面积（至少 30%）
                const nodeLeft = change.position.x;
                const nodeRight = change.position.x + nodeW;
                const nodeTop = change.position.y;
                const nodeBottom = change.position.y + nodeH;

                const loopLeft = loopNode.position.x;
                const loopRight = loopNode.position.x + loopW;
                const loopTop = loopNode.position.y;
                const loopBottom = loopNode.position.y + loopH;

                const overlapLeft = Math.max(nodeLeft, loopLeft);
                const overlapRight = Math.min(nodeRight, loopRight);
                const overlapTop = Math.max(nodeTop, loopTop);
                const overlapBottom = Math.min(nodeBottom, loopBottom);

                const overlapWidth = Math.max(0, overlapRight - overlapLeft);
                const overlapHeight = Math.max(0, overlapBottom - overlapTop);
                const overlapArea = overlapWidth * overlapHeight;
                const nodeArea = nodeW * nodeH;
                const overlapRatio = nodeArea > 0 ? overlapArea / nodeArea : 0;

                // ⭐ 满足任一条件即可移入循环体
                if (isInBodyArea || overlapRatio >= 0.3) {
                  console.log(`[LoopCollision] 节点 ${node.id} 移入循环体 ${loopNode.id}`, {
                    nodeCenter: { x: nodeCenterX, y: nodeCenterY },
                    bodyArea: { x: bodyX, y: bodyY, w: bodyW, h: bodyH },
                    overlapRatio,
                    isInBodyArea,
                    loopNodePosition: loopNode.position,
                    loopNodeMeasured: { width: loopW, height: loopH },
                  });

                  // 移入循环体：设置 parentId、相对坐标，并同步 internals.positionAbsolute
                  const relX = CHILD_NODE_PADDING_LEFT;  // 左侧间距
                  const relY = LOOP_HEADER_OFFSET + CHILD_NODE_PADDING_TOP; // 顶部间距（更紧凑）

                  // ⭐ 关键：positionAbsolute 必须是画布绝对坐标（不是相对于 parent）
                  // ReactFlow 12 使用此属性来确定子节点在画布上的实际位置
                  const absoluteX = loopNode.position.x + relX;
                  const absoluteY = loopNode.position.y + relY;

                  console.log(`[LoopCollision] 计算子节点绝对坐标`, {
                    relativePosition: { x: relX, y: relY },
                    parentPosition: loopNode.position,
                    absolutePosition: { x: absoluteX, y: absoluteY },
                  });

                  newNodes = newNodes.map((n) =>
                    n.id === node.id
                      ? {
                          ...n,
                          parentId: loopNode.id,
                          position: { x: relX, y: relY }, // 相对于 parent 的坐标（仅用于数据记录）
                          // ⭐ 不设置 extent: 'parent'，避免子节点卡在边缘
                          // extent: undefined,
                          // expandParent: false,
                          internals: {
                            ...n.internals,
                            // ⭐ 关键：positionAbsolute 是画布绝对坐标，ReactFlow 用此来渲染实际位置
                            positionAbsolute: {
                              x: absoluteX,
                              y: absoluteY,
                            },
                          },
                          // ⭐ 不设置额外的 style，让 ReactFlow 使用默认定位
                        }
                      : n
                  );

                  console.log(`[LoopCollision] 设置后的子节点数据`, {
                    parentId: loopNode.id,
                    relativePosition: { x: relX, y: relY },
                    positionAbsolute: { x: absoluteX, y: absoluteY },
                  });

                  // RF12 要求 parent 节点在 children 之前
                  newNodes.sort((a, b) => {
                    const aIsChild = !!a.parentId;
                    const bIsChild = !!b.parentId;
                    if (aIsChild && !bIsChild) return 1;
                    if (!aIsChild && bIsChild) return -1;
                    return 0;
                  });

                  break;
                }
              }
            }
          }

          // ⭐ 重新计算 loop 节点尺寸，同步 measured
          newNodes = recalcLoopDimensions(newNodes);
          return { nodes: newNodes, dirty: true };
        });
      },

      // 处理边变更（连接、删除等）
      onEdgesChange: (changes) => {
        set((state) => ({
          edges: applyEdgeChanges(changes, Array.isArray(state.edges) ? state.edges : []),
          dirty: true,
        }));
      },

      // ========== 批量操作 ==========

      // 设置所有节点和边
      setNodesAndEdges: (nodes, edges) => {
        const safeNodes = Array.isArray(nodes) ? nodes : [];
        const safeEdges = Array.isArray(edges) ? edges : [];
        set({ nodes: safeNodes, edges: safeEdges });
        get().saveToHistory({ nodes: safeNodes, edges: safeEdges });
      },

      // 批量更新节点
      updateNodes: (updates) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const newNodes = currentNodes.map((node) => {
            const update = updates.find((u) => u.id === node.id);
            return update ? { ...node, ...update, data: { ...node.data, ...update } } : node;
          });
          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });
      },

      // ========== 历史记录（撤销/重做） ==========

      saveToHistory: (data) => {
        set((state) => {
          const newHistory = state.history.slice(0, state.historyIndex + 1);
          newHistory.push(data);

          // 限制历史记录大小
          if (newHistory.length > state.maxHistorySize) {
            newHistory.shift();
          }

          return {
            history: newHistory,
            historyIndex: newHistory.length - 1
          };
        });
      },

      undo: () => {
        set((state) => {
          if (state.historyIndex <= 0) return state;

          const newIndex = state.historyIndex - 1;
          const historyItem = state.history[newIndex];

          return {
            historyIndex: newIndex,
            nodes: historyItem.nodes,
            edges: historyItem.edges
          };
        });
      },

      redo: () => {
        set((state) => {
          if (state.historyIndex >= state.history.length - 1) return state;

          const newIndex = state.historyIndex + 1;
          const historyItem = state.history[newIndex];

          return {
            historyIndex: newIndex,
            nodes: historyItem.nodes,
            edges: historyItem.edges
          };
        });
      },

      canUndo: () => {
        const state = get();
        return state.historyIndex > 0;
      },

      canRedo: () => {
        const state = get();
        return state.historyIndex < state.history.length - 1;
      },

      // ========== 调试功能 ==========

      startDebugging: () => {
        set({ isDebugging: true, debugResults: {} });
      },

      stopDebugging: () => {
        set({ isDebugging: false, debugNodeId: null, debugResults: {} });
      },

      setDebugNodeId: (nodeId) => {
        set({ debugNodeId: nodeId });
      },

      setDebugResult: (nodeId, result) => {
        set((state) => ({
          debugResults: {
            ...state.debugResults,
            [nodeId]: result
          }
        }));
      },

      // ========== 执行状态 ==========

      startExecution: (runId) => {
        set({
          isExecuting: true,
          executionRunId: runId,
          executionStatus: {},
          executionLogs: [{ timestamp: Date.now(), status: 'started', message: '执行开始' }],
        });
      },

      updateExecutionNode: (nodeId, status, output = {}, input = {}, duration = null) => {
        set((state) => ({
          executionStatus: {
            ...state.executionStatus,
            [nodeId]: { status, output, input, timestamp: Date.now(), duration },
          },
          executionLogs: [
            ...state.executionLogs,
            { timestamp: Date.now(), nodeId, status, message: `节点 ${nodeId}: ${status}` },
          ],
        }));
      },

      setExecutionMode: (mode, targetNodeId = null) => {
        set({ executionMode: mode, testTargetNodeId: targetNodeId });
      },

      stopExecution: () => {
        set({
          isExecuting: false,
          executionRunId: null,
          executionStatus: {},
          executionLogs: [],
        });
      },

      finishExecution: () => {
        set({ isExecuting: false, executionRunId: null });
      },

      // ========== UI 状态 ==========

      setShowNodeTemplates: (show) => {
        set({ showNodeTemplates: show });
      },

      setContextMenu: (menu) => {
        set({ contextMenu: menu });
      },

      setTracePanelOpen: (open) => {
        set({ isTracePanelOpen: open });
      },

      setTracePanelTab: (tab) => {
        set({ tracePanelTab: tab });
      },

      setTestTargetNodeId: (nodeId) => {
        set({ testTargetNodeId: nodeId });
      },

      setConfigDrawerOpen: (open) => {
        set({ configDrawerOpen: open });
      },

      setTestResultOpen: (open) => {
        set({ isTestResultOpen: open });
      },

      // ========== 画布状态 ==========

      setViewport: (viewport) => {
        set({ viewport });
      },

      // ========== 导入/导出 ==========

      exportWorkflow: () => {
        const state = get();
        const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
        const currentEdges = Array.isArray(state.edges) ? state.edges : [];
        return {
          nodes: currentNodes.map((node) => ({
            nodeId: node.id,
            flowNodeType: node.data?.flowNodeType,
            name: node.data?.name,
            position: node.position,
            inputs: node.data?.inputs || [],
            outputs: node.data?.outputs || []
          })),
          edges: currentEdges.map((edge) => ({
            source: edge.source,
            sourceHandle: edge.sourceHandle,
            target: edge.target,
            targetHandle: edge.targetHandle
          }))
        };
      },

      importWorkflow: (data) => {
        const nodes = (data.nodes || []).map((node) => ({
          id: node.nodeId || generateId(),
          type: node.flowNodeType || 'default',
          position: node.position || { x: 100, y: 100 },
          data: node
        }));

        const edges = (data.edges || []).map((edge) => ({
          id: generateId(),
          ...edge
        }));

        set({
          nodes,
          edges,
          history: [{ nodes, edges }],
          historyIndex: 0
        });
      },

      // ========== 未保存变更标记 ==========

      markSaved: () => {
        set({ dirty: false });
      },

      // ========== 跨页通信 ==========

      setPendingOpenRun: (runInfo) => {
        set({ pendingOpenRun: runInfo });
      },

      clearPendingOpenRun: () => {
        set({ pendingOpenRun: null });
      },

      // ========== 重置 ==========

      reset: () => {
        set({
          ...initialState,
          // 保留视口状态、跨页通信状态和节点注册表
          viewport: get().viewport,
          pendingOpenRun: get().pendingOpenRun,
          nodeRegistry: get().nodeRegistry,
        });
      },

      // ========== 循环体操作 ==========

      // ⭐ parentId 方案: 将节点移入循环体（通过 setNodeParent）
      moveNodeIntoLoop: (nodeId, loopNodeId) => {
        get().setNodeParent(nodeId, loopNodeId);
      },

      // ⭐ parentId 方案: 将节点从循环体移出到主画布（通过 unsetNodeParent）
      moveNodeOutOfLoop: (nodeId, _loopNodeId, position) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const childNode = currentNodes.find((n) => n.id === nodeId);
          if (!childNode || !childNode.parentId) return state;

          const parentNode = currentNodes.find((n) => n.id === childNode.parentId);

          // 将 position 从相对转为绝对，若指定了 position 则使用指定值
          const newPosition = position || (parentNode
            ? {
                x: parentNode.position.x + childNode.position.x,
                y: parentNode.position.y + childNode.position.y,
              }
            : childNode.position);

          const newNodes = currentNodes.map((n) =>
            n.id === nodeId
              ? {
                  ...n,
                  position: newPosition,
                  parentId: undefined,
                  extent: undefined,
                  expandParent: undefined,
                  internals: {
                    ...n.internals,
                    positionAbsolute: newPosition,
                  },
                }
              : n
          );

          const recalced = recalcLoopDimensions(newNodes);
          get().saveToHistory({ nodes: recalced, edges: state.edges });
          return { nodes: recalced, dirty: true };
        });
      },

      // ========== 循环体内部操作 ==========

      // 更新循环体内部节点
      updateLoopChildNodes: (loopNodeId, updater) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const loopNode = currentNodes.find((n) => n.id === loopNodeId);
          if (!loopNode || loopNode.type !== 'loop') return state;

          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const newChildNodes = updater(currentChildren.nodes || []);
          const newChildren = { ...currentChildren, nodes: newChildNodes };

          const newNodes = currentNodes.map((n) =>
            n.id === loopNodeId
              ? { ...n, data: { ...n.data, children: newChildren } }
              : n
          );

          return { nodes: newNodes, dirty: true };
        });
      },

      // 更新循环体内部边
      updateLoopChildEdges: (loopNodeId, updater) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const loopNode = currentNodes.find((n) => n.id === loopNodeId);
          if (!loopNode || loopNode.type !== 'loop') return state;

          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const newChildEdges = updater(currentChildren.edges || []);
          const newChildren = { ...currentChildren, edges: newChildEdges };

          const newNodes = currentNodes.map((n) =>
            n.id === loopNodeId
              ? { ...n, data: { ...n.data, children: newChildren } }
              : n
          );

          return { nodes: newNodes, dirty: true };
        });
      },

      // 添加边到循环体内部
      addLoopChildEdge: (loopNodeId, edgeData) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const loopNode = currentNodes.find((n) => n.id === loopNodeId);
          if (!loopNode || loopNode.type !== 'loop') return state;

          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const newEdge = {
            id: generateId(),
            source: edgeData.source,
            target: edgeData.target,
            sourceHandle: edgeData.sourceHandle || `${edgeData.source}-source`,
            targetHandle: edgeData.targetHandle || `${edgeData.target}-target`,
          };

          const exists = (currentChildren.edges || []).some(
            (e) => e.source === newEdge.source && e.target === newEdge.target
          );
          if (exists) return state;

          const newChildren = {
            ...currentChildren,
            edges: [...(currentChildren.edges || []), newEdge],
          };

          const newNodes = currentNodes.map((n) =>
            n.id === loopNodeId
              ? { ...n, data: { ...n.data, children: newChildren } }
              : n
          );

          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });
      },

      // ========== 循环体子节点操作 ==========

      // 选中循环体内部子节点
      selectLoopChildNode: (childNodeId, parentLoopId) => {
        set({
          selectedLoopChildNodeId: childNodeId,
          selectedLoopChildParentId: parentLoopId,
          selectedNodeId: null,
        });
      },

      // 更新循环体内部子节点的 data
      updateLoopChildNodeData: (parentLoopId, childNodeId, newData) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const loopNode = currentNodes.find((n) => n.id === parentLoopId);
          if (!loopNode) return state;

          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const newChildNodes = (currentChildren.nodes || []).map((n) =>
            n.id === childNodeId
              ? { ...n, data: { ...n.data, ...newData } }
              : n
          );
          const newChildren = { ...currentChildren, nodes: newChildNodes };

          const newNodes = currentNodes.map((n) =>
            n.id === parentLoopId
              ? { ...n, data: { ...n.data, children: newChildren } }
              : n
          );

          get().saveToHistory({ nodes: newNodes, edges: state.edges });
          return { nodes: newNodes, dirty: true };
        });
      },

      // 获取当前选中的子节点信息
      getSelectedChildNode: () => {
        const state = get();
        if (!state.selectedLoopChildNodeId || !state.selectedLoopChildParentId) return null;

        const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
        const loopNode = currentNodes.find((n) => n.id === state.selectedLoopChildParentId);
        if (!loopNode) return null;

        const children = loopNode.data?.children || { nodes: [], edges: [] };
        const childNode = (children.nodes || []).find(
          (n) => n.id === state.selectedLoopChildNodeId
        );
        return childNode || null;
      },

      // ========== 工作流信息 ==========

      setWorkflowInfo: (workflowId, versionId) => {
        set({ workflowId, versionId });
      },

      // 设置工作流基本信息（名称和更新时间）
      setWorkflowBasicInfo: (name, updatedAt) => {
        set({ workflowName: name, updatedAt });
      },

      // 更新工作流名称
      updateWorkflowName: (name) => {
        set({ workflowName: name, updatedAt: new Date().toISOString() });
      },

      // ========== 节点注册表 ==========

      setNodeRegistry: (registry) => {
        set({ nodeRegistry: registry });
      },

      // 获取指定节点类型的 Schema
      getNodeSchema: (nodeType) => {
        const registry = get().nodeRegistry;
        return registry[nodeType]?.configSchema || {};
      },
    }),
    { name: 'WorkflowStore' }
  )
);

export default useWorkflowStore;
