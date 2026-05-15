/**
 * 文本处理节点配置面板
 * 支持：
 *   - 选择应用（操作类型）：字符串拼接、文本替换、文本截取、正则匹配等
 *   - 输入变量管理（动态添加/删除）
 *   - 各操作类型的专属配置（如拼接模板、替换规则、截取范围等）
 *   - 输出变量管理
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Plus, Trash2, Info, Settings } from 'lucide-react';
import { Collapse, Tooltip, Select } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

// ==================== 常量定义 ====================

const OPERATION_OPTIONS = [
  { value: 'concat', label: '字符串拼接' },
  { value: 'replace', label: '文本替换' },
  { value: 'substring', label: '文本截取' },
  { value: 'regex', label: '正则匹配' },
  { value: 'split', label: '文本分割' },
  { value: 'trim', label: '去除空白' },
  { value: 'uppercase', label: '转大写' },
  { value: 'lowercase', label: '转小写' },
];

const DEFAULT_OUTPUTS = [
  { id: 'out_text', name: 'output', type: 'string' },
];

const generateId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// Cascader 类型选项（简化版）
const TYPE_OPTIONS = [
  { value: 'string', label: 'String' },
  { value: 'integer', label: 'Integer' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'object', label: 'Object' },
];

// ==================== 子组件 ====================

// 输入变量行
const InputRow = ({ input, index, onUpdate, onDelete, canDelete, nodes, edges, currentNodeId }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <input
        type="text"
        value={input.name || ''}
        onChange={(e) => onUpdate(index, 'name', e.target.value)}
        placeholder="变量名"
        style={{
          flex: '0 0 100px',
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#374151',
          height: '32px',
        }}
      />
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        border: '1px solid #e5e7eb',
        borderRadius: '6px',
        overflow: 'hidden',
        background: 'white',
        height: '32px',
      }}>
        <div style={{
          borderRight: '1px solid #e5e7eb',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          padding: '0 4px',
          flexShrink: 0,
        }}>
          <Select
            value={input.type || 'string'}
            onChange={(value) => onUpdate(index, 'type', value)}
            options={TYPE_OPTIONS}
            size="small"
            bordered={false}
            style={{ width: '80px' }}
            popupMatchSelectWidth={false}
          />
        </div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', minWidth: 0, height: '100%' }}>
          <ExpressionEditorField
            fields={[{ name: input.name, value: input.value || '' }]}
            onChange={(newFields) => {
              if (newFields.length > 0) {
                onUpdate(index, 'value', newFields[0].value);
              }
            }}
            nodes={nodes}
            edges={edges}
            currentNodeId={currentNodeId}
            compact
            useDropdown
            canAdd={false}
          />
        </div>
      </div>
      {canDelete && (
        <button
          onClick={() => onDelete(index)}
          style={{
            padding: '5px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: '#d1d5db',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
};

// 输出变量行
const OutputRow = ({ output, index, onUpdate, onDelete, canDelete }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <input
        type="text"
        value={output.name || ''}
        onChange={(e) => {
          const newName = e.target.value.replace(/[^a-zA-Z0-9_]/g, '');
          onUpdate(index, 'name', newName);
        }}
        placeholder="变量名"
        style={{
          flex: '0 0 120px',
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#374151',
          height: '32px',
        }}
      />
      <Select
        value={output.type || 'string'}
        onChange={(value) => onUpdate(index, 'type', value)}
        options={TYPE_OPTIONS}
        size="small"
        style={{ width: '120px' }}
      />
      {canDelete && (
        <button
          onClick={() => onDelete(index)}
          style={{
            padding: '5px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: '#d1d5db',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
};

// 操作配置面板 - 字符串拼接
const ConcatConfig = ({ config, onChange }) => {
  const template = config?.template || '';
  const separator = config?.separator || '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          拼接模板
        </div>
        <textarea
          value={template}
          onChange={(e) => onChange({ ...config, template: e.target.value })}
          placeholder="可以使用{{变量名}}、{{变量名.子变量名}}、{{变量名[数组索引]}}的方式引用输入参数中的变量"
          rows={4}
          style={{
            width: '100%',
            padding: '10px',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            fontSize: '13px',
            resize: 'vertical',
            outline: 'none',
            background: 'white',
            fontFamily: 'monospace',
            lineHeight: 1.6,
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          分隔符（可选）
        </div>
        <input
          type="text"
          value={separator}
          onChange={(e) => onChange({ ...config, separator: e.target.value })}
          placeholder="如：, 、 - 等"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
    </div>
  );
};

// 操作配置面板 - 文本替换
const ReplaceConfig = ({ config, onChange }) => {
  const searchValue = config?.searchValue || '';
  const replaceValue = config?.replaceValue || '';
  const useRegex = config?.useRegex || false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          查找内容
        </div>
        <input
          type="text"
          value={searchValue}
          onChange={(e) => onChange({ ...config, searchValue: e.target.value })}
          placeholder="要查找的文本"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          替换为
        </div>
        <input
          type="text"
          value={replaceValue}
          onChange={(e) => onChange({ ...config, replaceValue: e.target.value })}
          placeholder="替换后的文本"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <input
          type="checkbox"
          checked={useRegex}
          onChange={(e) => onChange({ ...config, useRegex: e.target.checked })}
          style={{ cursor: 'pointer' }}
        />
        <span style={{ fontSize: '12px', color: '#6b7280' }}>使用正则表达式</span>
      </div>
    </div>
  );
};

// 操作配置面板 - 文本截取
const SubstringConfig = ({ config, onChange }) => {
  const start = config?.start ?? 0;
  const end = config?.end ?? '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
            起始位置
          </div>
          <input
            type="number"
            value={start}
            onChange={(e) => onChange({ ...config, start: parseInt(e.target.value) || 0 })}
            placeholder="0"
            style={{
              width: '100%',
              padding: '6px 10px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '12px',
              outline: 'none',
            }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
            结束位置（可选）
          </div>
          <input
            type="number"
            value={end}
            onChange={(e) => onChange({ ...config, end: e.target.value ? parseInt(e.target.value) : '' })}
            placeholder="留空表示到末尾"
            style={{
              width: '100%',
              padding: '6px 10px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '12px',
              outline: 'none',
            }}
          />
        </div>
      </div>
    </div>
  );
};

// 操作配置面板 - 正则匹配
const RegexConfig = ({ config, onChange }) => {
  const pattern = config?.pattern || '';
  const flags = config?.flags || 'g';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          正则表达式
        </div>
        <input
          type="text"
          value={pattern}
          onChange={(e) => onChange({ ...config, pattern: e.target.value })}
          placeholder="如：\\d+"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
            fontFamily: 'monospace',
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          标志（flags）
        </div>
        <input
          type="text"
          value={flags}
          onChange={(e) => onChange({ ...config, flags: e.target.value })}
          placeholder="g, i, m 等"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
    </div>
  );
};

// 操作配置面板 - 文本分割
const SplitConfig = ({ config, onChange }) => {
  const delimiter = config?.delimiter || ',';
  const limit = config?.limit ?? '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          分隔符
        </div>
        <input
          type="text"
          value={delimiter}
          onChange={(e) => onChange({ ...config, delimiter: e.target.value })}
          placeholder="如：, 、 | 等"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
          最大分割数（可选）
        </div>
        <input
          type="number"
          value={limit}
          onChange={(e) => onChange({ ...config, limit: e.target.value ? parseInt(e.target.value) : '' })}
          placeholder="留空表示不限制"
          style={{
            width: '100%',
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
      </div>
    </div>
  );
};

// 操作配置面板 - 无需额外配置的操作（trim、uppercase、lowercase）
const NoConfigPanel = ({ operation }) => {
  const descriptions = {
    trim: '去除文本首尾的空白字符',
    uppercase: '将文本转换为大写字母',
    lowercase: '将文本转换为小写字母',
  };

  return (
    <div style={{
      padding: '12px',
      background: '#f9fafb',
      borderRadius: '6px',
      fontSize: '12px',
      color: '#6b7280',
      lineHeight: 1.5,
    }}>
      {descriptions[operation] || '此操作无需额外配置'}
    </div>
  );
};

// 根据操作类型渲染对应的配置面板
const OperationConfigPanel = ({ operation, config, onChange }) => {
  switch (operation) {
    case 'concat':
      return <ConcatConfig config={config} onChange={onChange} />;
    case 'replace':
      return <ReplaceConfig config={config} onChange={onChange} />;
    case 'substring':
      return <SubstringConfig config={config} onChange={onChange} />;
    case 'regex':
      return <RegexConfig config={config} onChange={onChange} />;
    case 'split':
      return <SplitConfig config={config} onChange={onChange} />;
    case 'trim':
    case 'uppercase':
    case 'lowercase':
      return <NoConfigPanel operation={operation} />;
    default:
      return <ConcatConfig config={config} onChange={onChange} />;
  }
};

// ==================== 主组件 ====================

const NodeConfigDrawer = ({
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = useState(['inputs', 'operation', 'outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  // 从 nodeData 读取配置
  const inputs = nodeData?.inputs || [];
  const outputs = nodeData?.outputs || DEFAULT_OUTPUTS;
  const operation = nodeData?.operation || 'concat';
  const operationConfig = nodeData?.operationConfig || {};

  const handleUpdate = useCallback(
    (updates) => {
      updateNode(currentNodeId, { ...nodeData, ...updates });
    },
    [currentNodeId, nodeData, updateNode]
  );

  // ---------- 输入变量管理 ----------
  const handleAddInput = useCallback(() => {
    const newInput = {
      id: generateId('input'),
      name: `String${inputs.length + 1}`,
      type: 'string',
      value: '',
    };
    handleUpdate({ inputs: [...inputs, newInput] });
  }, [inputs, handleUpdate]);

  const handleDeleteInput = useCallback(
    (index) => {
      handleUpdate({ inputs: inputs.filter((_, i) => i !== index) });
    },
    [inputs, handleUpdate]
  );

  const handleUpdateInputField = useCallback(
    (index, field, fieldValue) => {
      const newInputs = inputs.map((input, i) =>
        i === index ? { ...input, [field]: fieldValue } : input
      );
      handleUpdate({ inputs: newInputs });
    },
    [inputs, handleUpdate]
  );

  // ---------- 输出变量管理 ----------
  const handleAddOutput = useCallback(() => {
    const newOutput = {
      id: generateId('output'),
      name: `output_${outputs.length + 1}`,
      type: 'string',
    };
    handleUpdate({ outputs: [...outputs, newOutput] });
  }, [outputs, handleUpdate]);

  const handleDeleteOutput = useCallback(
    (index) => {
      handleUpdate({ outputs: outputs.filter((_, i) => i !== index) });
    },
    [outputs, handleUpdate]
  );

  const handleUpdateOutputField = useCallback(
    (index, field, fieldValue) => {
      const newOutputs = outputs.map((output, i) =>
        i === index ? { ...output, [field]: fieldValue } : output
      );
      handleUpdate({ outputs: newOutputs });
    },
    [outputs, handleUpdate]
  );

  // ---------- 操作类型变更 ----------
  const handleOperationChange = useCallback(
    (newOperation) => {
      // 切换操作时重置配置
      handleUpdate({ operation: newOperation, operationConfig: {} });
    },
    [handleUpdate]
  );

  const handleOperationConfigChange = useCallback(
    (newConfig) => {
      handleUpdate({ operationConfig: newConfig });
    },
    [handleUpdate]
  );

  const collapseItems = [
    // 1. 输入变量
    {
      key: 'inputs',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输入</span>
            <Tooltip title="定义文本处理节点的输入变量，支持引用上游节点输出">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleAddInput();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '24px',
              height: '24px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              background: 'white',
              cursor: 'pointer',
              color: '#6366f1',
            }}
          >
            <Plus size={14} />
          </button>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {inputs.length === 0 && (
            <div style={{
              padding: '16px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '13px',
            }}>
              暂无输入变量，点击右上角 + 按钮添加
            </div>
          )}
          {inputs.map((input, index) => (
            <InputRow
              key={input.id || index}
              input={input}
              index={index}
              onUpdate={handleUpdateInputField}
              onDelete={handleDeleteInput}
              canDelete={inputs.length > 0}
              nodes={nodes}
              edges={edges}
              currentNodeId={currentNodeId}
            />
          ))}
        </div>
      ),
    },

    // 2. 操作配置
    {
      key: 'operation',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              {OPERATION_OPTIONS.find(o => o.value === operation)?.label || '字符串拼接'}
            </span>
            <Tooltip title="选择文本处理的操作类型">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <Settings size={14} color="#9ca3af" />
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* 操作类型选择 */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
              选择应用
            </div>
            <Select
              value={operation}
              onChange={handleOperationChange}
              options={OPERATION_OPTIONS}
              style={{ width: '100%' }}
              size="middle"
            />
          </div>

          {/* 操作专属配置 */}
          <OperationConfigPanel
            operation={operation}
            config={operationConfig}
            onChange={handleOperationConfigChange}
          />
        </div>
      ),
    },

    // 3. 输出变量
    {
      key: 'outputs',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输出</span>
            <Tooltip title="配置文本处理节点的输出变量">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleAddOutput();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '24px',
              height: '24px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              background: 'white',
              cursor: 'pointer',
              color: '#6366f1',
            }}
          >
            <Plus size={14} />
          </button>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '0 0 6px 0',
              gap: '6px',
              borderBottom: '1px solid #f0f0f0',
            }}
          >
            <div style={{ flex: '0 0 120px', fontSize: '12px', color: '#9ca3af' }}>变量名</div>
            <div style={{ width: '120px', fontSize: '12px', color: '#9ca3af' }}>变量类型</div>
            <div style={{ width: '28px' }} />
          </div>

          {outputs.map((output, index) => (
            <OutputRow
              key={output.id || index}
              output={output}
              index={index}
              onUpdate={handleUpdateOutputField}
              onDelete={handleDeleteOutput}
              canDelete={outputs.length > 1}
            />
          ))}
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* 顶部描述 */}
      <div
        style={{
          padding: '10px 14px',
          background: '#f9fafb',
          borderRadius: '8px',
          fontSize: '13px',
          color: '#6b7280',
          lineHeight: 1.5,
        }}
      >
        用于处理多个字符串类型变量的格式，支持拼接、替换、截取、正则匹配等多种操作。
      </div>

      <Collapse
        ghost
        activeKey={activeKey}
        onChange={setActiveKey}
        items={collapseItems}
        style={{
          '--ant-collapse-header-padding': '10px 0',
          '--ant-collapse-content-padding': '0',
        }}
      />
    </div>
  );
};

export default NodeConfigDrawer;
