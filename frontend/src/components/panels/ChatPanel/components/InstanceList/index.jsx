import React, { useRef } from 'react';
import { RefreshCw, Plus } from 'lucide-react';
import WindowDots from '../../../../WindowDots';
import InstanceItem from './InstanceItem';
import './InstanceList.css';

function InstanceList({
  instances,
  selectedInstance,
  loading,
  initialLoading,
  error,
  hasMore,
  isLoadingMore,
  sendWSMessage,
  onSelect,
  onDelete,
  onCreateNew,
  onRefresh,
  isCreatingNew,
  onScrollEnd
}) {
  const instanceListRef = useRef(null);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    if (scrollHeight - scrollTop - clientHeight < 50 && hasMore && !isLoadingMore && !loading) {
      if (onScrollEnd) {
        onScrollEnd();
      }
    }
  };

  return (
    <div className="chat-sidebar">
      <div className="window-header">
        <WindowDots />
        <span className="window-title">CHATS</span>
        <button
          className="refresh-btn"
          onClick={onRefresh}
          disabled={loading || !sendWSMessage}
          title={!sendWSMessage ? 'WebSocket not connected' : 'Refresh'}
        >
          <RefreshCw size={10} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="new-chat-section">
        <button
          className={`new-chat-btn ${isCreatingNew ? 'active' : ''}`}
          onClick={onCreateNew}
        >
          <Plus size={12} />
          <span>NEW CHAT</span>
        </button>
      </div>

      <div 
        className="chat-instance-list" 
        ref={instanceListRef}
        onScroll={handleScroll}
      >
        {initialLoading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <div className="loading-text">Loading chats...</div>
          </div>
        )}
        {error && !initialLoading && (
          <div className="empty-state-small" style={{ color: 'var(--error)', fontSize: '11px' }}>
            Error: {error}
          </div>
        )}
        {!sendWSMessage && !initialLoading && (
          <div className="empty-state-small" style={{ color: 'var(--warning)', fontSize: '11px' }}>
            WebSocket not connected
          </div>
        )}
        {instances.length === 0 && !error && sendWSMessage && !initialLoading && (
          <div className="empty-state-small">
            No chats found
          </div>
        )}

        {instances.map((instance) => (
          <InstanceItem
            key={instance.id}
            instance={instance}
            isSelected={selectedInstance?.id === instance.id}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ))}

        {isLoadingMore && (
          <div className="loading-more">
            <div className="loading-spinner-small"></div>
            <span>Loading more...</span>
          </div>
        )}

        {!hasMore && instances.length > 0 && !initialLoading && (
          <div className="no-more-data">
            No more chats
          </div>
        )}
      </div>
    </div>
  );
}

export default InstanceList;
