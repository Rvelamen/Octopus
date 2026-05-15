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
 */
export const topologicalSort = (nodes, edges) => {
  const graph = new Map();
  const inDegree = new Map();

  // 初始化
  nodes.forEach((node) => {
    graph.set(node.id, []);
    inDegree.set(node.id, 0);
  });

  // 构建图
  edges.forEach((edge) => {
    graph.get(edge.source).push(edge.target);
    inDegree.set(edge.target, inDegree.get(edge.target) + 1);
  });

  // 找到入度为0的节点
  const queue = [];
  nodes.forEach((node) => {
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

  // 检查是否有环
  if (result.length !== nodes.length) {
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
