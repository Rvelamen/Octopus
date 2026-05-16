import React, { useState, useRef, useCallback, useEffect } from 'react';
import { CheckCircle, Edit2, Clock, Loader2 } from 'lucide-react';
import { message } from 'antd';
import { useWorkflowStore } from '../../../workflow/hooks/useWorkflowStore';
import { useWorkflowAPI } from '../../../workflow/services/workflowApi';
import './index.css';

const WorkflowTabTitle = () => {
  const workflowName = useWorkflowStore((state) => state.workflowName);
  const updatedAt = useWorkflowStore((state) => state.updatedAt);
  const dirty = useWorkflowStore((state) => state.dirty);
  const workflowId = useWorkflowStore((state) => state.workflowId);
  const updateWorkflowNameInStore = useWorkflowStore((state) => state.updateWorkflowName);

  const api = useWorkflowAPI();

  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(workflowName || '');
  const [isUpdating, setIsUpdating] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (workflowName && !isEditing) {
      setEditValue(workflowName);
    }
  }, [workflowName, isEditing]);

  const formatUpdateTime = useCallback((timestamp) => {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;

    const pad = (n) => n.toString().padStart(2, '0');
    return `${date.getMonth() + 1}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }, []);

  const handleDoubleClick = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!workflowName || isEditing || isUpdating || !workflowId) return;

    setIsEditing(true);
    setEditValue(workflowName);

    setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 50);
  }, [workflowName, isEditing, isUpdating, workflowId]);

  const handleSave = useCallback(async () => {
    const trimmedValue = editValue.trim();

    if (!trimmedValue) {
      message.warning('工作流名称不能为空');
      setEditValue(workflowName || '');
      setIsEditing(false);
      return;
    }

    if (trimmedValue === workflowName) {
      setIsEditing(false);
      return;
    }

    try {
      setIsUpdating(true);
      await api.updateWorkflow(workflowId, { name: trimmedValue });
      updateWorkflowNameInStore(trimmedValue);
      message.success('工作流名称已更新');
      setIsEditing(false);
    } catch (error) {
      message.error('更新失败');
      setEditValue(workflowName || '');
    } finally {
      setIsUpdating(false);
    }
  }, [editValue, workflowName, workflowId, api, updateWorkflowNameInStore]);

  const handleCancel = useCallback(() => {
    setEditValue(workflowName || '');
    setIsEditing(false);
  }, [workflowName]);

  const handleKeyDown = useCallback((e) => {
    e.stopPropagation();
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  }, [handleSave, handleCancel]);

  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (isEditing) handleSave();
    }, 150);
  }, [handleSave, isEditing]);

  if (!workflowName) return null;

  return (
    <div className="wf-title-bar">
      {/* 可拖拽区域 - 名称显示 */}
      {!isEditing ? (
        <span
          className="wf-title-bar__name"
          onDoubleClick={handleDoubleClick}
          title={`${workflowName}\n双击编辑`}
        >
          {workflowName}
        </span>
      ) : (
        <input
          ref={inputRef}
          className="wf-title-bar__input"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          disabled={isUpdating}
          placeholder="工作流名称"
          maxLength={30}
        />
      )}

      {/* 右侧信息区 - no-drag */}
      <div className="wf-title-bar__actions" style={{ WebkitAppRegion: 'no-drag' }}>
        {/* 状态指示 */}
        {dirty ? (
          <span className="wf-title-bar__dot wf-title-bar__dot--warn" title="未保存的更改" />
        ) : (
          <CheckCircle size={13} className="wf-title-bar__icon" color="#22c55e" title="已保存" />
        )}

        {/* 加载中 */}
        {isUpdating && <Loader2 size={13} className="wf-title-bar__icon wf-title-bar__spin" />}

        {/* 时间 */}
        {updatedAt && !isEditing && (
          <span className="wf-title-bar__time">
            <Clock size={11} />
            {formatUpdateTime(updatedAt)}
          </span>
        )}

        {/* 编辑按钮 */}
        {!isEditing && (
          <button
            className="wf-title-bar__btn"
            onClick={handleDoubleClick}
            title="重命名"
          >
            <Edit2 size={12} />
          </button>
        )}
      </div>
    </div>
  );
};

export default WorkflowTabTitle;