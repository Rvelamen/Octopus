/**
 * 文本处理节点
 * 用于处理多个字符串类型变量的格式，支持字符串拼接、替换、截取、正则等操作
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Type } from 'lucide-react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

// 类型前缀映射
const TYPE_PREFIXES = {
  string: 'str',
  integer: 'int',
  number: 'num',
  boolean: 'bool',
  time: 'time',
  object: 'obj',
  array: 'arr',
  arrayString: 'arr<str>',
  arrayInteger: 'arr<int>',
  arrayNumber: 'arr<num>',
  arrayBoolean: 'arr<bool>',
  arrayTime: 'arr<time>',
  arrayObject: 'arr<obj>',
  arrayFile: 'arr<file>',
  fileDefault: 'file',
  fileImage: 'img',
  fileSvg: 'svg',
  fileAudio: 'audio',
  fileVideo: 'video',
  fileVoice: 'voice',
  fileDoc: 'doc',
  filePpt: 'ppt',
  fileExcel: 'xls',
  fileTxt: 'txt',
  fileCode: 'code',
  fileZip: 'zip',
};

// 操作类型标签映射
const OPERATION_LABELS = {
  concat: '字符串拼接',
  replace: '文本替换',
  substring: '文本截取',
  regex: '正则匹配',
  split: '文本分割',
  trim: '去除空白',
  uppercase: '转大写',
  lowercase: '转小写',
};

const TextNode = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const inputs = useMemo(() => data.inputs || [], [data.inputs]);
  const outputs = useMemo(() => data.outputs || [], [data.outputs]);
  const operation = useMemo(() => data.operation || 'concat', [data.operation]);

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.target === id);
  }, [edges, id]);

  const hasOutgoingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.source === id);
  }, [edges, id]);

  const operationLabel = OPERATION_LABELS[operation] || '字符串拼接';

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
          <Type size={16} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '文本处理'}
          </div>
          {data.intro && (
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              {data.intro}
            </div>
          )}
        </div>
      </div>

      {/* 操作类型预览 */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 500,
            color: '#6366f1',
            background: '#eef2ff',
            padding: '2px 8px',
            borderRadius: '4px',
          }}
        >
          {operationLabel}
        </span>
      </div>

      {/* 输入参数预览 */}
      {inputs.length > 0 && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>输入</span>
            {inputs.slice(0, 3).map((input, idx) => {
              const typePrefix = TYPE_PREFIXES[input.type] || 'str';
              return (
                <span
                  key={idx}
                  style={{
                    fontSize: '11px',
                    color: '#6366f1',
                    background: '#eef2ff',
                    padding: '1px 6px',
                    borderRadius: '4px',
                  }}
                >
                  <span style={{ color: '#9ca3af', marginRight: '2px' }}>{typePrefix}.</span>
                  {input.name || '未定义'}
                </span>
              );
            })}
            {inputs.length > 3 && (
              <span style={{ fontSize: '11px', color: '#9ca3af' }}>+{inputs.length - 3}</span>
            )}
          </div>
        </div>
      )}

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
          background: hasOutgoingEdge ? '#6366f1' : 'white',
          border: '2px solid #6366f1',
          borderRadius: '50%',
          right: '-8px',
          top: '28px',
          transition: 'all 0.2s',
        }}
      />
    </div>
  );
});

TextNode.displayName = 'TextNode';

export default TextNode;
