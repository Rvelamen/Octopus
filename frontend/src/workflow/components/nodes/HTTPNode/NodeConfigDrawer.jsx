/**
 * HTTP 请求节点配置面板
 * 支持：
 *   - HTTP 方法选择（GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS）
 *   - URL 配置（支持变量引用）
 *   - 请求参数（Query Params）
 *   - 请求头（Headers）
 *   - 鉴权配置（Bearer Token / Basic Auth / API Key）
 *   - 请求体（Body）
 *   - 超时设置
 *   - 重试次数
 *   - 输出变量管理
 *   - 异常忽略开关
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Plus, Trash2, Info, ExternalLink } from 'lucide-react';
import { Collapse, Tooltip, Select, Switch, InputNumber, Radio } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

// ==================== 常量定义 ====================

const HTTP_METHODS = [
  { value: 'GET', label: 'GET', color: '#10b981' },
  { value: 'POST', label: 'POST', color: '#3b82f6' },
  { value: 'PUT', label: 'PUT', color: '#f59e0b' },
  { value: 'DELETE', label: 'DELETE', color: '#ef4444' },
  { value: 'PATCH', label: 'PATCH', color: '#8b5cf6' },
  { value: 'HEAD', label: 'HEAD', color: '#6b7280' },
  { value: 'OPTIONS', label: 'OPTIONS', color: '#9ca3af' },
];

const AUTH_TYPES = [
  { value: 'none', label: '无鉴权' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'apiKey', label: 'API Key' },
];

const BODY_TYPES = [
  { value: 'none', label: '无' },
  { value: 'json', label: 'JSON' },
  { value: 'form', label: 'Form Data' },
  { value: 'raw', label: 'Raw' },
];

const DEFAULT_OUTPUTS = [
  { id: 'out_body', name: 'body', type: 'string' },
  { id: 'out_status', name: 'statusCode', type: 'integer' },
  { id: 'out_headers', name: 'headers', type: 'string' },
];

const generateId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// ==================== 子组件 ====================

// 键值对行（用于 Query Params / Headers）
const KeyValueRow = ({ item, index, onUpdate, onDelete, canDelete, valuePlaceholder = '值' }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <input
        type="text"
        value={item.key || ''}
        onChange={(e) => onUpdate(index, 'key', e.target.value)}
        placeholder="键"
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
      <input
        type="text"
        value={item.value || ''}
        onChange={(e) => onUpdate(index, 'value', e.target.value)}
        placeholder={valuePlaceholder}
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
        options={[
          { value: 'string', label: 'String' },
          { value: 'integer', label: 'Integer' },
          { value: 'number', label: 'Number' },
          { value: 'boolean', label: 'Boolean' },
          { value: 'object', label: 'Object' },
        ]}
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

// ==================== 主组件 ====================

const NodeConfigDrawer = ({ nodes, edges, currentNodeId, nodeData }) => {
  const [activeKey, setActiveKey] = useState(['api', 'params', 'headers', 'outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  // 从 nodeData 读取配置
  const method = nodeData?.method || 'GET';
  const url = nodeData?.url || '';
  const params = nodeData?.params || [];
  const headers = nodeData?.headers || [];
  const authType = nodeData?.authType || 'none';
  const authConfig = nodeData?.authConfig || {};
  const bodyType = nodeData?.bodyType || 'none';
  const bodyContent = nodeData?.bodyContent || '';
  const timeout = nodeData?.timeout || 30;
  const retryCount = nodeData?.retryCount || 3;
  const outputs = nodeData?.outputs || DEFAULT_OUTPUTS;
  const ignoreError = nodeData?.ignoreError || false;
  const fallbackValue = nodeData?.fallbackValue || '';

  const handleUpdate = useCallback(
    (updates) => {
      updateNode(currentNodeId, { ...nodeData, ...updates });
    },
    [currentNodeId, nodeData, updateNode]
  );

  // ---------- 键值对管理（Params / Headers） ----------
  const createKVHandlers = (items, key) => ({
    add: () => {
      handleUpdate({ [key]: [...items, { id: generateId('kv'), key: '', value: '' }] });
    },
    delete: (index) => {
      handleUpdate({ [key]: items.filter((_, i) => i !== index) });
    },
    update: (index, field, fieldValue) => {
      const newItems = items.map((item, i) =>
        i === index ? { ...item, [field]: fieldValue } : item
      );
      handleUpdate({ [key]: newItems });
    },
  });

  const paramsHandlers = createKVHandlers(params, 'params');
  const headersHandlers = createKVHandlers(headers, 'headers');

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
    // 1. API 配置
    {
      key: 'api',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>API</span>
            <Tooltip title="配置请求方法和接口地址">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {method && (
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                color: 'white',
                background: HTTP_METHODS.find((m) => m.value === method)?.color || '#6b7280',
                padding: '1px 6px',
                borderRadius: '4px',
              }}
            >
              {method}
            </span>
          )}
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* 导入 cURL 按钮 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={() => {
                // TODO: 实现 cURL 导入功能
              }}
              style={{
                padding: '4px 10px',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                background: 'white',
                color: '#6366f1',
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <ExternalLink size={12} />
              导入 cURL
            </button>
          </div>

          {/* 方法选择 */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>请求方法</div>
            <Select
              value={method}
              onChange={(value) => handleUpdate({ method: value })}
              options={HTTP_METHODS}
              style={{ width: '100%' }}
              size="middle"
            />
          </div>

          {/* URL 输入 */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>请求地址</div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                overflow: 'hidden',
                background: 'white',
                minHeight: '36px',
              }}
            >
              <ExpressionEditorField
                fields={[{ name: 'url', value: url }]}
                onChange={(newFields) => {
                  if (newFields.length > 0) {
                    handleUpdate({ url: newFields[0].value });
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
            <div style={{ marginTop: '4px', fontSize: '11px', color: '#9ca3af' }}>
              请输入接口的URL，可以使用 {'{{'} 引用变量
            </div>
          </div>
        </div>
      ),
    },

    // 2. 请求参数
    {
      key: 'params',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>请求参数</span>
            <Tooltip title="配置 URL 查询参数（Query Params）">
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
            {params.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {params.length === 0 && (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '8px' }}>📭</div>
              参数为空
            </div>
          )}
          {params.map((param, index) => (
            <KeyValueRow
              key={param.id || index}
              item={param}
              index={index}
              onUpdate={paramsHandlers.update}
              onDelete={paramsHandlers.delete}
              canDelete={params.length > 0}
            />
          ))}
          <button
            onClick={paramsHandlers.add}
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
            新增参数
          </button>
        </div>
      ),
    },

    // 3. 请求头
    {
      key: 'headers',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>请求头</span>
            <Tooltip title="配置 HTTP 请求头">
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
            {headers.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {headers.length === 0 && (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: '#9ca3af',
                fontSize: '13px',
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '8px' }}>📭</div>
              参数为空
            </div>
          )}
          {headers.map((header, index) => (
            <KeyValueRow
              key={header.id || index}
              item={header}
              index={index}
              onUpdate={headersHandlers.update}
              onDelete={headersHandlers.delete}
              canDelete={headers.length > 0}
            />
          ))}
          <button
            onClick={headersHandlers.add}
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
            新增请求头
          </button>
        </div>
      ),
    },

    // 4. 鉴权
    {
      key: 'auth',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>鉴权</span>
            <Tooltip title="配置请求鉴权方式">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <Switch size="small" checked={authType !== 'none'} onChange={(checked) => handleUpdate({ authType: checked ? 'bearer' : 'none' })} />
        </div>
      ),
      children: authType === 'none' ? null : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Radio.Group
            value={authType}
            onChange={(e) => handleUpdate({ authType: e.target.value })}
            size="small"
          >
            {AUTH_TYPES.filter((t) => t.value !== 'none').map((type) => (
              <Radio.Button key={type.value} value={type.value}>
                {type.label}
              </Radio.Button>
            ))}
          </Radio.Group>

          {authType === 'bearer' && (
            <div>
              <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>Token</div>
              <input
                type="text"
                value={authConfig.token || ''}
                onChange={(e) => handleUpdate({ authConfig: { ...authConfig, token: e.target.value } })}
                placeholder="Bearer token"
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
          )}

          {authType === 'basic' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>用户名</div>
                <input
                  type="text"
                  value={authConfig.username || ''}
                  onChange={(e) => handleUpdate({ authConfig: { ...authConfig, username: e.target.value } })}
                  placeholder="Username"
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
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>密码</div>
                <input
                  type="password"
                  value={authConfig.password || ''}
                  onChange={(e) => handleUpdate({ authConfig: { ...authConfig, password: e.target.value } })}
                  placeholder="Password"
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
          )}

          {authType === 'apiKey' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>Key</div>
                <input
                  type="text"
                  value={authConfig.apiKey || ''}
                  onChange={(e) => handleUpdate({ authConfig: { ...authConfig, apiKey: e.target.value } })}
                  placeholder="API Key"
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
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>Value</div>
                <input
                  type="text"
                  value={authConfig.apiValue || ''}
                  onChange={(e) => handleUpdate({ authConfig: { ...authConfig, apiValue: e.target.value } })}
                  placeholder="API Value"
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
          )}
        </div>
      ),
    },

    // 5. 请求体
    {
      key: 'body',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>请求体</span>
            <Tooltip title="配置请求体内容">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {bodyType !== 'none' && (
            <span
              style={{
                fontSize: '11px',
                color: '#10b981',
                background: '#ecfdf5',
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              {BODY_TYPES.find((b) => b.value === bodyType)?.label}
            </span>
          )}
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Radio.Group
            value={bodyType}
            onChange={(e) => handleUpdate({ bodyType: e.target.value })}
            size="small"
          >
            {BODY_TYPES.map((type) => (
              <Radio.Button key={type.value} value={type.value}>
                {type.label}
              </Radio.Button>
            ))}
          </Radio.Group>

          {bodyType !== 'none' && (
            <textarea
              value={bodyContent}
              onChange={(e) => handleUpdate({ bodyContent: e.target.value })}
              placeholder={
                bodyType === 'json'
                  ? '{\n  "key": "value"\n}'
                  : bodyType === 'form'
                    ? 'key1=value1&key2=value2'
                    : '请求体内容'
              }
              rows={6}
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
          )}
        </div>
      ),
    },

    // 6. 超时设置
    {
      key: 'timeout',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>超时设置（秒）</span>
            <Tooltip title="请求超时时间">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div>
          <InputNumber
            value={timeout}
            onChange={(value) => handleUpdate({ timeout: value })}
            min={1}
            max={300}
            style={{ width: '100%' }}
            addonAfter="秒"
          />
        </div>
      ),
    },

    // 7. 重试次数
    {
      key: 'retry',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>重试次数</span>
            <Tooltip title="请求失败时的重试次数">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div>
          <InputNumber
            value={retryCount}
            onChange={(value) => handleUpdate({ retryCount: value })}
            min={0}
            max={10}
            style={{ width: '100%' }}
          />
        </div>
      ),
    },

    // 8. 输出
    {
      key: 'outputs',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>输出</span>
            <Tooltip title="配置输出变量">
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
        </div>
      ),
    },

    // 9. 异常忽略
    {
      key: 'error',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>异常忽略</span>
            <Tooltip title="开启后，请求异常时使用默认输出替代">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <Switch size="small" checked={ignoreError} onChange={(checked) => handleUpdate({ ignoreError: checked })} />
        </div>
      ),
      children: ignoreError ? (
        <div>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px' }}>默认输出</div>
          <textarea
            value={fallbackValue}
            onChange={(e) => handleUpdate({ fallbackValue: e.target.value })}
            placeholder="异常时的默认返回值"
            rows={3}
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
          <div style={{ marginTop: '6px', fontSize: '11px', color: '#9ca3af' }}>
            忽略异常并在异常发生时使用默认输出替代
          </div>
        </div>
      ) : null,
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
        用于发送 API 请求，从接口返回数据。支持 GET/POST/PUT/DELETE 等常用 HTTP 方法。
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
