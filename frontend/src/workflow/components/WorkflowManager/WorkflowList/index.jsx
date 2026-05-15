/**
 * 工作流列表组件
 * 显示所有工作流的列表，支持搜索、筛选、排序
 * 已接入后端 WebSocket API
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  X,
  Search,
  Plus,
  Edit3,
  Copy,
  Trash2,
  Clock,
  Play,
  CheckCircle,
  XCircle,
  ArrowUpDown,
  FolderOpen,
  Loader2,
} from 'lucide-react';
import { useWorkflowAPI } from '../../../services/workflowApi';
import ConfirmDialog from '../../common/ConfirmDialog';

const WorkflowList = ({ isOpen, onClose, onSelectWorkflow, onCreateWorkflow }) => {
  const api = useWorkflowAPI();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filterStatus, setFilterStatus] = useState('all');
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, workflowId: null });

  // 从后端加载工作流列表
  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filterStatus !== 'all') {
        params.status = filterStatus;
      }
      const list = await api.getWorkflowList(params);
      setWorkflows(list);
    } catch (err) {
      setError(err.message || '加载失败');
      console.error('[WorkflowList] load error:', err);
    } finally {
      setLoading(false);
    }
  }, [api, filterStatus]);

  useEffect(() => {
    if (isOpen) {
      loadWorkflows();
    }
  }, [isOpen, loadWorkflows]);

  const handleDeleteWorkflow = async (workflowId) => {
    if (confirmDialog.isOpen && confirmDialog.workflowId === workflowId) {
      try {
        await api.deleteWorkflow(workflowId);
        setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
        if (selectedWorkflow?.id === workflowId) {
          setSelectedWorkflow(null);
        }
        setConfirmDialog({ isOpen: false, workflowId: null });
      } catch (err) {
        alert('删除失败: ' + (err.message || '未知错误'));
        console.error('[WorkflowList] delete error:', err);
      }
    } else {
      setConfirmDialog({ isOpen: true, workflowId });
    }
  };

  const handleDuplicateWorkflow = async (workflow) => {
    try {
      const newWf = await api.saveWorkflow({
        name: `${workflow.name} (副本)`,
        description: workflow.description || '',
        category: workflow.category || 'general',
      });
      // 复制定义：先获取原工作流的版本定义
      const versions = await api.getVersionList(workflow.id);
      if (versions.length > 0) {
        const latestVersion = versions[0];
        const definition = await api.getDefinition(latestVersion.id);
        if (definition) {
          // 获取新工作流的初始版本
          const newVersions = await api.getVersionList(newWf.id);
          if (newVersions.length > 0) {
            await api.saveDefinition(
              newVersions[0].id,
              definition.nodes || [],
              definition.edges || [],
              definition.variables || []
            );
          }
        }
      }
      await loadWorkflows();
    } catch (err) {
      alert('复制失败: ' + (err.message || '未知错误'));
      console.error('[WorkflowList] duplicate error:', err);
    }
  };

  const filteredWorkflows = useMemo(() => {
    let result = [...workflows];

    // 搜索
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (w) =>
          w.name?.toLowerCase().includes(term) ||
          (w.description && w.description.toLowerCase().includes(term))
      );
    }

    // 排序
    result.sort((a, b) => {
      const aVal = a[sortBy] || '';
      const bVal = b[sortBy] || '';
      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      }
      return aVal < bVal ? 1 : -1;
    });

    return result;
  }, [workflows, searchTerm, sortBy, sortOrder]);

  const formatDate = (dateString) => {
    if (!dateString) return '从未';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;

    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'published':
      case 'active':
        return <CheckCircle size={14} color="#22c55e" />;
      case 'draft':
      case 'inactive':
        return <XCircle size={14} color="#9ca3af" />;
      case 'archived':
      case 'error':
        return <XCircle size={14} color="#ef4444" />;
      default:
        return <Clock size={14} color="#9ca3af" />;
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'published':
      case 'active':
        return '活跃';
      case 'draft':
      case 'inactive':
        return '草稿';
      case 'archived':
        return '已归档';
      case 'error':
        return '错误';
      default:
        return status || '未知';
    }
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
          width: '800px',
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
            <FolderOpen size={20} color="#4b5563" />
            <span style={{ fontSize: '18px', fontWeight: 600 }}>
              工作流列表
            </span>
            {workflows.length > 0 && (
              <span
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: '#f3f4f6',
                  color: '#6b7280',
                }}
              >
                {workflows.length} 个工作流
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: '#3b82f6',
                color: 'white',
                cursor: 'pointer',
                fontSize: '13px',
              }}
              onClick={() => {
                onCreateWorkflow?.();
                onClose();
              }}
            >
              <Plus size={14} />
              新建工作流
            </button>
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

        {/* 搜索和筛选 */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid #f3f4f6',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              flex: 1,
              gap: '8px',
              padding: '6px 12px',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              background: '#f9fafb',
            }}
          >
            <Search size={14} color="#9ca3af" />
            <input
              placeholder="搜索工作流..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                flex: 1,
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: '13px',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            {[
              { value: 'all', label: '全部' },
              { value: 'draft', label: '草稿' },
              { value: 'published', label: '已发布' },
              { value: 'archived', label: '已归档' },
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

          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              background: 'white',
              cursor: 'pointer',
              fontSize: '13px',
              color: '#6b7280',
            }}
            onClick={() => {
              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
            }}
          >
            <ArrowUpDown size={14} />
            {sortOrder === 'asc' ? '升序' : '降序'}
          </button>
        </div>

        {/* 工作流列表 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
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
                onClick={loadWorkflows}
              >
                重试
              </button>
            </div>
          )}

          {!loading && !error && filteredWorkflows.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
              <FolderOpen size={32} style={{ margin: '0 auto 12px' }} />
              <div style={{ fontSize: '14px' }}>
                {workflows.length === 0 ? '暂无工作流' : '没有符合条件的工作流'}
              </div>
              {workflows.length === 0 && (
                <button
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    margin: '12px auto 0',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: 'none',
                    background: '#3b82f6',
                    color: 'white',
                    cursor: 'pointer',
                    fontSize: '13px',
                  }}
                  onClick={() => {
                    onCreateWorkflow?.();
                    onClose();
                  }}
                >
                  <Plus size={14} />
                  创建第一个工作流
                </button>
              )}
            </div>
          )}

          {!loading && !error && filteredWorkflows.map((workflow) => (
            <div
              key={workflow.id}
              style={{
                border: `1px solid ${selectedWorkflow?.id === workflow.id ? '#93c5fd' : '#e5e7eb'}`,
                borderRadius: '8px',
                padding: '12px',
                cursor: 'pointer',
                background: selectedWorkflow?.id === workflow.id ? '#eff6ff' : 'white',
              }}
              onClick={() => {
                setSelectedWorkflow(
                  selectedWorkflow?.id === workflow.id ? null : workflow
                );
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {getStatusIcon(workflow.status)}
                  <span
                    style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      color: '#1f2937',
                    }}
                  >
                    {workflow.name}
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background:
                        workflow.status === 'published' || workflow.status === 'active'
                          ? '#f0fdf4'
                          : workflow.status === 'archived' || workflow.status === 'error'
                          ? '#fef2f2'
                          : '#f3f4f6',
                      color:
                        workflow.status === 'published' || workflow.status === 'active'
                          ? '#16a34a'
                          : workflow.status === 'archived' || workflow.status === 'error'
                          ? '#dc2626'
                          : '#6b7280',
                    }}
                  >
                    {getStatusLabel(workflow.status)}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    style={{
                      padding: '4px',
                      borderRadius: '4px',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      color: '#3b82f6',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectWorkflow?.(workflow);
                      onClose();
                    }}
                    title="打开"
                  >
                    <Edit3 size={14} />
                  </button>
                  <button
                    style={{
                      padding: '4px',
                      borderRadius: '4px',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      color: '#6b7280',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDuplicateWorkflow(workflow);
                    }}
                    title="复制"
                  >
                    <Copy size={14} />
                  </button>
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
                      handleDeleteWorkflow(workflow.id);
                    }}
                    title="删除"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {workflow.description && (
                <div
                  style={{
                    fontSize: '12px',
                    color: '#6b7280',
                    marginTop: '4px',
                  }}
                >
                  {workflow.description}
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginTop: '8px',
                  fontSize: '11px',
                  color: '#9ca3af',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={12} />
                  更新: {formatDate(workflow.updated_at)}
                </div>
                <div>版本: v{workflow.current_version || 1}</div>
                {workflow.category && (
                  <div>分类: {workflow.category}</div>
                )}
              </div>

              {/* 选中时显示操作按钮 */}
              {selectedWorkflow?.id === workflow.id && (
                <div
                  style={{
                    marginTop: '12px',
                    padding: '12px',
                    background: '#f9fafb',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    display: 'flex',
                    gap: '8px',
                  }}
                >
                  <button
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      background: '#3b82f6',
                      color: 'white',
                      cursor: 'pointer',
                      fontSize: '13px',
                    }}
                    onClick={() => {
                      onSelectWorkflow?.(workflow);
                      onClose();
                    }}
                  >
                    <Edit3 size={14} />
                    编辑工作流
                  </button>
                  <button
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #e5e7eb',
                      background: 'white',
                      cursor: 'pointer',
                      fontSize: '13px',
                      color: '#6b7280',
                    }}
                    onClick={() => handleDuplicateWorkflow(workflow)}
                  >
                    <Copy size={14} />
                    复制
                  </button>
                  <button
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #fca5a5',
                      background: '#fef2f2',
                      cursor: 'pointer',
                      fontSize: '13px',
                      color: '#ef4444',
                    }}
                    onClick={() => handleDeleteWorkflow(workflow.id)}
                  >
                    <Trash2 size={14} />
                    删除
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 删除确认弹窗 */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog({ isOpen: false, workflowId: null })}
        onConfirm={() => handleDeleteWorkflow(confirmDialog.workflowId)}
        title="删除工作流"
        message="确定要删除这个工作流吗？此操作不可恢复。"
        confirmText="删除"
        cancelText="取消"
        variant="danger"
      />
    </div>
  );
};

export default WorkflowList;
