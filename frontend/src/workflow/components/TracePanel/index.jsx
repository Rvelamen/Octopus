/**
 * 调试追踪面板
 * 显示工作流执行状态和节点输出
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  X,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Terminal,
  AlertTriangle,
  Info,
  Loader2,
} from 'lucide-react';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';

const TracePanel = ({ isOpen, onClose }) => {
  const nodes = useWorkflowStore((state) => state.nodes);
  const executionStatus = useWorkflowStore((state) => state.executionStatus);
  const [expandedNodes, setExpandedNodes] = useState(new Set());

  const toggleNode = (nodeId) => {
    setExpandedNodes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  const executionNodes = useMemo(() => {
    // 显示所有非开始/结束节点，将执行状态合并到节点数据中
    return nodes
      .filter((node) => node.type !== 'workflowStart' && node.type !== 'workflowEnd')
      .map((node) => {
        const statusInfo = executionStatus[node.id];
        return {
          ...node,
          data: {
            ...node.data,
            executionStatus: statusInfo?.status || 'pending',
            executionOutput: statusInfo?.output || {},
            executionInput: statusInfo?.input || {},
            executionError: statusInfo?.error,
            executionDuration: statusInfo?.duration,
          },
        };
      });
  }, [nodes, executionStatus]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Clock size={14} color="#60a5fa" />;
      case 'completed':
        return <CheckCircle size={14} color="#4ade80" />;
      case 'failed':
        return <XCircle size={14} color="#f87171" />;
      case 'pending':
        return <Info size={14} color="#9ca3af" />;
      default:
        return <Info size={14} color="#9ca3af" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return '#eff6ff';
      case 'completed':
        return '#f0fdf4';
      case 'failed':
        return '#fef2f2';
      default:
        return '#f9fafb';
    }
  };

  const getStatusBorderColor = (status) => {
    switch (status) {
      case 'running':
        return '#93c5fd';
      case 'completed':
        return '#86efac';
      case 'failed':
        return '#fca5a5';
      default:
        return '#e5e7eb';
    }
  };

  const formatValue = (value) => {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return String(value);
      }
    }
    return String(value);
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: '400px',
        background: 'white',
        borderLeft: '1px solid #e5e7eb',
        boxShadow: '-4px 0 16px rgba(0,0,0,0.1)',
        zIndex: 30,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f3f4f6',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Terminal size={18} color="#4b5563" />
            <span style={{ fontSize: '16px', fontWeight: 600, color: '#1f2937' }}>
              执行追踪
            </span>
            {executionNodes.length > 0 && (
              <span
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: '#eff6ff',
                  color: '#2563eb',
                }}
              >
                {executionNodes.length} 个节点
              </span>
            )}
          </div>
          <button
            style={{
              padding: '4px',
              borderRadius: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
            onClick={onClose}
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>

      </div>

      {/* 内容 */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {executionNodes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#9ca3af' }}>
            <Play size={32} style={{ margin: '0 auto 12px' }} />
            <div style={{ fontSize: '14px' }}>暂无执行记录</div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>
              点击"调试运行"开始执行工作流
            </div>
          </div>
        ) : (
          executionNodes.map((node) => {
            const nodeId = node.id;
            const data = node.data;
            const status = data.executionStatus;
            const isExpanded = expandedNodes.has(nodeId);
            const debugResult = data.debugResult;
            const executionOutput = data.executionOutput;

            return (
              <div
                key={nodeId}
                style={{
                  border: `1px solid ${getStatusBorderColor(status)}`,
                  borderRadius: '8px',
                  overflow: 'hidden',
                  background: getStatusColor(status),
                }}
              >
                {/* 节点头部 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 12px',
                    cursor: 'pointer',
                  }}
                  onClick={() => toggleNode(nodeId)}
                >
                  {getStatusIcon(status)}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: '#1f2937',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {data.name || '未命名节点'}
                    </div>
                    <div style={{ fontSize: '11px', color: '#6b7280' }}>
                      {status === 'running'
                        ? '执行中...'
                        : status === 'completed'
                        ? `执行完成${data.executionDuration != null ? ` · ${(() => {
                            const ms = data.executionDuration;
                            if (ms < 1000) return `${Math.round(ms)}ms`;
                            const sec = Math.round(ms / 1000);
                            if (sec < 60) return `${sec}s`;
                            if (sec < 3600) return `${Math.floor(sec / 60)}m${sec % 60}s`;
                            return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
                          })()}` : ''}`
                        : status === 'failed'
                        ? `执行失败${data.executionDuration != null ? ` · ${(() => {
                            const ms = data.executionDuration;
                            if (ms < 1000) return `${Math.round(ms)}ms`;
                            const sec = Math.round(ms / 1000);
                            if (sec < 60) return `${sec}s`;
                            if (sec < 3600) return `${Math.floor(sec / 60)}m${sec % 60}s`;
                            return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
                          })()}` : ''}`
                        : '等待执行'}
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp size={14} color="#9ca3af" />
                  ) : (
                    <ChevronDown size={14} color="#9ca3af" />
                  )}
                </div>

                {/* 展开的详情 */}
                {isExpanded && (
                  <div
                    style={{
                      padding: '10px 12px',
                      borderTop: `1px solid ${getStatusBorderColor(status)}`,
                      background: 'white',
                    }}
                  >
                    {/* 输入参数 */}
                    <div style={{ marginBottom: '12px' }}>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 500,
                          color: '#4b5563',
                          marginBottom: '6px',
                        }}
                      >
                        输入参数
                      </div>
                      {data.inputs && data.inputs.length > 0 ? (
                        <div
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '4px',
                          }}
                        >
                          {data.inputs.map((input, idx) => {
                            const inputKey = input.key || input.name;
                            if (!inputKey) return null;
                            // 优先显示执行时的实际输入值，其次显示节点配置值
                            const executedVal = data.executionInput?.[inputKey];
                            const configVal = data[inputKey];
                            const val = executedVal !== undefined ? executedVal : configVal;
                            const hasValue = val !== undefined && val !== null && val !== '';
                            return (
                              <div
                                key={idx}
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  fontSize: '12px',
                                }}
                              >
                                <span style={{ color: '#6b7280' }}>
                                  {input.label || input.name || input.key}
                                </span>
                                <span
                                  style={{
                                    color: hasValue ? '#374151' : '#9ca3af',
                                    fontFamily: 'monospace',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    maxWidth: '200px',
                                  }}
                                  title={hasValue ? formatValue(val) : '未设置'}
                                >
                                  {hasValue ? formatValue(val) : '--'}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                          该节点没有输入参数
                        </div>
                      )}
                    </div>

                    {/* 执行输出 */}
                    {executionOutput && Object.keys(executionOutput).length > 0 && (
                      <div style={{ marginBottom: '12px' }}>
                        <div
                          style={{
                            fontSize: '12px',
                            fontWeight: 500,
                            color: '#4b5563',
                            marginBottom: '6px',
                          }}
                        >
                          执行输出
                        </div>
                        <pre
                          style={{
                            fontSize: '11px',
                            fontFamily: 'monospace',
                            background: '#f9fafb',
                            padding: '8px',
                            borderRadius: '6px',
                            overflow: 'auto',
                            maxHeight: '200px',
                            margin: 0,
                            color: '#374151',
                          }}
                        >
                          {formatValue(executionOutput)}
                        </pre>
                      </div>
                    )}

                    {/* 调试结果 */}
                    {debugResult && (
                      <div>
                        <div
                          style={{
                            fontSize: '12px',
                            fontWeight: 500,
                            color: '#4b5563',
                            marginBottom: '6px',
                          }}
                        >
                          调试信息
                        </div>
                        <div
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '4px',
                          }}
                        >
                          {debugResult.status && (
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '12px',
                              }}
                            >
                              {debugResult.status === 'success' ? (
                                <CheckCircle size={12} color="#4ade80" />
                              ) : debugResult.status === 'failed' ? (
                                <XCircle size={12} color="#f87171" />
                              ) : (
                                <Clock size={12} color="#60a5fa" />
                              )}
                              <span>
                                状态:{' '}
                                {debugResult.status === 'success'
                                  ? '成功'
                                  : debugResult.status === 'failed'
                                  ? '失败'
                                  : '运行中'}
                              </span>
                            </div>
                          )}
                          {debugResult.message && (
                            <div
                              style={{
                                fontSize: '12px',
                                color:
                                  debugResult.status === 'failed'
                                    ? '#ef4444'
                                    : '#4b5563',
                                padding: '6px',
                                background:
                                  debugResult.status === 'failed'
                                    ? '#fef2f2'
                                    : '#f9fafb',
                                borderRadius: '4px',
                              }}
                            >
                              {debugResult.message}
                            </div>
                          )}
                          {debugResult.duration && (
                            <div style={{ fontSize: '12px', color: '#6b7280' }}>
                              耗时: {debugResult.duration}ms
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* 错误信息 */}
                    {status === 'failed' && data.executionError && (
                      <div
                        style={{
                          marginTop: '8px',
                          padding: '8px',
                          background: '#fef2f2',
                          borderRadius: '6px',
                          border: '1px solid #fca5a5',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '12px',
                            color: '#ef4444',
                            fontWeight: 500,
                          }}
                        >
                          <AlertTriangle size={12} />
                          错误信息
                        </div>
                        <div
                          style={{
                            fontSize: '11px',
                            color: '#dc2626',
                            marginTop: '4px',
                            fontFamily: 'monospace',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {data.executionError}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
      )}
      </div>
    </div>
  );
};
/* ── 辅助组件 ── */

const TraceKVDisplay = ({ data }) => {
  return (
    <div style={{
      background: '#f9fafb',
      borderRadius: '8px',
      padding: '10px 12px',
      border: '1px solid #f3f4f6',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
    }}>
      {Object.entries(data).map(([key, val]) => (
        <div key={key} style={{ fontSize: '13px', lineHeight: 1.6 }}>
          <span style={{ color: '#6366f1', fontWeight: 500 }}>{key}</span>
          <span style={{ color: '#9ca3af', margin: '0 4px' }}>:</span>
          <TraceValueDisplay value={val} />
        </div>
      ))}
    </div>
  );
};

const TraceValueDisplay = ({ value }) => {
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
            whiteSpace: 'pre-wrap',
          }}
          title={`变量引用未能解析为实际值: ${trimmed}`}
        >
          ⚠️ {isMarkedUnresolved ? trimmed : '[变量未解析]'}
        </span>
      );
    }

    return <span style={{ color: '#1f2937', whiteSpace: 'pre-wrap' }}>{value}</span>;
  }
  if (typeof value === 'object') {
    return <span style={{ color: '#4b5563' }}>{JSON.stringify(value)}</span>;
  }
  return <span style={{ color: '#1f2937' }}>{String(value)}</span>;
};

export default TracePanel;
