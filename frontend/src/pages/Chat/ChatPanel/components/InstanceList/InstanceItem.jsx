import React from 'react';
import { Trash2 } from 'lucide-react';

function InstanceItem({ instance, isSelected, onSelect, onDelete }) {
  const formatRelativeTime = (timestamp) => {
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
  };

  return (
    <div
      className={`instance-row ${isSelected ? 'selected' : ''}`}
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
          <span className="instance-time">{formatRelativeTime(instance.created_at)}</span>
        </div>
      </div>
      <button
        className="delete-instance-btn"
        onClick={(e) => onDelete(instance.id, e)}
        title="Delete this chat"
      >
        <Trash2 size={11} />
      </button>
    </div>
  );
}

export default InstanceItem;
