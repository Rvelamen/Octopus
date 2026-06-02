/**
 * 版本管理组件
 * 管理工作流的多个版本
 * 已接入后端 WebSocket API
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  GitBranch,
  Plus,
  Save,
  RotateCcw,
  Trash2,
  Clock,
  Check,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { useWorkflowAPI } from '../../../services/workflowApi';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

const VersionManager = ({ isOpen, onClose, workflowId, onSelectVersion }) => {
  const api = useWorkflowAPI();
  const nodes = useWorkflowStore((state) => state.nodes);
  const edges = useWorkflowStore((state) => state.edges);

  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newVersionName, setNewVersionName] = useState('');
  const [newVersionDesc, setNewVersionDesc] = useState('');
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // 从后端加载版本列表
  const loadVersions = useCallback(async () => {
    if (!workflowId) {
      setVersions([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await api.getVersionList(workflowId);
      setVersions(list);
    } catch (err) {
      setError(err.message || '加载失败');
      console.error('[VersionManager] load error:', err);
    } finally {
      setLoading(false);
    }
  }, [api, workflowId]);

  useEffect(() => {
    if (isOpen) {
      loadVersions();
    }
  }, [isOpen, loadVersions]);

  // 生成唯一ID（与 WorkflowStore 保持一致）
  const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // 递归替换对象中的节点 id 引用
  const deepReplaceNodeIds = useCallback((obj, idMap) => {
    if (typeof obj === 'string') {
      let result = obj;
      idMap.forEach((newId, oldId) => {
        result = result.split(oldId).join(newId);
      });
      return result;
    }
    if (Array.isArray(obj)) {
      return obj.map((item) => deepReplaceNodeIds(item, idMap));
    }
    if (obj && typeof obj === 'object') {
      const result = {};
      for (const [key, value] of Object.entries(obj)) {
        result[key] = deepReplaceNodeIds(value, idMap);
      }
      return result;
    }
    return obj;
  }, []);

  // 构建与 WorkflowEditor handleSave 一致的定义数据
  // 关键点：创建新版本时，必须重新生成节点 id，因为 workflow_nodes.id 是全局 PRIMARY KEY
  const buildDefinitionPayload = useCallback(() => {
    const idMap = new Map(); // oldId -> newId

    // 先生成所有新 id
    nodes.forEach((node) => {
      idMap.set(node.id, generateId());
    });

    const nodesData = nodes.map((node) => {
      const newId = idMap.get(node.id);
      let savePosition = node.position;

      // 子节点坐标转为绝对坐标（与 WorkflowEditor handleSave 保持一致）
      if (node.parentId) {
        const parentNode = nodes.find((n) => n.id === node.parentId);
        if (parentNode) {
          savePosition = {
            x: parentNode.position.x + node.position.x,
            y: parentNode.position.y + node.position.y,
          };
        }
      }

      const config = deepReplaceNodeIds(
        {
          ...node.data,
          __parentId: node.parentId ? idMap.get(node.parentId) : undefined,
        },
        idMap
      );

      return {
        id: newId,
        type: node.type,
        label: node.data?.name || node.data?.label || node.type,
        position: savePosition,
        width: node.width || 240,
        height: node.height || 120,
        config,
        timeout_seconds: node.data?.timeout_seconds || 60,
        max_retries: node.data?.max_retries || 0,
      };
    });

    const edgesData = edges
      .filter((edge) => idMap.has(edge.source) && idMap.has(edge.target))
      .map((edge) => {
        const newSourceId = idMap.get(edge.source);
        const newTargetId = idMap.get(edge.target);
        let sourceHandle = edge.sourceHandle;
        let targetHandle = edge.targetHandle;

        if (sourceHandle) {
          idMap.forEach((newId, oldId) => {
            sourceHandle = sourceHandle.split(oldId).join(newId);
          });
        } else {
          sourceHandle = `${newSourceId}-source`;
        }

        if (targetHandle) {
          idMap.forEach((newId, oldId) => {
            targetHandle = targetHandle.split(oldId).join(newId);
          });
        } else {
          targetHandle = `${newTargetId}-target`;
        }

        return {
          id: generateId(),
          source: newSourceId,
          target: newTargetId,
          label: edge.label || '',
          condition: edge.condition || '',
          sourceHandle,
          targetHandle,
        };
      });

    return { nodesData, edgesData };
  }, [nodes, edges, deepReplaceNodeIds]);

  // 保存定义后验证数据是否真正写入
  const saveAndVerifyDefinition = useCallback(async (versionId, nodesData, edgesData) => {
    await api.saveDefinition(versionId, nodesData, edgesData, []);

    // 验证：立即读取确认数据已持久化
    const definition = await api.getDefinition(versionId);
    const savedNodes = definition?.nodes || [];
    const savedEdges = definition?.edges || [];

    if (savedNodes.length === 0 && nodesData.length > 0) {
      throw new Error('定义保存验证失败：节点未成功写入');
    }
    if (savedEdges.length === 0 && edgesData.length > 0) {
      console.warn('[VersionManager] 边保存验证警告：边未成功写入');
    }

    return { savedNodes, savedEdges };
  }, [api]);

  const handleCreateVersion = async () => {
    if (!newVersionName.trim() || !workflowId) return;

    setIsSaving(true);
    try {
      // 创建新版本
      const versionNum = versions.length > 0
        ? Math.max(...versions.map((v) => v.version || 0)) + 1
        : 1;

      const newVersion = await api.createVersion(
        workflowId,
        versionNum,
        newVersionName.trim(),
        newVersionDesc.trim()
      );

      const { nodesData, edgesData } = buildDefinitionPayload();
      await saveAndVerifyDefinition(newVersion.id, nodesData, edgesData);

      await loadVersions();
      setNewVersionName('');
      setNewVersionDesc('');
      setIsCreating(false);
    } catch (err) {
      alert('创建版本失败: ' + (err.message || '未知错误'));
      console.error('[VersionManager] create error:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublishVersion = async (version) => {
    try {
      await api.publishVersion(version.id);

      // After publishing, automatically create a new draft version
      // so the user can keep editing without hitting "can only edit draft" errors.
      const versionNum = versions.length > 0
        ? Math.max(...versions.map((v) => v.version || 0)) + 1
        : 1;

      const newVersion = await api.createVersion(
        workflowId,
        versionNum,
        `${version.name || 'Version ' + version.version} (编辑中)`,
        'Auto-created draft after publish'
      );

      const { nodesData, edgesData } = buildDefinitionPayload();
      await saveAndVerifyDefinition(newVersion.id, nodesData, edgesData);

      await loadVersions();

      // Auto-switch to the new draft version so the canvas stays editable
      if (onSelectVersion) {
        onSelectVersion(newVersion);
      }
    } catch (err) {
      alert('发布失败: ' + (err.message || '未知错误'));
      console.error('[VersionManager] publish error:', err);
    }
  };

  const handleRestoreVersion = (version) => {
    if (onSelectVersion) {
      onSelectVersion(version);
      setSelectedVersion(null);
      onClose?.();
    }
  };

  const handleDeleteVersion = async (version) => {
    if (version.status === 'published') {
      alert('不能删除已发布的版本，请先取消发布');
      return;
    }
    if (!window.confirm(`确定要删除版本 "${version.name || 'Version ' + version.version}" 吗？此操作不可撤销。`)) {
      return;
    }
    try {
      await api.deleteVersion(version.id);
      await loadVersions();
      if (selectedVersion?.id === version.id) {
        setSelectedVersion(null);
      }
    } catch (err) {
      alert('删除失败: ' + (err.message || '未知错误'));
      console.error('[VersionManager] delete error:', err);
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
    });
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'published':
        return '已发布';
      case 'draft':
        return '草稿';
      case 'archived':
        return '已归档';
      default:
        return status || '未知';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'published':
        return { bg: '#f0fdf4', color: '#16a34a' };
      case 'draft':
        return { bg: '#f3f4f6', color: '#6b7280' };
      case 'archived':
        return { bg: '#fef2f2', color: '#dc2626' };
      default:
        return { bg: '#f3f4f6', color: '#6b7280' };
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
          width: '600px',
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
            <GitBranch size={20} color="#4b5563" />
            <span style={{ fontSize: '18px', fontWeight: 600 }}>
              版本管理
            </span>
            {versions.length > 0 && (
              <span
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: '#f3f4f6',
                  color: '#6b7280',
                }}
              >
                {versions.length} 个版本
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
            <X size={20} />
          </button>
        </div>

        {/* 未选择工作流提示 */}
        {!workflowId && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
            <AlertTriangle size={32} style={{ margin: '0 auto 12px' }} />
            <div style={{ fontSize: '14px' }}>请先选择或创建一个工作流</div>
          </div>
        )}

        {/* 创建新版本按钮 */}
        {workflowId && (
          <div style={{ padding: '12px 20px', borderBottom: '1px solid #f3f4f6' }}>
            {!isCreating ? (
              <button
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  width: '100%',
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px dashed #d1d5db',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#6b7280',
                  fontSize: '14px',
                }}
                onClick={() => setIsCreating(true)}
              >
                <Plus size={16} />
                创建新版本
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <input
                  placeholder="版本名称（必填）"
                  value={newVersionName}
                  onChange={(e) => setNewVersionName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '14px',
                    outline: 'none',
                  }}
                />
                <textarea
                  placeholder="版本描述（可选）"
                  value={newVersionDesc}
                  onChange={(e) => setNewVersionDesc(e.target.value)}
                  rows={2}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '14px',
                    resize: 'vertical',
                    outline: 'none',
                  }}
                />
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <button
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #e5e7eb',
                      background: 'white',
                      cursor: 'pointer',
                      fontSize: '13px',
                      color: '#6b7280',
                    }}
                    onClick={() => {
                      setIsCreating(false);
                      setNewVersionName('');
                      setNewVersionDesc('');
                    }}
                  >
                    取消
                  </button>
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
                    onClick={handleCreateVersion}
                    disabled={!newVersionName.trim() || isSaving}
                  >
                    {isSaving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
                    保存版本
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 版本列表 */}
        {workflowId && (
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
                  onClick={loadVersions}
                >
                  重试
                </button>
              </div>
            )}

            {!loading && !error && versions.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                <GitBranch size={32} style={{ margin: '0 auto 12px' }} />
                <div style={{ fontSize: '14px' }}>暂无版本记录</div>
                <div style={{ fontSize: '12px', marginTop: '4px' }}>
                  点击上方按钮创建第一个版本
                </div>
              </div>
            )}

            {!loading && !error && versions.map((version) => {
              const statusStyle = getStatusColor(version.status);
              return (
                <div
                  key={version.id}
                  style={{
                    border: `1px solid ${selectedVersion?.id === version.id ? '#93c5fd' : '#e5e7eb'}`,
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    background: selectedVersion?.id === version.id ? '#eff6ff' : 'white',
                  }}
                  onClick={() => setSelectedVersion(selectedVersion?.id === version.id ? null : version)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: '#f3f4f6',
                          color: '#4b5563',
                        }}
                      >
                        v{version.version}
                      </span>
                      <span style={{ fontSize: '14px', fontWeight: 500, color: '#1f2937' }}>
                        {version.name}
                      </span>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: statusStyle.bg,
                          color: statusStyle.color,
                        }}
                      >
                        {getStatusLabel(version.status)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {version.status === 'draft' && (
                        <button
                          style={{
                            padding: '4px',
                            borderRadius: '4px',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#22c55e',
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePublishVersion(version);
                          }}
                          title="发布版本"
                        >
                          <Check size={14} />
                        </button>
                      )}
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
                          handleRestoreVersion(version);
                        }}
                        title="加载此版本到画布"
                      >
                        <RotateCcw size={14} />
                      </button>
                      {version.status !== 'published' && (
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
                            handleDeleteVersion(version);
                          }}
                          title="删除版本"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>

                  {version.description && (
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                      {version.description}
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px', fontSize: '11px', color: '#9ca3af' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} />
                      {formatDate(version.created_at)}
                    </div>
                    {version.published_at && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Check size={12} />
                        发布于 {formatDate(version.published_at)}
                      </div>
                    )}
                  </div>

                  {/* 选中时显示操作按钮 */}
                  {selectedVersion?.id === version.id && (
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
                        onClick={() => handleRestoreVersion(version)}
                      >
                        <RotateCcw size={14} />
                        恢复此版本
                      </button>
                      {version.status === 'draft' && (
                        <button
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: '1px solid #22c55e',
                            background: '#f0fdf4',
                            cursor: 'pointer',
                            fontSize: '13px',
                            color: '#16a34a',
                          }}
                          onClick={() => handlePublishVersion(version)}
                        >
                          <Check size={14} />
                          发布
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default VersionManager;
