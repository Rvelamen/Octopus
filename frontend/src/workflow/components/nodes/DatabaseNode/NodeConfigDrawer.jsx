/**
 * 数据库节点配置面板
 * 支持：
 *   - 目标表名（下拉选择已有表）
 *   - 操作类型（INSERT/UPDATE/DELETE/QUERY）
 *   - 字段映射（INSERT/UPDATE）
 *   - WHERE 条件（UPDATE/DELETE/QUERY）
 *   - ORDER BY / LIMIT（QUERY）
 *   - 输出变量管理
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Info } from 'lucide-react';
import { Collapse, Tooltip, Select, InputNumber } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import { useDBAPI } from '../../../services/dbApi';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

const OPERATIONS = [
  { value: 'INSERT', label: '插入 (INSERT)', color: '#10b981' },
  { value: 'UPDATE', label: '更新 (UPDATE)', color: '#3b82f6' },
  { value: 'DELETE', label: '删除 (DELETE)', color: '#ef4444' },
  { value: 'QUERY', label: '查询 (QUERY)', color: '#f59e0b' },
];

const DEFAULT_OUTPUTS = [
  { id: 'out_result', name: 'result', type: 'object' },
];

const generateId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// 字段映射行
const FieldMappingRow = ({ item, index, onUpdate, onDelete, canDelete, nodes, edges, currentNodeId }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
      <input
        type="text"
        value={item.name || ''}
        onChange={(e) => onUpdate(index, 'name', e.target.value)}
        placeholder="字段名"
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
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden', background: 'white', minHeight: '36px' }}>
        <ExpressionEditorField
          fields={[{ name: item.name || '', value: item.value || '' }]}
          onChange={(newFields) => onUpdate(index, 'value', newFields[0]?.value || '')}
          nodes={nodes}
          edges={edges}
          currentNodeId={currentNodeId}
          compact
          useDropdown
          canAdd={false}
        />
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
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
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
        value={output.type || 'object'}
        onChange={(value) => onUpdate(index, 'type', value)}
        options={[
          { value: 'string', label: 'String' },
          { value: 'integer', label: 'Integer' },
          { value: 'number', label: 'Number' },
          { value: 'boolean', label: 'Boolean' },
          { value: 'object', label: 'Object' },
          { value: 'array', label: 'Array' },
        ]}
        size="middle"
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
  const [activeKey, setActiveKey] = useState(['basic', 'fields', 'filters', 'outputs']);
  const updateNode = useWorkflowStore((state) => state.updateNode);
  const dbApi = useDBAPI();

  const [tables, setTables] = useState([]);
  const [tablesLoading, setTablesLoading] = useState(false);

  // 加载表列表
  useEffect(() => {
    let cancelled = false;
    setTablesLoading(true);
    dbApi.getTableList()
      .then((list) => {
        if (!cancelled) setTables(list || []);
      })
      .catch(() => {
        if (!cancelled) setTables([]);
      })
      .finally(() => {
        if (!cancelled) setTablesLoading(false);
      });
    return () => { cancelled = true; };
  }, [dbApi]);

  // 从 nodeData 读取配置
  const tableName = nodeData?.tableName || '';
  const operation = nodeData?.operation || 'QUERY';
  const fieldMappings = nodeData?.fieldMappings || [];
  const whereCondition = nodeData?.whereCondition || '';
  const orderBy = nodeData?.orderBy || '';
  const limit = nodeData?.limit ?? 100;
  const outputs = nodeData?.outputs || DEFAULT_OUTPUTS;

  const handleUpdate = useCallback(
    (updates) => {
      updateNode(currentNodeId, { ...nodeData, ...updates });
    },
    [currentNodeId, nodeData, updateNode]
  );

  // ---------- 字段映射管理 ----------
  const handleAddField = useCallback(() => {
    const newField = { id: generateId('field'), name: '', value: '' };
    handleUpdate({ fieldMappings: [...fieldMappings, newField] });
  }, [fieldMappings, handleUpdate]);

  const handleDeleteField = useCallback(
    (index) => {
      handleUpdate({ fieldMappings: fieldMappings.filter((_, i) => i !== index) });
    },
    [fieldMappings, handleUpdate]
  );

  const handleUpdateField = useCallback(
    (index, field, fieldValue) => {
      const newFields = fieldMappings.map((item, i) =>
        i === index ? { ...item, [field]: fieldValue } : item
      );
      handleUpdate({ fieldMappings: newFields });
    },
    [fieldMappings, handleUpdate]
  );

  // ---------- 输出变量管理 ----------
  const handleAddOutput = useCallback(() => {
    const newOutput = {
      id: generateId('output'),
      name: `output_${outputs.length + 1}`,
      type: 'object',
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

  const showFieldsSection = operation === 'INSERT' || operation === 'UPDATE';
  const showWhereSection = operation === 'UPDATE' || operation === 'DELETE' || operation === 'QUERY';
  const showQueryOptions = operation === 'QUERY';

  const tableOptions = tables.map((t) => ({ value: t.name, label: t.name }));
  const opMeta = OPERATIONS.find((o) => o.value === operation);

  // ==================== Collapse 配置项 ====================

  const collapseItems = [];

  // 1. 基础配置
  collapseItems.push({
    key: 'basic',
    label: (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>基础配置</span>
          <Tooltip title="选择目标表和操作类型">
            <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
          </Tooltip>
        </div>
        {opMeta && (
          <span
            style={{
              fontSize: '10px',
              fontWeight: 700,
              color: 'white',
              background: opMeta.color,
              padding: '1px 6px',
              borderRadius: '4px',
            }}
          >
            {opMeta.label.split(' ')[0]}
          </span>
        )}
      </div>
    ),
    children: (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* 目标表名 */}
        <div>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
            目标表名
          </div>
          <Select
            value={tableName || undefined}
            onChange={(value) => handleUpdate({ tableName: value })}
            options={tableOptions}
            loading={tablesLoading}
            placeholder="选择数据表"
            style={{ width: '100%' }}
            size="middle"
            allowClear
            showSearch
          />
        </div>

        {/* 操作类型 */}
        <div>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
            操作类型
          </div>
          <Select
            value={operation}
            onChange={(value) => handleUpdate({ operation: value })}
            options={OPERATIONS}
            style={{ width: '100%' }}
            size="middle"
          />
        </div>
      </div>
    ),
  });

  // 2. 字段映射（INSERT/UPDATE）
  if (showFieldsSection) {
    collapseItems.push({
      key: 'fields',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>字段映射</span>
            <Tooltip title={`${operation === 'INSERT' ? '插入' : '更新'}的字段和值`}>
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          <span style={{ fontSize: '11px', color: '#9ca3af', background: '#f3f4f6', padding: '1px 6px', borderRadius: '10px' }}>
            {fieldMappings.length}
          </span>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {fieldMappings.map((item, index) => (
            <FieldMappingRow
              key={item.id || index}
              item={item}
              index={index}
              onUpdate={handleUpdateField}
              onDelete={handleDeleteField}
              canDelete={fieldMappings.length > 0}
              nodes={nodes}
              edges={edges}
              currentNodeId={currentNodeId}
            />
          ))}
          <button
            onClick={handleAddField}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 10px',
              border: '1px dashed #e5e7eb',
              borderRadius: '6px',
              background: 'white',
              color: '#6366f1',
              fontSize: '12px',
              cursor: 'pointer',
              width: 'fit-content',
            }}
          >
            <Plus size={14} />
            添加字段
          </button>
        </div>
      ),
    });
  }

  // 3. 过滤条件（UPDATE/DELETE/QUERY）
  if (showWhereSection) {
    collapseItems.push({
      key: 'filters',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>过滤条件</span>
          <Tooltip title="WHERE 条件支持变量引用">
            <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
          </Tooltip>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* WHERE */}
          <div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
              WHERE 条件
            </div>
            <ExpressionEditorField
              value={whereCondition}
              onChange={(value) => handleUpdate({ whereCondition: value })}
              placeholder='例如: {{nodeId.status}} = "active"'
              rows={2}
            />
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '4px' }}>
              支持 JSON 字段路径，如 age &gt; 18 或 name = &quot;张三&quot;
            </div>
          </div>

          {/* 查询选项（QUERY 专用） */}
          {showQueryOptions && (
            <>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
                  ORDER BY
                </div>
                <input
                  type="text"
                  value={orderBy}
                  onChange={(e) => handleUpdate({ orderBy: e.target.value })}
                  placeholder="created_at DESC"
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '12px',
                    outline: 'none',
                    color: '#374151',
                  }}
                />
              </div>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
                  LIMIT
                </div>
                <InputNumber
                  value={limit}
                  onChange={(value) => handleUpdate({ limit: value ?? 100 })}
                  min={1}
                  max={10000}
                  style={{ width: '100%' }}
                  size="middle"
                />
              </div>
            </>
          )}
        </div>
      ),
    });
  }

  // 4. 输出变量
  collapseItems.push({
    key: 'outputs',
    label: (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>输出变量</span>
          <Tooltip title="定义节点输出变量">
            <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
          </Tooltip>
        </div>
        <span style={{ fontSize: '11px', color: '#9ca3af', background: '#f3f4f6', padding: '1px 6px', borderRadius: '10px' }}>
          {outputs.length}
        </span>
      </div>
    ),
    children: (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
            gap: '4px',
            padding: '6px 10px',
            border: '1px dashed #e5e7eb',
            borderRadius: '6px',
            background: 'white',
            color: '#6366f1',
            fontSize: '12px',
            cursor: 'pointer',
            width: 'fit-content',
          }}
        >
          <Plus size={14} />
          添加输出变量
        </button>
      </div>
    ),
  });

  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <Collapse
        activeKey={activeKey}
        onChange={setActiveKey}
        ghost
        items={collapseItems}
      />
    </div>
  );
};

export default NodeConfigDrawer;
