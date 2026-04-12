import React from 'react';
import { Bot } from 'lucide-react';
import { useDistillTasks } from '../../contexts/DistillTaskContext';
import TaskMenu from './TaskMenu';

export default function TaskIndicator({ onViewTaskDetail }) {
  const { isMenuOpen, setIsMenuOpen, activeTaskCount } = useDistillTasks();

  const handleClick = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const handleCloseMenu = () => {
    setIsMenuOpen(false);
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          borderRadius: 6,
          border: '1px solid var(--border)',
          background: isMenuOpen ? 'var(--accent-soft)' : 'var(--surface)',
          color: activeTaskCount > 0 ? 'var(--accent)' : 'var(--text-2)',
          fontSize: 12,
          cursor: 'pointer',
          transition: 'all 0.15s',
          WebkitAppRegion: 'no-drag',
        }}
        title="Distill Tasks"
      >
        <Bot size={16} />
        {activeTaskCount > 0 && (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minWidth: 18,
              height: 18,
              padding: '0 5px',
              borderRadius: 9,
              background: 'var(--accent)',
              color: 'var(--text-invert)',
              fontSize: 10,
              fontWeight: 600,
            }}
          >
            {activeTaskCount > 99 ? '99+' : activeTaskCount}
          </span>
        )}
      </button>

      <TaskMenu onClose={handleCloseMenu} onViewTaskDetail={onViewTaskDetail} />
    </div>
  );
}
