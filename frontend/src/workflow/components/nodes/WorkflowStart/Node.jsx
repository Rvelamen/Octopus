/**
 * 工作流开始节点
 * 展示动态配置的输入参数，作为工作流的入口变量
 */

import React, { memo, useMemo, useRef, useState, useEffect } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Play } from 'lucide-react';
import { Tag, Tooltip } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

// 类型颜色映射
const TYPE_COLORS = {
  string: '#3b82f6',
  integer: '#22c55e',
  number: '#10b981',
  boolean: '#f97316',
  time: '#8b5cf6',
  object: '#a855f7',
  array: '#ec4899',
  file: '#06b6d4',
};

// 类型前缀映射（与 ConfigDrawer 保持一致）
const TYPE_PREFIXES = {
  string: 'str',
  integer: 'int',
  number: 'num',
  boolean: 'bool',
  time: 'time',
  object: 'obj',
  array: 'arr',
  file: 'file',
};

const WorkflowStart = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const inputs = useMemo(() => data.inputs || [], [data.inputs]);

  const hasOutgoingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.source === id);
  }, [edges, id]);

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#f8f9fe',
        border: `2px solid ${selected ? '#6366f1' : '#e0e7ff'}`,
        borderRadius: '16px',
        minWidth: '240px',
        maxWidth: '360px',
        boxShadow: selected ? '0 0 0 3px rgba(99, 102, 241, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
        position: 'relative',
      }}
    >
      {/* 节点头部 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '14px 18px',
          borderBottom: inputs.length > 0 ? '1px solid #eef2ff' : 'none',
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            background: '#6366f1',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          <Play size={18} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '开始'}
          </div>
          {data.intro && (
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              {data.intro}
            </div>
          )}
        </div>
      </div>

      {/* 输入参数列表 - Tag 样式 */}
      {inputs.length > 0 && (
        <div style={{ padding: '10px 18px 14px' }}>
          <InputTags inputs={inputs} />
        </div>
      )}

      {/* 单一输出连接点 */}
      <Handle
        type="source"
        id={`${id}-source`}
        position={Position.Right}
        style={{
          width: '16px',
          height: '16px',
          background: hasOutgoingEdge ? '#6366f1' : 'white',
          border: '2px solid #6366f1',
          borderRadius: '50%',
          right: '-8px',
          transition: 'all 0.2s',
        }}
      />
    </div>
  );
});

/**
 * 输入参数标签组
 * 单行展示，溢出时截断并显示 Tooltip
 */
const InputTags = memo(({ inputs }) => {
  const containerRef = useRef(null);
  const [overflowIndex, setOverflowIndex] = useState(-1);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const children = container.children;
    let totalWidth = 0;
    let foundOverflow = -1;
    const containerWidth = container.clientWidth;

    for (let i = 0; i < children.length; i++) {
      totalWidth += children[i].offsetWidth + 8; // 8px gap
      if (totalWidth > containerWidth && foundOverflow === -1) {
        foundOverflow = i;
      }
    }

    setOverflowIndex(foundOverflow);
  }, [inputs]);

  const visibleInputs = overflowIndex === -1 ? inputs : inputs.slice(0, overflowIndex);
  const hiddenInputs = overflowIndex === -1 ? [] : inputs.slice(overflowIndex);

  const tagStyle = (typeColor) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    padding: '2px 8px',
    borderRadius: '6px',
    fontSize: '11px',
    lineHeight: '18px',
    border: 'none',
    background: '#eef2ff',
    color: '#4b5563',
    margin: 0,
  });

  const typePrefixStyle = {
    color: '#9ca3af',
    fontSize: '10px',
    fontWeight: 400,
  };

  const nameStyle = {
    color: '#374151',
    fontWeight: 500,
    fontSize: '11px',
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ fontSize: '12px', color: '#9ca3af', flexShrink: 0, fontWeight: 500 }}>
        输入
      </span>
      <div
        ref={containerRef}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          flexWrap: 'nowrap',
          overflow: 'hidden',
          minWidth: 0,
          flex: 1,
        }}
      >
        {visibleInputs.map((input, idx) => {
          const typePrefix = TYPE_PREFIXES[input.type] || 'str';
          return (
            <Tag key={idx} style={tagStyle()}>
              <span style={typePrefixStyle}>{typePrefix}.</span>
              <span style={nameStyle}>{input.name || '未定义'}</span>
            </Tag>
          );
        })}

        {hiddenInputs.length > 0 && (
          <Tooltip
            title={
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', maxWidth: '280px' }}>
                {hiddenInputs.map((input, idx) => {
                  const typePrefix = TYPE_PREFIXES[input.type] || 'str';
                  return (
                    <Tag key={idx} style={tagStyle()}>
                      <span style={typePrefixStyle}>{typePrefix}.</span>
                      <span style={nameStyle}>{input.name || '未定义'}</span>
                    </Tag>
                  );
                })}
              </div>
            }
            placement="bottom"
          >
            <Tag
              style={{
                ...tagStyle(),
                cursor: 'pointer',
                background: '#f3f4f6',
                color: '#6b7280',
              }}
            >
              +{hiddenInputs.length}
            </Tag>
          </Tooltip>
        )}
      </div>
    </div>
  );
});

InputTags.displayName = 'InputTags';
WorkflowStart.displayName = 'WorkflowStart';

export default WorkflowStart;
