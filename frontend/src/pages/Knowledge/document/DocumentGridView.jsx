import React, { useEffect, useCallback, useState, useRef } from 'react';
import {
  FolderOpen,
  Grid3X3,
  List,
  ChevronRight,
  FolderPlus,
  Upload,
  Pencil,
  Trash2,
  X,
  Move,
  Folder,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { message } from 'antd';
import GridItem from './GridItem';

const ITEM_MIN_WIDTH = 110;
const ITEM_MAX_WIDTH = 160;
const GRID_GAP = 12;

function BreadcrumbNav({ currentPath, rootPath, onNavigate }) {
  const relPath = currentPath.startsWith(rootPath)
    ? currentPath.slice(rootPath.length).replace(/^\/+|\/+$/g, '')
    : currentPath.replace(/^\/+|\/+$/g, '');
  const parts = relPath.split('/').filter(Boolean);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        padding: '6px 14px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)',
        flexShrink: 0,
        overflowX: 'auto',
        fontSize: 12,
      }}
    >
      <FolderOpen size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
      <button
        onClick={() => onNavigate(rootPath)}
        style={{
          padding: '2px 6px',
          borderRadius: 4,
          border: 'none',
          background: !relPath ? 'var(--accent-soft)' : 'transparent',
          color: !relPath ? 'var(--accent)' : 'var(--text-2)',
          cursor: 'pointer',
          fontSize: 12,
          whiteSpace: 'nowrap',
          fontWeight: !relPath ? 600 : 400,
        }}
      >
        {rootPath}
      </button>
      {parts.map((part, i) => {
        const fullPath = parts.slice(0, i + 1).join('/');
        const isLast = i === parts.length - 1;
        return (
          <React.Fragment key={i}>
            <ChevronRight size={11} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
            <button
              onClick={() => onNavigate(`${rootPath}/${fullPath}`)}
              style={{
                padding: '2px 6px',
                borderRadius: 4,
                border: 'none',
                background: isLast ? 'var(--accent-soft)' : 'transparent',
                color: isLast ? 'var(--accent)' : 'var(--text-2)',
                cursor: 'pointer',
                fontSize: 12,
                whiteSpace: 'nowrap',
                fontWeight: isLast ? 600 : 400,
              }}
            >
              {part}
            </button>
          </React.Fragment>
        );
      })}
    </div>
  );
}

function ContextMenu({ x, y, item, onClose, onNewFolder, onUpload, onRename, onDelete, onMove }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) onClose();
    };
    const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [onClose]);

  useEffect(() => {
    const menu = menuRef.current;
    if (menu) {
      const rect = menu.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      if (rect.right > vw) menu.style.left = `${x - rect.width}px`;
      if (rect.bottom > vh) menu.style.top = `${y - rect.height}px`;
    }
  }, [x, y]);

  return (
    <div
      ref={menuRef}
      style={{
        position: 'fixed',
        left: x,
        top: y,
        zIndex: 10000,
        minWidth: 160,
        padding: '4px',
        borderRadius: 8,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.15), 0 2px 6px rgba(0,0,0,0.08)',
        fontSize: 12,
      }}
    >
      {!item && (
        <>
          <MenuItem onClick={() => { onNewFolder(); onClose(); }}>
            <FolderPlus size={14} />
            <span>New Folder</span>
          </MenuItem>
          <MenuItem onClick={() => { onUpload(); onClose(); }}>
            <Upload size={14} />
            <span>Upload File</span>
          </MenuItem>
          <div style={{ height: 1, margin: '4px 6px', background: 'var(--border)' }} />
        </>
      )}
      {item && (
        <>
          <MenuItem onClick={() => { onMove(item); onClose(); }}>
            <Move size={14} />
            <span>Move to...</span>
          </MenuItem>
          <MenuItem onClick={() => { onRename(item); onClose(); }}>
            <Pencil size={14} />
            <span>Rename</span>
          </MenuItem>
          <MenuItem onClick={() => { onDelete(item); onClose(); }} danger>
            <Trash2 size={14} />
            <span>Delete</span>
          </MenuItem>
        </>
      )}
    </div>
  );
}

const menuItemStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  width: '100%',
  padding: '8px 12px',
  borderRadius: 6,
  border: 'none',
  background: 'transparent',
  color: 'var(--text)',
  cursor: 'pointer',
  fontSize: 13,
  transition: 'all 0.15s ease',
};

const MenuItem = ({ children, onClick, danger = false }) => {
  const [isHovered, setIsHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        ...menuItemStyle,
        background: isHovered ? 'var(--accent-soft)' : 'transparent',
        color: danger ? (isHovered ? '#FF5252' : '#FF6B6B') : (isHovered ? 'var(--accent)' : 'var(--text)'),
        transform: isHovered ? 'translateX(2px)' : 'translateX(0)',
      }}
    >
      {children}
    </button>
  );
};

function MoveDialog({ visible, item, currentPath, rootPath, treeItems, onClose, onMove, onNavigate }) {
  const [selectedPath, setSelectedPath] = useState(currentPath);
  const [expandedPaths, setExpandedPaths] = useState(new Set([rootPath]));

  useEffect(() => {
    if (visible) {
      setSelectedPath(currentPath);
    }
  }, [visible, currentPath]);

  if (!visible || !item) return null;

  const getAllDirectories = (path) => {
    const dirs = treeItems[path]?.filter(i => i.is_directory) || [];
    return dirs;
  };

  const handleToggle = (path) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderTree = (path, level = 0) => {
    const dirs = getAllDirectories(path);
    const isExpanded = expandedPaths.has(path);
    const isSelected = selectedPath === path;
    const isCurrentDir = path === currentPath;
    const isItemSelf = path === item.path;
    // 禁止移动到自身，但允许移动到父目录（包括根目录）
    const isDisabled = isItemSelf;

    return (
      <div key={path}>
        <button
          onClick={() => setSelectedPath(path)}
          disabled={isDisabled}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            width: '100%',
            padding: '6px 10px',
            paddingLeft: `${10 + level * 16}px`,
            border: 'none',
            background: isSelected ? 'var(--accent-soft)' : 'transparent',
            color: isDisabled ? 'var(--text-3)' : isSelected ? 'var(--accent)' : 'var(--text)',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            fontSize: 12,
            textAlign: 'left',
            borderRadius: 4,
            opacity: isDisabled ? 0.5 : 1,
          }}
        >
          {dirs.length > 0 && (
            <span
              onClick={(e) => { e.stopPropagation(); handleToggle(path); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                cursor: 'pointer',
                padding: '2px',
              }}
            >
              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </span>
          )}
          {dirs.length === 0 && <span style={{ width: 16 }} />}
          <Folder size={14} style={{ color: isSelected ? 'var(--accent)' : '#FFBF2B' }} />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {path === rootPath ? 'Root' : path.split('/').pop()}
          </span>
          {isCurrentDir && <span style={{ fontSize: 10, color: 'var(--text-3)' }}>(current)</span>}
          {isItemSelf && <span style={{ fontSize: 10, color: 'var(--text-3)' }}>(self)</span>}
        </button>
        {isExpanded && dirs.map(dir => renderTree(dir.path, level + 1))}
      </div>
    );
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 10001,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 360,
          maxHeight: '70vh',
          background: 'var(--surface)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>
            Move "{item.name}"
          </h3>
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-2)' }}>
            Select destination folder
          </p>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
          {renderTree(rootPath)}
        </div>

        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'transparent',
              color: 'var(--text)',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => onMove(selectedPath)}
            disabled={selectedPath === currentPath || selectedPath === item.path}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: 'var(--accent)',
              color: 'var(--text-invert)',
              cursor: selectedPath === currentPath || selectedPath === item.path ? 'not-allowed' : 'pointer',
              fontSize: 13,
              opacity: selectedPath === currentPath || selectedPath === item.path ? 0.5 : 1,
            }}
          >
            Move
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DocumentGridView({
  items,
  currentPath,
  rootPath,
  selectedItem,
  loadDirectory,
  onSelect,
  onNavigate,
  onFileOpen,
  onCreateFolder,
  onUploadFile,
  onRenameFile,
  onDeleteFile,
  treeItems,
}) {
  const [viewMode, setViewMode] = useState('grid');
  const [containerWidth, setContainerWidth] = useState(800);
  const [contextMenu, setContextMenu] = useState(null);
  const [renamingItem, setRenamingItem] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [dragOverItem, setDragOverItem] = useState(null);
  const [moveDialogItem, setMoveDialogItem] = useState(null);
  const renameInputRef = useRef(null);

  const handleResize = useCallback((entries) => {
    for (const entry of entries) {
      setContainerWidth(entry.contentRect.width);
    }
  }, []);

  useEffect(() => {
    const observer = new ResizeObserver(handleResize);
    const el = document.getElementById('doc-grid-container');
    if (el) observer.observe(el);
    return () => observer.disconnect();
  }, [handleResize]);

  useEffect(() => {
    const handler = () => setContextMenu(null);
    window.addEventListener('scroll', handler, true);
    return () => window.removeEventListener('scroll', handler, true);
  }, []);

  useEffect(() => {
    if (renamingItem && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingItem]);

  const columns = Math.max(
    3,
    Math.floor((containerWidth + GRID_GAP) / (ITEM_MIN_WIDTH + GRID_GAP))
  );

  const itemWidth = Math.min(
    ITEM_MAX_WIDTH,
    Math.floor((containerWidth - GRID_GAP * (columns - 1)) / columns)
  );

  const handleDoubleClick = useCallback(
    (item) => {
      if (item.is_directory) {
        onNavigate(item.path);
        loadDirectory(item.path);
      } else {
        if (onFileOpen) onFileOpen(item);
      }
    },
    [onNavigate, loadDirectory, onFileOpen]
  );

  const handleContextMenu = useCallback((e, item) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, item: item || null });
  }, []);

  const sortedItems = [...items].sort((a, b) => {
    if (a.is_directory !== b.is_directory) {
      return a.is_directory ? -1 : 1;
    }
    return a.name.localeCompare(b.name);
  });

  const handleRenameSubmit = useCallback(async () => {
    if (!renamingItem || !renameValue.trim()) return;
    const newName = renameValue.trim();
    if (newName === renamingItem.name) {
      setRenamingItem(null);
      return;
    }
    if (onRenameFile) await onRenameFile(renamingItem, newName);
    setRenamingItem(null);
    loadDirectory(currentPath);
  }, [renamingItem, renameValue, onRenameFile, loadDirectory, currentPath]);

  const handleDragStart = useCallback((e, item) => {
    // 拖拽开始
  }, []);

  const handleDragEnd = useCallback((e, item) => {
    setDragOverItem(null);
  }, []);

  const handleDragOver = useCallback((e, item) => {
    if (item.is_directory) {
      setDragOverItem(item.path);
    }
  }, []);

  const handleDrop = useCallback(async (e, targetItem) => {
    setDragOverItem(null);
    if (!targetItem.is_directory) return;

    try {
      const data = e.dataTransfer.getData('application/json');
      if (!data) return;
      const sourceItem = JSON.parse(data);

      if (sourceItem.path === targetItem.path) return;
      if (sourceItem.path.startsWith(targetItem.path + '/')) return;

      const fileName = sourceItem.path.split('/').pop();
      const newPath = `${targetItem.path}/${fileName}`;

      if (onRenameFile) {
        await onRenameFile({ path: sourceItem.path }, fileName, targetItem.path);
        loadDirectory(currentPath);
        message.success(`Moved to ${targetItem.name}`);
      }
    } catch (err) {
      console.error('Drop failed:', err);
    }
  }, [onRenameFile, loadDirectory, currentPath]);

  const handleMove = useCallback(async (targetPath) => {
    if (!moveDialogItem || targetPath === currentPath) {
      setMoveDialogItem(null);
      return;
    }
    const fileName = moveDialogItem.path.split('/').pop();
    try {
      await onRenameFile({ path: moveDialogItem.path }, fileName, targetPath);
      await loadDirectory(currentPath);
      message.success(`Moved to ${targetPath.split('/').pop() || 'Root'}`);
      setMoveDialogItem(null);
    } catch (err) {
      message.error('Failed to move: ' + (err.message || String(err)));
      setMoveDialogItem(null);
    }
  }, [moveDialogItem, currentPath, onRenameFile, loadDirectory]);

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden' }}
      onContextMenu={(e) => handleContextMenu(e, null)}
    >
      <BreadcrumbNav currentPath={currentPath} rootPath={rootPath} onNavigate={(path) => {
        onNavigate(path);
        loadDirectory(path);
      }} />

      <div
        id="doc-grid-container"
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: '10px 16px',
        }}
      >
        {sortedItems.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-3)',
              gap: 10,
              fontSize: 12,
            }}
          >
            <FolderOpen size={36} style={{ opacity: 0.25 }} />
            <span>Empty folder</span>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button
                onClick={() => onCreateFolder && onCreateFolder()}
                style={{
                  padding: '6px 14px',
                  borderRadius: 6,
                  border: '1.5px dashed var(--border)',
                  background: 'transparent',
                  color: 'var(--text-2)',
                  cursor: 'pointer',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                <FolderPlus size={13} /> New Folder
              </button>
              <button
                onClick={() => onUploadFile && onUploadFile()}
                style={{
                  padding: '6px 14px',
                  borderRadius: 6,
                  border: '1.5px dashed var(--border)',
                  background: 'transparent',
                  color: 'var(--text-2)',
                  cursor: 'pointer',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                <Upload size={13} /> Upload
              </button>
            </div>
          </div>
        ) : viewMode === 'grid' ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${columns}, ${itemWidth}px)`,
              gap: `${GRID_GAP}px ${GRID_GAP}px`,
              justifyContent: 'start',
            }}
          >
            {sortedItems.map((item, idx) => (
              <GridItem
                key={item.path}
                item={item}
                index={idx}
                isSelected={selectedItem?.path === item.path}
                onSelect={onSelect}
                onDoubleClick={handleDoubleClick}
                onContextMenu={handleContextMenu}
                renaming={renamingItem?.path === item.path}
                renameValue={renamingItem?.path === item.path ? renameValue : ''}
                onRenameChange={setRenameValue}
                onRenameSubmit={handleRenameSubmit}
                onRenameStart={() => {
                  setRenamingItem(item);
                  setRenameValue(item.name);
                }}
                renameInputRef={renameInputRef}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                isDragOver={dragOverItem === item.path}
              />
            ))}
          </div>
        ) : (
          <div>
            {sortedItems.map((item, idx) => (
              <div
                key={item.path}
                onContextMenu={(e) => handleContextMenu(e, item)}
                onClick={() => onSelect(item)}
                onDoubleClick={() => handleDoubleClick(item)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '7px 12px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: selectedItem?.path === item.path ? 'var(--accent-soft)' : 'transparent',
                  border: selectedItem?.path === item.path ? '1.5px solid var(--accent)' : '1.5px solid transparent',
                  transition: 'all 0.12s ease',
                }}
              >
                <img
                  src={`data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23868E96' stroke-width='1.5'><path d='M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z'/><polyline points='13 2 13 9 20 9'/></svg>`}
                  alt=""
                  style={{ width: 18, height: 18, flexShrink: 0 }}
                />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                  <span style={{ fontSize: 12, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.meta?.title || item.name}
                  </span>
                  {item.meta?.source && (
                    <span style={{ fontSize: 10, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {new URL(item.meta.source).hostname}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                  {item.size != null ? formatSize(item.size) : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          item={contextMenu.item}
          onClose={() => setContextMenu(null)}
          onNewFolder={() => onCreateFolder && onCreateFolder()}
          onUpload={() => onUploadFile && onUploadFile()}
          onRename={(item) => {
            setRenamingItem(item);
            setRenameValue(item.name);
          }}
          onDelete={(item) => onDeleteFile && onDeleteFile(item)}
          onMove={(item) => setMoveDialogItem(item)}
        />
      )}

      <MoveDialog
        visible={!!moveDialogItem}
        item={moveDialogItem}
        currentPath={currentPath}
        rootPath={rootPath}
        treeItems={treeItems}
        onClose={() => setMoveDialogItem(null)}
        onMove={handleMove}
        onNavigate={onNavigate}
      />
    </div>
  );
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
