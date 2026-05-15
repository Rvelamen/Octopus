/**
 * 表达式编辑器字段组件
 * 支持 compact 紧凑模式（用于 Space.Compact 布局）
 * 支持下拉列表式变量选择器
 */

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Variable,
  X,
  Search,
  User,
  FolderOpen,
  Settings,
  ChevronRight,
} from 'lucide-react';

// 变量类型映射
export const VARIABLE_TYPES = {
  text: { label: '文本', color: '#6366f1' },
  number: { label: '数字', color: '#10b981' },
  boolean: { label: '布尔', color: '#f59e0b' },
  array: { label: '数组', color: '#ec4899' },
  object: { label: '对象', color: '#8b5cf6' },
  datetime: { label: '时间', color: '#3b82f6' },
};

// 类型兼容性映射 - 用于类型校验
const TYPE_COMPATIBILITY = {
  string: ['string', 'text'],
  integer: ['integer', 'number'],
  number: ['number', 'integer'],
  boolean: ['boolean'],
  time: ['time', 'datetime'],
  object: ['object'],
  array: ['array'],
  file: ['file'],
  filedefault: ['file'],
  fileimage: ['file'],
  filesvg: ['file'],
  fileaudio: ['file'],
  filevideo: ['file'],
  filevoice: ['file'],
  filedoc: ['file'],
  fileppt: ['file'],
  fileexcel: ['file'],
  filetxt: ['file'],
  filecode: ['file'],
  filezip: ['file'],
  arraystring: ['array'],
  arrayinteger: ['array'],
  arraynumber: ['array'],
  arrayboolean: ['array'],
  arraytime: ['array'],
  arrayobject: ['array'],
  arrayfile: ['array'],
};

/**
 * 检查类型是否兼容
 * @param {string} sourceType - 源类型（变量类型）
 * @param {string} targetType - 目标类型（output 类型）
 * @returns {boolean}
 */
export const isTypeCompatible = (sourceType, targetType) => {
  if (!sourceType || !targetType) return true;
  const normalizedSource = sourceType.toLowerCase().replace(/[^a-z0-9]/g, '');
  const normalizedTarget = targetType.toLowerCase().replace(/[^a-z0-9]/g, '');

  if (normalizedSource === normalizedTarget) return true;

  const compatibleTypes = TYPE_COMPATIBILITY[normalizedTarget];
  if (compatibleTypes) {
    return compatibleTypes.includes(normalizedSource);
  }

  return false;
};

/**
 * 获取变量引用的类型
 * @param {string} ref - 变量引用，如 {{nodeId.variableKey}}
 * @param {Array} nodes - 所有节点
 * @returns {string|null} - 变量类型
 */
export const getVariableType = (ref, nodes) => {
  const parsed = parseVariableRef(ref);
  if (!parsed) return null;

  const { nodeId, variableKey } = parsed;
  const node = nodes.find(n => n.id === nodeId);
  if (!node) return null;

  const outputs = getNodeOutputVariables(node);
  const variable = outputs.find(v => v.key === variableKey);
  return variable?.type || null;
};

/**
 * 获取节点的所有上游节点（通过边连接）
 */
export const getUpstreamNodes = (nodeId, nodes, edges) => {
  if (!nodeId) return [];

  const upstreamNodeIds = new Set();
  const visited = new Set();

  const traverse = (currentId) => {
    if (visited.has(currentId)) return;
    visited.add(currentId);

    edges.forEach((edge) => {
      if (edge.target === currentId) {
        upstreamNodeIds.add(edge.source);
        traverse(edge.source);
      }
    });
  };

  traverse(nodeId);
  return nodes.filter((n) => upstreamNodeIds.has(n.id));
};

/**
 * 节点类型默认输出变量映射
 */
const NODE_TYPE_DEFAULT_OUTPUTS = {
  workflowStart: [
    { key: 'userChatInput', label: '用户输入', type: 'string' },
    { key: 'userFiles', label: '用户文件', type: 'file' },
  ],
  llm: [
    { key: 'output', label: '输出', type: 'string' },
  ],
  code: [
    { key: 'result', label: '代码执行结果', type: 'string' },
  ],
  classifyQuestion: [
    { key: 'cqResult', label: '分类结果', type: 'string' },
  ],
  ifElseNode: [
    { key: 'system_resultTrue', label: '真分支', type: 'boolean' },
    { key: 'system_resultFalse', label: '假分支', type: 'boolean' },
  ],
  contentExtract: [
    { key: 'extractResult', label: '提取结果', type: 'object' },
  ],
  http: [
    { key: 'body', label: '响应体', type: 'string' },
    { key: 'statusCode', label: '状态码', type: 'integer' },
    { key: 'headers', label: '响应头', type: 'string' },
  ],
  textEditor: [
    { key: 'text', label: '文本结果', type: 'string' },
  ],
  variableUpdate: [
    { key: 'result', label: '聚合结果', type: 'string' },
  ],
  readFiles: [
    { key: 'fileContent', label: '文件内容', type: 'string' },
  ],
  loop: [
    { key: 'loopResult', label: '循环结果', type: 'array' },
  ],
  agent: [
    { key: 'answerText', label: 'AI 回复', type: 'string' },
  ],
  toolCall: [
    { key: 'toolResult', label: '工具结果', type: 'string' },
  ],
  queryExtension: [
    { key: 'query', label: '扩展查询', type: 'string' },
  ],
  formInput: [
    { key: 'formData', label: '表单数据', type: 'object' },
  ],
  userSelect: [
    { key: 'selectedOption', label: '用户选择', type: 'string' },
  ],
  pluginOutput: [
    { key: 'output', label: '输出结果', type: 'string' },
  ],
};

/**
 * 规范化类型值，统一为内部格式
 * 支持 array_string / arrayString / array_string 等变体
 */
const normalizeType = (type) => {
  if (!type) return 'string';
  // 处理 array_xxx 格式（WorkflowStart 使用）
  if (type.startsWith('array_')) {
    const child = type.replace('array_', '');
    return `array${child.charAt(0).toUpperCase() + child.slice(1)}`;
  }
  // 处理 file_xxx 格式
  if (type.startsWith('file_')) {
    const child = type.replace('file_', '');
    if (!child) return 'fileDefault';
    return `file${child.charAt(0).toUpperCase() + child.slice(1)}`;
  }
  // 基础类型小写
  const lower = type.toLowerCase();
  if (lower === 'file') return 'fileDefault';
  return lower;
};

/**
 * 获取节点的输出变量
 */
export const getNodeOutputVariables = (node) => {
  if (!node) return [];

  const nodeType = node.data?.flowNodeType || node.type;
  const outputs = node.data?.outputs || [];

  // workflowStart 节点特殊处理：inputs 作为输出变量
  if (nodeType === 'workflowStart') {
    const inputs = node.data?.inputs || [];
    if (inputs.length > 0) {
      return inputs.map((input) => ({
        key: input.name || input.key,
        label: input.name || input.label || input.key,
        type: normalizeType(input.type) || 'string',
      })).filter((v) => v.key); // 过滤掉没有 key 的
    }
    // 如果没有自定义输入，返回默认输出
    return NODE_TYPE_DEFAULT_OUTPUTS.workflowStart.map((o) => ({ ...o }));
  }

  // 如果节点有显式定义的 outputs，优先使用
  if (outputs.length > 0) {
    return outputs.map((output) => ({
      key: output.key || output.name,
      label: output.label || output.name || output.key,
      type: normalizeType(output.type) || inferTypeFromKey(output.key) || 'string',
    }));
  }

  // 否则使用节点类型的默认输出
  const defaultOutputs = NODE_TYPE_DEFAULT_OUTPUTS[nodeType];
  if (defaultOutputs) {
    return defaultOutputs.map((o) => ({ ...o }));
  }

  return [];
};

/**
 * 根据变量 key 推断类型
 */
const inferTypeFromKey = (key) => {
  if (!key) return 'string';
  const lowerKey = key.toLowerCase();
  if (lowerKey.includes('file')) return 'file';
  if (lowerKey.includes('count') || lowerKey.includes('num') || lowerKey.includes('index')) return 'integer';
  if (lowerKey.includes('code') || lowerKey.includes('status')) return 'integer';
  if (lowerKey.includes('flag') || lowerKey.includes('is') || lowerKey.includes('enable')) return 'boolean';
  if (lowerKey.includes('list') || lowerKey.includes('items') || lowerKey.includes('array')) return 'array';
  if (lowerKey.includes('data') || lowerKey.includes('config') || lowerKey.includes('object')) return 'object';
  if (lowerKey.includes('time') || lowerKey.includes('date')) return 'time';
  return 'string';
};

/**
 * 变量引用格式化
 */
export const formatVariableRef = (nodeId, variableKey) => {
  return `{{${nodeId}.${variableKey}}}`;
};

/**
 * 解析变量引用
 */
export const parseVariableRef = (ref) => {
  const match = ref?.match?.(/\{\{([^.]+)\.([^}]+)\}\}/);
  if (match) {
    return { nodeId: match[1], variableKey: match[2] };
  }
  return null;
};

/**
 * 变量选择弹窗（保留用于非紧凑模式）
 */
const VariableSelector = ({
  availableNodes,
  selectedValue,
  onSelect,
  onClose,
}) => {
  const [search, setSearch] = useState('');

  const filteredVariables = useMemo(() => {
    const vars = [];
    availableNodes.forEach((node) => {
      const outputs = getNodeOutputVariables(node);
      outputs.forEach((output) => {
        const ref = formatVariableRef(node.id, output.key);
        vars.push({
          nodeId: node.id,
          nodeName: node.data?.name || node.id,
          variableKey: output.key,
          variableLabel: output.label || output.key,
          variableType: output.type || 'text',
          ref,
        });
      });
    });

    if (!search) return vars;
    const q = search.toLowerCase();
    return vars.filter(
      (v) =>
        v.variableLabel.toLowerCase().includes(q) ||
        v.nodeName.toLowerCase().includes(q) ||
        v.variableKey.toLowerCase().includes(q)
    );
  }, [availableNodes, search]);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.5)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
          width: '400px',
          maxHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #f3f4f6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937' }}>
            选择变量
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={16} color="#6b7280" />
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} color="#9ca3af" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="搜索变量..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px 8px 32px',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>
        </div>

        {/* Variable List */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px',
          }}
        >
          {filteredVariables.length === 0 ? (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
              }}
            >
              {availableNodes.length === 0
                ? '没有可用的上游节点变量'
                : '没有找到匹配的变量'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {filteredVariables.map((variable) => {
                const typeInfo = VARIABLE_TYPES[variable.variableType] || VARIABLE_TYPES.text;
                const isSelected = selectedValue === variable.ref;

                return (
                  <div
                    key={`${variable.nodeId}.${variable.variableKey}`}
                    onClick={() => onSelect(variable.ref)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      background: isSelected ? '#eff6ff' : 'transparent',
                      border: isSelected ? '1px solid #3b82f6' : '1px solid transparent',
                    }}
                  >
                    <div
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: typeInfo.color,
                        marginRight: '12px',
                      }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 500,
                          color: '#1f2937',
                          marginBottom: '2px',
                        }}
                      >
                        {variable.variableLabel}
                      </div>
                      <div
                        style={{
                          fontSize: '11px',
                          color: '#9ca3af',
                        }}
                      >
                        {variable.nodeName} · {typeInfo.label}
                      </div>
                    </div>
                    {isSelected && (
                      <div
                        style={{
                          width: '18px',
                          height: '18px',
                          borderRadius: '50%',
                          background: '#3b82f6',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M20 6L9 17L4 12"
                            stroke="white"
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid #f3f4f6',
            fontSize: '12px',
            color: '#9ca3af',
          }}
        >
          共 {filteredVariables.length} 个变量
        </div>
      </div>
    </div>
  );
};

/**
 * 下拉列表式变量选择器
 * 参考图片中的设计：分类展示变量
 * 使用 Portal 渲染到 body，避免 overflow:hidden 裁剪
 */
const VariableDropdown = ({
  availableNodes,
  selectedValue,
  onSelect,
  onClose,
  triggerRef,
}) => {
  const [expandedNode, setExpandedNode] = useState(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const dropdownRef = useRef(null);

  // 计算下拉菜单位置
  useEffect(() => {
    if (triggerRef?.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX - 180, // 向左偏移，让菜单右侧对齐按钮
      });
    }
  }, [triggerRef]);

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) &&
          triggerRef?.current && !triggerRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose, triggerRef]);

  // 按节点分组变量
  const nodeVariables = useMemo(() => {
    return availableNodes.map((node) => {
      const outputs = getNodeOutputVariables(node);
      return {
        node,
        nodeName: node.data?.name || '未命名节点',
        nodeType: node.data?.flowNodeType || node.type,
        variables: outputs.map((output) => ({
          key: output.key,
          label: output.label || output.key,
          type: output.type || 'text',
          ref: formatVariableRef(node.id, output.key),
        })),
      };
    }).filter((group) => group.variables.length > 0);
  }, [availableNodes]);

  // 固定分类（用户变量、应用变量、系统变量）
  const categories = [
    { id: 'user', label: '用户变量', icon: <User size={16} /> },
    { id: 'app', label: '应用变量', icon: <FolderOpen size={16} /> },
    { id: 'system', label: '系统变量', icon: <Settings size={16} /> },
  ];

  const dropdownContent = (
    <div
      ref={dropdownRef}
      style={{
        position: 'fixed',
        top: dropdownPos.top,
        left: dropdownPos.left,
        background: 'white',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        zIndex: 10000,
        minWidth: '200px',
        maxWidth: '280px',
        maxHeight: '320px',
        overflowY: 'auto',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* 分类列表 */}
      {categories.map((cat) => (
        <div
          key={cat.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            cursor: 'pointer',
            fontSize: '13px',
            color: '#374151',
            borderBottom: '1px solid #f3f4f6',
          }}
          onMouseEnter={() => setExpandedNode(null)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#6b7280' }}>{cat.icon}</span>
            <span>{cat.label}</span>
          </div>
          <ChevronRight size={14} color="#9ca3af" />
        </div>
      ))}

      {/* 分隔线 */}
      <div style={{ height: '1px', background: '#f3f4f6', margin: '4px 0' }} />

      {/* 节点变量列表 */}
      {nodeVariables.map((group) => (
        <div key={group.node.id}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: '13px',
              color: '#374151',
              background: expandedNode === group.node.id ? '#f9fafb' : 'transparent',
            }}
            onClick={() => setExpandedNode(
              expandedNode === group.node.id ? null : group.node.id
            )}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: '20px',
                height: '20px',
                borderRadius: '4px',
                background: '#6366f1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '10px',
              }}>
                {group.nodeName.charAt(0)}
              </span>
              <span>{group.nodeName}</span>
            </div>
            <ChevronRight
              size={14}
              color="#9ca3af"
              style={{
                transform: expandedNode === group.node.id ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
              }}
            />
          </div>

          {/* 展开的变量列表 */}
          {expandedNode === group.node.id && (
            <div style={{ background: '#f9fafb' }}>
              {group.variables.map((variable) => {
                const typeInfo = VARIABLE_TYPES[variable.type] || VARIABLE_TYPES.text;
                const isSelected = selectedValue === variable.ref;

                return (
                  <div
                    key={variable.key}
                    onClick={() => {
                      onSelect(variable.ref);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '6px 12px 6px 40px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: isSelected ? '#6366f1' : '#374151',
                      background: isSelected ? '#eef2ff' : 'transparent',
                    }}
                  >
                    <div
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: typeInfo.color,
                        marginRight: '8px',
                      }}
                    />
                    <span>{variable.label}</span>
                    <span style={{ marginLeft: 'auto', color: '#9ca3af', fontSize: '11px' }}>
                      {typeInfo.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}

      {nodeVariables.length === 0 && (
        <div style={{ padding: '12px', textAlign: 'center', color: '#9ca3af', fontSize: '12px' }}>
          没有可用的上游节点变量
        </div>
      )}
    </div>
  );

  return createPortal(dropdownContent, document.body);
};

/**
 * 表达式编辑器字段组件
 */
const ExpressionEditorField = ({
  fields = [],
  onChange,
  nodes = [],
  edges = [],
  currentNodeId,
  canAdd = true,
  compact = false,
  useDropdown = false, // 新增：使用下拉列表模式
}) => {
  const [showVariableSelector, setShowVariableSelector] = useState(false);
  const [showVariableDropdown, setShowVariableDropdown] = useState(false);
  const buttonRef = useRef(null);

  // 获取当前节点的所有上游节点
  const availableNodes = useMemo(() => {
    if (!currentNodeId) return [];
    return getUpstreamNodes(currentNodeId, nodes, edges);
  }, [currentNodeId, nodes, edges]);

  // 第一个字段的值
  const firstField = fields[0] || { name: '', value: '' };

  const handleValueChange = useCallback(
    (e) => {
      if (fields.length > 0) {
        onChange?.([{ ...fields[0], value: e.target.value }]);
      }
    },
    [fields, onChange]
  );

  const handleVariableSelect = useCallback(
    (ref) => {
      if (fields.length > 0) {
        onChange?.([{ ...fields[0], value: ref }]);
      }
      setShowVariableSelector(false);
      setShowVariableDropdown(false);
    },
    [fields, onChange]
  );

  // 紧凑模式 + 下拉列表
  if (compact && useDropdown) {
    return (
      <>
        <input
          type="text"
          value={firstField.value || ''}
          onChange={handleValueChange}
          placeholder="输入值或引用变量"
          style={{
            flex: 1,
            padding: '5px 7px',
            border: 'none',
            borderRadius: '0',
            fontSize: '12px',
            outline: 'none',
            background: 'transparent',
            minWidth: 0,
          }}
        />
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            ref={buttonRef}
            onClick={(e) => {
              e.stopPropagation();
              setShowVariableDropdown(!showVariableDropdown);
            }}
            disabled={availableNodes.length === 0}
            title={availableNodes.length === 0 ? '没有可用的上游节点' : '引用变量'}
            style={{
              padding: '5px 7px',
              border: 'none',
              borderLeft: '1px solid #e5e7eb',
              borderRadius: '0',
              background: 'transparent',
              cursor: availableNodes.length > 0 ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Variable size={11} color={availableNodes.length > 0 ? '#6366f1' : '#9ca3af'} />
          </button>

          {showVariableDropdown && (
            <VariableDropdown
              availableNodes={availableNodes}
              selectedValue={firstField.value || ''}
              onSelect={handleVariableSelect}
              onClose={() => setShowVariableDropdown(false)}
              triggerRef={buttonRef}
            />
          )}
        </div>
      </>
    );
  }

  // compact 模式：纯输入框 + 变量引用按钮（弹窗）
  if (compact) {
    return (
      <>
        <input
          type="text"
          value={firstField.value || ''}
          onChange={handleValueChange}
          placeholder="输入值或引用变量"
          style={{
            flex: 1,
            padding: '5px 7px',
            border: 'none',
            borderRadius: '0',
            fontSize: '10px',
            outline: 'none',
            background: 'transparent',
            minWidth: 0,
          }}
        />
        <button
          type="button"
          onClick={() => setShowVariableSelector(true)}
          disabled={availableNodes.length === 0}
          title={availableNodes.length === 0 ? '没有可用的上游节点' : '引用变量'}
          style={{
            padding: '5px 7px',
            border: 'none',
            borderLeft: '1px solid #e5e7eb',
            borderRadius: '0',
            background: 'transparent',
            cursor: availableNodes.length > 0 ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <Variable size={11} color={availableNodes.length > 0 ? '#6366f1' : '#9ca3af'} />
        </button>

        {showVariableSelector && (
          <VariableSelector
            availableNodes={availableNodes}
            selectedValue={firstField.value || ''}
            onSelect={handleVariableSelect}
            onClose={() => setShowVariableSelector(false)}
          />
        )}
      </>
    );
  }

  // 普通模式
  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          background: 'white',
          flex: 1,
        }}
      >
        {/* 值输入框 */}
        <input
          type="text"
          value={firstField.value || ''}
          onChange={handleValueChange}
          placeholder="输入值或引用变量"
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px 0 0 6px',
            fontSize: '12px',
            outline: 'none',
            background: 'white',
            minWidth: 0,
          }}
        />

        {/* 变量引用按钮 */}
        <button
          type="button"
          onClick={() => setShowVariableSelector(true)}
          disabled={availableNodes.length === 0}
          title={availableNodes.length === 0 ? '没有可用的上游节点' : '引用变量'}
          style={{
            padding: '8px 12px',
            border: '1px solid #e5e7eb',
            borderLeft: 'none',
            borderRadius: '0 6px 6px 0',
            background: availableNodes.length > 0 ? '#6366f1' : '#f3f4f6',
            cursor: availableNodes.length > 0 ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Variable size={14} color={availableNodes.length > 0 ? 'white' : '#9ca3af'} />
        </button>
      </div>

      {showVariableSelector && (
        <VariableSelector
          availableNodes={availableNodes}
          selectedValue={firstField.value || ''}
          onSelect={handleVariableSelect}
          onClose={() => setShowVariableSelector(false)}
        />
      )}
    </>
  );
};

export default ExpressionEditorField;
