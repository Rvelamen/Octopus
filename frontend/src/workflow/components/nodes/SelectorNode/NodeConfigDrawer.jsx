/**
 * 选择器节点配置面板
 * 支持多分支条件管理：如果 / 否则如果 / 否则
 * 每个分支可包含多个"且"条件
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Plus, Trash2, GripVertical } from 'lucide-react';
import { Collapse, Select } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

// 操作符选项
const OPERATOR_OPTIONS = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
  { value: 'contains', label: '包含' },
  { value: 'notContains', label: '不包含' },
  { value: 'isEmpty', label: '为空' },
  { value: 'isNotEmpty', label: '不为空' },
];

const BRANCH_TYPE_LABELS = {
  if: '如果',
  elseIf: '否则如果',
  else: '否则',
};

// 生成唯一 ID
const generateId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// 创建默认分支
const createDefaultBranches = () => [
  {
    id: generateId('branch'),
    type: 'if',
    priority: 1,
    conditions: [
      {
        id: generateId('cond'),
        left: '',
        operator: 'eq',
        right: '',
      },
    ],
  },
  {
    id: generateId('branch'),
    type: 'else',
    priority: 999,
    conditions: [],
  },
];

// 条件行组件
const ConditionRow = ({
  condition,
  index,
  onUpdate,
  onDelete,
  canDelete,
  nodes,
  edges,
  currentNodeId,
}) => {
  const isEmptyOp = condition.operator === 'isEmpty' || condition.operator === 'isNotEmpty';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '4px 0',
      }}
    >
      {/* 左侧变量引用 */}
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
          fields={[{ name: 'left', value: condition.left || '' }]}
          onChange={(newFields) => {
            if (newFields.length > 0) {
              onUpdate(index, 'left', newFields[0].value);
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

      {/* 操作符选择 */}
      <Select
        value={condition.operator || 'eq'}
        onChange={(value) => onUpdate(index, 'operator', value)}
        options={OPERATOR_OPTIONS}
        size="small"
        style={{ width: '100px', flexShrink: 0 }}
        popupMatchSelectWidth={false}
      />

      {/* 右侧值输入（为空/不为空 时隐藏） */}
      {!isEmptyOp && (
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
            fields={[{ name: 'right', value: condition.right || '' }]}
            onChange={(newFields) => {
              if (newFields.length > 0) {
                onUpdate(index, 'right', newFields[0].value);
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
      )}

      {/* 删除条件 */}
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
            flexShrink: 0,
          }}
        >
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
};

// 分支卡片组件
const BranchCard = ({
  branch,
  index,
  totalBranches,
  onUpdateBranch,
  onDeleteBranch,
  onAddCondition,
  onUpdateCondition,
  onDeleteCondition,
  nodes,
  edges,
  currentNodeId,
}) => {
  const isElse = branch.type === 'else';
  const label = BRANCH_TYPE_LABELS[branch.type] || '如果';
  const priority = branch.priority || index + 1;

  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '10px',
        background: 'white',
        marginBottom: '12px',
        overflow: 'hidden',
      }}
    >
      {/* 分支头部 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          background: '#f9fafb',
          borderBottom: isElse ? 'none' : '1px solid #f3f4f6',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GripVertical size={14} color="#d1d5db" />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
            {label}
          </span>
          {!isElse && (
            <span
              style={{
                fontSize: '11px',
                color: '#9ca3af',
                background: '#f3f4f6',
                padding: '1px 8px',
                borderRadius: '10px',
              }}
            >
              优先级 {priority}
            </span>
          )}
        </div>

        {!isElse && totalBranches > 2 && (
          <button
            onClick={() => onDeleteBranch(branch.id)}
            style={{
              padding: '4px',
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

      {/* 条件列表 */}
      {!isElse && (
        <div style={{ padding: '8px 12px 12px' }}>
          {branch.conditions && branch.conditions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {branch.conditions.map((condition, condIndex) => (
                <div key={condition.id || condIndex}>
                  {condIndex > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '4px 0',
                        gap: '8px',
                      }}
                    >
                      <div
                        style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '4px',
                          background: '#eef2ff',
                          color: '#6366f1',
                          fontSize: '10px',
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        且
                      </div>
                      <div style={{ flex: 1, height: '1px', background: '#f3f4f6' }} />
                    </div>
                  )}
                  <ConditionRow
                    condition={condition}
                    index={condIndex}
                    onUpdate={onUpdateCondition}
                    onDelete={onDeleteCondition}
                    canDelete={branch.conditions.length > 1}
                    nodes={nodes}
                    edges={edges}
                    currentNodeId={currentNodeId}
                  />
                </div>
              ))}
            </div>
          )}

          {/* 新增条件按钮 */}
          <button
            onClick={() => onAddCondition(branch.id)}
            style={{
              marginTop: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 10px',
              border: '1px dashed #c7d2fe',
              borderRadius: '6px',
              background: '#f5f7ff',
              color: '#6366f1',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            <Plus size={12} />
            新增条件
          </button>
        </div>
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
  const [activeKey, setActiveKey] = useState(['branches']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const branches = useMemo(() => {
    const saved = nodeData?.branches;
    if (saved && saved.length > 0) return saved;
    return createDefaultBranches();
  }, [nodeData?.branches]);

  const handleUpdateBranches = useCallback((newBranches) => {
    updateNode(currentNodeId, { ...nodeData, branches: newBranches });
  }, [currentNodeId, nodeData, updateNode]);

  // 新增分支（插入到 else 之前）
  const handleAddBranch = useCallback(() => {
    const elseBranch = branches.find((b) => b.type === 'else');
    const normalBranches = branches.filter((b) => b.type !== 'else');
    const newBranch = {
      id: generateId('branch'),
      type: normalBranches.length > 0 ? 'elseIf' : 'if',
      priority: normalBranches.length + 1,
      conditions: [
        {
          id: generateId('cond'),
          left: '',
          operator: 'eq',
          right: '',
        },
      ],
    };
    const updated = [...normalBranches, newBranch];
    if (elseBranch) updated.push(elseBranch);
    // 重新计算优先级
    updated.forEach((b, idx) => {
      if (b.type !== 'else') b.priority = idx + 1;
    });
    handleUpdateBranches(updated);
  }, [branches, handleUpdateBranches]);

  // 删除分支
  const handleDeleteBranch = useCallback((branchId) => {
    const filtered = branches.filter((b) => b.id !== branchId);
    // 重新计算优先级
    filtered.forEach((b, idx) => {
      if (b.type !== 'else') b.priority = idx + 1;
    });
    handleUpdateBranches(filtered);
  }, [branches, handleUpdateBranches]);

  // 新增条件
  const handleAddCondition = useCallback((branchId) => {
    const newBranches = branches.map((b) => {
      if (b.id !== branchId) return b;
      return {
        ...b,
        conditions: [
          ...(b.conditions || []),
          {
            id: generateId('cond'),
            left: '',
            operator: 'eq',
            right: '',
          },
        ],
      };
    });
    handleUpdateBranches(newBranches);
  }, [branches, handleUpdateBranches]);

  // 更新条件字段
  const handleUpdateCondition = useCallback((branchId, condIndex, field, value) => {
    const newBranches = branches.map((b) => {
      if (b.id !== branchId) return b;
      const newConditions = (b.conditions || []).map((c, idx) =>
        idx === condIndex ? { ...c, [field]: value } : c
      );
      return { ...b, conditions: newConditions };
    });
    handleUpdateBranches(newBranches);
  }, [branches, handleUpdateBranches]);

  // 删除条件
  const handleDeleteCondition = useCallback((branchId, condIndex) => {
    const newBranches = branches.map((b) => {
      if (b.id !== branchId) return b;
      return {
        ...b,
        conditions: (b.conditions || []).filter((_, idx) => idx !== condIndex),
      };
    });
    handleUpdateBranches(newBranches);
  }, [branches, handleUpdateBranches]);

  const collapseItems = [
    {
      key: 'branches',
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
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
              条件分支
            </span>
            <span
              style={{
                fontSize: '11px',
                color: '#9ca3af',
                background: '#f3f4f6',
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              {branches.length}
            </span>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {/* 说明文字 */}
          <div
            style={{
              padding: '8px 0 12px',
              fontSize: '12px',
              color: '#9ca3af',
              lineHeight: 1.5,
            }}
          >
            连接多个下游分支，若设定的条件成立则仅运行对应的分支，若均不成立则只运行“否则”分支
          </div>

          {/* 分支列表 */}
          {branches.map((branch, index) => (
            <BranchCard
              key={branch.id}
              branch={branch}
              index={index}
              totalBranches={branches.length}
              onUpdateBranch={(id, field, value) => {
                const updated = branches.map((b) =>
                  b.id === id ? { ...b, [field]: value } : b
                );
                handleUpdateBranches(updated);
              }}
              onDeleteBranch={handleDeleteBranch}
              onAddCondition={handleAddCondition}
              onUpdateCondition={(condIndex, field, value) =>
                handleUpdateCondition(branch.id, condIndex, field, value)
              }
              onDeleteCondition={(condIndex) =>
                handleDeleteCondition(branch.id, condIndex)
              }
              nodes={nodes}
              edges={edges}
              currentNodeId={currentNodeId}
            />
          ))}

          {/* 新增分支按钮 */}
          <button
            onClick={handleAddBranch}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '8px',
              border: '1px dashed #c7d2fe',
              borderRadius: '8px',
              background: '#f5f7ff',
              color: '#6366f1',
              fontSize: '13px',
              cursor: 'pointer',
              fontWeight: 500,
              width: '100%',
            }}
          >
            <Plus size={14} />
            新增分支
          </button>
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
