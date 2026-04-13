import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Bot, Check, X, Loader2, Trash2, ExternalLink, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { useDistillTasks } from '@contexts/DistillTaskContext';

const statusConfig = {
  queued: { color: 'var(--text-2)', icon: Loader2, spin: true },
  running: { color: 'var(--accent)', icon: Loader2, spin: true },
  completed: { color: 'var(--accent-green)', icon: Check, spin: false },
  failed: { color: 'var(--accent-red)', icon: X, spin: false },
};

function TaskItem({ task, onViewDetail }) {
  const config = statusConfig[task.status] || statusConfig.queued;
  const Icon = config.icon;
  const fileName = task.sourceFile?.split('/').pop() || 'Unknown';

  // 格式化时间显示
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      onClick={() => onViewDetail?.(task)}
      style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        opacity: task.status === 'completed' || task.status === 'failed' ? 0.8 : 1,
        cursor: onViewDetail ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon
          size={14}
          style={{
            color: config.color,
            animation: config.spin ? 'spin 1s linear infinite' : 'none',
          }}
        />
        <span
          style={{
            fontSize: 12,
            fontWeight: 500,
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={fileName}
        >
          {fileName}
        </span>
        <span
          style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background:
              task.status === 'completed'
                ? 'var(--accent-green-soft)'
                : task.status === 'failed'
                ? 'var(--accent-red-soft)'
                : task.status === 'running'
                ? 'var(--accent-soft)'
                : 'var(--surface-2)',
            color:
              task.status === 'completed'
                ? 'var(--accent-green)'
                : task.status === 'failed'
                ? 'var(--accent-red)'
                : task.status === 'running'
                ? 'var(--accent)'
                : 'var(--text-2)',
            textTransform: 'uppercase',
          }}
        >
          {task.status}
        </span>
      </div>

      {(task.status === 'running' || task.status === 'queued') && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--text-2)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={task.message}
          >
            {task.message}
          </div>
          <div
            style={{
              width: '100%',
              height: 3,
              background: 'var(--border)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${task.progress * 100}%`,
                height: '100%',
                background: 'var(--accent)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default function TaskMenu({
  onClose,
  onViewTaskDetail,
  pagination,
  onPrevPage,
  onNextPage,
  currentPage,
  totalPages,
  hasPrevPage,
  hasNextPage,
  onRefresh,
}) {
  const { tasks, removeCompletedTasks, clearAllTasks, isMenuOpen } = useDistillTasks();
  const menuRef = useRef(null);
  const listRef = useRef(null);
  const [isSyncing, setIsSyncing] = useState(false);

  // 活跃任务：running 或 queued
  const activeTasks = tasks.filter((t) => t.status === 'running' || t.status === 'queued');

  // 已完成的任务：completed 或 failed
  const completedTasks = tasks.filter((t) => t.status === 'completed' || t.status === 'failed');

  const handleSync = async () => {
    setIsSyncing(true);
    await onRefresh();
    setTimeout(() => setIsSyncing(false), 500);
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose?.();
      }
    };

    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen, onClose]);

  // 计算显示范围
  const startItem = pagination.total > 0 ? pagination.offset + 1 : 0;
  const endItem = Math.min(pagination.offset + pagination.limit, pagination.total);

  if (!isMenuOpen) return null;

  return (
    <div
      ref={menuRef}
      style={{
        position: 'absolute',
        top: '100%',
        right: 0,
        marginTop: 8,
        width: 320,
        maxHeight: '60vh',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--surface-2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={16} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: 13, fontWeight: 600 }}>Distill Tasks</span>
          {tasks.length > 0 && (
            <span
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 10,
                background: 'var(--accent)',
                color: 'var(--text-invert)',
              }}
            >
              {tasks.length}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onClick={handleSync}
            disabled={isSyncing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 8px',
              borderRadius: 4,
              border: 'none',
              background: 'transparent',
              color: 'var(--text-2)',
              fontSize: 11,
              cursor: 'pointer',
              opacity: isSyncing ? 0.5 : 1,
            }}
            title="Sync with backend"
          >
            <RefreshCw size={12} style={{ animation: isSyncing ? 'spin 0.5s linear infinite' : 'none' }} />
          </button>
          {completedTasks.length > 0 && (
            <button
              onClick={removeCompletedTasks}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 4,
                border: 'none',
                background: 'transparent',
                color: 'var(--text-2)',
                fontSize: 11,
                cursor: 'pointer',
              }}
              title="Clear completed"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Task List */}
      <div
        ref={listRef}
        style={{ flex: 1, overflow: 'auto', maxHeight: '50vh' }}
      >
        {tasks.length === 0 ? (
          <div
            style={{
              padding: 32,
              textAlign: 'center',
              color: 'var(--text-2)',
              fontSize: 12,
            }}
          >
            <Bot size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <p>No distill tasks</p>
            <p style={{ fontSize: 11, marginTop: 4 }}>Select a document and click "Distill with AI" to start</p>
          </div>
        ) : (
          <>
            {/* Active Tasks */}
            {activeTasks.length > 0 && (
              <div>
                <div
                  style={{
                    padding: '8px 12px',
                    fontSize: 10,
                    fontWeight: 600,
                    color: 'var(--text-2)',
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    background: 'var(--bg)',
                  }}
                >
                  In Progress ({activeTasks.length})
                </div>
                {activeTasks.map((task) => (
                  <TaskItem key={task.id} task={task} onViewDetail={onViewTaskDetail} />
                ))}
              </div>
            )}

            {/* Completed Tasks */}
            {completedTasks.length > 0 && (
              <div>
                <div
                  style={{
                    padding: '8px 12px',
                    fontSize: 10,
                    fontWeight: 600,
                    color: 'var(--text-2)',
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    background: 'var(--bg)',
                  }}
                >
                  Completed ({completedTasks.length})
                </div>
                {completedTasks.map((task) => (
                  <TaskItem key={task.id} task={task} onViewDetail={onViewTaskDetail} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      {tasks.length > 0 && (
        <div
          style={{
            padding: '10px 12px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            background: 'var(--surface-2)',
          }}
        >
          {/* 分页控件 */}
          {pagination.total > 0 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
              }}
            >
              <button
                onClick={onPrevPage}
                disabled={!hasPrevPage}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  color: hasPrevPage ? 'var(--text)' : 'var(--text-3)',
                  fontSize: 11,
                  cursor: hasPrevPage ? 'pointer' : 'not-allowed',
                  opacity: hasPrevPage ? 1 : 0.5,
                }}
              >
                <ChevronLeft size={12} />
                Prev
              </button>

              <span
                style={{
                  fontSize: 11,
                  color: 'var(--text-2)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span style={{ fontWeight: 600, color: 'var(--text)' }}>
                  {currentPage}
                </span>
                <span>/</span>
                <span>{totalPages}</span>
                <span style={{ marginLeft: 4 }}>
                  ({startItem}-{endItem} of {pagination.total})
                </span>
              </span>

              <button
                onClick={onNextPage}
                disabled={!hasNextPage}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  color: hasNextPage ? 'var(--text)' : 'var(--text-3)',
                  fontSize: 11,
                  cursor: hasNextPage ? 'pointer' : 'not-allowed',
                  opacity: hasNextPage ? 1 : 0.5,
                }}
              >
                Next
                <ChevronRight size={12} />
              </button>
            </div>
          )}

          {/* 状态信息和清除按钮 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
              {activeTasks.length > 0
                ? `${activeTasks.length} task${activeTasks.length > 1 ? 's' : ''} running`
                : completedTasks.length > 0
                ? `${completedTasks.length} completed`
                : 'No tasks'}
            </span>
            <button
              onClick={() => {
                clearAllTasks();
                onClose?.();
              }}
              style={{
                fontSize: 11,
                color: 'var(--accent-red)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: '4px 8px',
              }}
            >
              Clear All
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
