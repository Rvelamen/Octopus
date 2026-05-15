/**
 * 连接点(Handle)工具函数
 * 用于管理多输入/多输出连接点
 */

import { Position } from '@xyflow/react';

/**
 * 生成连接点ID
 * @param {string} nodeId - 节点ID
 * @param {string} type - 连接点类型 ('source' | 'target')
 * @param {string} key - 连接点标识key
 * @returns {string} 连接点ID
 */
export const getHandleId = (nodeId, type, key) => {
  return `${nodeId}-${type}-${key}`;
};

/**
 * 解析连接点ID
 * @param {string} handleId - 连接点ID
 * @returns {Object} { nodeId, type, key }
 */
export const parseHandleId = (handleId) => {
  if (!handleId) return null;
  const parts = handleId.split('-');
  if (parts.length < 3) return null;
  
  return {
    nodeId: parts[0],
    type: parts[1], // 'source' | 'target'
    key: parts.slice(2).join('-')
  };
};

/**
 * 获取输入连接点配置
 * @param {Object} input - 输入项配置
 * @param {number} index - 输入项索引
 * @param {number} total - 输入项总数
 * @returns {Object} 连接点位置和样式配置
 */
export const getInputHandleConfig = (input, index, total) => {
  // 默认左侧分布，垂直居中排列
  const spacing = total > 1 ? 40 : 0;
  const startY = -((total - 1) * spacing) / 2;
  
  return {
    position: Position.Left,
    offsetY: startY + index * spacing,
    style: {
      width: '12px',
      height: '12px',
      background: '#fff',
      border: '2px solid #3182ce',
      borderRadius: '50%',
      zIndex: 10
    }
  };
};

/**
 * 获取输出连接点配置
 * @param {Object} output - 输出项配置
 * @param {number} index - 输出项索引
 * @param {number} total - 输出项总数
 * @returns {Object} 连接点位置和样式配置
 */
export const getOutputHandleConfig = (output, index, total) => {
  // 默认右侧分布，垂直居中排列
  const spacing = total > 1 ? 40 : 0;
  const startY = -((total - 1) * spacing) / 2;
  
  return {
    position: Position.Right,
    offsetY: startY + index * spacing,
    style: {
      width: '12px',
      height: '12px',
      background: '#fff',
      border: '2px solid #38a169',
      borderRadius: '50%',
      zIndex: 10
    }
  };
};

/**
 * 获取条件分支输出连接点配置（用于IfElse节点）
 * @param {Object} condition - 条件配置
 * @param {number} index - 条件索引
 * @param {number} total - 条件总数
 * @returns {Object} 连接点配置
 */
export const getConditionHandleConfig = (condition, index, total) => {
  const spacing = total > 1 ? 50 : 0;
  const startY = -((total - 1) * spacing) / 2;
  
  return {
    position: Position.Right,
    offsetY: startY + index * spacing,
    label: condition.label || `条件${index + 1}`,
    style: {
      width: '14px',
      height: '14px',
      background: condition.isElse ? '#fc8181' : '#68d391',
      border: '2px solid #fff',
      borderRadius: '50%',
      zIndex: 10,
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }
  };
};

/**
 * 计算连接点垂直位置
 * @param {number} index - 当前索引
 * @param {number} total - 总数
 * @param {number} itemHeight - 每项高度
 * @returns {number} 垂直偏移量
 */
export const calculateHandleOffsetY = (index, total, itemHeight = 40) => {
  if (total <= 1) return 0;
  const totalHeight = (total - 1) * itemHeight;
  return -totalHeight / 2 + index * itemHeight;
};

/**
 * 检查连接点是否已连接
 * @param {Array} edges - 所有边
 * @param {string} handleId - 连接点ID
 * @param {string} type - 'source' | 'target'
 * @returns {boolean}
 */
export const isHandleConnected = (edges, handleId, type) => {
  if (!edges || !Array.isArray(edges) || !handleId) return false;
  
  return edges.some(edge => {
    if (type === 'source') {
      return edge.sourceHandle === handleId;
    }
    return edge.targetHandle === handleId;
  });
};

/**
 * 获取节点已连接的输入连接点列表
 * @param {Array} edges - 所有边
 * @param {string} nodeId - 节点ID
 * @returns {Array} 已连接的输入handleId列表
 */
export const getConnectedInputHandles = (edges, nodeId) => {
  if (!edges || !Array.isArray(edges) || !nodeId) return [];
  return edges
    .filter(edge => edge.target === nodeId)
    .map(edge => edge.targetHandle)
    .filter(Boolean);
};

/**
 * 获取节点已连接的输出连接点列表
 * @param {Array} edges - 所有边
 * @param {string} nodeId - 节点ID
 * @returns {Array} 已连接的输出handleId列表
 */
export const getConnectedOutputHandles = (edges, nodeId) => {
  if (!edges || !Array.isArray(edges) || !nodeId) return [];
  return edges
    .filter(edge => edge.source === nodeId)
    .map(edge => edge.sourceHandle)
    .filter(Boolean);
};

/**
 * 获取连接点标签
 * @param {Object} output - 输出项
 * @param {number} index - 索引
 * @returns {string} 标签文本
 */
export const getHandleLabel = (output, index) => {
  if (output.label) return output.label;
  if (output.key) return output.key;
  return `输出${index + 1}`;
};

/**
 * 获取条件分支标签（用于IfElse节点）
 * @param {number} index - 条件索引
 * @param {boolean} isElse - 是否为else分支
 * @returns {string} 标签
 */
export const getElseIfLabel = (index, isElse = false) => {
  if (isElse) return 'else';
  if (index === 0) return 'if';
  return `elseIf${index}`;
};
