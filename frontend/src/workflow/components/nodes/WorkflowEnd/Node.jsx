/**
 * 工作流结束节点
 * 展示动态配置的输出参数，作为工作流的返回结果
 */

import React, { memo, useMemo, useRef, useState, useEffect } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Flag } from 'lucide-react';
import { Tag, Tooltip } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

// 类型英文缩写映射 - 支持所有类型包括子类型
const TYPE_SHORT_LABELS = {
  // 基础类型
  string: 'str',
  integer: 'int',
  number: 'num',
  boolean: 'bool',
  time: 'time',
  object: 'obj',
  // Array 子类型
  arrayString: 'arr<str>',
  arrayInteger: 'arr<int>',
  arrayNumber: 'arr<num>',
  arrayBoolean: 'arr<bool>',
  arrayTime: 'arr<time>',
  arrayObject: 'arr<obj>',
  arrayFile: 'arr<file>',
  // File 子类型
  fileDefault: 'file',
  fileImage: 'img',
  fileSvg: 'svg',
  fileAudio: 'audio',
  fileVideo: 'video',
  fileDoc: 'doc',
  filePpt: 'ppt',
  fileExcel: 'xls',
  fileTxt: 'txt',
  fileCode: 'code',
  fileZip: 'zip',
};

const WorkflowEnd = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const outputs = useMemo(() => data.outputs || [], [data.outputs]);
  const returnMode = data.returnMode || 'variables';

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.target === id);
  }, [edges, id]);

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#f8f9fe',
        border: `2px solid ${selected ? '#6366f1' : '#e0e7ff'}`,
        borderRadius: '12px',
        minWidth: '240px',
        maxWidth: '320px',
        boxShadow: selected ? '0 0 0 3px rgba(99, 102, 241, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
        position: 'relative',
      }}
    >
      {/* 单一输入连接点 */}
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
          borderBottom: '1px solid #eef2ff',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            background: '#6366f1',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          <Flag size={16} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '结束'}
          </div>
        </div>
      </div>

      {/* 输出参数列表 - Tag 样式 */}
      {returnMode === 'variables' && outputs.length > 0 && (
        <div style={{ padding: '10px 16px' }}>
          <OutputTags outputs={outputs} />
        </div>
      )}

      {/* 返回文本模式提示 */}
      {returnMode === 'text' && (
        <div style={{ padding: '10px 16px' }}>
          <Tag
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '12px',
              lineHeight: '18px',
              border: 'none',
              background: '#eef2ff',
              color: '#4b5563',
              margin: 0,
            }}
          >
            文本模式
          </Tag>
        </div>
      )}

      {/* 底部输出类型 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          borderTop: '1px solid #eef2ff',
          fontSize: '12px',
          color: '#9ca3af',
        }}
      >
        <span>输出类型</span>
        <span style={{ color: '#6366f1', fontWeight: 500 }}>
          {returnMode === 'variables' ? '返回变量' : '返回文本'}
        </span>
      </div>
    </div>
  );
});

/**
 * 输出参数标签组
 * 单行展示，溢出时截断并显示 Tooltip
 */
const OutputTags = memo(({ outputs }) => {
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
  }, [outputs]);

  const visibleOutputs = overflowIndex === -1 ? outputs : outputs.slice(0, overflowIndex);
  const hiddenOutputs = overflowIndex === -1 ? [] : outputs.slice(overflowIndex);

  const tagStyle = (isUndefined) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    padding: '2px 8px',
    borderRadius: '6px',
    fontSize: '11px',
    lineHeight: '18px',
    border: 'none',
    background: isUndefined ? '#fff7ed' : '#eef2ff',
    color: isUndefined ? '#f97316' : '#4b5563',
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
        输出
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
        {visibleOutputs.map((output, idx) => {
          const typeShort = TYPE_SHORT_LABELS[output.type] || 'str';
          const isUndefined = !output.value || output.value === '';
          return (
            <Tag key={idx} style={tagStyle(isUndefined)}>
              <span style={typePrefixStyle}>{typeShort}.</span>
              <span style={nameStyle}>{output.name || '未定义'}</span>
            </Tag>
          );
        })}

        {hiddenOutputs.length > 0 && (
          <Tooltip
            title={
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', maxWidth: '280px' }}>
                {hiddenOutputs.map((output, idx) => {
                  const typeShort = TYPE_SHORT_LABELS[output.type] || 'str';
                  const isUndefined = !output.value || output.value === '';
                  return (
                    <Tag key={idx} style={tagStyle(isUndefined)}>
                      <span style={typePrefixStyle}>{typeShort}.</span>
                      <span style={nameStyle}>{output.name || '未定义'}</span>
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
              +{hiddenOutputs.length}
            </Tag>
          </Tooltip>
        )}
      </div>
    </div>
  );
});

OutputTags.displayName = 'OutputTags';
WorkflowEnd.displayName = 'WorkflowEnd';

export default WorkflowEnd;
