import React from 'react';
import { Bot, ChevronDown, ListTodo } from 'lucide-react';
import DistillTaskDetail from './DistillTaskDetail';

export default function DistillTaskList({
  tasks,
  expandedTaskId,
  taskDetailResult,
  onExpandTask,
  sendWSMessage,
}) {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
      <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600 }}>Distill Tasks</h3>
      {tasks.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-2)' }}>
          <ListTodo size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
          <p>No distill tasks yet. Select a document and click "Distill with AI" to start.</p>
        </div>
      ) : (
        tasks.map((task) => (
          <div
            key={task.id}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 8,
              marginBottom: 8,
              background: 'var(--surface)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '10px 14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: expandedTaskId === task.id ? 'var(--surface-2)' : 'transparent',
              }}
              onClick={() => onExpandTask(task.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                <Bot
                  size={16}
                  style={{
                    color:
                      task.status === 'completed'
                        ? 'var(--accent-green)'
                        : task.status === 'running'
                        ? 'var(--accent)'
                        : 'var(--accent-red)',
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {task.source_path.split('/').pop()}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                {task.status === 'running' && (
                  <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
                    {task.message} ({Math.round(task.progress * 100)}%)
                  </span>
                )}
                <span
                  style={{
                    fontSize: 11,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background:
                      task.status === 'completed'
                        ? 'var(--accent-green-soft)'
                        : task.status === 'running'
                        ? 'var(--accent-soft)'
                        : 'var(--accent-red-soft)',
                    color:
                      task.status === 'completed'
                        ? 'var(--accent-green)'
                        : task.status === 'running'
                        ? 'var(--accent)'
                        : 'var(--accent-red)',
                  }}
                >
                  {task.status}
                </span>
                <ChevronDown
                  size={14}
                  style={{
                    color: 'var(--text-2)',
                    transform: expandedTaskId === task.id ? 'rotate(180deg)' : 'none',
                    transition: 'transform 0.2s',
                  }}
                />
              </div>
            </div>

            {task.status === 'running' && (
              <div style={{ height: 3, background: 'var(--border)' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${task.progress * 100}%`,
                    background: 'var(--accent)',
                    transition: 'width 0.3s',
                  }}
                />
              </div>
            )}

            {expandedTaskId === task.id && (
              <div style={{ borderTop: '1px solid var(--border)', padding: 16 }}>
                {taskDetailResult ? (
                  <DistillTaskDetail result={taskDetailResult} sendWSMessage={sendWSMessage} />
                ) : (
                  <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-2)' }}>
                    Loading...
                  </div>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
