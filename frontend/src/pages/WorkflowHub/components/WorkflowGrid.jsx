/**
 * WorkflowHub — 工作流卡片网格（管理视图）
 * 替代原来弹窗式的 WorkflowList
 */
import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  Search,
  Plus,
  Edit3,
  Copy,
  Trash2,
  Clock,
  CheckCircle,
  XCircle,
  Play,
  Loader2,
  GitBranch,
  MoreHorizontal,
} from 'lucide-react';
import { useWorkflowAPI } from '../../../workflow/services/workflowApi';
import ConfirmDialog from '../../../workflow/components/common/ConfirmDialog';

const STATUS_META = {
  published: { label: '已发布', color: '#22c55e', bg: '#f0fdf4' },
  active: { label: '活跃', color: '#22c55e', bg: '#f0fdf4' },
  draft: { label: '草稿', color: '#6b7280', bg: '#f3f4f6' },
  inactive: { label: '未激活', color: '#6b7280', bg: '#f3f4f6' },
  archived: { label: '已归档', color: '#ef4444', bg: '#fef2f2' },
  error: { label: '错误', color: '#ef4444', bg: '#fef2f2' },
};

const formatDate = (dateString) => {
  if (!dateString) return '从未';
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const WorkflowGrid = ({ onEditWorkflow, onCreateWorkflow }) => {
  const api = useWorkflowAPI();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, workflowId: null });
  const [actionMenuId, setActionMenuId] = useState(null);

  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    try {
      const params = filterStatus !== 'all' ? { status: filterStatus } : {};
      const list = await api.getWorkflowList(params);
      setWorkflows(list);
    } catch (err) {
      console.error('[WorkflowGrid] load error:', err);
    } finally {
      setLoading(false);
    }
  }, [api, filterStatus]);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  const filtered = useMemo(() => {
    let result = [...workflows];
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      result = result.filter((w) =>
        w.name?.toLowerCase().includes(q) ||
        w.description?.toLowerCase().includes(q)
      );
    }
    return result.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
  }, [workflows, searchTerm]);

  const handleDelete = async (workflowId) => {
    if (confirmDialog.isOpen && confirmDialog.workflowId === workflowId) {
      try {
        await api.deleteWorkflow(workflowId);
        setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
        setConfirmDialog({ isOpen: false, workflowId: null });
      } catch (err) {
        alert('删除失败: ' + (err.message || '未知错误'));
      }
    } else {
      setConfirmDialog({ isOpen: true, workflowId });
    }
  };

  const handleDuplicate = async (workflow) => {
    try {
      const newWf = await api.saveWorkflow({
        name: `${workflow.name} (副本)`,
        description: workflow.description || '',
        category: workflow.category || 'general',
      });
      const versions = await api.getVersionList(workflow.id);
      if (versions.length > 0) {
        const definition = await api.getDefinition(versions[0].id);
        const newVersions = await api.getVersionList(newWf.id);
        if (newVersions.length > 0 && definition) {
          await api.saveDefinition(
            newVersions[0].id,
            definition.nodes || [],
            definition.edges || [],
            definition.variables || []
          );
        }
      }
      await loadWorkflows();
    } catch (err) {
      alert('复制失败: ' + (err.message || '未知错误'));
    }
  };

  return (
    <div className="wf-hub-panel">
      {/* 顶部工具栏 */}
      <div className="wf-hub-panel-header">
        <div className="wf-hub-panel-title">
          <GitBranch size={20} />
          <h2>流程列表</h2>
          <span className="wf-hub-count">{filtered.length} 个工作流</span>
        </div>
        <button className="wf-hub-btn-primary" onClick={onCreateWorkflow}>
          <Plus size={16} />
          新建工作流
        </button>
      </div>

      {/* 搜索与筛选 */}
      <div className="wf-hub-toolbar">
        <div className="wf-hub-search">
          <Search size={16} color="#9ca3af" />
          <input
            placeholder="搜索工作流名称..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="wf-hub-filters">
          {[
            { value: 'all', label: '全部' },
            { value: 'draft', label: '草稿' },
            { value: 'published', label: '已发布' },
            { value: 'archived', label: '已归档' },
          ].map((opt) => (
            <button
              key={opt.value}
              className={filterStatus === opt.value ? 'active' : ''}
              onClick={() => setFilterStatus(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 网格内容 */}
      <div className="wf-hub-grid-scroll">
        {loading && (
          <div className="wf-hub-empty">
            <Loader2 size={32} className="wf-hub-spin" />
            <p>加载中...</p>
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="wf-hub-empty">
            <GitBranch size={48} color="#d1d5db" />
            <p>{workflows.length === 0 ? '暂无工作流，创建一个吧' : '没有符合条件的工作流'}</p>
            {workflows.length === 0 && (
              <button className="wf-hub-btn-primary" onClick={onCreateWorkflow}>
                <Plus size={16} />
                新建工作流
              </button>
            )}
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="wf-hub-grid">
            {filtered.map((wf) => {
              const status = STATUS_META[wf.status] || STATUS_META.draft;
              return (
                <div key={wf.id} className="wf-hub-card">
                  <div className="wf-hub-card-header">
                    <div className="wf-hub-card-title-row">
                      <h3 className="wf-hub-card-name">{wf.name}</h3>
                      <span
                        className="wf-hub-card-status"
                        style={{ color: status.color, background: status.bg }}
                      >
                        {status.label}
                      </span>
                    </div>
                    {wf.description && (
                      <p className="wf-hub-card-desc">{wf.description}</p>
                    )}
                  </div>

                  <div className="wf-hub-card-meta">
                    <span><Clock size={12} /> 更新 {formatDate(wf.updated_at)}</span>
                    <span>v{wf.current_version || 1}</span>
                    {wf.category && <span>{wf.category}</span>}
                  </div>

                  <div className="wf-hub-card-actions">
                    <button
                      className="wf-hub-card-btn primary"
                      onClick={() => onEditWorkflow?.(wf.id)}
                      title="编辑"
                    >
                      <Edit3 size={14} />
                      编辑
                    </button>
                    <button
                      className="wf-hub-card-btn"
                      onClick={() => handleDuplicate(wf)}
                      title="复制"
                    >
                      <Copy size={14} />
                    </button>
                    <div className="wf-hub-card-menu-wrap">
                      <button
                        className="wf-hub-card-btn"
                        onClick={() => setActionMenuId(actionMenuId === wf.id ? null : wf.id)}
                      >
                        <MoreHorizontal size={14} />
                      </button>
                      {actionMenuId === wf.id && (
                        <>
                          <div
                            className="wf-hub-menu-overlay"
                            onClick={() => setActionMenuId(null)}
                          />
                          <div className="wf-hub-card-menu">
                            <button onClick={() => { setActionMenuId(null); handleDuplicate(wf); }}>
                              <Copy size={14} /> 复制
                            </button>
                            <button
                              className="danger"
                              onClick={() => { setActionMenuId(null); handleDelete(wf.id); }}
                            >
                              <Trash2 size={14} /> 删除
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog({ isOpen: false, workflowId: null })}
        onConfirm={() => handleDelete(confirmDialog.workflowId)}
        title="删除工作流"
        message="确定要删除这个工作流吗？此操作不可恢复。"
        confirmText="删除"
        cancelText="取消"
        variant="danger"
      />
    </div>
  );
};

export default WorkflowGrid;
