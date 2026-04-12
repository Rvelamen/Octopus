import React from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import FileIcon from './FileIcon';

export default function TreeNode({
  item,
  level = 0,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  treeItems,
}) {
  const isExpanded = expandedPaths.has(item.path);
  const isSelected = selectedPath === item.path;
  const children = treeItems?.[item.path] || [];
  const hasChildren = item.is_directory && children.length > 0;

  if (!item.is_directory) {
    return (
      <div>
        <div
          onClick={() => onSelect(item)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: `6px 12px 6px ${level * 16 + 8}px`,
            cursor: 'pointer',
            background: isSelected ? 'var(--accent-soft)' : 'transparent',
            color: isSelected ? 'var(--text)' : 'var(--text-2)',
            borderRadius: 4,
            margin: '2px 6px',
            transition: 'background 0.15s',
          }}
        >
          <span style={{ width: 14, flexShrink: 0 }} />
          <FileIcon name={item.name} isDirectory={false} size={16} />
          <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 13 }}>
            {item.name}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        onClick={() => onSelect(item)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: `6px 12px 6px ${level * 16 + 8}px`,
          cursor: 'pointer',
          background: isSelected ? 'var(--accent-soft)' : 'transparent',
          color: isSelected ? 'var(--text)' : 'var(--text-2)',
          borderRadius: 4,
          margin: '2px 6px',
          transition: 'background 0.15s',
        }}
      >
        <span
          style={{ width: 14, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(item.path);
          }}
        >
          {hasChildren ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span style={{ width: 14 }} />
          )}
        </span>
        <FileIcon name={item.name} isDirectory={true} size={16} />
        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 13 }}>
          {item.name}
        </span>
      </div>
      {isExpanded && hasChildren && (
        <div>
          {children.map((child) => (
            <TreeNode
              key={child.path}
              item={child}
              level={level + 1}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onSelect={onSelect}
              onToggle={onToggle}
              treeItems={treeItems}
            />
          ))}
        </div>
      )}
    </div>
  );
}
