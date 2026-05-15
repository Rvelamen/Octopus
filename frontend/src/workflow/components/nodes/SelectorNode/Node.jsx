/**
 * 选择器节点（IF / 条件分支）
 * 支持多分支条件判断，每个分支可包含多个"且"条件
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { GitFork } from 'lucide-react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

const BRANCH_LABELS = {
  if: '如果',
  elseIf: '否则如果',
  else: '否则',
};

const SelectorNode = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const branches = useMemo(() => data.branches || [], [data.branches]);

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some((edge) => edge.target === id);
  }, [edges, id]);

  const getBranchEdgeCount = (branchId) => {
    if (!Array.isArray(edges)) return 0;
    return edges.filter(
      (edge) => edge.source === id && edge.sourceHandle === `${id}-source`
    ).length;
  };

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#f8f9fe',
        border: `2px solid ${selected ? '#6366f1' : '#e0e7ff'}`,
        borderRadius: '16px',
        minWidth: '240px',
        maxWidth: '320px',
        boxShadow: selected ? '0 0 0 3px rgba(99, 102, 241, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
        position: 'relative',
      }}
    >
      {/* 输入连接点 */}
      <Handle
        type="target"
        id={`${id}-target`}
        position={Position.Left}
        style={{
          width: '16px',
          height: '16px',
          background: hasIncomingEdge ? '#6366f1' : 'white',
          border: '2px solid #6366f1',
          borderRadius: '50%',
          left: '-8px',
          top: '28px',
          transition: 'all 0.2s',
        }}
      />

      {/* 节点头部 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '12px 16px',
          borderBottom: branches.length > 0 ? '1px solid #eef2ff' : 'none',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            background: '#06b6d4',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          <GitFork size={16} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '选择器'}
          </div>
          {data.intro && (
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              {data.intro}
            </div>
          )}
        </div>
      </div>

      {/* 分支列表 */}
      {branches.length > 0 && (
        <div style={{ padding: '8px 0' }}>
          {branches.map((branch, index) => {
            const label = branch.type === 'else'
              ? BRANCH_LABELS.else
              : branch.type === 'elseIf'
                ? BRANCH_LABELS.elseIf
                : BRANCH_LABELS.if;
            const hasEdge = getBranchEdgeCount(branch.id) > 0;

            return (
              <div
                key={branch.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 16px',
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      fontSize: '12px',
                      color: '#9ca3af',
                      fontWeight: 500,
                      minWidth: '48px',
                    }}
                  >
                    {label}
                  </span>
                  {branch.conditions && branch.conditions.length > 0 && (
                    <span
                      style={{
                        fontSize: '11px',
                        color: '#6366f1',
                        background: '#eef2ff',
                        padding: '1px 6px',
                        borderRadius: '4px',
                      }}
                    >
                      {branch.conditions.length} 个条件
                    </span>
                  )}
                </div>

                {/* 分支输出连接点 */}
                <Handle
                  type="source"
                  id={`${id}-source`}
                  position={Position.Right}
                  style={{
                    width: '14px',
                    height: '14px',
                    background: hasEdge ? '#6366f1' : 'white',
                    border: '2px solid #6366f1',
                    borderRadius: '50%',
                    right: '-7px',
                    position: 'absolute',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    transition: 'all 0.2s',
                  }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

SelectorNode.displayName = 'SelectorNode';

export default SelectorNode;
