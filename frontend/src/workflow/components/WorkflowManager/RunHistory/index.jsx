/**
 * 运行历史组件
 * 显示工作流的执行历史记录
 * 已接入后端 WebSocket API
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  X,
  History,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Terminal,
  AlertTriangle,
  RotateCcw,
  Trash2,
  Filter,
  Loader2,
} from 'lucide-react';
import { useWorkflowAPI } from '../../../services/workflowApi';
import ConfirmDialog from '../../common/ConfirmDialog';

const RunHistory = ({ isOpen, onClose, workflowId }) => {
  const api = useWorkflowAPI();

  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedRuns, setExpandedRuns] = useState(new Set());
  const [filterStatus, setFilterStatus] = useState('all');
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // 从后端加载运行历史
  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (workflowId) {
        params.workflow_id = workflowId;
      }
      const list = await api.getRunList(params);
      setRuns(list);
    } catch (err) {
      setError(err.message || '加载失败');
      console.error('[RunHistory] load error:', err);
    } finally {
      setLoading(false);
    }
  }, [api, workflowId]);

  useEffect(() => {
    if (isOpen) {
      loadRuns();
    }
  }, [isOpen, loadRuns]);

  const toggleRun = (runId) => {
    setExpandedRuns((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(runId)) {
        newSet.delete(runId);
      } else {
        newSet.add(runId);
      }
      return newSet;
    });
  };

  const handleDeleteRun = async (runId) => {
    try {
      await api.deleteRun(runId);
      setRuns((prev) => prev.filter((r) => r.id !== runId));
    } catch (err) {
      alert('删除失败: ' + (err.message || '未知错误'));
      console.error('[RunHistory] delete error:', err);
    }
  };

  const handleClearAll = async () => {
    if (showClearConfirm) {
      try {
        if (workflowId) {
          await api.deleteWorkflowRuns(workflowId);
        } else {
          await Promise.all(runs.map((r) => api.deleteRun(r.id)));
        }
        setRuns([]);
        setExpandedRuns(new Set());
        setShowClearConfirm(false);
      } catch (err) {
        alert('清空失败: ' + (err.message || '未知错误'));
        console.error('[RunHistory] clear error:', err);
      }
    } else {
      setShowClearConfirm(true);
    }
  };

  const filteredRuns = useMemo(() => {
    if (filterStatus === 'all') return runs;
    if (filterStatus === 'success') {
      return runs.filter((run) => run.status === 'success' || run.status === 'completed');
    }
    return runs.filter((run) => run.status === filterStatus);
  }, [runs, filterStatus]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Clock size={14} color="#60a5fa" />;
      case 'success':
      case 'completed':
        return <CheckCircle size={14} color="#22c55e" />;
      case 'failed':
        return <XCircle size={14} color="#ef4444" />;
      default:
        return <Play size={14} color="#9ca3af" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return '#eff6ff';
      case 'success':
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
      case 'success':
      case 'completed':
        return '#86efac';
      case 'failed':
        return '#fca5a5';
      default:
        return '#e5e7eb';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'running':
        return '运行中';
      case 'success':
      case 'completed':
        return '成功';
      case 'failed':
        return '失败';
      default:
        return '未知';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '未知时间';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatDuration = (ms) => {
    if (!ms) return '0ms';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.5)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '700px',
          height: '80vh',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={20} color="#4b5563" />
            <span style={{ fontSize: '18px', fontWeight: 600 }}>
              运行历史
            </span>
            {runs.length > 0 && (
              <span
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: '#f3f4f6',
                  color: '#6b7280',
                }}
              >
                {runs.length} 条记录
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {runs.length > 0 && (
              <button
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid #e5e7eb',
                  background: 'white',
                  cursor: 'pointer',
                  fontSize: '12px',
                  color: '#ef4444',
                }}
                onClick={handleClearAll}
              >
                清空记录
              </button>
            )}
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
              <X size={20} />
            </button>
          </div>
        </div>

        {/* 筛选 */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid #f3f4f6',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Filter size={14} color="#9ca3af" />
          <div style={{ display: 'flex', gap: '4px' }}>
            {[
              { value: 'all', label: '全部' },
              { value: 'success', label: '成功' },
              { value: 'failed', label: '失败' },
              { value: 'running', label: '运行中' },
            ].map((option) => (
              <button
                key={option.value}
                style={{
                  padding: '4px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: filterStatus === option.value ? '#eff6ff' : 'transparent',
                  color: filterStatus === option.value ? '#2563eb' : '#6b7280',
                  cursor: 'pointer',
                  fontSize: '13px',
                }}
                onClick={() => setFilterStatus(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* 运行记录列表 */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: '12px 20px',
            display: 'block',
          }}
        >
          {loading && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
              <Loader2 size={32} style={{ margin: '0 auto 12px', animation: 'spin 1s linear infinite' }} />
              <div style={{ fontSize: '14px' }}>加载中...</div>
            </div>
          )}

          {error && !loading && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#ef4444' }}>
              <div style={{ fontSize: '14px' }}>加载失败: {error}</div>
              <button
                style={{
                  marginTop: '12px',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid #e5e7eb',
                  background: 'white',
                  cursor: 'pointer',
                  fontSize: '13px',
                }}
                onClick={loadRuns}
              >
                重试
              </button>
            </div>
          )}

          {!loading && !error && filteredRuns.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
              <History size={32} style={{ margin: '0 auto 12px' }} />
              <div style={{ fontSize: '14px' }}>
                {runs.length === 0 ? '暂无运行记录' : '没有符合条件的记录'}
              </div>
            </div>
          )}

          {!loading && !error && filteredRuns.map((run) => {
            const isExpanded = expandedRuns.has(run.id);

            return (
              <div
                key={run.id}
                style={{
                  border: `1px solid ${getStatusBorderColor(run.status)}`,
                  borderRadius: '8px',
                  overflow: 'hidden',
                  background: getStatusColor(run.status),
                }}
              >
                {/* 运行记录头部 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 12px',
                    cursor: 'pointer',
                  }}
                  onClick={() => toggleRun(run.id)}
                >
                  {getStatusIcon(run.status)}
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
                      运行 #{run.id?.slice(-6) || run.id}
                    </div>
                    <div style={{ fontSize: '11px', color: '#6b7280' }}>
                      {formatDate(run.started_at || run.startTime)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background:
                          run.status === 'success' || run.status === 'completed'
                            ? '#bbf7d0'
                            : run.status === 'failed'
                            ? '#fecaca'
                            : '#bfdbfe',
                        color:
                          run.status === 'success' || run.status === 'completed'
                            ? '#16a34a'
                            : run.status === 'failed'
                            ? '#dc2626'
                            : '#2563eb',
                      }}
                    >
                      {getStatusLabel(run.status)}
                    </span>
                    {run.duration_ms && (
                      <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                        {formatDuration(run.duration_ms)}
                      </span>
                    )}
                    <button
                      style={{
                        padding: '4px',
                        borderRadius: '4px',
                        border: 'none',
                        background: 'transparent',
                        cursor: 'pointer',
                        color: '#ef4444',
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteRun(run.id);
                      }}
                      title="删除"
                    >
                      <Trash2 size={14} />
                    </button>
                    {isExpanded ? (
                      <ChevronUp size={14} color="#9ca3af" />
                    ) : (
                      <ChevronDown size={14} color="#9ca3af" />
                    )}
                  </div>
                </div>

                {/* 展开的详情 */}
                {isExpanded && (
                  <div
                    style={{
                      padding: '10px 12px',
                      borderTop: `1px solid ${getStatusBorderColor(run.status)}`,
                      background: 'white',
                    }}
                  >
                    {/* 输入参数 */}
                    {run.input_variables && Object.keys(run.input_variables).length > 0 && (
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
                        <pre
                          style={{
                            fontSize: '11px',
                            fontFamily: 'monospace',
                            background: '#f9fafb',
                            padding: '8px',
                            borderRadius: '6px',
                            overflow: 'auto',
                            maxHeight: '150px',
                            margin: 0,
                            color: '#374151',
                          }}
                        >
                          {JSON.stringify(run.input_variables, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* 输出结果 */}
                    {run.output_result && Object.keys(run.output_result).length > 0 && (
                      <div style={{ marginBottom: '12px' }}>
                        <div
                          style={{
                            fontSize: '12px',
                            fontWeight: 500,
                            color: '#4b5563',
                            marginBottom: '6px',
                          }}
                        >
                          输出结果
                        </div>
                        <pre
                          style={{
                            fontSize: '11px',
                            fontFamily: 'monospace',
                            background: '#f9fafb',
                            padding: '8px',
                            borderRadius: '6px',
                            overflow: 'auto',
                            maxHeight: '150px',
                            margin: 0,
                            color: '#374151',
                          }}
                        >
                          {JSON.stringify(run.output_result, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* 错误信息 */}
                    {run.error_message && (
                      <div
                        style={{
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
                          {run.error_message}
                        </div>
                      </div>
                    )}

                    {/* 运行统计 */}
                    <div
                      style={{
                        display: 'flex',
                        gap: '16px',
                        marginTop: '12px',
                        fontSize: '11px',
                        color: '#9ca3af',
                      }}
                    >
                      <div>开始: {formatDate(run.started_at || run.startTime)}</div>
                      {run.completed_at && <div>结束: {formatDate(run.completed_at)}</div>}
                      {run.endTime && <div>结束: {formatDate(run.endTime)}</div>}
                      {run.duration_ms && <div>耗时: {formatDuration(run.duration_ms)}</div>}
                      {run.duration && <div>耗时: {formatDuration(run.duration)}</div>}
                      {run.node_count && <div>节点数: {run.node_count}</div>}
                      {run.nodeCount && <div>节点数: {run.nodeCount}</div>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <ConfirmDialog
        isOpen={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        onConfirm={handleClearAll}
        title="清空运行记录"
        message="确定要清空所有运行记录吗？此操作不可恢复。"
        confirmText="清空"
        cancelText="取消"
        variant="danger"
      />
    </div>
  );
};

export default RunHistory;
