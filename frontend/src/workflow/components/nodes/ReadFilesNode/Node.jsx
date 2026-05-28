/**
 * 读取文件节点
 * 支持输入多个 URL（换行分隔），一次性下载内容
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { FileText } from 'lucide-react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

const TYPE_PREFIXES = {
  string: 'str',
  integer: 'int',
  number: 'num',
  boolean: 'bool',
  array: 'arr',
  arrayString: 'arr<str>',
  fileDefault: 'file',
};

const ReadFilesNode = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);

  const inputs = useMemo(() => data.inputs || [], [data.inputs]);
  const outputs = useMemo(() => data.outputs || [], [data.outputs]);
  const fileUrlList = data?.fileUrlList || '';

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.target === id);
  }, [edges, id]);

  const hasOutgoingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some(edge => edge.source === id);
  }, [edges, id]);

  const urlCount = useMemo(() => {
    if (!fileUrlList) return 0;
    if (typeof fileUrlList === 'string') {
      return fileUrlList.split('\n').filter(u => u.trim()).length;
    }
    if (Array.isArray(fileUrlList)) return fileUrlList.length;
    return 0;
  }, [fileUrlList]);

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#fffbeb',
        border: `2px solid ${selected ? '#eab308' : '#fef3c7'}`,
        borderRadius: '12px',
        minWidth: '240px',
        maxWidth: '320px',
        boxShadow: selected ? '0 0 0 3px rgba(234, 179, 8, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
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
          background: hasIncomingEdge ? '#eab308' : 'white',
          border: '2px solid #eab308',
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
          borderBottom: '1px solid #fef3c7',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            background: '#eab308',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          <FileText size={16} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '读取文件'}
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>
            {urlCount > 0 ? `${urlCount} 个 URL` : '输入 URL 读取内容'}
          </div>
        </div>
      </div>

      {/* 输入参数预览 */}
      {inputs.length > 0 && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #fef3c7' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>输入</span>
            {inputs.slice(0, 3).map((input, idx) => {
              const typePrefix = TYPE_PREFIXES[input.type] || 'str';
              return (
                <span
                  key={idx}
                  style={{
                    fontSize: '11px',
                    color: '#eab308',
                    background: '#fef3c7',
                    padding: '1px 6px',
                    borderRadius: '4px',
                  }}
                >
                  <span style={{ color: '#9ca3af', marginRight: '2px' }}>{typePrefix}.</span>
                  {input.name}
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
          background: hasOutgoingEdge ? '#eab308' : 'white',
          border: '2px solid #eab308',
          borderRadius: '50%',
          right: '-8px',
          transition: 'all 0.2s',
        }}
      />
    </div>
  );
});

ReadFilesNode.displayName = 'ReadFilesNode';

export default ReadFilesNode;
