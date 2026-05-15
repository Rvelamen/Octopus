/**
 * 变量引用解析工具
 * 处理 {{nodeId.outputKey}} 格式的变量引用
 */

// 变量引用的正则表达式
const VARIABLE_REF_REGEX = /^\{\{([^.]+)\.([^}]+)\}\}$/;

/**
 * 判断字符串是否为变量引用
 * @param {string} str
 * @returns {boolean}
 */
export function isVariableRef(str) {
  if (typeof str !== 'string') return false;
  return VARIABLE_REF_REGEX.test(str.trim());
}

/**
 * 解析变量引用
 * @param {string} str - 变量引用字符串，如 {{nodeId.outputKey}}
 * @returns {{ nodeId: string, outputKey: string } | null}
 */
export function parseVariableRef(str) {
  if (!str || !isVariableRef(str)) {
    return null;
  }
  const match = str.trim().match(VARIABLE_REF_REGEX);
  if (!match) return null;
  return {
    nodeId: match[1],
    outputKey: match[2],
  };
}

/**
 * 构建变量引用字符串
 * @param {string} nodeId
 * @param {string} outputKey
 * @returns {string}
 */
export function buildVariableRef(nodeId, outputKey) {
  return `{{${nodeId}.${outputKey}}}`;
}

/**
 * 从输入值中提取变量引用
 * 支持直接输入 {{nodeId.outputKey}} 格式
 * @param {string} value
 * @returns {{ type: 'reference', nodeId: string, outputKey: string } | { type: 'literal', value: string }}
 */
export function extractVariable(value) {
  if (!value || typeof value !== 'string') {
    return { type: 'literal', value: String(value || '') };
  }

  const trimmed = value.trim();
  const parsed = parseVariableRef(trimmed);

  if (parsed) {
    return {
      type: 'reference',
      nodeId: parsed.nodeId,
      outputKey: parsed.outputKey,
    };
  }

  return { type: 'literal', value: trimmed };
}

/**
 * 解析变量引用为可显示的路径
 * @param {string} nodeId
 * @param {string} outputKey
 * @param {Array} nodes - 所有节点列表
 * @returns {string}
 */
export function resolveVariableDisplay(nodeId, outputKey, nodes) {
  if (!nodes || !Array.isArray(nodes)) {
    return `${nodeId}.${outputKey}`;
  }

  const node = nodes.find((n) => n.id === nodeId || n.data?.id === nodeId);
  const nodeName = node?.data?.name || node?.name || node?.id || nodeId;
  return `${nodeName}.${outputKey}`;
}

/**
 * 获取节点的可引用输出列表
 * @param {Object} node - 节点对象
 * @returns {Array<{key: string, label: string, type: string}>}
 */
export function getNodeOutputs(node) {
  if (!node) return [];

  const nodeData = node.data || node;
  const outputs = nodeData.outputs || [];

  return outputs.map((output) => ({
    key: output.key,
    label: output.label || output.key,
    type: output.valueType || output.type || 'string',
  }));
}

/**
 * 获取直接连接的上游节点ID集合
 * @param {string} currentNodeId - 当前节点 ID
 * @param {Array} edges - 所有边
 * @returns {Set<string>}
 */
const getConnectedUpstreamNodeIds = (currentNodeId, edges) => {
  const upstreamNodeIds = new Set();
  if (!edges || !Array.isArray(edges)) return upstreamNodeIds;
  
  edges.forEach((edge) => {
    if (edge.target === currentNodeId) {
      upstreamNodeIds.add(edge.source);
    }
  });
  
  return upstreamNodeIds;
};

/**
 * 获取所有可引用的节点列表
 * 默认情况下，只返回通过连接线直接连接的上游节点
 * 如果 requireConnection 为 false，则返回所有上游节点（排除当前节点和下游节点）
 * @param {Array} nodes - 所有节点
 * @param {string} currentNodeId - 当前节点 ID
 * @param {Array} edges - 所有边
 * @param {boolean} requireConnection - 是否要求必须有连接线，默认为 true
 * @returns {Array}
 */
export function getAvailableNodes(nodes, currentNodeId, edges = [], requireConnection = true) {
  if (!nodes || !Array.isArray(nodes)) return [];

  // 如果要求必须有连接线，则只返回直接连接的上游节点
  if (requireConnection) {
    const upstreamNodeIds = getConnectedUpstreamNodeIds(currentNodeId, edges);
    return nodes.filter((node) => {
      const nodeId = node.id || node.data?.id;
      return upstreamNodeIds.has(nodeId);
    });
  }

  // 否则使用原有逻辑：找出当前节点的所有下游节点（直接和间接）
  const downstreamNodes = new Set();
  const findDownstream = (nodeId) => {
    edges.forEach((edge) => {
      if (edge.source === nodeId && !downstreamNodes.has(edge.target)) {
        downstreamNodes.add(edge.target);
        findDownstream(edge.target);
      }
    });
  };
  findDownstream(currentNodeId);

  return nodes.filter((node) => {
    const nodeId = node.id || node.data?.id;
    // 排除当前节点和下游节点
    return nodeId !== currentNodeId && !downstreamNodes.has(nodeId);
  });
}

/**
 * 验证变量引用是否有效
 * @param {string} nodeId
 * @param {string} outputKey
 * @param {Array} nodes
 * @returns {{ valid: boolean, error?: string }}
 */
export function validateVariableRef(nodeId, outputKey, nodes) {
  if (!nodeId) {
    return { valid: false, error: '未选择节点' };
  }

  const node = nodes.find((n) => (n.id === nodeId || n.data?.id === nodeId));
  if (!node) {
    return { valid: false, error: `节点 ${nodeId} 不存在` };
  }

  const outputs = getNodeOutputs(node);
  const outputExists = outputs.some((o) => o.key === outputKey);
  if (!outputExists) {
    return { valid: false, error: `节点 ${node.data?.name || nodeId} 没有输出 ${outputKey}` };
  }

  return { valid: true };
}

/**
 * 格式化变量引用用于显示
 * @param {string} value
 * @param {Array} nodes
 * @returns {string}
 */
export function formatVariableRefForDisplay(value, nodes) {
  const parsed = parseVariableRef(value);
  if (!parsed) {
    return value;
  }
  return resolveVariableDisplay(parsed.nodeId, parsed.outputKey, nodes);
}

/**
 * 替换文本中的变量引用
 * @param {string} text - 包含 {{}} 占位符的文本
 * @param {Object} variables - 变量值映射 { 'nodeId.outputKey': value }
 * @returns {string}
 */
export function resolveVariablesInText(text, variables) {
  if (!text || typeof text !== 'string') return text;

  return text.replace(VARIABLE_REF_REGEX, (match, nodeId, outputKey) => {
    const key = `${nodeId}.${outputKey}`;
    const value = variables[key];
    if (value !== undefined) {
      return typeof value === 'object' ? JSON.stringify(value) : String(value);
    }
    return match; // 保持原样
  });
}

/**
 * 提取文本中的所有变量引用
 * @param {string} text
 * @returns {Array<{nodeId: string, outputKey: string}>}
 */
export function extractAllVariableRefs(text) {
  if (!text || typeof text !== 'string') return [];

  const refs = [];
  const regex = /\{\{([^.]+)\.([^}]+)\}\}/g;
  let match;

  while ((match = regex.exec(text)) !== null) {
    refs.push({
      nodeId: match[1],
      outputKey: match[2],
    });
  }

  return refs;
}

export default {
  isVariableRef,
  parseVariableRef,
  buildVariableRef,
  extractVariable,
  resolveVariableDisplay,
  getNodeOutputs,
  getAvailableNodes,
  validateVariableRef,
  formatVariableRefForDisplay,
  resolveVariablesInText,
  extractAllVariableRefs,
};
