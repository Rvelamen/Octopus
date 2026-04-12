import React from 'react';
import TreeNode from './TreeNode';

export default function KnowledgeTree({
  rootPath,
  treeItems,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
}) {
  const rootItems = treeItems[rootPath] || [];

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
      {rootItems.length === 0 && (
        <div style={{ padding: 16, color: 'var(--text-2)', fontSize: 12, textAlign: 'center' }}>
          Empty directory
        </div>
      )}
      {rootItems.map((item) => (
        <TreeNode
          key={item.path}
          item={item}
          level={0}
          selectedPath={selectedPath}
          expandedPaths={expandedPaths}
          onSelect={onSelect}
          onToggle={onToggle}
          treeItems={treeItems}
        />
      ))}
    </div>
  );
}
