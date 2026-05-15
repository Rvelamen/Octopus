/**
 * 工作流状态管理 - Zustand Store
 * 替代 FastGPT 中的 use-context-selector
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react';

// 生成唯一ID
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

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
          const newNodes = currentNodes
            .filter((node) => node.id !== nodeId)
            .map((node) => ({
              ...node,
              data: cleanNodeDataRefs(node.data, nodeId),
            }));
          // 同时删除相关的边
          const newEdges = currentEdges.filter(
            (edge) => edge.source !== nodeId && edge.target !== nodeId
          );
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

      // ========== 边操作 ==========

      // 添加边
      addEdge: (edgeData) => {
        const newEdge = {
          id: generateId(),
          source: edgeData.source,
          target: edgeData.target,
          sourceHandle: `${edgeData.source}-source`,
          targetHandle: `${edgeData.target}-target`,
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
        set((state) => ({
          nodes: applyNodeChanges(changes, Array.isArray(state.nodes) ? state.nodes : []),
          dirty: true,
        }));
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

      // 将节点移入循环体
      moveNodeIntoLoop: (nodeId, loopNodeId) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const currentEdges = Array.isArray(state.edges) ? state.edges : [];
          const nodeToMove = currentNodes.find((n) => n.id === nodeId);
          const loopNode = currentNodes.find((n) => n.id === loopNodeId);

          if (!nodeToMove || !loopNode) return state;
          if (nodeToMove.type === 'workflowStart' || nodeToMove.type === 'workflowEnd') return state;
          if (loopNode.type !== 'loop') return state;

          // 从主画布移除该节点
          const remainingNodes = currentNodes.filter((n) => n.id !== nodeId);

          // 分离与该节点相关的边（移入 loop 内部）
          const edgesToMove = currentEdges.filter((e) => e.source === nodeId || e.target === nodeId);
          const remainingEdges = currentEdges.filter((e) => e.source !== nodeId && e.target !== nodeId);

          // 将该节点加入循环体的 children
          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const newNode = {
            ...nodeToMove,
            position: { x: 10, y: 10 },
          };
          const newChildren = {
            ...currentChildren,
            nodes: [...(currentChildren.nodes || []), newNode],
            edges: [...(currentChildren.edges || []), ...edgesToMove],
          };

          // 更新循环节点
          const newNodes = remainingNodes.map((n) =>
            n.id === loopNodeId
              ? { ...n, data: { ...n.data, children: newChildren } }
              : n
          );

          get().saveToHistory({ nodes: newNodes, edges: remainingEdges });
          return { nodes: newNodes, edges: remainingEdges, dirty: true };
        });
      },

      // 将节点从循环体移出到主画布
      moveNodeOutOfLoop: (nodeId, loopNodeId, position) => {
        set((state) => {
          const currentNodes = Array.isArray(state.nodes) ? state.nodes : [];
          const currentEdges = Array.isArray(state.edges) ? state.edges : [];
          const loopNode = currentNodes.find((n) => n.id === loopNodeId);

          if (!loopNode) return state;

          const currentChildren = loopNode.data?.children || { nodes: [], edges: [] };
          const childNode = (currentChildren.nodes || []).find((n) => n.id === nodeId);

          if (!childNode) return state;

          // 从循环体移除该节点，同时分离相关边
          const newChildNodes = (currentChildren.nodes || []).filter((n) => n.id !== nodeId);
          const edgesToMove = (currentChildren.edges || []).filter((e) => e.source === nodeId || e.target === nodeId);
          const remainingChildEdges = (currentChildren.edges || []).filter((e) => e.source !== nodeId && e.target !== nodeId);
          const newChildren = {
            ...currentChildren,
            nodes: newChildNodes,
            edges: remainingChildEdges,
          };

          // 更新循环节点并添加节点回主画布
          const nodeToAdd = {
            ...childNode,
            position: position || childNode.position,
          };

          const newNodes = currentNodes
            .map((n) =>
              n.id === loopNodeId
                ? { ...n, data: { ...n.data, children: newChildren } }
                : n
            )
            .concat(nodeToAdd);

          const newEdges = [...currentEdges, ...edgesToMove];

          get().saveToHistory({ nodes: newNodes, edges: newEdges });
          return { nodes: newNodes, edges: newEdges, dirty: true };
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
