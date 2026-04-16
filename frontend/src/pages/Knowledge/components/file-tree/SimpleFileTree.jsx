import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  ChevronRight,
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  FileImage,
  FileJson,
  FileType,
} from 'lucide-react';
import './SimpleFileTree.css';

// 兼容两种数据格式：item.is_directory 或 item.type === 'directory'
const isDirectory = (item) => item?.is_directory || item?.type === 'directory';

// 文件图标映射 - 使用主题色 CSS 变量
const getFileIcon = (fileName, isDirectoryFlag, isExpanded) => {
  if (isDirectoryFlag) {
    return isExpanded ? (
      <FolderOpen size={16} className="simple-tree-icon-folder" />
    ) : (
      <Folder size={16} className="simple-tree-icon-folder" />
    );
  }

  const ext = fileName.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
      return <FileCode size={16} className="simple-tree-icon-code" />;
    case 'json':
      return <FileJson size={16} className="simple-tree-icon-json" />;
    case 'md':
      return <FileText size={16} className="simple-tree-icon-md" />;
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
      return <FileImage size={16} className="simple-tree-icon-image" />;
    case 'css':
    case 'scss':
    case 'less':
      return <FileType size={16} className="simple-tree-icon-style" />;
    default:
      return <FileText size={16} className="simple-tree-icon-default" />;
  }
};

// 右键菜单组件
const ContextMenu = ({ x, y, items, onClose }) => {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div ref={menuRef} className="simple-context-menu" style={{ left: x, top: y }}>
      {items.map((item, index) =>
        item.divider ? (
          <div key={index} className="simple-context-menu-divider" />
        ) : (
          <div
            key={index}
            className={`simple-context-menu-item ${item.danger ? 'danger' : ''}`}
            onClick={() => {
              item.onClick();
              onClose();
            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </div>
        )
      )}
    </div>
  );
};

// 单个树节点
const TreeNode = ({
  item,
  treeItems,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  onContextMenu,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  level = 0,
}) => {
  const isExpanded = expandedPaths.has(item.path);
  const isSelected = selectedPath === item.path;
  const children = treeItems?.[item.path] || [];
  const hasChildren = isDirectory(item) && children.length > 0;
  const [isDragOver, setIsDragOver] = useState(false);

  const handleClick = (e) => {
    // 如果点击的是箭头，不触发选择
    if (e.target.closest('.simple-tree-arrow')) return;
    onSelect(item);
    // 目录项点击整行也触发 toggle（展开/折叠）
    if (isDirectory(item)) {
      onToggle(item.path);
    }
  };

  const handleArrowClick = (e) => {
    e.stopPropagation();
    onToggle(item.path);
  };

  const handleContextMenu = (e) => {
    e.preventDefault();
    e.stopPropagation();
    onContextMenu(e, item);
  };

  // 拖拽处理
  const handleDragStart = (e) => {
    e.dataTransfer.setData('text/plain', item.path);
    e.dataTransfer.effectAllowed = 'move';
    onDragStart?.(item);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isDirectory(item)) {
      e.dataTransfer.dropEffect = 'move';
      setIsDragOver(true);
      onDragOver?.(item);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    onDragLeave?.(item);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const draggedPath = e.dataTransfer.getData('text/plain');
    if (draggedPath && draggedPath !== item.path) {
      onDrop?.(draggedPath, item);
    }
  };

  return (
    <div>
      <div
        className={`simple-tree-item ${isSelected ? 'selected' : ''} ${isDragOver ? 'drag-over' : ''}`}
        style={{ paddingLeft: `${8 + level * 12}px` }}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        draggable
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <span
          className={`simple-tree-arrow ${isExpanded ? 'expanded' : ''}`}
          onClick={isDirectory(item) ? handleArrowClick : undefined}
          style={{ visibility: isDirectory(item) ? 'visible' : 'hidden' }}
        >
          <ChevronRight size={14} />
        </span>
        <span className="simple-tree-icon">
          {getFileIcon(item.name, isDirectory(item), isExpanded)}
        </span>
        <span className="simple-tree-name">{item.name}</span>
      </div>
      {isExpanded && hasChildren && (
        <div className="simple-tree-children">
          {children.map((child) => (
            <TreeNode
              key={child.path}
              item={child}
              treeItems={treeItems}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onSelect={onSelect}
              onToggle={onToggle}
              onContextMenu={onContextMenu}
              onDragStart={onDragStart}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default function SimpleFileTree({
  rootPath,
  treeItems,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  onCreateFile,
  onCreateFolder,
  onUploadFile,
  onRename,
  onDelete,
  onRefresh,
  onMove,
}) {
  const [contextMenu, setContextMenu] = useState(null);
  const [focusedItem, setFocusedItem] = useState(null);
  const [draggedItem, setDraggedItem] = useState(null);

  const rootItems = treeItems[rootPath] || [];

  // 构建 root 目录项 - 用于右键菜单
  const rootItem = {
    path: rootPath,
    name: rootPath.split('/').pop() || rootPath,
    is_directory: true,
  };

  // 处理右键菜单
  const handleContextMenu = useCallback((e, item) => {
    e.preventDefault();
    e.stopPropagation();
    setFocusedItem(item);
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  // 处理容器右键菜单（当点击空白区域时，显示 root 目录菜单）
  const handleContainerContextMenu = useCallback((e) => {
    // 如果点击的是文件项，不处理（让文件项自己的 onContextMenu 处理）
    if (e.target.closest('.simple-tree-item')) return;
    
    e.preventDefault();
    e.stopPropagation();
    setFocusedItem(rootItem);
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, [rootItem]);

  // 拖拽处理
  const handleDragStart = useCallback((item) => {
    setDraggedItem(item);
  }, []);

  const handleDragOver = useCallback((item) => {
    // 可以在这里添加视觉反馈逻辑
  }, []);

  const handleDragLeave = useCallback((item) => {
    // 可以在这里移除视觉反馈逻辑
  }, []);

  const handleDrop = useCallback((draggedPath, targetItem) => {
    if (!isDirectory(targetItem)) return;
    if (draggedPath === targetItem.path) return;
    
    // 检查是否拖入自己的子目录
    if (draggedPath.startsWith(targetItem.path + '/')) return;

    onMove?.(draggedPath, targetItem.path);
    setDraggedItem(null);
  }, [onMove]);

  // 构建右键菜单项
  const buildContextMenuItems = useCallback(() => {
    if (!focusedItem) return [];

    const isDir = isDirectory(focusedItem);
    const items = [];

    if (isDir) {
      items.push(
        {
          label: 'New File',
          icon: <FileText size={14} />,
          onClick: () => onCreateFile?.(focusedItem.path),
        },
        {
          label: 'New Folder',
          icon: <Folder size={14} />,
          onClick: () => onCreateFolder?.(focusedItem.path),
        },
        {
          label: 'Upload File',
          icon: <FileText size={14} />,
          onClick: () => onUploadFile?.(focusedItem.path),
        },
        { divider: true }
      );
    }

    items.push(
      {
        label: 'Rename',
        icon: <FileText size={14} />,
        onClick: () => onRename?.(focusedItem),
      },
      {
        label: 'Delete',
        icon: <FileText size={14} />,
        danger: true,
        onClick: () => onDelete?.(focusedItem),
      }
    );

    if (isDir) {
      items.push(
        { divider: true },
        {
          label: 'Refresh',
          icon: <FileText size={14} />,
          onClick: () => onRefresh?.(focusedItem.path),
        }
      );
    }

    return items;
  }, [focusedItem, onCreateFile, onCreateFolder, onUploadFile, onRename, onDelete, onRefresh]);

  const isRootExpanded = expandedPaths.has(rootPath);
  const [isRootDragOver, setIsRootDragOver] = useState(false);

  // 根目录拖拽处理
  const handleRootDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // 检查是否拖拽的是文件项
    const draggedPath = e.dataTransfer.getData('text/plain') || draggedItem?.path;
    if (draggedPath) {
      // 获取被拖拽文件的父目录
      const draggedParent = draggedPath.substring(0, draggedPath.lastIndexOf('/'));
      // 只有当文件不是已经在根目录时，才允许拖拽到根目录
      if (draggedParent !== rootPath) {
        e.dataTransfer.dropEffect = 'move';
        setIsRootDragOver(true);
      }
    }
  }, [draggedItem, rootPath]);

  const handleRootDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsRootDragOver(false);
  }, []);

  const handleRootDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsRootDragOver(false);
    const draggedPath = e.dataTransfer.getData('text/plain');
    if (draggedPath) {
      const draggedParent = draggedPath.substring(0, draggedPath.lastIndexOf('/'));
      // 只有当文件不是已经在根目录时，才执行移动
      if (draggedParent !== rootPath) {
        onMove?.(draggedPath, rootPath);
      }
    }
    setDraggedItem(null);
  }, [onMove, rootPath]);

  return (
    <div 
      className={`simple-file-tree ${isRootDragOver ? 'root-drag-over' : ''}`}
      onContextMenu={handleContainerContextMenu}
      onDragOver={handleRootDragOver}
      onDragLeave={handleRootDragLeave}
      onDrop={handleRootDrop}
    >
      {rootItems.length === 0 ? (
        <div className="simple-tree-empty">Empty directory</div>
      ) : (
        rootItems.map((item) => (
          <TreeNode
            key={item.path}
            item={item}
            treeItems={treeItems}
            selectedPath={selectedPath}
            expandedPaths={expandedPaths}
            onSelect={onSelect}
            onToggle={onToggle}
            onContextMenu={handleContextMenu}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          />
        ))
      )}

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={buildContextMenuItems()}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
