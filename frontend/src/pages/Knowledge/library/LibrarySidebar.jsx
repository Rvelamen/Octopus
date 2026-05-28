import React, { useState } from 'react';
import { Layers, Inbox, Folder, FolderOpen, ChevronRight, ChevronDown, Plus, Trash2, Hash, GitGraph } from 'lucide-react';
import { Popconfirm } from 'antd';

const CollectionTreeNode = ({ node, level, selectedId, onSelect, onDelete, onOpenGraph, expanded, toggleExpand }) => {
  const isSelected = node.id === selectedId;
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expanded.has(node.id);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 8px',
          paddingLeft: 8 + level * 16,
          cursor: 'pointer',
          borderRadius: 4,
          background: isSelected ? 'var(--accent-soft)' : 'transparent',
          color: isSelected ? 'var(--accent)' : 'var(--text)',
          fontSize: 13,
          userSelect: 'none',
        }}
        onClick={() => onSelect(node.id)}
      >
        {hasChildren ? (
          <span onClick={(e) => { e.stopPropagation(); toggleExpand(node.id); }} style={{ display: 'flex' }}>
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        ) : (
          <span style={{ width: 12 }} />
        )}

        <span style={{ color: node.color || '#1890ff', display: 'flex' }}>
          {isExpanded ? <FolderOpen size={14} /> : <Folder size={14} />}
        </span>

        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.name}
        </span>

        {node.count > 0 && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
            {node.count}
          </span>
        )}

        {onOpenGraph && node.id > 2 && (
          <span
            style={{ display: 'flex', opacity: 0.4, cursor: 'pointer' }}
            onClick={(e) => { e.stopPropagation(); onOpenGraph(node.id); }}
            title="Open in Graph"
          >
            <GitGraph size={12} />
          </span>
        )}
        {node.id > 2 && (
          <Popconfirm
            title="Delete collection?"
            description="Papers will not be deleted."
            onConfirm={(e) => { e.stopPropagation(); onDelete(node.id); }}
            okText="Delete"
            cancelText="Cancel"
            okType="danger"
          >
            <span
              style={{ display: 'flex', opacity: 0.5 }}
              onClick={(e) => e.stopPropagation()}
            >
              <Trash2 size={12} />
            </span>
          </Popconfirm>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <CollectionTreeNode
              key={child.id}
              node={child}
              level={level + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              onDelete={onDelete}
              onOpenGraph={onOpenGraph}
              expanded={expanded}
              toggleExpand={toggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const QuickAccessItem = ({ icon, label, count, isSelected, onClick }) => (
  <div
    onClick={onClick}
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '5px 8px',
      borderRadius: 4,
      cursor: 'pointer',
      background: isSelected ? 'var(--accent-soft)' : 'transparent',
      color: isSelected ? 'var(--accent)' : 'var(--text)',
      fontSize: 13,
      userSelect: 'none',
    }}
  >
    <span style={{ display: 'flex', opacity: 0.7 }}>{icon}</span>
    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {label}
    </span>
    {count !== undefined && count > 0 && (
      <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
        {count}
      </span>
    )}
  </div>
);

const LibrarySidebar = ({
  collections,
  selectedId,
  onSelect,
  onCreateCollection,
  onDeleteCollection,
  onOpenGraph,
  loading,
}) => {
  const [expanded, setExpanded] = useState(new Set([1]));

  const toggleExpand = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Separate system collections (All Items=1, Uncategorized=2) from user collections
  const systemIds = new Set([1, 2]);
  const systemCollections = collections.filter((c) => systemIds.has(c.id));
  const userCollections = collections.filter((c) => !systemIds.has(c.id));

  const allItems = systemCollections.find((c) => c.id === 1);
  const uncategorized = systemCollections.find((c) => c.id === 2);

  // All Items is conceptually "selected" when selectedId is null or 1
  const isAllItemsSelected = selectedId === null || selectedId === 1;

  // Flatten tags from all items (placeholder until we have real tag aggregation)
  const allTags = [];

  return (
    <div
      style={{
        width: 220,
        minWidth: 180,
        maxWidth: 320,
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg-elevated)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 12px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Library
        </span>
        <span
          style={{ cursor: 'pointer', display: 'flex', color: 'var(--accent)' }}
          onClick={onCreateCollection}
        >
          <Plus size={14} />
        </span>
      </div>

      {/* Quick Access */}
      <div style={{ padding: '6px 4px' }}>
        {allItems && (
          <QuickAccessItem
            icon={<Layers size={14} />}
            label={allItems.name}
            isSelected={isAllItemsSelected}
            onClick={() => onSelect(null)}
          />
        )}
        {uncategorized && (
          <QuickAccessItem
            icon={<Inbox size={14} />}
            label={uncategorized.name}
            count={uncategorized.count}
            isSelected={selectedId === 2}
            onClick={() => onSelect(2)}
          />
        )}
      </div>

      {/* Divider */}
      {userCollections.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)', margin: '0 8px' }} />
      )}

      {/* Collections Tree */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {userCollections.length > 0 && (
          <div
            style={{
              padding: '6px 12px 4px',
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
            }}
          >
            Collections
          </div>
        )}
        {userCollections.map((node) => (
          <CollectionTreeNode
            key={node.id}
            node={node}
            level={0}
            selectedId={selectedId}
            onSelect={onSelect}
            onDelete={onDeleteCollection}
            onOpenGraph={onOpenGraph}
            expanded={expanded}
            toggleExpand={toggleExpand}
          />
        ))}
      </div>

      {/* Tags section */}
      {allTags.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '8px 12px' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Tags
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
            {allTags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: 11,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: 'var(--accent-soft)',
                  color: 'var(--accent)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <Hash size={10} />
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LibrarySidebar;
