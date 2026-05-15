/**
 * 输出节点配置表单
 * 支持输出变量配置和输出内容配置
 * 支持流式和非流式两种输出方式
 */

import React, { useCallback, useState, useMemo } from 'react';
import { Plus, Trash2, Info } from 'lucide-react';
import { Collapse, Tooltip, Switch, Cascader } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField, { getVariableType, isTypeCompatible } from '../../common/ExpressionEditorField/index.jsx';

const DEFAULT_OUTPUTS = [
  { id: 'default_0', name: 'output', type: 'string', value: '' },
];

// Cascader 类型选项
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

// 类型选择器 - 基于 AntD Cascader
const TypeSelector = ({ value, onChange }) => {
  const cascaderValue = useMemo(() => typeToCascaderValue(value), [value]);
  const displayAbbr = useMemo(() => getDisplayAbbr(value), [value]);

  const handleChange = (selectedValue) => {
    const newType = cascaderValueToType(selectedValue);
    onChange(newType);
  };

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

// 变量值输入区域
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

  const variableType = useMemo(() => {
    if (!output.value) return null;
    return getVariableType(output.value, nodes);
  }, [output.value, nodes]);

  const typeMismatch = useMemo(() => {
    if (!variableType || !output.type) return false;
    return !isTypeCompatible(variableType, output.type);
  }, [variableType, output.type]);

  const getTypeLabel = (type) => {
    if (!type) return '未知';
    const map = {
      string: 'String', integer: 'Integer', number: 'Number',
      boolean: 'Boolean', time: 'Time', object: 'Object',
      array: 'Array', file: 'File', text: 'Text',
    };
    return map[type.toLowerCase()] || type;
  };

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

  return (
    <div
      onClick={() => setIsEditing(true)}
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        border: '1px solid #e5e7eb',
        borderRadius: '6px',
        overflow: 'hidden',
        background: 'white',
        height: '32px',
        cursor: 'pointer',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          borderRight: '1px solid #e5e7eb',
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
          color: '#9ca3af',
          fontSize: '12px',
        }}>
          输入或引用参数值
        </span>
      </div>

      <div style={{
        borderLeft: '1px solid #e5e7eb',
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

// 表格表头
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

// 输出变量行
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

      <ValueInput
        output={output}
        index={index}
        nodes={nodes}
        edges={edges}
        currentNodeId={currentNodeId}
        onUpdate={onUpdate}
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

const NodeConfigDrawer = ({
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = React.useState(['outputs', 'content']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const outputs = nodeData?.outputs || DEFAULT_OUTPUTS;
  const content = nodeData?.content || '';
  const streamOutput = nodeData?.streamOutput || false;

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

  const handleUpdateContent = useCallback((text) => {
    updateNode(currentNodeId, { ...nodeData, content: text });
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
            <Tooltip title="配置输出节点的变量，可在后续节点中引用">
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
      ),
    },
    {
      key: 'content',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              输出内容
            </span>
            <Tooltip title="配置输出的文本内容，支持变量引用">
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
      children: (
        <div style={{ padding: '4px 0' }}>
          <textarea
            value={content}
            onChange={(e) => handleUpdateContent(e.target.value)}
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
        节点从"消息"更名为"输出"，支持中间过程的消息输出，支持流式和非流式两种方式
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
