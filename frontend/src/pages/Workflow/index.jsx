/**
 * 工作流编排页面
 * 集成 ReactFlow 和 Coze 风格的工作流编辑器
 * 已接入后端 WebSocket API
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './Workflow.css';
import {
  Play,
  Save,
  FolderOpen,
  Undo2,
  Redo2,
  Bug,
  ZoomIn,
  ZoomOut,
  Maximize,
  GitBranch,
  History,
  Plus,
  Trash2,
  Terminal,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  CloudOff,
  Cloud,
} from 'lucide-react';

import { useWorkflowStore } from '../../workflow/hooks/useWorkflowStore';
import { useWorkflowAPI } from '../../workflow/services/workflowApi';
import { useWebSocket } from '../../contexts/WebSocketContext';
import NodeTemplates from '../../workflow/components/NodeTemplates';
import NodeConfigDrawer from '../../workflow/components/NodeConfigDrawer';
import NodeTestResultDrawer from '../../workflow/components/NodeTestResultDrawer';
import TracePanel from '../../workflow/components/TracePanel';
import VersionManager from '../../workflow/components/WorkflowManager/VersionManager';
import VersionCompare from '../../workflow/components/WorkflowManager/VersionCompare';
import RunHistory from '../../workflow/components/WorkflowManager/RunHistory';
import WorkflowList from '../../workflow/components/WorkflowManager/WorkflowList';
import RunDialog from '../../workflow/components/common/RunDialog';

import nodeTypes from '../../workflow/components/nodes';
import { createNodeFromTemplate } from '../../workflow/templates';

import { message } from 'antd';

// 工具栏按钮
const ToolbarButton = ({ icon: Icon, label, onClick, active, disabled, color }) => (
  <button
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '2px',
      padding: '6px 8px',
      borderRadius: '6px',
      border: 'none',
      background: active ? '#eff6ff' : 'transparent',
      color: active ? '#2563eb' : color || '#6b7280',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      fontSize: '11px',
      minWidth: '48px',
      whiteSpace: 'nowrap',
    }}
    onClick={onClick}
    disabled={disabled}
    title={label}
  >
    <Icon size={18} />
    <span>{label}</span>
  </button>
);

// 分隔线
const ToolbarDivider = () => (
  <div style={{ width: '1px', height: '32px', background: '#e5e7eb', margin: '0 4px' }} />
);

// 底部工具栏
const BottomToolbar = ({
  onSave,
  onLoad,
  onUndo,
  onRedo,
  onRun,
  onDebug,
  onZoomIn,
  onZoomOut,
  onFitView,
  onToggleTemplates,
  onToggleTrace,
  onToggleVersionManager,
  onToggleVersionCompare,
  onToggleRunHistory,
  onToggleWorkflowList,
  canUndo,
  canRedo,
  isRunning,
  isSaving,
  isDirty,
  isConnected,
  currentWorkflowName,
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexWrap: 'wrap',
      gap: '4px',
      padding: '6px 12px',
      background: 'white',
      borderRadius: '12px',
      boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      border: '1px solid #f3f4f6',
      width: '120%',
    }}
  >
    <ToolbarButton 
      icon={isSaving ? Loader2 : Save} 
      label={isSaving ? '保存中' : '保存'} 
      onClick={onSave} 
      color="#3b82f6" 
      disabled={isSaving}
    />
    <ToolbarButton icon={FolderOpen} label="打开" onClick={onLoad} />
    <ToolbarDivider />
    <ToolbarButton icon={Undo2} label="撤销" onClick={onUndo} disabled={!canUndo} />
    <ToolbarButton icon={Redo2} label="重做" onClick={onRedo} disabled={!canRedo} />
    <ToolbarDivider />
    <ToolbarButton
      icon={isRunning ? AlertCircle : Play}
      label={isRunning ? '运行中' : '运行'}
      onClick={onRun}
      color={isRunning ? '#f59e0b' : '#22c55e'}
      disabled={isRunning}
    />
    <ToolbarButton icon={Bug} label="调试" onClick={onDebug} color="#8b5cf6" />
    <ToolbarDivider />
    <ToolbarButton icon={ZoomIn} label="放大" onClick={onZoomIn} />
    <ToolbarButton icon={ZoomOut} label="缩小" onClick={onZoomOut} />
    <ToolbarButton icon={Maximize} label="适应" onClick={onFitView} />
    <ToolbarDivider />
    <ToolbarButton icon={Plus} label="添加" onClick={onToggleTemplates} />
    <ToolbarButton icon={Terminal} label="追踪" onClick={onToggleTrace} />
    <ToolbarButton icon={GitBranch} label="版本" onClick={onToggleVersionManager} />
    <ToolbarButton icon={History} label="历史" onClick={onToggleRunHistory} />
    <ToolbarButton icon={FolderOpen} label="列表" onClick={onToggleWorkflowList} />
    {currentWorkflowName && (
      <>
        <ToolbarDivider />
        <span style={{ fontSize: '11px', color: '#6b7280', padding: '0 8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
          {isDirty && (
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
          )}
          {currentWorkflowName}
          {isSaving && <Loader2 size={12} style={{ animation: 'spin 1s linear infinite', marginLeft: 4 }} />}
          {isConnected === false && (
            <span title="WebSocket 已断开"><CloudOff size={12} color="#ef4444" style={{ marginLeft: 4 }} /></span>
          )}
          {isConnected && <Cloud size={12} color="#22c55e" style={{ marginLeft: 4 }} />}
        </span>
      </>
    )}
  </div>
);

// 状态栏
const StatusBar = ({ nodeCount, edgeCount, selectedNode, workflowId, versionId, isDirty }) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '4px 12px',
      background: '#f8fafc',
      fontSize: '11px',
      color: '#6b7280',
      borderTop: '1px solid #e5e7eb',
      minHeight: '28px',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <span>{nodeCount} 个节点</span>
      <span>{edgeCount} 条连接</span>
      {isDirty && (
        <span style={{ color: '#f59e0b', fontWeight: 500 }}>
          ● 未保存
        </span>
      )}
      {selectedNode && (
        <span style={{ color: '#2563eb' }}>
          已选择: {selectedNode.data?.name || selectedNode.id}
        </span>
      )}
      {workflowId && (
        <span style={{ color: '#059669' }}>
          WF: {workflowId.slice(0, 8)}...
        </span>
      )}
      {versionId && (
        <span style={{ color: '#7c3aed' }}>
          VER: {versionId.slice(0, 8)}...
        </span>
      )}
    </div>
    <div>按 Ctrl+K 添加节点 | Ctrl+S 保存</div>
  </div>
);

// 主工作流编辑器组件
const WorkflowEditor = () => {
  const reactFlowWrapper = useRef(null);
  const reactFlow = useReactFlow();
  const api = useWorkflowAPI();

  const nodes = useWorkflowStore((state) => state.nodes);
  const edges = useWorkflowStore((state) => state.edges);
  const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId);
  const setNodes = useWorkflowStore((state) => state.setNodes);
  const setEdges = useWorkflowStore((state) => state.setEdges);
  const onNodesChange = useWorkflowStore((state) => state.onNodesChange);
  const onEdgesChange = useWorkflowStore((state) => state.onEdgesChange);
  const addNode = useWorkflowStore((state) => state.addNode);
  const addEdgeToStore = useWorkflowStore((state) => state.addEdge);
  const selectNode = useWorkflowStore((state) => state.selectNode);
  const removeNode = useWorkflowStore((state) => state.removeNode);
  const moveNodeIntoLoop = useWorkflowStore((state) => state.moveNodeIntoLoop);
  const undo = useWorkflowStore((state) => state.undo);
  const redo = useWorkflowStore((state) => state.redo);
  const canUndo = useWorkflowStore((state) => state.canUndo);
  const canRedo = useWorkflowStore((state) => state.canRedo);
  const markSaved = useWorkflowStore((state) => state.markSaved);
  const dirty = useWorkflowStore((state) => state.dirty);
  const startExecution = useWorkflowStore((state) => state.startExecution);
  const updateExecutionNode = useWorkflowStore((state) => state.updateExecutionNode);
  const stopExecution = useWorkflowStore((state) => state.stopExecution);
  const finishExecution = useWorkflowStore((state) => state.finishExecution);
  const setExecutionMode = useWorkflowStore((state) => state.setExecutionMode);
  const executionStatus = useWorkflowStore((state) => state.executionStatus);

  const { connected: isConnected, subscribe, unsubscribe: wsUnsubscribe } = useWebSocket();

  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false);
  const isConfigOpen = useWorkflowStore((state) => state.configDrawerOpen);
  const setIsConfigOpen = useWorkflowStore((state) => state.setConfigDrawerOpen);
  const isTraceOpen = useWorkflowStore((state) => state.isTracePanelOpen);
  const setIsTraceOpen = useWorkflowStore((state) => state.setTracePanelOpen);
  const [isVersionManagerOpen, setIsVersionManagerOpen] = useState(false);
  const [isVersionCompareOpen, setIsVersionCompareOpen] = useState(false);
  const [isRunHistoryOpen, setIsRunHistoryOpen] = useState(false);
  const [isWorkflowListOpen, setIsWorkflowListOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // 根据运行状态动态设置连接线样式
  const styledEdges = useMemo(() => {
    const hasRunning = Object.values(executionStatus).some((s) => s?.status === 'running');
    return (edges || []).map((edge) => ({
      ...edge,
      animated: hasRunning,
      style: {
        ...edge.style,
        stroke: '#6366f1',
        strokeWidth: 2,
        strokeDasharray: hasRunning ? '5,5' : undefined,
      },
    }));
  }, [edges, executionStatus]);

  // 当前工作流状态
  const [workflowId, setWorkflowId] = useState(null);
  const [versionId, setVersionId] = useState(null);
  const setWorkflowInfo = useWorkflowStore((state) => state.setWorkflowInfo);
  const [workflowName, setWorkflowName] = useState('');
  const [versions, setVersions] = useState([]);

  // 运行弹窗状态
  const [isRunDialogOpen, setIsRunDialogOpen] = useState(false);
  const [pendingRunVariables, setPendingRunVariables] = useState([]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  // 将执行状态合并到节点数据中，用于 ReactFlow 渲染高亮
  const nodesWithStatus = useMemo(() => {
    if (Object.keys(executionStatus).length === 0) {
      return nodes;
    }
    return nodes.map((node) => {
      const statusInfo = executionStatus[node.id];
      if (!statusInfo) return node;
      const className = `workflow-node--${statusInfo.status}`;
      return {
        ...node,
        className: node.className ? `${node.className} ${className}` : className,
        data: {
          ...node.data,
          executionStatus: statusInfo,
        },
      };
    });
  }, [nodes, executionStatus]);

  // 连接边
  const onConnect = useCallback(
    (params) => {
      addEdgeToStore({
        source: params.source,
        target: params.target,
      });
    },
    [addEdgeToStore]
  );

  // 点击画布空白处
  const onPaneClick = useCallback(() => {
    selectNode(null);
    setIsConfigOpen(false);
  }, [selectNode]);

  // 点击节点
  const onNodeClick = useCallback(
    (event, node) => {
      event.stopPropagation();
      selectNode(node.id);
      setIsConfigOpen(true);
    },
    [selectNode]
  );

  // 从模板添加节点
  const handleSelectNodeTemplate = useCallback(
    (template) => {
      const centerX = reactFlowWrapper.current?.clientWidth / 2 || 400;
      const centerY = reactFlowWrapper.current?.clientHeight / 2 || 300;
      const position = reactFlow.screenToFlowPosition({ x: centerX, y: centerY });

      const newNode = createNodeFromTemplate(template, position);
      addNode(newNode);
      setIsTemplatesOpen(false);
      message.success(`已添加节点: ${template.name}`);
    },
    [addNode, reactFlow]
  );

  // 保存工作流到后端
  const handleSave = useCallback(async () => {
    if (!workflowId || !versionId) {
      message.warning('请先创建或加载一个工作流');
      setIsWorkflowListOpen(true);
      return;
    }

    setIsSaving(true);
    try {
      // 收集所有有效节点 ID（主画布 + loop 内部子节点）
      const collectNodeIds = (nodeList) => {
        const ids = new Set();
        for (const node of nodeList) {
          ids.add(node.id);
          const childNodes = node.data?.children?.nodes;
          if (childNodes) {
            for (const child of childNodes) {
              ids.add(child.id);
            }
          }
        }
        return ids;
      };
      const validNodeIds = collectNodeIds(nodes);

      // 转换节点格式以匹配后端期望
      const nodesData = nodes.map((node) => ({
        id: node.id,
        type: node.type,
        label: node.data?.name || node.data?.label || node.type,
        position: node.position,
        width: node.width || 240,
        height: node.height || 120,
        config: node.data || {},
        timeout_seconds: node.data?.timeout_seconds || 60,
        max_retries: node.data?.max_retries || 0,
      }));

      // 过滤掉 source/target 不在有效节点列表中的边（避免 FOREIGN KEY 错误）
      const edgesData = edges
        .filter((edge) => validNodeIds.has(edge.source) && validNodeIds.has(edge.target))
        .map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || '',
          condition: edge.condition || '',
          sourceHandle: edge.sourceHandle || `${edge.source}-source`,
          targetHandle: edge.targetHandle || `${edge.target}-target`,
        }));

      await api.saveDefinition(versionId, nodesData, edgesData, []);
      markSaved();
      message.success('工作流已保存到数据库');
    } catch (error) {
      message.error('保存失败: ' + (error.message || '未知错误'));
      console.error('[WorkflowEditor] save error:', error);
    } finally {
      setIsSaving(false);
    }
  }, [workflowId, versionId, nodes, edges, api, markSaved]);

  // 加载工作流
  const handleLoad = useCallback(async () => {
    setIsWorkflowListOpen(true);
  }, []);

  // 选择工作流并加载定义
  const handleSelectWorkflow = useCallback(async (workflow) => {
    setWorkflowId(workflow.id);
    setWorkflowName(workflow.name);

    try {
      // 获取版本列表
      const versions = await api.getVersionList(workflow.id);
      if (versions.length === 0) {
        message.warning('该工作流没有版本');
        setVersionId(null);
        setNodes([]);
        setEdges([]);
        return;
      }

      // 使用最新版本（草稿优先，否则取第一个）
      const targetVersion = versions.find((v) => v.status === 'draft') || versions[0];
      setVersionId(targetVersion.id);

      // 加载定义
      const definition = await api.getDefinition(targetVersion.id);
      if (definition) {
        // 转换后端节点格式为 ReactFlow 格式
        const loadedNodes = (definition.nodes || []).map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position || { x: 0, y: 0 },
          width: n.width || 240,
          height: n.height || 120,
          data: {
            ...n.config,
            name: n.label,
            flowNodeType: n.type,
          },
        }));

        const loadedEdges = (definition.edges || []).map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle || `${e.source}-source`,
          targetHandle: e.targetHandle || `${e.target}-target`,
          label: e.label || '',
        }));

        setNodes(loadedNodes);
        setEdges(loadedEdges);
        markSaved();
        message.success(`已加载工作流: ${workflow.name}`);
      }
    } catch (error) {
      message.error('加载失败: ' + (error.message || '未知错误'));
      console.error('[WorkflowEditor] load error:', error);
    }
  }, [api, setNodes, setEdges, markSaved]);

  // 创建新工作流
  const handleCreateWorkflow = useCallback(async () => {
    try {
      const name = window.prompt('请输入工作流名称:', '新工作流');
      if (!name) return;

      const description = window.prompt('请输入工作流描述（可选）:', '') || '';

      const newWf = await api.saveWorkflow({
        name,
        description,
        category: 'general',
      });

      setWorkflowId(newWf.id);
      setWorkflowName(newWf.name);

      // 获取初始版本
      const versions = await api.getVersionList(newWf.id);
      if (versions.length > 0) {
        setVersionId(versions[0].id);
      }

      setNodes([]);
      setEdges([]);
      markSaved();
      message.success(`已创建工作流: ${name}`);
    } catch (error) {
      message.error('创建失败: ' + (error.message || '未知错误'));
      console.error('[WorkflowEditor] create error:', error);
    }
  }, [api, setNodes, setEdges, markSaved]);

  // 获取 WorkflowStart 节点的输入变量
  const getStartNodeInputs = useCallback(() => {
    const startNode = nodes.find((n) => n.type === 'workflowStart');
    if (!startNode) return [];
    const inputs = startNode.data?.inputs || [];
    return inputs.filter((i) => i.name && i.name.trim() !== '');
  }, [nodes]);

  // 运行工作流
  const handleRun = useCallback(async () => {
    if (!workflowId || !versionId) {
      message.warning('请先保存工作流');
      return;
    }

    if (isRunning) return;

    // 检查是否有输入变量
    const inputVars = getStartNodeInputs();
    if (inputVars.length > 0) {
      setPendingRunVariables(inputVars);
      setIsRunDialogOpen(true);
      return;
    }

    // 无输入变量,直接运行
    setIsRunning(true);
    message.info('开始运行工作流...');
    setExecutionMode('run');
    startExecution(null);

    let currentRunId = null;
    const handleNodeUpdate = (data) => {
      console.log('[handleNodeUpdate] received:', data);
      if (!data?.run_id) return;
      if (!currentRunId) {
        currentRunId = data.run_id;
      }
      if (data.run_id !== currentRunId) return;
      if (data.node_id && data.status) {
        const trace = data.output?.trace;
        const inputSnapshot = trace?.input_snapshot || {};
        updateExecutionNode(data.node_id, data.status, data.output?.result || {}, inputSnapshot, data.output?.duration_ms);
      }
    };
    const unsub = subscribe('workflow_node_update', handleNodeUpdate);
    console.log('[handleRun] subscribed, calling runWorkflow...');

    try {
      const result = await api.runWorkflow(workflowId, {
        version_id: versionId,
        input_variables: {},
      });
      console.log('[handleRun] runWorkflow returned:', result);
      if (result?.run_id) {
        currentRunId = result.run_id;
      }
      message.success(`工作流运行完成，Run ID: ${result?.run_id}`);
    } catch (error) {
      message.error('工作流运行失败: ' + (error.message || '未知错误'));
      console.error('[WorkflowEditor] run error:', error);
    } finally {
      setIsRunning(false);
      if (typeof unsub === 'function') unsub();
      finishExecution();
    }
  }, [workflowId, versionId, isRunning, api, getStartNodeInputs, startExecution, updateExecutionNode, finishExecution, subscribe, setExecutionMode]);

  // 带输入变量的运行确认
  const handleRunWithInputs = useCallback(async (inputValues) => {
    console.log('[handleRunWithInputs] called, inputValues:', inputValues);
    setIsRunDialogOpen(false);
    setIsRunning(true);
    message.info('开始运行工作流...');
    setExecutionMode('run');
    startExecution(null);

    let currentRunId = null;
    const handleNodeUpdate = (data) => {
      console.log('[handleNodeUpdate] received:', data);
      if (!data?.run_id) return;
      if (!currentRunId) {
        currentRunId = data.run_id;
      }
      if (data.run_id !== currentRunId) return;
      if (data.node_id && data.status) {
        const trace = data.output?.trace;
        const inputSnapshot = trace?.input_snapshot || {};
        updateExecutionNode(data.node_id, data.status, data.output?.result || {}, inputSnapshot, data.output?.duration_ms);
      }
    };
    const unsub = subscribe('workflow_node_update', handleNodeUpdate);
    console.log('[handleRunWithInputs] subscribed, calling runWorkflow...');

    try {
      const result = await api.runWorkflow(workflowId, {
        version_id: versionId,
        input_variables: inputValues,
      });
      console.log('[handleRunWithInputs] runWorkflow returned:', result);
      if (result?.run_id) {
        currentRunId = result.run_id;
      }
      message.success(`工作流运行完成，Run ID: ${result?.run_id}`);
    } catch (error) {
      message.error('工作流运行失败: ' + (error.message || '未知错误'));
      console.error('[WorkflowEditor] run error:', error);
    } finally {
      setIsRunning(false);
      if (typeof unsub === 'function') unsub();
      finishExecution();
    }
  }, [workflowId, versionId, api, startExecution, updateExecutionNode, finishExecution, subscribe, setExecutionMode]);

  // 调试工作流
  const handleDebug = useCallback(() => {
    setIsTraceOpen(true);
    message.info('调试面板已打开');
  }, [setIsTraceOpen]);

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 's':
            e.preventDefault();
            handleSave();
            break;
          case 'z':
            e.preventDefault();
            if (e.shiftKey) {
              redo();
            } else {
              undo();
            }
            break;
          case 'k':
            e.preventDefault();
            setIsTemplatesOpen(true);
            break;
        }
      }
      if (e.key === 'Delete' && selectedNodeId) {
        const node = nodes.find((n) => n.id === selectedNodeId);
        if (node && !node.data?.forbidDelete) {
          removeNode(selectedNodeId);
          selectNode(null);
          setIsConfigOpen(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave, undo, redo, selectedNodeId, nodes, removeNode, selectNode]);

  // 自动保存：5 秒无操作后自动保存
  const autoSaveTimerRef = useRef(null);
  useEffect(() => {
    if (!dirty || !workflowId || !versionId) return;
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(() => {
      handleSave();
    }, 5000);
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [dirty, workflowId, versionId, handleSave]);

  // 监听版本列表变化
  const loadVersions = useCallback(async () => {
    if (!workflowId) {
      setVersions([]);
      return;
    }
    try {
      const list = await api.getVersionList(workflowId);
      setVersions(list);
    } catch (err) {
      console.error('[WorkflowEditor] load versions error:', err);
    }
  }, [api, workflowId]);

  useEffect(() => {
    loadVersions();
  }, [workflowId, loadVersions]);

  // 同步工作流信息到 store，供节点测试等使用
  useEffect(() => {
    setWorkflowInfo(workflowId, versionId);
  }, [workflowId, versionId, setWorkflowInfo]);

  // 首次加载时自动加载第一个工作流
  const hasAutoLoaded = useRef(false);
  useEffect(() => {
    if (hasAutoLoaded.current || workflowId) return;
    hasAutoLoaded.current = true;

    const autoLoadFirstWorkflow = async () => {
      try {
        const list = await api.getWorkflowList();
        if (list && list.length > 0) {
          await handleSelectWorkflow(list[0]);
        }
      } catch (err) {
        console.error('[WorkflowEditor] auto-load first workflow error:', err);
      }
    };

    autoLoadFirstWorkflow();
  }, [api, workflowId, handleSelectWorkflow]);

  return (
    <div
      ref={reactFlowWrapper}
      style={{
        width: '100vw',
        height: '100vh',
        position: 'relative',
        background: '#f9fafb',
      }}
    >
      <ReactFlow
        nodes={nodesWithStatus || []}
        edges={styledEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onNodeDragStop={(_event, node) => {
          const loopNodes = (nodes || []).filter((n) => n.type === 'loop' && n.id !== node.id);
          if (loopNodes.length === 0) return;

          const nodeRect = {
            x: node.position.x,
            y: node.position.y,
            width: node.width || 280,
            height: node.height || 200,
          };

          for (const loopNode of loopNodes) {
            const loopRect = {
              x: loopNode.position.x,
              y: loopNode.position.y,
              width: loopNode.width || 280,
              height: loopNode.height || 400,
            };

            const nodeCenterX = nodeRect.x + nodeRect.width / 2;
            const nodeCenterY = nodeRect.y + nodeRect.height / 2;

            if (
              nodeCenterX >= loopRect.x &&
              nodeCenterX <= loopRect.x + loopRect.width &&
              nodeCenterY >= loopRect.y &&
              nodeCenterY <= loopRect.y + loopRect.height
            ) {
              moveNodeIntoLoop(node.id, loopNode.id);
              message.success(`节点已移入循环体: ${loopNode.data?.name || '循环'}`);
              break;
            }
          }
        }}
        nodeTypes={nodeTypes}
        connectionMode="loose"
        fitView
        attributionPosition="bottom-left"
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'default',
          animated: false,
          style: { stroke: '#6366f1', strokeWidth: 2 },
          markerEnd: {
            type: 'arrow',
            width: 12,
            height: 12,
            color: '#6366f1',
          },
        }}
      >
        <Background color="#e5e7eb" gap={20} size={1} />
        <Controls />

        <MiniMap
          position="top-right"
          nodeColor="#3b82f6"
          nodeStrokeWidth={3}
          maskColor="rgba(240, 240, 240, 0.6)"
          style={{
            width: 150,
            height: 100,
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            margin: 12,
            left: 0,
          }}
        />

        {/* 底部工具栏 */}
        <Panel position="bottom-center" style={{ left: '45%' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
            <BottomToolbar
              onSave={handleSave}
              onLoad={handleLoad}
              onUndo={undo}
              onRedo={redo}
              onRun={handleRun}
              onDebug={handleDebug}
              onZoomIn={() => reactFlow.zoomIn()}
              onZoomOut={() => reactFlow.zoomOut()}
              onFitView={() => reactFlow.fitView()}
              onToggleTemplates={() => setIsTemplatesOpen(!isTemplatesOpen)}
              onToggleTrace={() => setIsTraceOpen(!isTraceOpen)}
              onToggleVersionManager={() => setIsVersionManagerOpen(!isVersionManagerOpen)}
              onToggleVersionCompare={() => setIsVersionCompareOpen(!isVersionCompareOpen)}
              onToggleRunHistory={() => setIsRunHistoryOpen(!isRunHistoryOpen)}
              onToggleWorkflowList={() => setIsWorkflowListOpen(!isWorkflowListOpen)}
              canUndo={canUndo}
              canRedo={canRedo}
              isRunning={isRunning}
              isSaving={isSaving}
              isDirty={dirty}
              isConnected={isConnected}
              currentWorkflowName={workflowName}
            />
            <StatusBar
              nodeCount={nodes.length}
              edgeCount={edges.length}
              selectedNode={selectedNode}
              workflowId={workflowId}
              versionId={versionId}
              isDirty={dirty}
            />
          </div>
        </Panel>
      </ReactFlow>

      {/* 节点模板弹窗 */}
      <NodeTemplates
        isOpen={isTemplatesOpen}
        onClose={() => setIsTemplatesOpen(false)}
        onSelectNode={handleSelectNodeTemplate}
      />

      {/* 节点配置抽屉 */}
      <NodeConfigDrawer
        isOpen={isConfigOpen}
        onClose={() => {
          setIsConfigOpen(false);
          selectNode(null);
        }}
      />

      {/* 试运行结果抽屉 —— 独立渲染在 ConfigDrawer 之上 */}
      <NodeTestResultDrawer />

      {/* 追踪面板 */}
      <TracePanel
        isOpen={isTraceOpen}
        onClose={() => setIsTraceOpen(false)}
      />

      {/* 版本管理 */}
      <VersionManager
        isOpen={isVersionManagerOpen}
        onClose={() => setIsVersionManagerOpen(false)}
        workflowId={workflowId}
        onSelectVersion={(version) => {
          setVersionId(version.id);
          // 加载版本定义
          api.getDefinition(version.id).then((definition) => {
            if (definition) {
              const loadedNodes = (definition.nodes || []).map((n) => ({
                id: n.id,
                type: n.type,
                position: n.position || { x: 0, y: 0 },
                width: n.width || 240,
                height: n.height || 120,
                data: {
                  ...n.config,
                  name: n.label,
                  flowNodeType: n.type,
                },
              }));
              const loadedEdges = (definition.edges || []).map((e) => ({
                id: e.id,
                source: e.source,
                target: e.target,
                sourceHandle: e.sourceHandle || `${e.source}-source`,
                targetHandle: e.targetHandle || `${e.target}-target`,
                label: e.label || '',
              }));
              setNodes(loadedNodes);
              setEdges(loadedEdges);
              markSaved();
              message.success(`已切换到版本: ${version.name || version.version}`);
            }
          }).catch((err) => {
            message.error('加载版本失败: ' + err.message);
          });
        }}
      />

      {/* 版本对比 */}
      <VersionCompare
        isOpen={isVersionCompareOpen}
        onClose={() => setIsVersionCompareOpen(false)}
        versions={versions}
      />

      {/* 运行历史 */}
      <RunHistory
        isOpen={isRunHistoryOpen}
        onClose={() => setIsRunHistoryOpen(false)}
        workflowId={workflowId}
      />

      {/* 工作流列表 */}
      <WorkflowList
        isOpen={isWorkflowListOpen}
        onClose={() => setIsWorkflowListOpen(false)}
        onSelectWorkflow={handleSelectWorkflow}
        onCreateWorkflow={handleCreateWorkflow}
      />

      {/* 运行弹窗 */}
      <RunDialog
        isOpen={isRunDialogOpen}
        onClose={() => {
          if (!isRunning) setIsRunDialogOpen(false);
        }}
        onConfirm={handleRunWithInputs}
        workflowName={workflowName}
        inputVariables={pendingRunVariables}
        isRunning={isRunning}
      />
    </div>
  );
};

// 包装组件，提供 ReactFlowProvider
const WorkflowPage = () => {
  return (
    <ReactFlowProvider>
      <WorkflowEditor />
    </ReactFlowProvider>
  );
};

export default WorkflowPage;
