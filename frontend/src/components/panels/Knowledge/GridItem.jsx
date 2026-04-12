import React, { useState, useCallback, useRef } from 'react';
import FileIcon from './FileIcon';

export default function GridItem({
  item,
  isSelected,
  onSelect,
  onDoubleClick,
  index,
  onContextMenu,
  renaming = false,
  renameValue = '',
  onRenameChange,
  onRenameSubmit,
  onRenameStart,
  renameInputRef,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  isDragOver = false,
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const timerRef = useRef(null);

  const handleClick = useCallback((e) => {
    e.stopPropagation();
    if (renaming) return;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
      if (onDoubleClick) onDoubleClick(item);
    } else {
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        if (onSelect) onSelect(item);
      }, 220);
    }
  }, [item, onSelect, onDoubleClick, renaming]);

  const handleKeyDown = useCallback((e) => {
    if (!renaming) {
      if (e.key === 'Enter') {
        if (onDoubleClick) onDoubleClick(item);
      } else if (e.key === 'F2') {
        e.preventDefault();
        if (onRenameStart) onRenameStart();
      }
    } else {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (onRenameSubmit) onRenameSubmit();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        if (onRenameChange) onRenameChange(item.name);
      }
    }
  }, [item, onDoubleClick, onSelect, renaming, onRenameStart, onRenameSubmit, onRenameChange, item.name]);

  const handleDragStart = (e) => {
    if (renaming) {
      e.preventDefault();
      return;
    }
    setIsDragging(true);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/json', JSON.stringify({ path: item.path, name: item.name }));
    if (onDragStart) onDragStart(e, item);
  };

  const handleDragEnd = (e) => {
    setIsDragging(false);
    if (onDragEnd) onDragEnd(e, item);
  };

  const handleDragOver = (e) => {
    if (!item.is_directory) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (onDragOver) onDragOver(e, item);
  };

  const handleDrop = (e) => {
    if (!item.is_directory) return;
    e.preventDefault();
    e.stopPropagation();
    if (onDrop) onDrop(e, item);
  };

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
      }}
      onContextMenu={(e) => !renaming && onContextMenu && onContextMenu(e, item)}
      draggable={!renaming}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        padding: '14px 10px 10px',
        borderRadius: 12,
        cursor: renaming ? 'text' : 'pointer',
        userSelect: 'none',
        background: isSelected
          ? 'var(--accent-soft)'
          : isDragOver
            ? 'rgba(64, 192, 87, 0.15)'
            : isHovered
              ? 'rgba(128, 128, 128, 0.06)'
              : 'transparent',
        border: isSelected
          ? '2px solid var(--accent)'
          : isDragOver
            ? '2px dashed #40C057'
            : '2px solid transparent',
        opacity: isDragging ? 0.5 : 1,
        transition: 'all 0.15s ease',
        outline: 'none',
      }}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      data-index={index}
    >
      <FileIcon name={item.name} isDirectory={item.is_directory} size={56} />
      {renaming ? (
        <input
          ref={renameInputRef}
          value={renameValue}
          onChange={(e) => onRenameChange && onRenameChange(e.target.value)}
          onBlur={() => onRenameSubmit && onRenameSubmit()}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); onRenameSubmit && onRenameSubmit(); }
            if (e.key === 'Escape') { e.preventDefault(); onRenameChange && onRenameChange(item.name); }
          }}
          style={{
            width: '100%',
            fontSize: 12,
            textAlign: 'center',
            border: '2px solid var(--accent)',
            borderRadius: 6,
            outline: 'none',
            padding: '3px 6px',
            background: 'var(--bg)',
            color: 'var(--text)',
            fontFamily: 'inherit',
          }}
        />
      ) : (
        <span
          style={{
            fontSize: 12,
            lineHeight: 1.4,
            textAlign: 'center',
            color: isSelected ? 'var(--accent)' : 'var(--text)',
            maxWidth: '100%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            wordBreak: 'break-word',
            fontWeight: isSelected ? 600 : 400,
          }}
          title={item.name}
        >
          {item.name}
        </span>
      )}
    </div>
  );
}
