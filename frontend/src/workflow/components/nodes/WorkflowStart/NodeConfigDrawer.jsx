/**
 * 工作流开始节点配置表单
 * 三列表格布局：变量名 | 变量类型 | 必填
 * 参考 Coze/Dify 风格，纯变量声明模式（无默认值输入）
 * 通过加号按钮添加变量，输入框仅编辑已有变量
 */

import React, { useCallback, useState } from 'react';
import { Plus, Maximize2 } from 'lucide-react';
import { Collapse, Checkbox, Cascader } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

// Cascader 类型选项 - 与结束节点保持一致
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
  if (type.startsWith('array_')) {
    const child = type.replace('array_', '');
    return ['Array', child.charAt(0).toUpperCase() + child.slice(1)];
  }
  if (type.startsWith('file_')) {
    const child = type.replace('file_', '');
    if (!child) return ['File', 'Default'];
    return ['File', child.charAt(0).toUpperCase() + child.slice(1)];
  }
  if (type === 'file') {
    return ['File', 'Default'];
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
    return `array_${child.toLowerCase()}`;
  }
  if (parent === 'File') {
    if (child === 'Default') return 'file';
    return `file_${child.toLowerCase()}`;
  }
  return parent.toLowerCase();
};

// 获取类型的显示文本
const getTypeDisplay = (typeValue) => {
  if (!typeValue) return { prefix: 'str', label: 'String' };
  if (typeValue.startsWith('array_')) {
    const child = typeValue.replace('array_', '');
    const childAbbr = TYPE_ABBR[child.charAt(0).toUpperCase() + child.slice(1)] || child;
    return { prefix: `arr<${childAbbr}>`, label: `Array<${child.charAt(0).toUpperCase() + child.slice(1)}>` };
  }
  if (typeValue.startsWith('file_')) {
    const child = typeValue.replace('file_', '');
    const childLabel = child.charAt(0).toUpperCase() + child.slice(1);
    const childAbbr = TYPE_ABBR[childLabel] || child;
    return { prefix: childAbbr || 'file', label: childLabel || 'File' };
  }
  if (typeValue === 'file') {
    return { prefix: 'file', label: 'File' };
  }
  const abbr = TYPE_ABBR[typeValue.charAt(0).toUpperCase() + typeValue.slice(1)] || typeValue;
  const label = typeValue.charAt(0).toUpperCase() + typeValue.slice(1);
  return { prefix: abbr, label };
};

// 表头
const TableHeader = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    padding: '0 0 8px 0',
    gap: '8px',
    borderBottom: '1px solid #f0f0f0',
    marginBottom: '4px',
  }}>
    <div style={{ flex: 1, fontSize: '12px', fontWeight: 500, color: '#9ca3af' }}>变量名</div>
    <div style={{ width: '140px', fontSize: '12px', fontWeight: 500, color: '#9ca3af' }}>变量类型</div>
    <div style={{ width: '40px', fontSize: '12px', fontWeight: 500, color: '#9ca3af', textAlign: 'center' }}>必填</div>
    <div style={{ width: '60px' }}></div>
  </div>
);

// 类型选择器 - 基于 AntD Cascader
const TypeSelector = ({ value, onChange }) => {
  const cascaderValue = typeToCascaderValue(value);
  const display = getTypeDisplay(value);

  const handleChange = (selectedValue) => {
    if (!selectedValue || selectedValue.length === 0) return;
    const newType = cascaderValueToType(selectedValue);
    onChange(newType);
  };

  return (
    <Cascader
      key={value}
      options={TYPE_CASCADER_OPTIONS}
      value={cascaderValue}
      onChange={handleChange}
      expandTrigger="hover"
      changeOnSelect
      displayRender={() => (
        <span style={{ color: '#6b7280', fontSize: '12px' }}>
          {display.prefix}. {display.label}
        </span>
      )}
      dropdownStyle={{ maxHeight: 'none', overflow: 'visible' }}
      dropdownMenuColumnStyle={{ maxHeight: 'none', height: 'auto', overflow: 'visible' }}
      style={{ width: '100%' }}
      size="small"
    />
  );
};

// 表格行组件
const VariableRow = ({
  input,
  index,
  onUpdate,
  onDelete,
  canDelete,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '4px 0',
        gap: '8px',
      }}
    >
      {/* 变量名输入 - 仅编辑已有变量 */}
      <input
        type="text"
        value={input.name || ''}
        onChange={(e) => {
          onUpdate(index, 'name', e.target.value);
        }}
        placeholder="变量名"
        style={{
          flex: 1,
          padding: '6px 10px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          fontFamily: 'monospace',
          outline: 'none',
          color: input.name ? '#374151' : '#9ca3af',
          background: 'white',
        }}
      />

      {/* 变量类型选择 */}
      <div style={{ width: '140px' }}>
        <TypeSelector
          value={input.type || 'string'}
          onChange={(type) => onUpdate(index, 'type', type)}
        />
      </div>

      {/* 必填复选框 */}
      <div style={{ width: '40px', display: 'flex', justifyContent: 'center' }}>
        <Checkbox
          checked={!!input.required}
          onChange={(e) => onUpdate(index, 'required', e.target.checked)}
          style={{ transform: 'scale(0.9)' }}
        />
      </div>

      {/* 操作按钮 */}
      <div style={{
        width: '60px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '4px',
      }}>
        {/* 展开按钮 */}
        <button
          style={{
            padding: '4px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: '#9ca3af',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '4px',
          }}
          title="展开配置"
        >
          <Maximize2 size={12} />
        </button>

        {/* 删除按钮 */}
        {canDelete && (
          <button
            onClick={() => onDelete(index)}
            style={{
              padding: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#9ca3af',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 300,
            }}
            title="删除"
          >
            —
          </button>
        )}
      </div>
    </div>
  );
};

const NodeConfigDrawer = ({
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = React.useState(['1']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  // 从 nodeData 获取有效输入（有 name 的）
  const savedInputs = nodeData?.inputs || [];
  const validInputs = savedInputs.filter(i => i.name && i.name.trim() !== '');

  const handleUpdateInputs = useCallback((newValidInputs) => {
    updateNode(currentNodeId, { ...nodeData, inputs: newValidInputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleDeleteInput = useCallback((index) => {
    const input = validInputs[index];
    if (!input) return;

    const newValidInputs = validInputs.filter((_, i) => i !== index);
    handleUpdateInputs(newValidInputs);
  }, [validInputs, handleUpdateInputs]);

  const handleUpdateField = useCallback((index, field, fieldValue) => {
    const input = validInputs[index];
    if (!input) return;

    const newValidInputs = validInputs.map((i, idx) =>
      idx === index ? { ...i, [field]: fieldValue } : i
    );
    handleUpdateInputs(newValidInputs);
  }, [validInputs, handleUpdateInputs]);

  const collapseItems = [
    {
      key: '1',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>输入</span>
            <span style={{
              fontSize: '11px',
              color: '#9ca3af',
              background: '#f3f4f6',
              padding: '1px 6px',
              borderRadius: '10px',
            }}>
              {validInputs.length}
            </span>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <TableHeader />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {validInputs.map((input, index) => (
              <VariableRow
                key={input.id || index}
                input={input}
                index={index}
                onUpdate={handleUpdateField}
                onDelete={handleDeleteInput}
                canDelete={validInputs.length > 1}
              />
            ))}
            {validInputs.length === 0 && (
              <div style={{
                padding: '16px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
              }}>
                暂无输入变量，点击右上角 + 按钮添加
              </div>
            )}
          </div>
        </div>
      ),
    },
  ];

  return (
    <div style={{ position: 'relative' }}>
      {/* 右上角添加按钮 */}
      <button
        onClick={() => {
          const newInput = {
            id: `input_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            name: `var_${validInputs.length + 1}`,
            type: 'string',
            required: false,
          };
          handleUpdateInputs([...validInputs, newInput]);
        }}
        style={{
          position: 'absolute',
          top: '8px',
          right: '40px',
          width: '24px',
          height: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          background: 'white',
          cursor: 'pointer',
          color: '#6b7280',
          zIndex: 10,
        }}
        title="添加变量"
      >
        <Plus size={14} />
      </button>

      <Collapse
        ghost
        activeKey={activeKey}
        onChange={setActiveKey}
        items={collapseItems}
        style={{ '--ant-collapse-header-padding': '8px 0', '--ant-collapse-content-padding': '0px' }}
      />
    </div>
  );
};

export default NodeConfigDrawer;
