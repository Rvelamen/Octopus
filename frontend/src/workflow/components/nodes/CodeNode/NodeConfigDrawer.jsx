/**
 * 代码节点配置面板
 * 参考图片设计：输入变量 + 代码编辑器 + 输出变量
 * 支持 Python 代码编写
 */

import React, { useCallback, useState, useMemo, useEffect } from 'react';
import { Plus, Trash2, Info, Maximize2, ChevronRight, ChevronDown } from 'lucide-react';
import { Collapse, Tooltip, Cascader } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

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
    <Cascader
      options={TYPE_CASCADER_OPTIONS}
      value={cascaderValue}
      onChange={handleChange}
      expandTrigger="hover"
      changeOnSelect
      displayRender={() => (
        <span style={{ color: '#6b7280', fontSize: '12px' }}>
          {displayAbbr}.
        </span>
      )}
      dropdownStyle={{ maxHeight: 'none', overflow: 'visible' }}
      dropdownMenuColumnStyle={{ maxHeight: 'none', height: 'auto', overflow: 'visible' }}
      style={{ width: '100%' }}
      size="small"
      bordered={false}
    />
  );
};

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
          <TypeSelector
            value={input.type || 'string'}
            onChange={(type) => onUpdate(index, 'type', type)}
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

// 输出变量行（支持嵌套 Object）
const OutputRow = ({ output, index, onUpdate, onDelete, canDelete, depth = 0 }) => {
  const [expanded, setExpanded] = useState(false);
  const isObject = output.type === 'object';
  const hasChildren = isObject && output.children && output.children.length > 0;

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        paddingLeft: `${depth * 20}px`,
      }}>
        {isObject && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              padding: '2px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#9ca3af',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        )}
        {!isObject && <div style={{ width: '20px' }} />}
        <input
          type="text"
          value={output.name || ''}
          onChange={(e) => onUpdate(index, 'name', e.target.value, depth)}
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
        <div style={{ width: '120px' }}>
          <TypeSelector
            value={output.type || 'string'}
            onChange={(type) => onUpdate(index, 'type', type, depth)}
          />
        </div>
        {isObject && (
          <button
            onClick={() => onUpdate(index, 'addChild', null, depth)}
            style={{
              padding: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#6366f1',
              display: 'flex',
              alignItems: 'center',
            }}
            title="添加子变量"
          >
            <Plus size={14} />
          </button>
        )}
        {canDelete && (
          <button
            onClick={() => onDelete(index, depth)}
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
      {expanded && hasChildren && (
        <div style={{ marginTop: '4px' }}>
          {output.children.map((child, childIdx) => (
            <OutputRow
              key={child.id || childIdx}
              output={child}
              index={childIdx}
              onUpdate={onUpdate}
              onDelete={onDelete}
              canDelete={true}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// 全屏代码编辑器弹窗
const FullscreenCodeEditor = ({ value, onChange, onClose }) => {
  const [localValue, setLocalValue] = useState(value || '');

  const handleSave = () => {
    onChange(localValue);
    onClose();
  };

  // Ctrl+S 快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [localValue, onChange, onClose]);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        flexDirection: 'column',
        background: '#1e1e1e',
      }}
    >
      {/* 顶部工具栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: '#2d2d2d',
        borderBottom: '1px solid #3d3d3d',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', color: '#e5e7eb', fontWeight: 500 }}>Python 代码编辑器</span>
          <span style={{
            fontSize: '11px',
            color: '#9ca3af',
            background: '#3d3d3d',
            padding: '2px 8px',
            borderRadius: '4px',
          }}>
            全屏模式
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={handleSave}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: '#6366f1',
              color: 'white',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 500,
            }}
          >
            保存
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #4b5563',
              background: 'transparent',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            取消
          </button>
        </div>
      </div>

      {/* 编辑器区域 */}
      <div style={{ flex: 1, display: 'flex' }}>
        {/* 行号 */}
        <div style={{
          width: '48px',
          background: '#1e1e1e',
          borderRight: '1px solid #2d2d2d',
          padding: '12px 8px',
          textAlign: 'right',
          fontSize: '13px',
          lineHeight: '1.6',
          color: '#4b5563',
          fontFamily: '"Fira Code", "Consolas", monospace',
          overflow: 'hidden',
          userSelect: 'none',
        }}>
          {localValue.split('\n').map((_, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
        {/* 文本区域 */}
        <textarea
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          style={{
            flex: 1,
            padding: '12px',
            border: 'none',
            fontSize: '13px',
            fontFamily: '"Fira Code", "Consolas", monospace',
            resize: 'none',
            outline: 'none',
            background: '#1e1e1e',
            lineHeight: '1.6',
            color: '#e5e7eb',
            tabSize: 4,
          }}
          spellCheck={false}
        />
      </div>

      {/* 底部提示 */}
      <div style={{
        padding: '8px 16px',
        background: '#2d2d2d',
        borderTop: '1px solid #3d3d3d',
        fontSize: '12px',
        color: '#6b7280',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
      }}>
        <span>通过 <code style={{ color: '#6366f1' }}>params</code> 获取输入变量</span>
        <span>返回 <code style={{ color: '#6366f1' }}>ret</code> 对象作为输出</span>
        <span style={{ marginLeft: 'auto' }}>按 Ctrl+S 保存</span>
      </div>
    </div>
  );
};

// 代码编辑器（简单 textarea 版本，支持全屏弹窗）
const CodeEditor = ({ value, onChange }) => {
  const [showFullscreen, setShowFullscreen] = useState(false);

  return (
    <>
      <div style={{ position: 'relative' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: '#1e1e1e',
          borderRadius: '8px 8px 0 0',
        }}>
          <span style={{ fontSize: '12px', color: '#9ca3af' }}>Python</span>
          <button
            onClick={() => setShowFullscreen(true)}
            style={{
              padding: '4px 8px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#9ca3af',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '12px',
            }}
          >
            <Maximize2 size={12} />
            在IDE中编辑
          </button>
        </div>
        <textarea
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`# 在这里编写 Python 代码\n# 可以通过 params 获取输入变量\n# 通过 ret 输出结果\n\ndef main(params):\n    ret = {\n        "result": params.get("input", "")\n    }\n    return ret`}
          style={{
            width: '100%',
            minHeight: '200px',
            padding: '12px',
            border: '1px solid #e5e7eb',
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
            fontSize: '13px',
            fontFamily: '"Fira Code", "Consolas", monospace',
            resize: 'vertical',
            outline: 'none',
            background: '#fafafa',
            lineHeight: 1.6,
            color: '#374151',
          }}
        />
      </div>
      {showFullscreen && (
        <FullscreenCodeEditor
          value={value}
          onChange={onChange}
          onClose={() => setShowFullscreen(false)}
        />
      )}
    </>
  );
};

// 默认代码模板
const DEFAULT_CODE_TEMPLATE = `def main(params):
    # 在这里编写 Python 代码
    # 可以通过 params 获取输入变量
    # 通过 ret 输出结果

    ret = {
        "result": params.get("input", "")
    }
    return ret`;

const NodeConfigDrawer = ({
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = useState(['inputs', 'code', 'outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const inputs = nodeData?.inputs || [];
  const outputs = nodeData?.outputs || [];
  const code = nodeData?.code || '';

  // 初始化时如果代码为空，填充默认模板
  useEffect(() => {
    if (!code || code.trim() === '') {
      handleUpdateCode(DEFAULT_CODE_TEMPLATE);
    }
  }, []);

  const handleUpdateInputs = useCallback((newInputs) => {
    updateNode(currentNodeId, { ...nodeData, inputs: newInputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleUpdateOutputs = useCallback((newOutputs) => {
    updateNode(currentNodeId, { ...nodeData, outputs: newOutputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleUpdateCode = useCallback((newCode) => {
    updateNode(currentNodeId, { ...nodeData, code: newCode });
  }, [currentNodeId, nodeData, updateNode]);

  const handleAddInput = useCallback(() => {
    const newInput = {
      id: `input_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `var_${inputs.length + 1}`,
      type: 'string',
      value: '',
    };
    handleUpdateInputs([...inputs, newInput]);
  }, [inputs, handleUpdateInputs]);

  const handleDeleteInput = useCallback((index) => {
    handleUpdateInputs(inputs.filter((_, i) => i !== index));
  }, [inputs, handleUpdateInputs]);

  const handleUpdateInputField = useCallback((index, field, fieldValue) => {
    const newInputs = inputs.map((input, i) =>
      i === index ? { ...input, [field]: fieldValue } : input
    );
    handleUpdateInputs(newInputs);
  }, [inputs, handleUpdateInputs]);

  const handleAddOutput = useCallback(() => {
    const newOutput = {
      id: `output_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `result_${outputs.length + 1}`,
      type: 'string',
    };
    handleUpdateOutputs([...outputs, newOutput]);
  }, [outputs, handleUpdateOutputs]);

  const handleDeleteOutput = useCallback((index, depth = 0) => {
    if (depth === 0) {
      handleUpdateOutputs(outputs.filter((_, i) => i !== index));
    }
  }, [outputs, handleUpdateOutputs]);

  const handleUpdateOutputField = useCallback((index, field, fieldValue, depth = 0) => {
    if (depth === 0) {
      if (field === 'addChild') {
        const newOutputs = outputs.map((output, i) => {
          if (i === index) {
            const children = output.children || [];
            return {
              ...output,
              children: [...children, {
                id: `child_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                name: `sub_${children.length + 1}`,
                type: 'string',
              }],
            };
          }
          return output;
        });
        handleUpdateOutputs(newOutputs);
      } else {
        const newOutputs = outputs.map((output, i) =>
          i === index ? { ...output, [field]: fieldValue } : output
        );
        handleUpdateOutputs(newOutputs);
      }
    }
  }, [outputs, handleUpdateOutputs]);

  const collapseItems = [
    {
      key: 'inputs',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输入</span>
            <Tooltip title="定义代码节点的输入变量，可在代码中通过 params 访问">
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
    {
      key: 'code',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>代码</span>
            <Tooltip title="编写 Python 代码，通过 params 获取输入，通过 ret 返回结果">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <span style={{
            fontSize: '11px',
            color: '#9ca3af',
            background: '#f3f4f6',
            padding: '2px 8px',
            borderRadius: '4px',
          }}>
            Python
          </span>
        </div>
      ),
      children: (
        <div>
          <CodeEditor value={code} onChange={handleUpdateCode} />
          <div style={{
            marginTop: '8px',
            padding: '8px 12px',
            background: '#f9fafb',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#6b7280',
            lineHeight: 1.5,
          }}>
            提示：通过 <code style={{ color: '#6366f1', background: '#eef2ff', padding: '1px 4px', borderRadius: '3px' }}>params</code> 获取输入变量，返回 <code style={{ color: '#6366f1', background: '#eef2ff', padding: '1px 4px', borderRadius: '3px' }}>ret</code> 对象作为输出
          </div>
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
            <Tooltip title="定义代码节点的输出变量类型，支持嵌套 Object">
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
