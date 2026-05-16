/**
 * 节点测试按钮高阶组件
 * 为工作流节点添加右上角测试按钮（排除开始/结束节点）
 * 并在节点下方显示执行状态条
 */

import React, { memo, useState, useEffect } from 'react';
import { Play, Clock, CheckCircle, XCircle, ChevronDown, ChevronUp, Copy } from 'lucide-react';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';

export const withTestButton = (Component) => {
  const WrappedComponent = memo((props) => {
    const { id, type: nodeType, data: nodeData } = props;
    const executionStatus = useWorkflowStore((state) => state.executionStatus);
    const executionMode = useWorkflowStore((state) => state.executionMode);
    const testTargetNodeId = useWorkflowStore((state) => state.testTargetNodeId);
    const selectNode = useWorkflowStore((state) => state.selectNode);
    const setTestResultOpen = useWorkflowStore((state) => state.setTestResultOpen);

    const statusInfo = executionStatus[id];
    // 单节点测试时，只显示被测试节点的状态
    const status = executionMode === 'test' && testTargetNodeId !== id
      ? null
      : statusInfo?.status;
    const [isExpanded, setIsExpanded] = useState(false);
    const [liveDuration, setLiveDuration] = useState(0);

    // 开始/结束节点不显示测试按钮
    const isStartOrEnd = nodeType === 'workflowStart' || nodeType === 'workflowEnd' ||
      nodeData?.flowNodeType === 'workflowStart' || nodeData?.flowNodeType === 'workflowEnd';

    useEffect(() => {
      if (status !== 'running') {
        setLiveDuration(0);
        return;
      }
      const start = statusInfo?.timestamp || Date.now();
      setLiveDuration(Date.now() - start);
      const timer = setInterval(() => {
        setLiveDuration(Date.now() - start);
      }, 100);
      return () => clearInterval(timer);
    }, [status, statusInfo?.timestamp]);

    const handleTest = (e) => {
      e.stopPropagation();
      e.preventDefault();
      selectNode(id);
      setTestResultOpen(true);
    };

    const handleTestPointerDown = (e) => {
      // 阻止 ReactFlow 在 pointer-down 阶段选中节点并打开 config drawer
      e.stopPropagation();
      e.preventDefault();
    };

    return (
      <div style={{ position: 'relative' }}>
        <div style={{ position: 'relative' }}>
          <Component {...props} />
          {!isStartOrEnd && (
            <button
              onClick={handleTest}
              onPointerDown={handleTestPointerDown}
              onMouseDown={handleTestPointerDown}
              title="测试此节点"
              style={{
              position: 'absolute',
              top: '6px',
              right: '6px',
              width: '20px',
              height: '20px',
              borderRadius: '50%',
              border: 'none',
              background: '#22c55e',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              zIndex: 10,
              padding: 0,
              opacity: 0.85,
              transition: 'opacity 0.2s, transform 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = '1';
              e.currentTarget.style.transform = 'scale(1.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = '0.85';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <Play size={10} fill="white" />
          </button>
          )}
        </div>

        {/* 节点下方执行状态条 */}
        {status && (
          <>
            <div
              onClick={(e) => {
                e.stopPropagation();
                if (status !== 'running') setIsExpanded((v) => !v);
              }}
              style={{
                position: 'absolute',
                bottom: '-34px',
                left: '0',
                right: '0',
                height: '32px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 12px',
                fontSize: '13px',
                fontWeight: 500,
                zIndex: 5,
                cursor: status === 'running' ? 'default' : 'pointer',
                userSelect: 'none',
                transition: 'all 0.2s',
                ...(status === 'running' && {
                  background: '#eff6ff',
                  color: '#3b82f6',
                  border: '1px solid #bfdbfe',
                }),
                ...(status === 'completed' && {
                  background: '#f0fdf4',
                  color: '#16a34a',
                  border: '1px solid #86efac',
                }),
                ...(status === 'failed' && {
                  background: '#fef2f2',
                  color: '#dc2626',
                  border: '1px solid #fca5a5',
                }),
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {status === 'running' && (
                  <>
                    <Clock size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    <span>运行中</span>
                    {liveDuration > 0 && (
                      <span style={{
                        fontSize: '11px',
                        background: '#dbeafe',
                        color: '#2563eb',
                        padding: '1px 8px',
                        borderRadius: '10px',
                        fontWeight: 500,
                      }}>
                        {formatDuration(liveDuration)}
                      </span>
                    )}
                  </>
                )}
                {status === 'completed' && (
                  <>
                    <div style={{ width: '14px', height: '14px', borderRadius: '50%', background: '#22c55e' }} />
                    <span>运行成功</span>
                    {statusInfo?.duration != null && (
                      <span style={{
                        fontSize: '11px',
                        background: '#dcfce7',
                        color: '#16a34a',
                        padding: '1px 8px',
                        borderRadius: '10px',
                        fontWeight: 500,
                      }}>
                        {formatDuration(statusInfo.duration)}
                      </span>
                    )}
                  </>
                )}
                {status === 'failed' && (
                  <>
                    <div style={{ width: '14px', height: '14px', borderRadius: '50%', background: '#ef4444' }} />
                    <span>运行失败</span>
                    {statusInfo?.duration != null && (
                      <span style={{
                        fontSize: '11px',
                        background: '#fee2e2',
                        color: '#dc2626',
                        padding: '1px 8px',
                        borderRadius: '10px',
                        fontWeight: 500,
                      }}>
                        {formatDuration(statusInfo.duration)}
                      </span>
                    )}
                  </>
                )}
              </div>
              {status !== 'running' && (
                isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />
              )}
            </div>

            {/* 展开的执行详情 */}
            {isExpanded && status !== 'running' && statusInfo && (
              <DetailPanel
                statusInfo={statusInfo}
                nodeData={props.data}
              />
            )}
          </>
        )}
      </div>
    );
  });

  WrappedComponent.displayName = `WithTestButton(${Component.displayName || Component.name || 'Node'})`;
  return WrappedComponent;
};

/* ── 辅助组件 ── */

const DetailPanel = memo(({ statusInfo, nodeData }) => {
  const handleWheel = (e) => {
    e.stopPropagation();
    e.preventDefault();
  };

  const output = statusInfo.output || {};

  // reasoningText 作为大模型固定参数，单独提取
  const reasoning = output.reasoningText || output.reasoning_text || output.reasoningContent || output.reasoning_content;

  // 用户配置的输出变量名列表
  const configuredOutputs = (nodeData?.outputs || []).map(o => o.name).filter(Boolean);

  // 构建输出显示：有配置就按配置来，没配置就显示所有非内部字段
  const userOutput = {};
  for (const key of configuredOutputs) {
    if (key in output) userOutput[key] = output[key];
  }

  const nodeType = nodeData?.flowNodeType;
  const isStartNode = nodeType === 'workflowStart';
  const isEndNode = nodeType === 'workflowEnd';

  const internalKeys = ['reasoningText', 'reasoning_text', 'reasoningContent', 'reasoning_content', 'trace', 'tool_calls', 'function_calls'];
  const displayOutput = Object.keys(userOutput).length > 0
    ? userOutput
    : Object.fromEntries(Object.entries(output).filter(([k]) => !internalKeys.includes(k)));

  // 技能调用
  const toolCalls = output.tool_calls || output.function_calls || output.toolCalls || output.functionCalls;

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      onWheel={handleWheel}
      style={{
        position: 'absolute',
        bottom: '-34px',
        left: '0',
        right: '0',
        transform: 'translateY(100%)',
        zIndex: 6,
        background: 'white',
        borderRadius: '12px',
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        border: '1px solid #e5e7eb',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        maxHeight: '400px',
        overflowY: 'auto',
      }}
    >
      {/* 输入 —— 结束节点不显示 */}
      {!isEndNode && statusInfo.input && Object.keys(statusInfo.input).length > 0 && (
        <Section title="输入" data={statusInfo.input} />
      )}

      {/* 推理内容 */}
      {reasoning && (
        <Section title="推理内容" value={reasoning} />
      )}

      {/* 技能调用 */}
      {toolCalls && (
        <Section title="技能调用" value={typeof toolCalls === 'string' ? toolCalls : JSON.stringify(toolCalls, null, 2)} />
      )}

      {/* 输出 —— 开始节点不显示 */}
      {!isStartNode && Object.keys(displayOutput).length > 0 && (
        <Section title="输出" data={displayOutput} />
      )}

      {/* 错误 */}
      {statusInfo.error && (
        <div>
          <div style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#ef4444',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <span>错误</span>
          </div>
          <div style={{
            fontSize: '13px',
            color: '#dc2626',
            background: '#fef2f2',
            padding: '10px 12px',
            borderRadius: '8px',
            lineHeight: 1.6,
            wordBreak: 'break-word',
          }}>
            {statusInfo.error}
          </div>
        </div>
      )}
    </div>
  );
});

const Section = memo(({ title, data, value }) => {
  const handleCopy = () => {
    const text = value !== undefined ? String(value) : JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div>
      <div style={{
        fontSize: '14px',
        fontWeight: 600,
        color: '#1f2937',
        marginBottom: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span>{title}</span>
        <button
          onClick={handleCopy}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '2px',
            color: '#9ca3af',
            display: 'flex',
            alignItems: 'center',
          }}
          title="复制"
        >
          <Copy size={14} />
        </button>
      </div>
      <div style={{
        background: '#f9fafb',
        borderRadius: '8px',
        padding: '10px 12px',
        border: '1px solid #f3f4f6',
      }}>
        {value !== undefined ? (
          <div style={{ fontSize: '13px', color: '#4b5563', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {String(value)}
          </div>
        ) : (
          <KVDisplay data={data} />
        )}
      </div>
    </div>
  );
});

const KVDisplay = memo(({ data }) => {
  const entries = Object.entries(data);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {entries.map(([key, val]) => (
        <div key={key} style={{ fontSize: '13px', lineHeight: 1.6 }}>
          <span style={{ color: '#6366f1', fontWeight: 500 }}>{key}</span>
          <span style={{ color: '#9ca3af', margin: '0 4px' }}>:</span>
          <ValueDisplay value={val} />
        </div>
      ))}
    </div>
  );
});

const ValueDisplay = memo(({ value }) => {
  if (value === null) return <span style={{ color: '#9ca3af' }}>null</span>;
  if (value === undefined) return <span style={{ color: '#9ca3af' }}>undefined</span>;
  if (typeof value === 'boolean') return <span style={{ color: '#f97316' }}>{String(value)}</span>;
  if (typeof value === 'number') return <span style={{ color: '#10b981' }}>{value}</span>;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    const isUnresolvedRef = /^\{\{.+\..+\}\}$/.test(trimmed);
    const isMarkedUnresolved = /^\[未解析/.test(trimmed);

    if (isUnresolvedRef || isMarkedUnresolved) {
      return (
        <span
          style={{
            color: '#ef4444',
            background: '#fef2f2',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '12px',
          }}
          title={`变量引用未能解析为实际值: ${trimmed}`}
        >
          ⚠️ {isMarkedUnresolved ? trimmed : '[变量未解析]'}
        </span>
      );
    }

    return <span style={{ color: '#1f2937' }}>{value}</span>;
  }
  if (typeof value === 'object') {
    return (
      <span style={{ color: '#4b5563' }}>
        {JSON.stringify(value)}
      </span>
    );
  }
  return <span style={{ color: '#1f2937' }}>{String(value)}</span>;
});

const formatDuration = (ms) => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
};
