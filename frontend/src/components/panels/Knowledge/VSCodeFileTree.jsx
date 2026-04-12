import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  UncontrolledTreeEnvironment,
  Tree,
  StaticTreeDataProvider,
} from 'react-complex-tree';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  FileImage,
  FileJson,
  FileType,
  MoreHorizontal,
} from 'lucide-react';
import './VSCodeFileTree.css';

// 文件图标映射
const getFileIcon = (fileName, isDirectory, isExpanded) => {
  if (isDirectory) {
    return isExpanded ? <FolderOpen size={16} color="#dcb67a" /> : <Folder size={16} color="#dcb67a" />;
  }

  const ext = fileName.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
      return <FileCode size={16} color="#519aba" />;
    case 'json':
      return <FileJson size={16} color="#cbcb41" />;
    case 'md':
      return <FileText size={16} color="#519aba" />;
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
      return <FileImage size={16} color="#a074c4" />;
    case 'css':
    case 'scss':
    case 'less':
      return <FileType size={16} color="#42a5f5" />;
    default:
      return <FileText size={16} color="#7f7f7f" />;
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
    <div
      ref={menuRef}
      className="vscode-context-menu"
      style={{ left: x, top: y }}
    >
      {items.map((item, index) =>
        item.divider ? (
          <div key={index} className="vscode-context-menu-divider" />
        ) : (
          <div
            key={index}
            className={`vscode-context-menu-item ${item.danger ? 'vscode-context-menu-item-danger' : ''}`}
            onClick={() => {
              item.onClick();
              onClose();
            }}
          >
            {item.icon}
            <span>{item.label}</span>
            {item.shortcut && (
              <span className="vscode-context-menu-shortcut">{item.shortcut}</span>
            )}
          </div>
        )
      )}
    </div>
  );
};

// 将树形数据转换为 react-complex-tree 格式
const convertToTreeData = (items, treeItems) => {
  const result = {};

  const processItem = (item) => {
    const children = item.is_directory ? (treeItems[item.path] || []).map(child => child.path) : undefined;

    result[item.path] = {
      index: item.path,
      canMove: true,
      isFolder: item.is_directory,
      children: children,
      data: item,
      canRename: true,
      title: item.name,
    };

    if (item.is_directory && treeItems[item.path]) {
      treeItems[item.path].forEach(child => processItem(child));
    }
  };

  items.forEach(item => processItem(item));

  return result;
};

export default function VSCodeFileTree({
  rootPath,
  treeItems,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  onCreateFile,
  onCreateFolder,
  onRename,
  onDelete,
  onRefresh,
}) {
  const [contextMenu, setContextMenu] = useState(null);
  const [focusedItem, setFocusedItem] = useState(null);
  const treeEnvironmentRef = useRef(null);

  const rootItems = treeItems[rootPath] || [];

  // 构建树数据
  const treeData = React.useMemo(() => {
    const data = convertToTreeData(rootItems, treeItems);
    return {
      root: {
        index: 'root',
        canMove: false,
        isFolder: true,
        children: rootItems.map(item => item.path),
        data: { name: 'root', path: rootPath, is_directory: true },
        title: 'root',
      },
      ...data,
    };
  }, [rootItems, treeItems, rootPath]);

  const dataProvider = React.useMemo(
    () => new StaticTreeDataProvider(treeData),
    [treeData]
  );

  // 处理右键菜单
  const handleContextMenu = useCallback((e, item) => {
    e.preventDefault();
    e.stopPropagation();
    setFocusedItem(item);
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  // 构建右键菜单项
  const buildContextMenuItems = useCallback(() => {
    if (!focusedItem) return [];

    const isDirectory = focusedItem.is_directory;
    const items = [];

    if (isDirectory) {
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
        { divider: true }
      );
    }

    items.push(
      {
        label: 'Rename',
        icon: <MoreHorizontal size={14} />,
        shortcut: 'F2',
        onClick: () => {
          // 触发重命名 - react-complex-tree 内置支持
          treeEnvironmentRef.current?.startRenamingItem?.(focusedItem.path);
        },
      },
      {
        label: 'Delete',
        icon: <MoreHorizontal size={14} />,
        shortcut: 'Del',
        danger: true,
        onClick: () => onDelete?.(focusedItem),
      }
    );

    if (isDirectory) {
      items.push(
        { divider: true },
        {
          label: 'Refresh',
          icon: <MoreHorizontal size={14} />,
          onClick: () => onRefresh?.(focusedItem.path),
        }
      );
    }

    return items;
  }, [focusedItem, onCreateFile, onCreateFolder, onDelete, onRefresh]);

  // 自定义渲染项
  const renderItem = ({ item, title, arrow, depth, context, children }) => {
    const isSelected = selectedPath === item.data?.path;
    const isFocused = focusedItem?.path === item.data?.path;

    return (
      <div
        {...context.itemContainerWithChildrenProps}
        style={{ marginLeft: depth * 8 }}
        onContextMenu={(e) => handleContextMenu(e, item.data)}
      >
        <div
          {...context.itemContainerWithoutChildrenProps}
          {...context.interactiveElementProps}
          className={`rct-tree-item-title-container ${isSelected ? 'rct-tree-item-title-container-selected' : ''} ${isFocused ? 'rct-tree-item-title-container-focused' : ''}`}
          onClick={() => {
            onSelect?.(item.data);
            if (item.isFolder) {
              onToggle?.(item.data.path);
            }
          }}
        >
          <span className={`rct-tree-item-arrow ${context.isExpanded ? 'rct-tree-item-arrow-expanded' : ''}`}>
            {arrow}
          </span>
          <span className="rct-tree-item-file-icon">
            {getFileIcon(item.data?.name, item.isFolder, context.isExpanded)}
          </span>
          <span className="rct-tree-item-title">{title}</span>
        </div>
        {children}
      </div>
    );
  };

  // 自定义渲染箭头
  const renderItemArrow = ({ item, context }) => {
    if (!item.isFolder) return null;
    return context.isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />;
  };

  // 处理重命名完成
  const handleRenameItem = useCallback((item, newName) => {
    if (newName && newName !== item.data.name) {
      onRename?.(item.data, newName);
    }
  }, [onRename]);

  if (rootItems.length === 0) {
    return (
      <div className="vscode-file-tree vscode-file-tree-empty">
        <Folder size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
        <span>Empty directory</span>
      </div>
    );
  }

  return (
    <div className="vscode-file-tree">
      <UncontrolledTreeEnvironment
        ref={treeEnvironmentRef}
        dataProvider={dataProvider}
        getItemTitle={(item) => item.data?.name || item.title}
        viewState={{
          ['file-tree']: {
            expandedItems: Array.from(expandedPaths),
            selectedItems: selectedPath ? [selectedPath] : [],
          },
        }}
        renderItem={renderItem}
        renderItemArrow={renderItemArrow}
        renderItemTitle={({ title }) => <span>{title}</span>}
        onRenameItem={handleRenameItem}
        canRename={true}
        canDragAndDrop={true}
        canDropOnFolder={true}
        canDropOnNonFolder={false}
        canReorderItems={false}
      >
        <Tree treeId="file-tree" rootItem="root" treeLabel="File Explorer" />
      </UncontrolledTreeEnvironment>

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
