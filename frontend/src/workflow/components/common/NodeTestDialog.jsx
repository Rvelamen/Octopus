/**
 * 节点测试对话框
 * 为单个节点提供输入参数填写并触发工作流运行
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';
import { useWorkflowAPI } from '../../services/workflowApi';
import { useWebSocket } from '../../../contexts/WebSocketContext';
import { message } from 'antd';

const NodeTestDialog = ({ isOpen, onClose, nodeId }) => {
  const nodes = useWorkflowStore((state) => state.nodes);
  const workflowId = useWorkflowStore((state) => state.workflowId);
  const versionId = useWorkflowStore((state) => state.versionId);
  const setTracePanelOpen = useWorkflowStore((state) => state.setTracePanelOpen);
  const startExecution = useWorkflowStore((state) => state.startExecution);
  const updateExecutionNode = useWorkflowStore((state) => state.updateExecutionNode);
  const finishExecution = useWorkflowStore((state) => state.finishExecution);

  const api = useWorkflowAPI();
  const { subscribe } = useWebSocket();

  const node = useMemo(() => nodes.find((n) => n.id === nodeId), [nodes, nodeId]);
  const inputs = useMemo(() => node?.data?.inputs || [], [node]);

  const [inputValues, setInputValues] = useState({});
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    if (isOpen && node) {
      const initial = {};
      inputs.forEach((input) => {
        const inputKey = input.key || input.name;
        if (!inputKey) return;
        const rawValue = input.value !== undefined
          ? input.value
          : (node.data?.[inputKey] ?? '');
        // 测试模式下，变量引用（如 {{nodeId.key}}）不应作为默认值，
        // 否则用户看到的是变量名而非可测试的值
        const isVariableRef = typeof rawValue === 'string' && rawValue.trim().startsWith('{{') && rawValue.trim().endsWith('}}');
        initial[inputKey] = isVariableRef ? '' : rawValue;
      });
      setInputValues(initial);
    }
  }, [isOpen, node, inputs]);

  const handleRun = useCallback(async () => {
    if (!workflowId || !versionId) {
      message.warning('请先保存工作流');
      return;
    }
    if (isRunning) return;

    setIsRunning(true);
    setTracePanelOpen(true);
    message.info('开始运行工作流...');

    // 将填写的输入值同步到节点 data 中（作为测试值保存）
    // 注意：这里只影响前端展示，不会自动保存到后端

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
        updateExecutionNode(data.node_id, data.status, data.output?.result || {}, inputSnapshot, data.output?.duration_ms);
      }
    };
    const unsub = subscribe('workflow_node_update', handleNodeUpdate);

    try {
      const result = await api.runWorkflow(workflowId, {
        version_id: versionId,
        input_variables: inputValues,
        test_mode: true,
      });
      if (result?.run_id) {
        currentRunId = result.run_id;
      }
      message.success(`工作流运行完成，Run ID: ${result?.run_id}`);
    } catch (error) {
      message.error('工作流运行失败: ' + (error.message || '未知错误'));
      console.error('[NodeTestDialog] run error:', error);
    } finally {
      setIsRunning(false);
      unsub();
      // 保留执行状态供用户在 TracePanel 中查看，下次运行时会自动清空
      finishExecution();
    }
  }, [
    workflowId,
    versionId,
    isRunning,
    inputValues,
    api,
    startExecution,
    updateExecutionNode,
    finishExecution,
    subscribe,
    setTracePanelOpen,
  ]);

  if (!isOpen || !node) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.4)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '520px',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: '#dcfce7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Play size={16} color="#22c55e" />
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: '#1f2937' }}>
                测试节点
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '2px' }}>
                {node.data?.name || nodeId}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px',
              color: '#9ca3af',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* 内容 */}
        <div
          style={{
            padding: '16px 20px',
            overflowY: 'auto',
            flex: 1,
          }}
        >
          {inputs.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '24px',
                color: '#9ca3af',
                fontSize: '14px',
              }}
            >
              该节点没有配置输入参数
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '4px' }}>
                请填写以下输入参数进行测试：
              </div>
              {inputs.map((input) => {
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
                    <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
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
                  {input.description && (
                    <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '6px' }}>
                      {input.description}
                    </div>
                  )}
                  <input
                    type="text"
                    value={inputValues[inputKey] ?? ''}
                    onChange={(e) =>
                      setInputValues((prev) => ({
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

          {/* 提示信息 */}
          <div
            style={{
              marginTop: '16px',
              padding: '10px 12px',
              background: '#f9fafb',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#6b7280',
              lineHeight: 1.5,
            }}
          >
            💡 提示：点击「运行」将执行整个工作流，执行结果会自动显示在右侧「执行追踪」面板中。
            {!workflowId && ' 请先保存工作流后再测试。'}
          </div>
        </div>

        {/* 底部 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            gap: '10px',
            padding: '12px 20px',
            borderTop: '1px solid #f3f4f6',
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: '1px solid #e5e7eb',
              background: 'white',
              color: '#374151',
              fontSize: '14px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            取消
          </button>
          <button
            onClick={handleRun}
            disabled={isRunning || !workflowId}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              background: !workflowId ? '#d1d5db' : '#22c55e',
              color: 'white',
              fontSize: '14px',
              cursor: isRunning || !workflowId ? 'not-allowed' : 'pointer',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'opacity 0.2s',
              opacity: isRunning ? 0.8 : 1,
            }}
          >
            {isRunning ? (
              <>
                <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                运行中...
              </>
            ) : (
              <>
                <Play size={14} fill="white" />
                运行
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NodeTestDialog;
