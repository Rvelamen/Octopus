import React, { useState, useEffect, useCallback } from 'react';

const formatDuration = (ms) => {
  if (ms == null) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
};
import { X, Play } from 'lucide-react';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';
import { useWorkflowAPI } from '../../services/workflowApi';
import { useWebSocket } from '../../../contexts/WebSocketContext';
import { message } from 'antd';

const NodeTestResultDrawer = () => {
  const isOpen = useWorkflowStore((state) => state.isTestResultOpen);
  const setIsOpen = useWorkflowStore((state) => state.setTestResultOpen);
  const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId);
  const nodes = useWorkflowStore((state) => state.nodes);
  const executionStatus = useWorkflowStore((state) => state.executionStatus);
  const workflowId = useWorkflowStore((state) => state.workflowId);
  const versionId = useWorkflowStore((state) => state.versionId);
  const startExecution = useWorkflowStore((state) => state.startExecution);
  const updateExecutionNode = useWorkflowStore((state) => state.updateExecutionNode);
  const finishExecution = useWorkflowStore((state) => state.finishExecution);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const nodeExecution = selectedNodeId ? executionStatus[selectedNodeId] : null;

  const [testInputValues, setTestInputValues] = useState({});
  const [isTestRunning, setIsTestRunning] = useState(false);
  const [liveDuration, setLiveDuration] = useState(0);
  const setExecutionMode = useWorkflowStore((state) => state.setExecutionMode);

  useEffect(() => {
    if (!nodeExecution || nodeExecution.status !== 'running') {
      setLiveDuration(0);
      return;
    }
    const start = nodeExecution.timestamp || Date.now();
    setLiveDuration(Date.now() - start);
    const timer = setInterval(() => {
      setLiveDuration(Date.now() - start);
    }, 100);
    return () => clearInterval(timer);
  }, [nodeExecution?.status, nodeExecution?.timestamp]);

  const api = useWorkflowAPI();
  const { subscribe } = useWebSocket();

  // 当 drawer 打开或选中节点变化时，初始化输入值
  useEffect(() => {
    if (isOpen && selectedNode?.data) {
      const initial = {};
      const inputs = selectedNode.data.inputs || [];
      inputs.forEach((input) => {
        const inputKey = input.key || input.name;
        if (!inputKey) return;
        const rawValue =
          input.value !== undefined
            ? input.value
            : (selectedNode.data?.[inputKey] ?? '');
        const isVariableRef =
          typeof rawValue === 'string' &&
          rawValue.trim().startsWith('{{') &&
          rawValue.trim().endsWith('}}');
        initial[inputKey] = isVariableRef ? '' : rawValue;
      });
      setTestInputValues(initial);
    }
  }, [isOpen, selectedNode]);

  const handleTestRun = useCallback(async () => {
    if (!workflowId || !versionId) {
      message.warning('请先保存工作流');
      return;
    }
    if (isTestRunning) return;

    setIsTestRunning(true);
    message.info('开始运行工作流...');
    setExecutionMode('test', selectedNodeId);
    startExecution(null);

    let currentRunId = null;
    const handleNodeUpdate = (data) => {
      if (!data?.run_id) return;
      if (!currentRunId) {
        currentRunId = data.run_id;
        startExecution(data.run_id);
      }
      if (data.run_id !== currentRunId) return;
      if (data.node_id && data.status) {
        const trace = data.output?.trace;
        const inputSnapshot = trace?.input_snapshot || {};
        updateExecutionNode(
          data.node_id,
          data.status,
          data.output?.result || {},
          inputSnapshot,
          data.output?.duration_ms
        );
      }
    };
    const unsub = subscribe('workflow_node_update', handleNodeUpdate);

    try {
      const result = await api.runWorkflow(workflowId, {
        version_id: versionId,
        input_variables: testInputValues,
        test_mode: true,
      });
      if (result?.run_id) {
        currentRunId = result.run_id;
      }
      message.success('工作流运行完成');
    } catch (error) {
      message.error('工作流运行失败: ' + (error.message || '未知错误'));
    } finally {
      setIsTestRunning(false);
      unsub();
      finishExecution();
    }
  }, [
    workflowId,
    versionId,
    isTestRunning,
    testInputValues,
    api,
    startExecution,
    updateExecutionNode,
    finishExecution,
    subscribe,
  ]);

  if (!isOpen || !selectedNode) return null;

  const testInputs = selectedNode?.data?.inputs || [];
  const hasResult = !!nodeExecution?.status;

  return (
    <>
      {/* 全屏遮罩 */}
      <div
        onClick={() => setIsOpen(false)}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.35)',
          zIndex: 300,
          animation: 'fadeIn 0.2s ease-out',
        }}
      />

      {/* 抽屉面板 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          right: 0,
          width: '480px',
          maxWidth: '100vw',
          background: 'white',
          borderRadius: '16px 16px 0 0',
          boxShadow: '0 -8px 32px rgba(0,0,0,0.15)',
          borderTop: '1px solid #e5e7eb',
          zIndex: 310,
          minHeight: '320px',
          height: '90vh',
          display: 'flex',
          flexDirection: 'column',
          animation: 'slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          <div>
            <span style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937' }}>
              节点试运行
            </span>
            {selectedNode?.data?.name && (
              <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '8px' }}>
                {selectedNode.data.name}
              </span>
            )}
          </div>
          <button
            onClick={() => setIsOpen(false)}
            style={{
              padding: '4px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={18} color="#6b7280" />
          </button>
        </div>

        {/* Content */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          {/* 输入参数 */}
          <div>
            <div
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#1f2937',
                marginBottom: '12px',
              }}
            >
              输入参数
            </div>
            {testInputs.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#9ca3af', padding: '8px 0' }}>
                该节点没有配置输入参数
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {testInputs.map((input) => {
                  const inputKey = input.key || input.name;
                  if (!inputKey) return null;
                  return (
                    <div key={inputKey}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          marginBottom: '6px',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '13px',
                            fontWeight: 500,
                            color: '#374151',
                          }}
                        >
                          {input.label || input.name || input.key}
                        </span>
                        {input.required && (
                          <span style={{ fontSize: '11px', color: '#ef4444' }}>*</span>
                        )}
                        <span
                          style={{
                            fontSize: '11px',
                            color: '#9ca3af',
                            background: '#f3f4f6',
                            padding: '1px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          {input.type || 'string'}
                        </span>
                      </div>
                      <input
                        type="text"
                        value={testInputValues[inputKey] ?? ''}
                        onChange={(e) =>
                          setTestInputValues((prev) => ({
                            ...prev,
                            [inputKey]: e.target.value,
                          }))
                        }
                        placeholder={`请输入 ${input.label || input.name || input.key}`}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          border: '1px solid #e5e7eb',
                          fontSize: '14px',
                          outline: 'none',
                          transition: 'border-color 0.2s',
                        }}
                        onFocus={(e) => (e.target.style.borderColor = '#6366f1')}
                        onBlur={(e) => (e.target.style.borderColor = '#e5e7eb')}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 运行按钮 */}
          <button
            onClick={handleTestRun}
            disabled={isTestRunning}
            style={{
              width: '100%',
              padding: '10px 16px',
              borderRadius: '8px',
              border: 'none',
              background: isTestRunning ? '#9ca3af' : '#22c55e',
              color: 'white',
              fontSize: '14px',
              fontWeight: 500,
              cursor: isTestRunning ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            {isTestRunning ? (
              <>
                <div
                  style={{
                    width: '14px',
                    height: '14px',
                    border: '2px solid white',
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }}
                />
                运行中...
              </>
            ) : (
              <>
                <Play size={16} fill="white" />
                运行
              </>
            )}
          </button>

          {/* 运行结果 */}
          {hasResult && (
            <div
              style={{
                marginTop: '8px',
                paddingTop: '16px',
                borderTop: '1px solid #f3f4f6',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
              }}
            >
              <div
                style={{
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#1f2937',
                }}
              >
                运行结果
              </div>

              {/* 状态 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{ fontSize: '13px', fontWeight: 600, color: '#1f2937' }}
                >
                  状态:
                </span>
                <span
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background:
                      nodeExecution.status === 'completed'
                        ? '#dcfce7'
                        : nodeExecution.status === 'failed'
                          ? '#fee2e2'
                          : '#fef3c7',
                    color:
                      nodeExecution.status === 'completed'
                        ? '#166534'
                        : nodeExecution.status === 'failed'
                          ? '#991b1b'
                          : '#92400e',
                  }}
                >
                  {nodeExecution.status === 'completed'
                    ? '完成'
                    : nodeExecution.status === 'failed'
                      ? '失败'
                      : nodeExecution.status === 'running'
                        ? '运行中'
                        : nodeExecution.status}
                </span>
                {nodeExecution.status === 'running' && liveDuration > 0 && (
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>
                    {formatDuration(liveDuration)}
                  </span>
                )}
                {nodeExecution.status !== 'running' &&
                  nodeExecution.duration !== null &&
                  nodeExecution.duration !== undefined && (
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>
                      {formatDuration(nodeExecution.duration)}
                    </span>
                  )}
              </div>

              {/* 输入 —— 结束节点不显示 */}
              {selectedNode?.data?.flowNodeType !== 'workflowEnd' &&
                nodeExecution.input &&
                Object.keys(nodeExecution.input).length > 0 && (
                  <div>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '6px',
                      }}
                    >
                      输入
                    </div>
                    <DrawerKVDisplay data={nodeExecution.input} />
                  </div>
                )}

              {/* 推理内容 */}
              {(() => {
                const out = nodeExecution.output || {};
                const reasoning =
                  out.reasoningText ||
                  out.reasoning_text ||
                  out.reasoningContent ||
                  out.reasoning_content;
                return reasoning ? (
                  <div>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '6px',
                      }}
                    >
                      推理内容
                    </div>
                    <div
                      style={{
                        background: '#f9fafb',
                        borderRadius: '8px',
                        padding: '10px 12px',
                        border: '1px solid #f3f4f6',
                        fontSize: '13px',
                        color: '#4b5563',
                        lineHeight: 1.6,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {String(reasoning)}
                    </div>
                  </div>
                ) : null;
              })()}

              {/* 输出 */}
              {(() => {
                const out = nodeExecution.output || {};
                const configuredOutputs = (selectedNode?.data?.outputs || [])
                  .map((o) => o.name)
                  .filter(Boolean);
                const userOutput = {};
                for (const key of configuredOutputs) {
                  if (key in out) userOutput[key] = out[key];
                }
                const displayOutput =
                  Object.keys(userOutput).length > 0
                    ? userOutput
                    : Object.keys(out).length > 0
                      ? out
                      : {};
                return Object.keys(displayOutput).length > 0 ? (
                  <div>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '6px',
                      }}
                    >
                      输出
                    </div>
                    <DrawerKVDisplay data={displayOutput} />
                  </div>
                ) : null;
              })()}

              {/* 错误 */}
              {nodeExecution.error && (
                <div>
                  <div
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: '#ef4444',
                      marginBottom: '6px',
                    }}
                  >
                    错误
                  </div>
                  <div
                    style={{
                      fontSize: '13px',
                      color: '#dc2626',
                      background: '#fef2f2',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      lineHeight: 1.6,
                      wordBreak: 'break-word',
                    }}
                  >
                    {nodeExecution.error}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </>
  );
};

const DrawerKVDisplay = ({ data }) => {
  return (
    <div
      style={{
        background: '#f9fafb',
        borderRadius: '8px',
        padding: '10px 12px',
        border: '1px solid #f3f4f6',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      }}
    >
      {Object.entries(data).map(([key, val]) => (
        <div key={key} style={{ fontSize: '13px', lineHeight: 1.6 }}>
          <span style={{ color: '#6366f1', fontWeight: 500 }}>{key}</span>
          <span style={{ color: '#9ca3af', margin: '0 4px' }}>:</span>
          <DrawerValueDisplay value={val} />
        </div>
      ))}
    </div>
  );
};

const DrawerValueDisplay = ({ value }) => {
  if (value === null) return <span style={{ color: '#9ca3af' }}>null</span>;
  if (value === undefined) return <span style={{ color: '#9ca3af' }}>undefined</span>;
  if (typeof value === 'boolean')
    return <span style={{ color: '#f97316' }}>{String(value)}</span>;
  if (typeof value === 'number')
    return <span style={{ color: '#10b981' }}>{value}</span>;
  if (typeof value === 'string') {
    return (
      <span style={{ color: '#1f2937', whiteSpace: 'pre-wrap' }}>{value}</span>
    );
  }
  if (typeof value === 'object') {
    return <span style={{ color: '#4b5563' }}>{JSON.stringify(value)}</span>;
  }
  return <span style={{ color: '#1f2937' }}>{String(value)}</span>;
};

export default NodeTestResultDrawer;
