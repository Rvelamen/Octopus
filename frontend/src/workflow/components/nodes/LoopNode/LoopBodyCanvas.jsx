/**
 * 循环体内部画布 - 最终版
 * 无滚动条、自适应高度、支持拖拽和点击配置
 */

import React, { memo, useCallback, useRef, useState, useEffect } from 'react';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

// 节点类型颜色映射
const NODE_COLORS = {
  workflowStart: '#10b981',
  workflowEnd: '#ef4444',
  code: '#f59e0b',
  loop: '#06b6d4',
  selector: '#8b5cf6',
  inputNode: '#6366f1',
  pluginOutput: '#ec4899',
};

// 节点类型图标首字母
const NODE_ICONS = {
  workflowStart: 'S',
  workflowEnd: 'E',
  code: 'C',
  loop: 'L',
  selector: 'IF',
  inputNode: 'I',
  pluginOutput: 'O',
};

// 简易节点卡片
const ChildNodeCard = memo(({ node, isSelected, onClick, onMouseDown }) => {
  const color = NODE_COLORS[node.type] || '#6366f1';
  const icon = NODE_ICONS[node.type] || (node.data?.name || 'N').charAt(0);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClick(node.id);
      }}
      onMouseDown={(e) => onMouseDown(e, node.id)}
      style={{
        position: 'relative',
        width: '150px',
        background: 'white',
        border: `2px solid ${isSelected ? '#6366f1' : '#e5e7eb'}`,
        borderRadius: '10px',
        padding: '10px 12px',
        boxShadow: isSelected
          ? '0 0 0 3px rgba(99, 102, 241, 0.2), 0 4px 12px rgba(0,0,0,0.1)'
          : '0 2px 6px rgba(0,0,0,0.06)',
        cursor: 'grab',
        zIndex: isSelected ? 10 : 1,
        transition: 'box-shadow 0.2s, border-color 0.2s',
        userSelect: 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div
          style={{
            width: '24px',
            height: '24px',
            borderRadius: '6px',
            background: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontSize: '10px',
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#1f2937',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {node.data?.name || '未命名'}
          </div>
          <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '1px' }}>
            {node.type}
          </div>
        </div>
      </div>

      {/* 输入连接点 */}
      <div
        style={{
          position: 'absolute',
          left: '-6px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '10px',
          height: '10px',
          background: '#6366f1',
          borderRadius: '50%',
          border: '2px solid white',
          boxShadow: '0 0 0 1px #c7d2fe',
        }}
      />
      {/* 输出连接点 */}
      <div
        style={{
          position: 'absolute',
          right: '-6px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '10px',
          height: '10px',
          background: '#6366f1',
          borderRadius: '50%',
          border: '2px solid white',
          boxShadow: '0 0 0 1px #c7d2fe',
        }}
      />
    </div>
  );
});

ChildNodeCard.displayName = 'ChildNodeCard';

// SVG 连线
const ChildEdges = memo(({ edges, nodes }) => {
  const getNodeCenter = (nodeId) => {
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return { x: 0, y: 0 };
    return {
      x: (node.position?.x || 0) + 150,
      y: (node.position?.y || 0) + 22,
    };
  };

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    >
      <defs>
        <marker
          id="loop-arrow"
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,6 L9,3 z" fill="#6366f1" />
        </marker>
      </defs>
      {edges.map((edge) => {
        const source = getNodeCenter(edge.source);
        const target = getNodeCenter(edge.target);
        const midX = (source.x + target.x) / 2;

        return (
          <path
            key={edge.id}
            d={`M ${source.x} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${target.x} ${target.y}`}
            fill="none"
            stroke="#6366f1"
            strokeWidth="1.5"
            markerEnd="url(#loop-arrow)"
          />
        );
      })}
    </svg>
  );
});

ChildEdges.displayName = 'ChildEdges';

const LoopBodyCanvas = memo(({
  loopNodeId,
  childNodes,
  childEdges,
  onNodesChange,
  onConnect,
  isSelected,
}) => {
  const containerRef = useRef(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [draggingNodeId, setDraggingNodeId] = useState(null);
  const dragOffset = useRef({ x: 0, y: 0 });
  const dragStartPos = useRef({ x: 0, y: 0 });
  const [connectingFrom, setConnectingFrom] = useState(null);
  const selectLoopChildNode = useWorkflowStore((state) => state.selectLoopChildNode);
  const selectedLoopChildNodeId = useWorkflowStore((state) => state.selectedLoopChildNodeId);

  // 同步外部选中状态
  useEffect(() => {
    if (selectedLoopChildNodeId) {
      setSelectedNodeId(selectedLoopChildNodeId);
    }
  }, [selectedLoopChildNodeId]);

  // 拖拽状态 ref，供 window 事件处理器使用
  const dragStateRef = useRef({
    isDragging: false,
    nodeId: null,
    offsetX: 0,
    offsetY: 0,
    startX: 0,
    startY: 0,
    hasMoved: false,
  });

  // 使用 ref 存储 childNodes 和 onNodesChange 的最新引用，避免 window 监听器频繁重绑定
  const childNodesRef = useRef(childNodes);
  const onNodesChangeRef = useRef(onNodesChange);

  useEffect(() => {
    childNodesRef.current = childNodes;
  }, [childNodes]);

  useEffect(() => {
    onNodesChangeRef.current = onNodesChange;
  }, [onNodesChange]);

  const handleMouseDown = useCallback((e, nodeId) => {
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    e.preventDefault();
    setSelectedNodeId(nodeId);
    selectLoopChildNode(nodeId, loopNodeId);

    const node = childNodes.find((n) => n.id === nodeId);
    if (!node) return;

    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    dragStateRef.current = {
      isDragging: true,
      nodeId,
      offsetX: e.clientX - rect.left - (node.position?.x || 0),
      offsetY: e.clientY - rect.top - (node.position?.y || 0),
      startX: e.clientX,
      startY: e.clientY,
      hasMoved: false,
    };
  }, [childNodes, loopNodeId, selectLoopChildNode]);

  // 使用 window 级别事件监听实现拖拽，避免 pointer capture 问题
  // 依赖为空数组，监听器只绑定一次；通过 ref 获取最新的 childNodes 和 onNodesChange
  useEffect(() => {
    const handleMouseMove = (e) => {
      const state = dragStateRef.current;
      if (!state.isDragging) return;

      const dx = Math.abs(e.clientX - state.startX);
      const dy = Math.abs(e.clientY - state.startY);

      if (!state.hasMoved && (dx > 3 || dy > 3)) {
        state.hasMoved = true;
        setDraggingNodeId(state.nodeId);
      }

      if (!state.hasMoved) return;

      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const newX = e.clientX - rect.left - state.offsetX;
      const newY = e.clientY - rect.top - state.offsetY;

      const currentChildNodes = childNodesRef.current;
      const newNodes = currentChildNodes.map((n) =>
        n.id === state.nodeId
          ? { ...n, position: { x: Math.max(0, newX), y: Math.max(0, newY) } }
          : n
      );

      const currentOnNodesChange = onNodesChangeRef.current;
      if (currentOnNodesChange) {
        currentOnNodesChange(loopNodeId, newNodes);
      }
    };

    const handleMouseUp = () => {
      const state = dragStateRef.current;
      if (!state.isDragging) return;

      dragStateRef.current = {
        isDragging: false,
        nodeId: null,
        offsetX: 0,
        offsetY: 0,
        startX: 0,
        startY: 0,
        hasMoved: false,
      };
      setDraggingNodeId(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const handleOutputClick = useCallback((e, nodeId) => {
    e.stopPropagation();
    e.preventDefault();
    if (connectingFrom) {
      if (connectingFrom !== nodeId && onConnect) {
        onConnect(loopNodeId, {
          source: connectingFrom,
          target: nodeId,
        });
      }
      setConnectingFrom(null);
    } else {
      setConnectingFrom(nodeId);
    }
  }, [connectingFrom, onConnect, loopNodeId]);

  // 计算画布内容区域 - 无滚动条，完全自适应
  const canvasWidth = Math.max(
    280,
    ...(childNodes || []).map((n) => (n.position?.x || 0) + 170)
  );
  const canvasHeight = Math.max(
    80,
    ...(childNodes || []).map((n) => (n.position?.y || 0) + 55)
  );

  return (
    <div
      ref={containerRef}
      className="nodrag"
      onPointerDown={(e) => e.stopPropagation()}
      style={{
        width: '100%',
        minHeight: `${canvasHeight + 16}px`,
        background: '#f8f9fe',
        borderRadius: '6px',
        position: 'relative',
        overflow: 'visible',
        cursor: draggingNodeId ? 'grabbing' : 'default',
        padding: '8px',
      }}
    >
      {/* 内部画布区域 - 自适应撑开 */}
      <div
        style={{
          width: `${canvasWidth}px`,
          minHeight: `${canvasHeight}px`,
          position: 'relative',
          minWidth: '100%',
        }}
      >
        <ChildEdges edges={childEdges || []} nodes={childNodes || []} />

        {(childNodes || []).map((node) => (
          <div
            key={node.id}
            style={{
              position: 'absolute',
              left: node.position?.x || 0,
              top: node.position?.y || 0,
              width: '150px',
              height: '44px',
              zIndex: selectedNodeId === node.id || connectingFrom === node.id ? 10 : 1,
            }}
          >
            <ChildNodeCard
              node={node}
              isSelected={selectedNodeId === node.id || connectingFrom === node.id}
              onClick={(id) => {
                setSelectedNodeId(id);
                selectLoopChildNode(id, loopNodeId);
              }}
              onMouseDown={handleMouseDown}
            />
            {/* 输出连接点点击区域 */}
            <div
              onMouseDown={(e) => handleOutputClick(e, node.id)}
              style={{
                position: 'absolute',
                right: '-8px',
                top: '50%',
                transform: 'translateY(-50%)',
                width: '16px',
                height: '16px',
                cursor: 'crosshair',
                zIndex: 20,
                borderRadius: '50%',
                background: connectingFrom === node.id ? 'rgba(99, 102, 241, 0.3)' : 'transparent',
              }}
              title={connectingFrom === node.id ? '点击目标节点完成连线' : '点击开始连线'}
            />
          </div>
        ))}

        {connectingFrom && (
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: '11px',
              color: '#6366f1',
              background: '#eef2ff',
              padding: '3px 10px',
              borderRadius: '6px',
              zIndex: 30,
              whiteSpace: 'nowrap',
            }}
          >
            点击目标节点完成连线
          </div>
        )}
      </div>
    </div>
  );
});

LoopBodyCanvas.displayName = 'LoopBodyCanvas';

export default LoopBodyCanvas;
