/**
 * 工作流工具函数
 */

// 导出连接点工具函数
export * from './handle';

/**
 * 生成唯一ID
 */
export const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

/**
 * 解析变量引用
 * 格式: {{nodeId.outputKey}}
 */
export const parseVariableReference = (value) => {
  if (typeof value !== 'string') return null;

  const match = value.match(/^\{\{(.+?)\.(.+?)\}\}$/);
  if (!match) return null;

  return {
    nodeId: match[1],
    outputKey: match[2]
  };
};

/**
 * 创建变量引用字符串
 */
export const createVariableReference = (nodeId, outputKey) => {
  return `{{${nodeId}.${outputKey}}}`;
};

/**
 * 获取节点输出值
 */
export const getNodeOutputValue = (nodeId, outputKey, nodeOutputs) => {
  const nodeOutput = nodeOutputs[nodeId];
  if (!nodeOutput) return undefined;

  return nodeOutput[outputKey];
};

/**
 * 替换变量引用
 */
export const replaceVariableReferences = (text, nodeOutputs) => {
  if (typeof text !== 'string') return text;

  return text.replace(/\{\{(.+?)\.(.+?)\}\}/g, (match, nodeId, outputKey) => {
    const value = getNodeOutputValue(nodeId, outputKey, nodeOutputs);
    return value !== undefined ? String(value) : match;
  });
};

/**
 * 拓扑排序 - 确定节点执行顺序
 * ⭐ 改进版：支持循环节点（Loop Node），将其视为超级节点，忽略内部连接
 */
export const topologicalSort = (nodes, edges) => {
  // 1️⃣ 识别 Loop 节点和它们的子节点
  const loopNodeIds = new Set(nodes.filter((n) => n.type === 'loop').map((n) => n.id));
  const childNodeIds = new Set(
    nodes.filter((n) => n.parentId && loopNodeIds.has(n.parentId)).map((n) => n.id)
  );

  // 2️⃣ 过滤出需要参与拓扑排序的"有效节点"
  //    - 所有非子节点的普通节点
  //    - Loop 节点本身（作为超级节点代表整个循环体）
  const effectiveNodes = nodes.filter((n) => !childNodeIds.has(n.id));

  // 3️⃣ 过滤出"有效边"
  //    排除以下类型的边：
  //    a) 涉及子节点的边（循环体内部连接）
  //    b) 涉及 body-start / body-end handles 的边（循环体入口/出口）
  const isLoopInternalEdge = (edge) => {
    const { source, target, sourceHandle, targetHandle } = edge;

    // 如果 source 或 target 是子节点，这是内部连接
    if (childNodeIds.has(source) || childNodeIds.has(target)) {
      return true;
    }

    // 如果涉及 body-start 或 body-end handle，这是循环体的入口/出口连接
    if (
      sourceHandle?.includes('body-start') ||
      sourceHandle?.includes('body-end') ||
      targetHandle?.includes('body-start') ||
      targetHandle?.includes('body-end')
    ) {
      return true;
    }

    return false;
  };

  const effectiveEdges = edges.filter((edge) => !isLoopInternalEdge(edge));

  // 4️⃣ 使用过滤后的节点和边进行拓扑排序
  const graph = new Map();
  const inDegree = new Map();

  // 初始化图
  effectiveNodes.forEach((node) => {
    graph.set(node.id, []);
    inDegree.set(node.id, 0);
  });

  // 构建图（只使用有效边）
  effectiveEdges.forEach((edge) => {
    // 确保边的两端都在有效节点中
    if (graph.has(edge.source) && graph.has(edge.target)) {
      graph.get(edge.source).push(edge.target);
      inDegree.set(edge.target, inDegree.get(edge.target) + 1);
    }
  });

  // 找到入度为0的节点
  const queue = [];
  effectiveNodes.forEach((node) => {
    if (inDegree.get(node.id) === 0) {
      queue.push(node.id);
    }
  });

  const result = [];

  while (queue.length > 0) {
    const nodeId = queue.shift();
    result.push(nodeId);

    const neighbors = graph.get(nodeId);
    neighbors.forEach((neighborId) => {
      const newInDegree = inDegree.get(neighborId) - 1;
      inDegree.set(neighborId, newInDegree);

      if (newInDegree === 0) {
        queue.push(neighborId);
      }
    });
  }

  // 检查是否有环（基于有效节点的数量）
  if (result.length !== effectiveNodes.length) {
    throw new Error('工作流中存在循环依赖');
  }

  return result;
};

/**
 * 验证工作流
 */
export const validateWorkflow = (nodes, edges) => {
  const errors = [];

  // 检查是否有开始节点
  const hasStartNode = nodes.some((node) => node.type === 'workflowStart');
  if (!hasStartNode) {
    errors.push('工作流缺少开始节点');
  }

  // 检查是否有未连接的节点
  const connectedNodeIds = new Set();
  edges.forEach((edge) => {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  });

  nodes.forEach((node) => {
    if (!connectedNodeIds.has(node.id) && node.type !== 'workflowStart') {
      errors.push(`节点 "${node.data?.name || node.id}" 未连接`);
    }
  });

  // 检查循环依赖
  try {
    topologicalSort(nodes, edges);
  } catch (error) {
    errors.push(error.message);
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * 导出工作流为 JSON
 */
export const exportWorkflow = (nodes, edges) => {
  return {
    version: '1.0',
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: node.data
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle
    }))
  };
};

/**
 * 从 JSON 导入工作流
 */
export const importWorkflow = (json) => {
  try {
    const data = typeof json === 'string' ? JSON.parse(json) : json;

    return {
      nodes: data.nodes || [],
      edges: data.edges || []
    };
  } catch (error) {
    throw new Error('无效的工作流数据: ' + error.message);
  }
};
