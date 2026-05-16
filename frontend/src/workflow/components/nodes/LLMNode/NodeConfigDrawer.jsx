/**
 * 大模型节点配置面板（LLM Node Config Drawer）
 * 支持：
 *   - 单次/批处理模式切换
 *   - 模型选择
 *   - 技能配置
 *   - 输入变量管理（变量名 + 类型 + 值/引用）
 *   - 视觉理解输入
 *   - 系统提示词
 *   - 用户提示词
 *   - 输出变量管理（变量名 + 类型 + 输出格式）
 *   - 支持续写开关
 *   - 异常处理
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, Info, Settings } from 'lucide-react';
import { Collapse, Tooltip, Select, Switch, Cascader, Radio } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import { useWebSocket } from '../../../../contexts/WebSocketContext';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

// ==================== 常量定义 ====================

const EXEC_MODE_OPTIONS = [
  { label: '单次', value: 'single' },
  { label: '批处理', value: 'batch' },
];



// 输出格式选项
const OUTPUT_FORMAT_OPTIONS = [
  { value: 'text', label: '文本' },
  { value: 'json', label: 'JSON' },
  { value: 'markdown', label: 'Markdown' },
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

const generateId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// ==================== 子组件 ====================

// 类型选择器
const TypeSelector = ({ value, onChange }) => {
  const cascaderValue = useMemo(() => typeToCascaderValue(value), [value]);
  const displayAbbr = useMemo(() => getDisplayAbbr(value), [value]);

  return (
    <Cascader
      options={TYPE_CASCADER_OPTIONS}
      value={cascaderValue}
      onChange={(v) => onChange(cascaderValueToType(v))}
      expandTrigger="hover"
      changeOnSelect
      displayRender={() => (
        <span style={{ color: '#6b7280', fontSize: '12px' }}>{displayAbbr}.</span>
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
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          overflow: 'hidden',
          background: 'white',
          height: '32px',
        }}
      >
        <div
          style={{
            borderRight: '1px solid #e5e7eb',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            padding: '0 4px',
            flexShrink: 0,
          }}
        >
          <TypeSelector value={input.type || 'string'} onChange={(type) => onUpdate(index, 'type', type)} />
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
      <div style={{ width: '120px' }}>
        <TypeSelector value={output.type || 'string'} onChange={(type) => onUpdate(index, 'type', type)} />
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

// 提示词编辑器
const PromptEditor = ({ value, onChange, placeholder, rows = 4 }) => {
  return (
    <textarea
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
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
  );
};

// ==================== 主组件 ====================

const NodeConfigDrawer = ({ nodes, edges, currentNodeId, nodeData }) => {
  const [activeKey, setActiveKey] = useState([
    'model',
    'inputs',
    'systemPrompt',
    'userPrompt',
    'outputs',
  ]);
  const updateNode = useWorkflowStore((state) => state.updateNode);
  const { sendMessage } = useWebSocket();

  // Provider / Model 动态数据
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);

  // 从 nodeData 读取配置（兼容旧数据的 model 字段）
  const execMode = nodeData?.execMode || 'single';
  const providerId = nodeData?.providerId || '';
  const modelId = nodeData?.modelId || nodeData?.model || '';
  const skills = nodeData?.skills || [];
  const inputs = nodeData?.inputs || [];
  const visionInputs = nodeData?.visionInputs || [];
  const systemPrompt = nodeData?.systemPrompt || '';
  const userPrompt = nodeData?.userPrompt || '';
  const outputs = nodeData?.outputs || [{ id: 'default_out', name: 'output', type: 'string' }];
  const outputFormat = nodeData?.outputFormat || 'text';
  const enableContinuation = nodeData?.enableContinuation || false;
  const exceptionHandler = nodeData?.exceptionHandler || 'default';

  // 加载 providers
  useEffect(() => {
    let cancelled = false;
    setLoadingProviders(true);
    sendMessage('model_get_providers', {}, 10000)
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.providers || [];
        setProviders(list);
      })
      .catch((err) => {
        if (cancelled) return;
      })
      .finally(() => {
        if (!cancelled) setLoadingProviders(false);
      });
    return () => { cancelled = true; };
  }, [sendMessage]);

  // 当 providerId 变化时加载 models
  useEffect(() => {
    let cancelled = false;
    if (!providerId) {
      setModels([]);
      return;
    }
    setLoadingModels(true);
    sendMessage('model_get_models', { provider_id: providerId }, 10000)
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.models || [];
        setModels(list);
      })
      .catch((err) => {
        if (cancelled) return;
      })
      .finally(() => {
        if (!cancelled) setLoadingModels(false);
      });
    return () => { cancelled = true; };
  }, [providerId, sendMessage]);

  const handleUpdate = useCallback(
    (updates) => {
      updateNode(currentNodeId, { ...nodeData, ...updates });
    },
    [currentNodeId, nodeData, updateNode]
  );

  const selectedProvider = useMemo(() => providers.find((p) => p.id === providerId), [providers, providerId]);
  const selectedModel = useMemo(() => models.find((m) => m.id === modelId), [models, modelId]);

  const handleProviderChange = useCallback(
    (value) => {
      // 切换 provider 时，清空 model 选择，等待新的 model 列表加载后再选
      handleUpdate({
        providerId: value,
        modelId: '',
        // 同时清除旧兼容字段
        model: undefined,
      });
    },
    [handleUpdate]
  );

  const handleModelChange = useCallback(
    (value) => {
      handleUpdate({ modelId: value, model: undefined });
    },
    [handleUpdate]
  );

  // ---------- 输入变量管理 ----------
  const handleAddInput = useCallback(() => {
    const newInput = {
      id: generateId('input'),
      name: `input_${inputs.length + 1}`,
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

  // ---------- 视觉理解输入管理 ----------
  const handleAddVisionInput = useCallback(() => {
    const newVision = {
      id: generateId('vision'),
      value: '',
    };
    handleUpdate({ visionInputs: [...visionInputs, newVision] });
  }, [visionInputs, handleUpdate]);

  const handleDeleteVisionInput = useCallback(
    (index) => {
      handleUpdate({ visionInputs: visionInputs.filter((_, i) => i !== index) });
    },
    [visionInputs, handleUpdate]
  );

  const handleUpdateVisionInput = useCallback(
    (index, value) => {
      const newVisionInputs = visionInputs.map((v, i) =>
        i === index ? { ...v, value } : v
      );
      handleUpdate({ visionInputs: newVisionInputs });
    },
    [visionInputs, handleUpdate]
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

  // ==================== Collapse 配置项 ====================

  const collapseItems = [
    // 1. 模型配置
    {
      key: 'model',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>模型</span>
            <Tooltip title="选择要调用的大语言模型">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {(providerId || modelId) && (
            <span
              style={{
                fontSize: '11px',
                color: '#8b5cf6',
                background: '#f3f0ff',
                padding: '1px 8px',
                borderRadius: '10px',
              }}
            >
              {selectedProvider?.name || providerId}
              {modelId ? ` / ${selectedModel?.name || modelId}` : ''}
            </span>
          )}
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* 执行模式 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '4px',
              background: '#f3f4f6',
              borderRadius: '8px',
            }}
          >
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              size="small"
              value={execMode}
              onChange={(e) => handleUpdate({ execMode: e.target.value })}
              options={EXEC_MODE_OPTIONS}
            />
          </div>

          {/* Provider 选择 */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
              选择 Provider
            </div>
            <Select
              value={providerId || undefined}
              onChange={handleProviderChange}
              options={providers.map((p) => ({ value: p.id, label: p.name || p.id }))}
              placeholder="请选择 Provider"
              style={{ width: '100%' }}
              size="middle"
              loading={loadingProviders}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>

          {/* Model 选择 */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
              选择模型
            </div>
            <Select
              value={modelId || undefined}
              onChange={handleModelChange}
              options={models.map((m) => ({ value: m.id, label: m.name || m.id }))}
              placeholder={providerId ? '请选择模型' : '请先选择 Provider'}
              style={{ width: '100%' }}
              size="middle"
              loading={loadingModels}
              disabled={!providerId || loadingModels}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>

          {/* 技能配置 */}
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '6px',
              }}
            >
              <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: 500 }}>技能</span>
              <button
                onClick={() => {
                  // 技能添加逻辑（后续扩展）
                }}
                style={{
                  padding: '4px 10px',
                  border: '1px dashed #c7d2fe',
                  borderRadius: '6px',
                  background: '#f5f7ff',
                  color: '#6366f1',
                  fontSize: '12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Plus size={12} />
                添加技能
              </button>
            </div>
            {skills.length === 0 && (
              <div
                style={{
                  padding: '12px',
                  textAlign: 'center',
                  color: '#9ca3af',
                  fontSize: '12px',
                  background: '#f9fafb',
                  borderRadius: '6px',
                }}
              >
                未配置技能
              </div>
            )}
            {skills.map((skill, idx) => (
              <div
                key={skill.id || idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: '#f9fafb',
                  borderRadius: '6px',
                  marginBottom: '4px',
                }}
              >
                <span style={{ fontSize: '12px', color: '#374151' }}>{skill.name || '未命名技能'}</span>
                <button
                  onClick={() => {
                    const newSkills = skills.filter((_, i) => i !== idx);
                    handleUpdate({ skills: newSkills });
                  }}
                  style={{
                    padding: '4px',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: '#d1d5db',
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ),
    },

    // 2. 输入变量
    {
      key: 'inputs',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>输入</span>
            <Tooltip title="配置输入变量，可在提示词中引用">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <span
            style={{
              fontSize: '11px',
              color: '#9ca3af',
              background: '#f3f4f6',
              padding: '1px 6px',
              borderRadius: '10px',
            }}
          >
            {inputs.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {/* 表头 */}
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
            <div style={{ flex: 1, fontSize: '12px', color: '#9ca3af' }}>变量值</div>
            <div style={{ width: '28px' }} />
          </div>

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

          {inputs.length === 0 && (
            <div
              style={{
                padding: '16px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
              }}
            >
              暂无输入变量
            </div>
          )}

          <button
            onClick={handleAddInput}
            style={{
              marginTop: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              padding: '6px',
              border: '1px dashed #c7d2fe',
              borderRadius: '6px',
              background: '#f5f7ff',
              color: '#6366f1',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
              width: '100%',
            }}
          >
            <Plus size={12} />
            新增输入变量
          </button>
        </div>
      ),
    },

    // 3. 视觉理解输入
    {
      key: 'visionInputs',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>视觉理解输入</span>
            <Tooltip title="配置视觉理解输入（图片等），用于多模态模型">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <span
            style={{
              fontSize: '11px',
              color: '#9ca3af',
              background: '#f3f4f6',
              padding: '1px 6px',
              borderRadius: '10px',
            }}
          >
            {visionInputs.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {visionInputs.map((vision, index) => (
            <div key={vision.id || index} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  overflow: 'hidden',
                  background: 'white',
                  height: '32px',
                }}
              >
                <ExpressionEditorField
                  fields={[{ name: `vision_${index}`, value: vision.value || '' }]}
                  onChange={(newFields) => {
                    if (newFields.length > 0) {
                      handleUpdateVisionInput(index, newFields[0].value);
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
              <button
                onClick={() => handleDeleteVisionInput(index)}
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
            </div>
          ))}

          {visionInputs.length === 0 && (
            <div
              style={{
                padding: '12px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
                background: '#f9fafb',
                borderRadius: '6px',
              }}
            >
              暂无视觉理解输入
            </div>
          )}

          <button
            onClick={handleAddVisionInput}
            style={{
              marginTop: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              padding: '6px',
              border: '1px dashed #c7d2fe',
              borderRadius: '6px',
              background: '#f5f7ff',
              color: '#6366f1',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
              width: '100%',
            }}
          >
            <Plus size={12} />
            新增视觉输入
          </button>
        </div>
      ),
    },

    // 4. 系统提示词
    {
      key: 'systemPrompt',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>系统提示词</span>
            <Tooltip title="设置系统级提示词，定义模型的行为角色和全局约束">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {systemPrompt && (
            <span
              style={{
                fontSize: '11px',
                color: '#10b981',
                background: '#ecfdf5',
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              已配置
            </span>
          )}
        </div>
      ),
      children: (
        <div>
          <PromptEditor
            value={systemPrompt}
            onChange={(value) => handleUpdate({ systemPrompt: value })}
            placeholder="你是一个专业的助手..."
            rows={4}
          />
          <div
            style={{
              marginTop: '6px',
              fontSize: '11px',
              color: '#9ca3af',
              lineHeight: 1.5,
            }}
          >
            系统提示词用于定义模型的角色和行为规范
          </div>
        </div>
      ),
    },

    // 5. 用户提示词
    {
      key: 'userPrompt',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>用户提示词</span>
            <Tooltip title="设置用户提示词，支持使用 {{变量名}} 引用输入变量">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {userPrompt && (
            <span
              style={{
                fontSize: '11px',
                color: '#10b981',
                background: '#ecfdf5',
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              已配置
            </span>
          )}
        </div>
      ),
      children: (
        <div>
          <PromptEditor
            value={userPrompt}
            onChange={(value) => handleUpdate({ userPrompt: value })}
            placeholder="请根据以下信息回答问题：{{input}}"
            rows={6}
          />
          <div
            style={{
              marginTop: '6px',
              fontSize: '11px',
              color: '#9ca3af',
              lineHeight: 1.5,
            }}
          >
            支持使用 {'{{变量名}}'} 引用输入变量
          </div>
        </div>
      ),
    },

    // 6. 输出配置
    {
      key: 'outputs',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>输出</span>
            <Tooltip title="配置输出变量和输出格式">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <span
            style={{
              fontSize: '11px',
              color: '#9ca3af',
              background: '#f3f4f6',
              padding: '1px 6px',
              borderRadius: '10px',
            }}
          >
            {outputs.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* 输出格式 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: 500 }}>输出格式</span>
            <Select
              value={outputFormat}
              onChange={(value) => handleUpdate({ outputFormat: value })}
              options={OUTPUT_FORMAT_OPTIONS}
              size="small"
              style={{ width: '120px' }}
            />
          </div>

          {/* 输出变量列表 */}
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

          <button
            onClick={handleAddOutput}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              padding: '6px',
              border: '1px dashed #c7d2fe',
              borderRadius: '6px',
              background: '#f5f7ff',
              color: '#6366f1',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
              width: '100%',
            }}
          >
            <Plus size={12} />
            新增输出变量
          </button>

          {/* 支持续写 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 0',
              borderTop: '1px solid #f0f0f0',
              marginTop: '4px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '12px', color: '#374151' }}>支持续写</span>
              <Tooltip title="开启后支持对话续写功能">
                <Info size={12} color="#9ca3af" style={{ cursor: 'pointer' }} />
              </Tooltip>
            </div>
            <Switch
              size="small"
              checked={enableContinuation}
              onChange={(checked) => handleUpdate({ enableContinuation: checked })}
            />
          </div>
        </div>
      ),
    },

    // 7. 异常处理
    {
      key: 'exception',
      label: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>异常处理</span>
            <Tooltip title="配置节点执行异常时的处理策略">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Radio.Group
            value={exceptionHandler}
            onChange={(e) => handleUpdate({ exceptionHandler: e.target.value })}
            style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
          >
            <Radio value="default">
              <span style={{ fontSize: '12px', color: '#374151' }}>默认处理（中断执行并上报错误）</span>
            </Radio>
            <Radio value="ignore">
              <span style={{ fontSize: '12px', color: '#374151' }}>忽略异常（继续执行后续节点）</span>
            </Radio>
            <Radio value="fallback">
              <span style={{ fontSize: '12px', color: '#374151' }}>使用默认值（输出预设的默认值）</span>
            </Radio>
          </Radio.Group>

          {exceptionHandler === 'fallback' && (
            <div style={{ marginTop: '4px' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>默认返回值</div>
              <PromptEditor
                value={nodeData?.fallbackValue || ''}
                onChange={(value) => handleUpdate({ fallbackValue: value })}
                placeholder="请输入异常时的默认返回值"
                rows={3}
              />
            </div>
          )}
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
        调用大语言模型，使用变量和提示词生成回复。支持单次/批处理、多模态视觉理解、系统/用户提示词配置。
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
