/**
 * 循环节点配置面板
 * 支持循环类型选择、循环数组配置、中间变量、输出变量
 * 参考 Coze/Dify 风格设计
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Plus, Trash2, Info } from 'lucide-react';
import { Collapse, Tooltip, Select } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

// 循环类型选项
const LOOP_TYPE_OPTIONS = [
  { value: 'array', label: '使用数组循环' },
  { value: 'count', label: '使用次数循环' },
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
  Doc: 'doc',
  PPT: 'ppt',
  Excel: 'xls',
  Txt: 'txt',
  Code: 'code',
  Zip: 'zip',
};

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

const cascaderValueToType = (value) => {
  if (!value || value.length === 0) return 'string';
  if (value.length === 1) return value[0].toLowerCase();
  const [parent, child] = value;
  if (parent === 'Array') return `array${child}`;
  if (parent === 'File') {
    if (child === 'Default') return 'fileDefault';
    return `file${child}`;
  }
  return parent.toLowerCase();
};

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

// 类型选择器
const TypeSelector = ({ value, onChange }) => {
  const cascaderValue = useMemo(() => typeToCascaderValue(value), [value]);
  const displayAbbr = useMemo(() => getDisplayAbbr(value), [value]);

  const handleChange = (selectedValue) => {
    const newType = cascaderValueToType(selectedValue);
    onChange(newType);
  };

  return (
    <span style={{ color: '#9ca3af', fontSize: '12px' }}>
      {displayAbbr}.
    </span>
  );
};

// 循环数组配置行
const LoopArrayRow = ({
  loopArray,
  nodes,
  edges,
  currentNodeId,
  onUpdate,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '12px', color: '#6b7280', minWidth: '60px' }}>变量名</span>
        <input
          type="text"
          value={loopArray?.varName || 'input'}
          onChange={(e) => onUpdate('varName', e.target.value)}
          placeholder="变量名"
          style={{
            flex: 1,
            padding: '6px 10px',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
            color: '#374151',
            background: 'white',
          }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '12px', color: '#6b7280', minWidth: '60px' }}>变量值</span>
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
            padding: '0 8px',
            flexShrink: 0,
          }}>
            <TypeSelector
              value={loopArray?.varType || 'arrayString'}
              onChange={(type) => onUpdate('varType', type)}
            />
          </div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', minWidth: 0, height: '100%' }}>
            <ExpressionEditorField
              fields={[{ name: 'value', value: loopArray?.varValue || '' }]}
              onChange={(newFields) => {
                if (newFields.length > 0) {
                  onUpdate('varValue', newFields[0].value);
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
      </div>
    </div>
  );
};

// 次数循环配置
const LoopCountRow = ({ loopCount, onUpdate }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ fontSize: '12px', color: '#6b7280', minWidth: '60px' }}>循环次数</span>
      <input
        type="number"
        min={1}
        max={1000}
        value={loopCount?.value || 1}
        onChange={(e) => onUpdate('value', parseInt(e.target.value, 10) || 1)}
        style={{
          flex: 1,
          padding: '6px 10px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#374151',
          background: 'white',
        }}
      />
    </div>
  );
};

// 中间变量行
const IntermediateVarRow = ({
  variable,
  index,
  onUpdate,
  onDelete,
  canDelete,
}) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <input
        type="text"
        value={variable.name || ''}
        onChange={(e) => onUpdate(index, 'name', e.target.value)}
        placeholder="变量名"
        style={{
          flex: 1,
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#374151',
          height: '32px',
        }}
      />
      <div style={{ width: '80px' }}>
        <TypeSelector
          value={variable.type || 'string'}
          onChange={(type) => onUpdate(index, 'type', type)}
        />
      </div>
      <input
        type="text"
        value={variable.desc || ''}
        onChange={(e) => onUpdate(index, 'desc', e.target.value)}
        placeholder="描述"
        style={{
          flex: 1,
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#9ca3af',
          height: '32px',
        }}
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

// 输出行
const OutputRow = ({
  output,
  index,
  onUpdate,
  onDelete,
  canDelete,
}) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <input
        type="text"
        value={output.name || ''}
        onChange={(e) => onUpdate(index, 'name', e.target.value)}
        placeholder="变量名"
        style={{
          flex: 1,
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#374151',
          height: '32px',
        }}
      />
      <div style={{ width: '80px' }}>
        <TypeSelector
          value={output.type || 'string'}
          onChange={(type) => onUpdate(index, 'type', type)}
        />
      </div>
      <input
        type="text"
        value={output.value || ''}
        onChange={(e) => onUpdate(index, 'value', e.target.value)}
        placeholder="引用参数值"
        style={{
          flex: 1,
          padding: '5px 8px',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          fontSize: '12px',
          outline: 'none',
          color: '#9ca3af',
          height: '32px',
        }}
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
  const [activeKey, setActiveKey] = useState(['loopSettings', 'loopArray', 'intermediateVars', 'outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const loopConfig = nodeData?.loopConfig || { loopType: 'array' };
  const loopArray = loopConfig.loopArray || { varName: 'input', varValue: '', varType: 'arrayString' };
  const loopCount = loopConfig.loopCount || { value: 10 };
  const intermediateVars = nodeData?.intermediateVars || [
    { id: 'var_1', name: 'item', type: 'string', desc: '当前元素' },
    { id: 'var_2', name: 'index', type: 'integer', desc: '当前索引' },
  ];
  const outputs = nodeData?.outputs || [
    { id: 'output_1', name: 'output', type: 'arrayString', value: '' },
  ];

  const handleUpdateLoopConfig = useCallback((updates) => {
    const newLoopConfig = { ...loopConfig, ...updates };
    updateNode(currentNodeId, { ...nodeData, loopConfig: newLoopConfig });
  }, [currentNodeId, nodeData, loopConfig, updateNode]);

  const handleUpdateLoopArray = useCallback((field, value) => {
    const newLoopArray = { ...loopArray, [field]: value };
    handleUpdateLoopConfig({ loopArray: newLoopArray });
  }, [loopArray, handleUpdateLoopConfig]);

  const handleUpdateLoopCount = useCallback((field, value) => {
    const newLoopCount = { ...loopCount, [field]: value };
    handleUpdateLoopConfig({ loopCount: newLoopCount });
  }, [loopCount, handleUpdateLoopConfig]);

  const handleUpdateIntermediateVars = useCallback((newVars) => {
    updateNode(currentNodeId, { ...nodeData, intermediateVars: newVars });
  }, [currentNodeId, nodeData, updateNode]);

  const handleAddIntermediateVar = useCallback(() => {
    const newVar = {
      id: `var_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `var_${intermediateVars.length + 1}`,
      type: 'string',
      desc: '',
    };
    handleUpdateIntermediateVars([...intermediateVars, newVar]);
  }, [intermediateVars, handleUpdateIntermediateVars]);

  const handleDeleteIntermediateVar = useCallback((index) => {
    handleUpdateIntermediateVars(intermediateVars.filter((_, i) => i !== index));
  }, [intermediateVars, handleUpdateIntermediateVars]);

  const handleUpdateIntermediateField = useCallback((index, field, value) => {
    const newVars = intermediateVars.map((v, i) =>
      i === index ? { ...v, [field]: value } : v
    );
    handleUpdateIntermediateVars(newVars);
  }, [intermediateVars, handleUpdateIntermediateVars]);

  const handleUpdateOutputs = useCallback((newOutputs) => {
    updateNode(currentNodeId, { ...nodeData, outputs: newOutputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleAddOutput = useCallback(() => {
    const newOutput = {
      id: `output_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `result_${outputs.length + 1}`,
      type: 'string',
      value: '',
    };
    handleUpdateOutputs([...outputs, newOutput]);
  }, [outputs, handleUpdateOutputs]);

  const handleDeleteOutput = useCallback((index) => {
    handleUpdateOutputs(outputs.filter((_, i) => i !== index));
  }, [outputs, handleUpdateOutputs]);

  const handleUpdateOutputField = useCallback((index, field, value) => {
    const newOutputs = outputs.map((o, i) =>
      i === index ? { ...o, [field]: value } : o
    );
    handleUpdateOutputs(newOutputs);
  }, [outputs, handleUpdateOutputs]);

  const collapseItems = [
    {
      key: 'loopSettings',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>循环设置</span>
            <Tooltip title="选择循环的执行方式">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: '#6b7280', minWidth: '60px' }}>循环类型</span>
            <Select
              value={loopConfig.loopType || 'array'}
              onChange={(value) => handleUpdateLoopConfig({ loopType: value })}
              options={LOOP_TYPE_OPTIONS}
              style={{ flex: 1 }}
              size="small"
            />
          </div>
        </div>
      ),
    },
    {
      key: 'loopArray',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              {loopConfig.loopType === 'array' ? '循环数组' : '循环次数'}
            </span>
            <Tooltip title={loopConfig.loopType === 'array' ? '配置要遍历的数组变量' : '配置循环执行的次数'}>
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: loopConfig.loopType === 'array' ? (
        <LoopArrayRow
          loopArray={loopArray}
          nodes={nodes}
          edges={edges}
          currentNodeId={currentNodeId}
          onUpdate={handleUpdateLoopArray}
        />
      ) : (
        <LoopCountRow
          loopCount={loopCount}
          onUpdate={handleUpdateLoopCount}
        />
      ),
    },
    {
      key: 'intermediateVars',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>中间变量</span>
            <Tooltip title="每次迭代时注入循环体的变量">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleAddIntermediateVar();
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
          {intermediateVars.length === 0 && (
            <div style={{
              padding: '16px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '13px',
            }}>
              暂无中间变量，点击右上角 + 按钮添加
            </div>
          )}
          {intermediateVars.map((variable, index) => (
            <IntermediateVarRow
              key={variable.id || index}
              variable={variable}
              index={index}
              onUpdate={handleUpdateIntermediateField}
              onDelete={handleDeleteIntermediateVar}
              canDelete={intermediateVars.length > 0}
            />
          ))}
        </div>
      ),
    },
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
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输出</span>
            <Tooltip title="配置循环执行后的输出变量">
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
          {outputs.length === 0 && (
            <div style={{
              padding: '16px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '13px',
            }}>
              暂无输出变量，点击右上角 + 按钮添加
            </div>
          )}
          {outputs.map((output, index) => (
            <OutputRow
              key={output.id || index}
              output={output}
              index={index}
              onUpdate={handleUpdateOutputField}
              onDelete={handleDeleteOutput}
              canDelete={outputs.length > 0}
            />
          ))}
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
        用于通过设定循环次数和逻辑，重复执行一系列任务
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
