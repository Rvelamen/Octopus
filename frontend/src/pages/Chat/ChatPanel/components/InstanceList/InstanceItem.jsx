import React from 'react';
import { Trash2, Archive, ArchiveRestore } from 'lucide-react';

function formatRelativeTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

function InstanceItem({
  t,
  instance,
  isSelected,
  onSelect,
  onDelete,
  onArchive,
  onUnarchive,
  mode = 'active',
}) {
  const isArchived = mode === 'archived';
  const tr = (key, fallback) => (typeof t === 'function' ? t(key) : fallback) || fallback;

  return (
    <div
      className={`instance-row ${isSelected ? 'selected' : ''} ${isArchived ? 'archived' : ''}`}
      onClick={() => onSelect(instance)}
    >
      <div className="instance-info">
        <div className="instance-name-row">
          <span className="instance-indicator"></span>
          <span className="instance-name" title={instance.instance_name}>
            {instance.instance_name}
          </span>
          {instance.is_active === true && <span className="active-badge">active</span>}
        </div>
        <div className="instance-meta">
          {isArchived ? (
            <span className="instance-time">
              {tr('chat.archivedAt', `Archived ${formatRelativeTime(instance.archived_at)}`)
                .replace('{{time}}', formatRelativeTime(instance.archived_at))}
            </span>
          ) : (
            <span className="instance-time">{formatRelativeTime(instance.created_at)}</span>
          )}
        </div>
      </div>

      {isArchived ? (
        <>
          <button
            className="restore-instance-btn"
            onClick={(e) => {
              e.stopPropagation();
              onUnarchive?.(instance);
            }}
            title={tr('chat.unarchive', 'Restore this chat')}
          >
            <ArchiveRestore size={12} />
          </button>
          <button
            className="delete-instance-btn"
            onClick={(e) => onDelete(instance.id, e)}
            title="Delete this chat"
          >
            <Trash2 size={11} />
          </button>
        </>
      ) : (
        <>
          <button
            className="archive-instance-btn"
            onClick={(e) => {
              e.stopPropagation();
              onArchive?.(instance);
            }}
            title={tr('chat.archive', 'Archive this chat')}
          >
            <Archive size={11} />
          </button>
          <button
            className="delete-instance-btn"
            onClick={(e) => onDelete(instance.id, e)}
            title="Delete this chat"
          >
            <Trash2 size={11} />
          </button>
        </>
      )}
    </div>
  );
}

export default InstanceItem;
