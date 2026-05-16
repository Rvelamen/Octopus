/**
 * 循环节点
 * 支持数组循环、次数循环等模式，重复执行循环体内任务
 * 包含循环体容器框体，内部支持节点拖拽和连线
 * 循环体自适应撑开，无滚动条
 *
 * ⭐ 关键修复：确保与 ReactFlow 12 parentId 机制兼容
 * - 使用数字类型的 width/height（不是字符串）
 * - 根元素必须有明确的像素尺寸
 * - 避免复杂的 CSS 布局影响子节点定位
 */

import React, { memo, useMemo, useState } from 'react';
import { Handle, Position, useReactFlow } from '@xyflow/react';
import { RefreshCw, Box, Maximize2, Minimize2 } from 'lucide-react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import { useLoopDragDetect } from './useLoopDragDetect';
import './index.css';

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
  fileDoc: 'doc',
  filePpt: 'ppt',
  fileExcel: 'xls',
  fileTxt: 'txt',
  fileCode: 'code',
  fileZip: 'zip',
};

const LoopNode = memo(({ id, data, selected }) => {
  const edges = useWorkflowStore((state) => state.edges);
  const nodes = useWorkflowStore((state) => state.nodes);
  const reactFlow = useReactFlow();

  const loopConfig = useMemo(() => data.loopConfig || {}, [data.loopConfig]);
  const intermediateVars = useMemo(() => data.intermediateVars || [], [data.intermediateVars]);
  const outputs = useMemo(() => data.outputs || [], [data.outputs]);
  const [isBodyExpanded, setIsBodyExpanded] = useState(true);

  // ⭐ 关键修复：获取当前 LoopNode 的完整数据，包括宽高尺寸
  // ReactFlow parentId 机制要求父节点必须有明确的像素宽高
  const currentNode = useMemo(
    () => nodes.find((n) => n.id === id),
    [nodes, id]
  );

  // ⭐ 使用数字类型（不是字符串），确保 ReactFlow 正确计算尺寸
  const nodeWidth = currentNode?.measured?.width ?? currentNode?.width ?? 400;
  const nodeHeight = currentNode?.measured?.height ?? currentNode?.height ?? 280;

  const isDragOver = useLoopDragDetect({ loopNodeId: id, nodes, reactFlow });

  const hasIncomingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some((edge) => edge.target === id);
  }, [edges, id]);

  const hasOutgoingEdge = useMemo(() => {
    if (!Array.isArray(edges)) return false;
    return edges.some((edge) => edge.source === id);
  }, [edges, id]);

  const loopTypeLabel = useMemo(() => {
    const type = loopConfig.loopType;
    if (type === 'array') return '数组循环';
    if (type === 'count') return '次数循环';
    if (type === 'condition') return '条件循环';
    return '未配置';
  }, [loopConfig.loopType]);

  // ⭐ parentId 方案: 子节点是独立的 ReactFlow 节点，通过 parentId 关联
  const childNodes = useMemo(() => (nodes || []).filter((n) => n.parentId === id), [nodes, id]);
  const childEdges = useMemo(() => (edges || []).filter((e) => childNodes.some((n) => n.id === e.source || n.id === e.target)), [edges, childNodes]);
  const childNodesCount = childNodes.length;
  const childEdgesCount = childEdges.length;

  // ⭐ 调试日志：输出当前节点的关键信息
  console.log(`[LoopNode ${id}] 渲染信息`, {
    nodeWidth,
    nodeHeight,
    measured: currentNode?.measured,
    dataWidth: currentNode?.width,
    dataHeight: currentNode?.height,
    childNodesCount,
    selected,
  });

  return (
    <div
      className="workflow-node-card"
      style={{
        background: '#f8f9fe',
        border: `2px solid ${selected ? '#6366f1' : '#e0e7ff'}`,
        borderRadius: '12px',
        // ⭐ 关键：使用数字类型的像素值（不是字符串模板）
        width: nodeWidth,
        height: nodeHeight,
        display: 'flex',
        flexDirection: 'column',
        boxShadow: selected ? '0 0 0 3px rgba(99, 102, 241, 0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
        position: 'relative', // ⭐ 确保定位上下文
        overflow: 'visible', // ⭐ 允许子节点溢出可见
        boxSizing: 'border-box', // ⭐ 确保 border 不影响尺寸计算
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
          flexShrink: 0,
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
          <RefreshCw size={16} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937', lineHeight: 1.4 }}>
            {data.name || '循环'}
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>
            {loopTypeLabel}
          </div>
        </div>
      </div>

      {/* 循环数组/条件预览 */}
      {loopConfig.loopType === 'array' && loopConfig.loopArray?.varName && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>输入</span>
            <span
              style={{
                fontSize: '11px',
                color: '#6366f1',
                background: '#eef2ff',
                padding: '1px 6px',
                borderRadius: '4px',
              }}
            >
              {loopConfig.loopArray.varName}
            </span>
          </div>
        </div>
      )}

      {loopConfig.loopType === 'count' && loopConfig.loopCount?.value && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>次数</span>
            <span
              style={{
                fontSize: '11px',
                color: '#6366f1',
                background: '#eef2ff',
                padding: '1px 6px',
                borderRadius: '4px',
              }}
            >
              {loopConfig.loopCount.value}
            </span>
          </div>
        </div>
      )}

      {/* 中间变量预览 */}
      {intermediateVars.length > 0 && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>中间变量</span>
            {intermediateVars.slice(0, 2).map((v, idx) => (
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
                <span style={{ color: '#9ca3af', marginRight: '2px' }}>
                  {TYPE_PREFIXES[v.type] || 'str'}.
                </span>
                {v.name}
              </span>
            ))}
            {intermediateVars.length > 2 && (
              <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                +{intermediateVars.length - 2}
              </span>
            )}
          </div>
        </div>
      )}

      {/* 输出参数预览 */}
      {outputs.length > 0 && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #eef2ff', flexShrink: 0 }}>
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

      {/* 循环体容器框体 - 视觉指示 */}
      <div
        style={{
          margin: '0 12px 12px',
          border: `2px dashed ${isDragOver ? '#22c55e' : '#c7d2fe'}`,
          borderRadius: '8px',
          background: isDragOver ? '#f0fdf4' : '#fafbff',
          position: 'relative',
          overflow: 'visible',
          minHeight: '80px',
          flex: 1,
          transition: 'all 0.2s ease',
          boxShadow: isDragOver ? '0 0 0 3px rgba(34, 197, 94, 0.2), inset 0 0 20px rgba(34, 197, 94, 0.05)' : 'none',
        }}
        onPointerDown={(e) => {
          // 阻止 ReactFlow 将事件冒泡到父 LoopNode，避免点击循环体内部时选中父节点
          e.stopPropagation();
        }}
      >
        {/* 循环体标题栏 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 12px',
            borderBottom: isBodyExpanded ? '1px dashed #c7d2fe' : 'none',
          }}
        >
          <Box size={14} color="#818cf8" />
          <span style={{ fontSize: '12px', fontWeight: 500, color: '#6366f1' }}>循环体</span>
          <span
            style={{
              fontSize: '11px',
              color: '#9ca3af',
              background: '#eef2ff',
              padding: '1px 6px',
              borderRadius: '10px',
            }}
          >
            {childNodesCount} 节点 / {childEdgesCount} 连线
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsBodyExpanded(!isBodyExpanded);
            }}
            style={{
              marginLeft: 'auto',
              padding: '2px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#9ca3af',
              display: 'flex',
              alignItems: 'center',
            }}
            title={isBodyExpanded ? '收起' : '展开'}
          >
            {isBodyExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>

        {/* ⭐ parentId 方案: 子节点由 ReactFlow 直接渲染，此处仅保留空状态提示 */}
        {isBodyExpanded && childNodesCount === 0 && (
          <div style={{ padding: '8px' }}>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                padding: '24px',
                color: isDragOver ? '#22c55e' : '#9ca3af',
                fontSize: '12px',
                transition: 'color 0.2s ease',
              }}
            >
              <Box size={28} color={isDragOver ? '#22c55e' : '#c7d2fe'} />
              <span style={{ fontWeight: isDragOver ? 600 : 400 }}>
                {isDragOver ? '松开鼠标将节点加入循环体' : '循环体为空'}
              </span>
              {!isDragOver && (
                <span style={{ fontSize: '11px' }}>拖拽节点到循环节点范围内即可加入</span>
              )}
            </div>
          </div>
        )}

        {/* ⭐ LoopNode Handle semantics: body-start 为 source (绿色/入口)，body-end 为 target (橙色/出口) */}
        {/* ⭐ 关键修复：Handle 必须存在以支持连线，但通过 CSS 定位到循环体容器内部 */}
        <div
          className="loop-body-handle loop-body-handle--in"
          onPointerDown={(e) => e.stopPropagation()}
          title="循环体入口 (IN)"
        >
          <span className="loop-body-handle__label">IN</span>
          <Handle
            type="source"
            id={`${id}-body-start`}
            position={Position.Left}
            className="loop-body-handle__reactflow"
            style={{
              width: '12px',
              height: '12px',
              background: '#22c55e',
              border: '2px solid white',
              borderRadius: '50%',
              boxShadow: '0 0 0 2px #86efac, 0 0 8px rgba(34,197,94,0.3)',
              cursor: 'crosshair',
              transition: 'all 0.2s',
            }}
          />
        </div>

        <div
          className="loop-body-handle loop-body-handle--out"
          onPointerDown={(e) => e.stopPropagation()}
          title="循环体出口 (OUT)"
        >
          <Handle
            type="target"
            id={`${id}-body-end`}
            position={Position.Right}
            className="loop-body-handle__reactflow"
            style={{
              width: '12px',
              height: '12px',
              background: '#f97316',
              border: '2px solid white',
              borderRadius: '50%',
              boxShadow: '0 0 0 2px #fdba74, 0 0 8px rgba(249,115,22,0.3)',
              cursor: 'crosshair',
              transition: 'all 0.2s',
            }}
          />
          <span className="loop-body-handle__label">OUT</span>
        </div>
      </div>

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

LoopNode.displayName = 'LoopNode';

export default LoopNode;
