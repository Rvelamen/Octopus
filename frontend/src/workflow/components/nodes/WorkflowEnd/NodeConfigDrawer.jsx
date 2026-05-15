/**
 * 工作流结束节点配置表单
 * 参考 Coze 风格设计：Space.Compact 布局，可点击的未定义状态，完整的类型子菜单
 * 支持两种返回模式：返回变量 / 返回文本
 */

import React, { useCallback, useState, useMemo } from 'react';
import { Plus, Trash2, Info, AlertCircle } from 'lucide-react';
import { Collapse, Tooltip, Switch, Cascader } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField, { getVariableType, isTypeCompatible } from '../../common/ExpressionEditorField/index.jsx';

const DEFAULT_OUTPUTS = [
  { id: 'default_0', name: 'result', type: 'string', value: '' },
];

// Cascader 类型选项 - 与 VariableTypeSelector 保持一致
const TYPE_CASCADER_OPTIONS = [
  { value: 'String', label: 'String' },
  { value: 'Integer', label: 'Integer' },
  { value: 'Number', label: 'Number' },
  { value: 'Boolean', label: 'Boolean' },
  { value: 'Time', label: 'Time' },
  { value: 'Object', label: 'Object' },
  {
    value: 'Array',
    label: 'Array',
    children: [
      { value: 'String', label: 'String' },
      { value: 'Integer', label: 'Integer' },
      { value: 'Number', label: 'Number' },
      { value: 'Boolean', label: 'Boolean' },
      { value: 'Time', label: 'Time' },
      { value: 'Object', label: 'Object' },
      { value: 'File', label: 'File' },
    ],
  },
  {
    value: 'File',
    label: 'File',
    children: [
      { value: 'Default', label: 'Default' },
      { value: 'Image', label: 'Image' },
      { value: 'Svg', label: 'Svg' },
      { value: 'Audio', label: 'Audio' },
      { value: 'Video', label: 'Video' },
      { value: 'Voice', label: 'Voice' },
      { value: 'Doc', label: 'Doc' },
      { value: 'PPT', label: 'PPT' },
      { value: 'Excel', label: 'Excel' },
      { value: 'Txt', label: 'Txt' },
      { value: 'Code', label: 'Code' },
      { value: 'Zip', label: 'Zip' },
    ],
  },
];

// 类型缩写映射
const TYPE_ABBR = {
  String: 'str',
  Integer: 'int',
  Number: 'num',
  Boolean: 'bool',
  Time: 'time',
  Object: 'obj',
  Array: 'arr',
  File: 'file',
  Default: '',
  Image: 'img',
  Svg: 'svg',
  Audio: 'audio',
  Video: 'video',
  Voice: 'voice',
  Doc: 'doc',
  PPT: 'ppt',
  Excel: 'xls',
  Txt: 'txt',
  Code: 'code',
  Zip: 'zip',
};

// 将内部类型值转换为 Cascader 值数组
const typeToCascaderValue = (type) => {
  if (!type) return ['String'];
  if (type.startsWith('array')) {
    const child = type.replace('array', '');
    return ['Array', child.charAt(0).toUpperCase() + child.slice(1)];
  }
  if (type.startsWith('file')) {
    const child = type.replace('file', '');
    if (!child || child === 'Default') return ['File', 'Default'];
    return ['File', child];
  }
  return [type.charAt(0).toUpperCase() + type.slice(1)];
};

// 将 Cascader 值数组转换为内部类型值
const cascaderValueToType = (value) => {
  if (!value || value.length === 0) return 'string';
  if (value.length === 1) {
    return value[0].toLowerCase();
  }
  const [parent, child] = value;
  if (parent === 'Array') {
    return `array${child}`;
  }
  if (parent === 'File') {
    if (child === 'Default') return 'fileDefault';
    return `file${child}`;
  }
  return parent.toLowerCase();
};

// 获取显示用的缩写
const getDisplayAbbr = (type) => {
  if (!type) return 'str';
  if (type.startsWith('array')) {
    const child = type.replace('array', '');
    const childAbbr = TYPE_ABBR[child] || child.toLowerCase();
    return `arr<${childAbbr}>`;
  }
  if (type.startsWith('file')) {
    const child = type.replace('file', '');
    if (!child || child === 'Default') return 'file';
    return TYPE_ABBR[child] || child.toLowerCase();
  }
  return TYPE_ABBR[type.charAt(0).toUpperCase() + type.slice(1)] || type;
};

// 表格表头 - 紧凑
const TableHeader = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    padding: '0 0 6px 0',
    marginBottom: '6px',
  }}>
    <div style={{ flex: '0 0 100px', fontSize: '12px', color: '#9ca3af' }}>变量名</div>
    <div style={{ flex: 1, fontSize: '12px', color: '#9ca3af' }}>变量值</div>
  </div>
);

// 类型选择器 - 基于 AntD Cascader
const TypeSelector = ({ value, onChange }) => {
  const cascaderValue = useMemo(() => typeToCascaderValue(value), [value]);
  const displayAbbr = useMemo(() => getDisplayAbbr(value), [value]);

  const handleChange = (selectedValue) => {
    const newType = cascaderValueToType(selectedValue);
    onChange(newType);
  };

  // 自定义显示渲染
  const displayRender = () => (
    <span style={{ color: '#9ca3af', fontSize: '12px' }}>
      {displayAbbr}.
    </span>
  );

  return (
    <Cascader
      options={TYPE_CASCADER_OPTIONS}
      value={cascaderValue}
      onChange={handleChange}
      expandTrigger="hover"
      changeOnSelect
      displayRender={displayRender}
      dropdownStyle={{ maxHeight: 'none', overflow: 'visible' }}
      dropdownMenuColumnStyle={{ maxHeight: 'none', height: 'auto', overflow: 'visible' }}
      style={{ width: 'auto', minWidth: '60px' }}
      bordered={false}
      size="small"
    />
  );
};

// 变量值输入区域 - Space.Compact 风格
// 类型选择器 + 输入框 + 变量引用按钮 三者紧密连接
const ValueInput = ({
  output,
  index,
  nodes,
  edges,
  currentNodeId,
  onUpdate,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const isUndefined = !output.value || output.value === '';

  // 获取变量引用的类型，进行类型校验
  const variableType = useMemo(() => {
    if (!output.value) return null;
    return getVariableType(output.value, nodes);
  }, [output.value, nodes]);

  // 检查类型是否兼容
  const typeMismatch = useMemo(() => {
    if (!variableType || !output.type) return false;
    return !isTypeCompatible(variableType, output.type);
  }, [variableType, output.type]);

  // 获取类型显示文本
  const getTypeLabel = (type) => {
    if (!type) return '未知';
    const map = {
      string: 'String', integer: 'Integer', number: 'Number',
      boolean: 'Boolean', time: 'Time', object: 'Object',
      array: 'Array', file: 'File', text: 'Text',
    };
    return map[type.toLowerCase()] || type;
  };

  // 如果正在编辑或有值，显示 ExpressionEditorField（在Compact容器内）
  if (isEditing || !isUndefined) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        border: typeMismatch ? '1px solid #fbbf24' : '1px solid #e5e7eb',
        borderRadius: '6px',
        overflow: 'hidden',
        background: 'white',
        height: '32px',
      }}>
        {/* 类型选择器 - 左侧，无边框，圆角左 */}
        <div style={{
          borderRight: `1px solid ${typeMismatch ? '#fbbf24' : '#e5e7eb'}`,
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          padding: '0 4px',
        }}>
          <Tooltip
            title={typeMismatch ? `建议与引用变量类型（${getTypeLabel(variableType)}）保持一致，否则可能会转换失败` : ''}
            color="#f59e0b"
          >
            <div>
              <TypeSelector
                value={output.type || 'string'}
                onChange={(type) => onUpdate(index, 'type', type)}
              />
            </div>
          </Tooltip>
        </div>

        {/* 输入框 - 中间，无边框 */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          minWidth: 0,
          height: '100%',
        }}>
          <ExpressionEditorField
            fields={[{ name: output.name, value: output.value || '' }]}
            onChange={(newFields) => {
              if (newFields.length > 0) {
                onUpdate(index, 'value', newFields[0].value);
                if (!newFields[0].value) {
                  setIsEditing(false);
                }
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
    );
  }

  // 未定义状态 - Space.Compact 风格，整个区域可点击
  return (
    <div
      onClick={() => setIsEditing(true)}
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        border: '1px solid #fed7aa',
        borderRadius: '6px',
        overflow: 'hidden',
        background: '#fff7ed',
        height: '32px',
        cursor: 'pointer',
      }}
    >
      {/* 类型选择器 - 左侧 */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          borderRight: '1px solid #fed7aa',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          padding: '0 4px',
        }}
      >
        <TypeSelector
          value={output.type || 'string'}
          onChange={(type) => onUpdate(index, 'type', type)}
        />
      </div>

      {/* 未定义提示 - 中间 */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        padding: '0 8px',
        height: '100%',
      }}>
        <span style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          color: '#f97316',
          fontSize: '12px',
        }}>
          <AlertCircle size={14} />
          未定义
        </span>
      </div>

      {/* 变量引用按钮 - 右侧 */}
      <div style={{
        borderLeft: '1px solid #fed7aa',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 8px',
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
      </div>
    </div>
  );
};

// 表格行 - 紧凑，Space.Compact 风格
const OutputRow = ({
  output,
  index,
  nodes,
  edges,
  currentNodeId,
  onUpdate,
  onDelete,
  canDelete,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}
    >
      {/* 变量名 */}
      <input
        type="text"
        value={output.name || ''}
        onChange={(e) => {
          const newName = e.target.value.replace(/[^a-zA-Z0-9_]/g, '');
          onUpdate(index, 'name', newName);
        }}
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

      {/* 变量值 - Space.Compact 容器 */}
      <ValueInput
        output={output}
        index={index}
        nodes={nodes}
        edges={edges}
        currentNodeId={currentNodeId}
        onUpdate={onUpdate}
      />

      {/* 删除按钮 */}
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

// Tab 切换组件 - 紧凑
const ModeTabs = ({ activeMode, onChange }) => {
  return (
    <div style={{
      display: 'flex',
      borderBottom: '1px solid #e5e7eb',
    }}>
      <button
        onClick={() => onChange('variables')}
        style={{
          flex: 1,
          padding: '10px 12px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          fontSize: '13px',
          color: activeMode === 'variables' ? '#6366f1' : '#6b7280',
          fontWeight: activeMode === 'variables' ? 500 : 400,
          borderBottom: `2px solid ${activeMode === 'variables' ? '#6366f1' : 'transparent'}`,
          marginBottom: '-1px',
        }}
      >
        返回变量
      </button>
      <button
        onClick={() => onChange('text')}
        style={{
          flex: 1,
          padding: '10px 12px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          fontSize: '13px',
          color: activeMode === 'text' ? '#6366f1' : '#6b7280',
          fontWeight: activeMode === 'text' ? 500 : 400,
          borderBottom: `2px solid ${activeMode === 'text' ? '#6366f1' : 'transparent'}`,
          marginBottom: '-1px',
        }}
      >
        返回文本
      </button>
    </div>
  );
};

const NodeConfigDrawer = ({
  values,
  onChange,
  errors,
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = React.useState(['outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const outputs = nodeData?.outputs || DEFAULT_OUTPUTS;
  const returnMode = nodeData?.returnMode || 'variables';
  const returnText = nodeData?.returnText || '';
  const streamOutput = nodeData?.streamOutput || false;

  const handleModeChange = useCallback((mode) => {
    updateNode(currentNodeId, { ...nodeData, returnMode: mode });
    setActiveKey(mode === 'variables' ? ['outputs'] : ['answer']);
  }, [currentNodeId, nodeData, updateNode]);

  const handleUpdateOutputs = useCallback((newOutputs) => {
    updateNode(currentNodeId, { ...nodeData, outputs: newOutputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleAddOutput = useCallback(() => {
    const newOutput = {
      id: `output_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `var_${outputs.length + 1}`,
      type: 'string',
      value: '',
    };
    handleUpdateOutputs([...outputs, newOutput]);
  }, [outputs, handleUpdateOutputs]);

  const handleDeleteOutput = useCallback((index) => {
    const newOutputs = outputs.filter((_, i) => i !== index);
    handleUpdateOutputs(newOutputs);
  }, [outputs, handleUpdateOutputs]);

  const handleUpdateField = useCallback((index, field, fieldValue) => {
    const newOutputs = [...outputs];
    newOutputs[index] = { ...newOutputs[index], [field]: fieldValue };
    handleUpdateOutputs(newOutputs);
  }, [outputs, handleUpdateOutputs]);

  const handleUpdateReturnText = useCallback((text) => {
    updateNode(currentNodeId, { ...nodeData, returnText: text });
  }, [currentNodeId, nodeData, updateNode]);

  const handleToggleStream = useCallback((checked) => {
    updateNode(currentNodeId, { ...nodeData, streamOutput: checked });
  }, [currentNodeId, nodeData, updateNode]);

  const collapseItems = [
    {
      key: 'outputs',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              输出变量
            </span>
            <Tooltip title="配置工作流执行完成后返回的变量">
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
      children: returnMode === 'variables' ? (
        <div>
          <TableHeader />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {outputs.map((output, index) => (
              <OutputRow
                key={output.id || index}
                output={output}
                index={index}
                nodes={nodes}
                edges={edges}
                currentNodeId={currentNodeId}
                onUpdate={handleUpdateField}
                onDelete={handleDeleteOutput}
                canDelete={outputs.length > 1}
              />
            ))}
          </div>
        </div>
      ) : (
        <div style={{ padding: '16px', textAlign: 'center', color: '#9ca3af', fontSize: '13px' }}>
          切换到"返回变量"模式以配置输出变量
        </div>
      ),
    },
  ];

  const answerCollapseItems = [
    {
      key: 'answer',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              回答内容
            </span>
            <Tooltip title="配置返回的文本内容，支持变量引用">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13px',
              color: '#6b7280',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <span>流式输出</span>
            <Switch
              size="small"
              checked={streamOutput}
              onChange={handleToggleStream}
            />
          </div>
        </div>
      ),
      children: returnMode === 'text' ? (
        <div style={{ padding: '4px 0' }}>
          <textarea
            value={returnText}
            onChange={(e) => handleUpdateReturnText(e.target.value)}
            placeholder="可以使用{{变量名}}、{{变量名.子变量名}}、{{变量名[数组索引]}}的方式引用输出参数中的变量"
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
      ) : (
        <div style={{ padding: '16px', textAlign: 'center', color: '#9ca3af', fontSize: '13px' }}>
          切换到"返回文本"模式以配置返回内容
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* 顶部描述 */}
      <div style={{
        padding: '10px 14px',
        background: '#f9fafb',
        borderRadius: '8px',
        fontSize: '13px',
        color: '#6b7280',
        lineHeight: 1.5,
      }}>
        工作流的最终节点，用于返回工作流运行后的结果信息
      </div>

      {/* Tab 切换 */}
      <ModeTabs activeMode={returnMode} onChange={handleModeChange} />

      {/* 内容区域 */}
      {returnMode === 'variables' ? (
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
      ) : (
        <Collapse
          ghost
          activeKey={activeKey}
          onChange={setActiveKey}
          items={answerCollapseItems}
          style={{
            '--ant-collapse-header-padding': '10px 0',
            '--ant-collapse-content-padding': '0',
          }}
        />
      )}
    </div>
  );
};

export default NodeConfigDrawer;
