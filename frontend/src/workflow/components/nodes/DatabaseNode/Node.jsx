/**
 * 数据库操作节点
 * 支持 INSERT / UPDATE / DELETE / QUERY 操作
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Database } from 'lucide-react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

const OPERATION_COLORS = {
  INSERT: '#10b981',
  UPDATE: '#3b82f6',
  DELETE: '#ef4444',
  QUERY: '#f59e0b',
};

const OPERATION_LABELS = {
  INSERT: '插入',
  UPDATE: '更新',
  DELETE: '删除',
  QUERY: '查询',
};

const TYPE_PREFIXES = {
  string: 'str',
  integer: 'int',
  number: 'num',
  boolean: 'bool',
  object: 'obj',
  array: 'arr',
  arrayString: 'arr<str>',
  arrayNumber: 'arr<num>',
  arrayObject: 'arr<obj>',
};

const DatabaseNode = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const operation = useMemo(() => data.operation || 'QUERY', [data.operation]);
  const tableName = useMemo(() => data.tableName || '', [data.tableName]);
  const outputs = useMemo(() => data.outputs || [], [data.outputs]);

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some((edge) => edge.target === id);
  }, [edges, id]);

  const hasOutgoingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some((edge) => edge.source === id);
  }, [edges, id]);

  const opColor = OPERATION_COLORS[operation] || '#6b7280';
  const opLabel = OPERATION_LABELS[operation] || operation;
  const tablePreview = tableName
    ? tableName.length > 20
      ? tableName.slice(0, 20) + '...'
      : tableName
    : '未配置表名';

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#fefcf8',
        border: `2px solid ${selected ? '#f97316' : '#fed7aa'}`,
        borderRadius: '16px',
        minWidth: '240px',
        maxWidth: '320px',
        boxShadow: selected ? '0 0 0 3px rgba(249, 115, 22, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
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
          background: hasIncomingEdge ? '#f97316' : 'white',
          border: '2px solid #f97316',
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
          borderBottom: '1px solid #fff7ed',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            background: '#f97316',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          <Database size={16} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '数据库'}
          </div>
          {data.intro && (
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              {data.intro}
            </div>
          )}
        </div>
      </div>

      {/* 操作类型和表名预览 */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #fff7ed' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '10px',
              fontWeight: 700,
              color: 'white',
              background: opColor,
              padding: '2px 8px',
              borderRadius: '4px',
              letterSpacing: '0.5px',
            }}
          >
            {opLabel}
          </span>
          <span
            style={{
              fontSize: '11px',
              color: tableName ? '#6b7280' : '#9ca3af',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
            }}
          >
            {tablePreview}
          </span>
        </div>
      </div>

      {/* 输出参数预览 */}
      {outputs.length > 0 && (
        <div style={{ padding: '8px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>输出</span>
            {outputs.slice(0, 3).map((output, idx) => {
              const typePrefix = TYPE_PREFIXES[output.type] || 'str';
              return (
                <span
                  key={idx}
                  style={{
                    fontSize: '11px',
                    color: '#374151',
                    background: '#f3f4f6',
                    padding: '1px 6px',
                    borderRadius: '4px',
                  }}
                >
                  <span style={{ color: '#9ca3af', marginRight: '2px' }}>{typePrefix}.</span>
                  {output.name}
                </span>
              );
            })}
            {outputs.length > 3 && (
              <span style={{ fontSize: '11px', color: '#9ca3af' }}>+{outputs.length - 3}</span>
            )}
          </div>
        </div>
      )}

      {/* 输出连接点 */}
      <Handle
        type="source"
        id={`${id}-source`}
        position={Position.Right}
        style={{
          width: '16px',
          height: '16px',
          background: hasOutgoingEdge ? '#f97316' : 'white',
          border: '2px solid #f97316',
          borderRadius: '50%',
          right: '-8px',
          top: '28px',
          transition: 'all 0.2s',
        }}
      />
    </div>
  );
});

DatabaseNode.displayName = 'DatabaseNode';

export default DatabaseNode;
