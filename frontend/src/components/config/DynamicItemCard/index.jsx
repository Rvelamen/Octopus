import React, { useState, useEffect } from 'react';
import WindowDots from '@components/layout/WindowDots';

/**
 * DynamicItemCard 组件 - 动态配置项卡片（可折叠）
 */
function DynamicItemCard({ 
  title, 
  children, 
  onDelete, 
  itemKey, 
  defaultExpanded = false, 
  showDots = true,
  enabled = true,
  onToggleEnabled = null,
  showEnabledSwitch = false
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [isEnabled, setIsEnabled] = useState(enabled);
  const [isToggling, setIsToggling] = useState(false);

  useEffect(() => {
    if (defaultExpanded && !isExpanded) {
      setIsExpanded(true);
    }
  }, [defaultExpanded]);

  useEffect(() => {
    setIsEnabled(enabled);
  }, [enabled]);

  const handleHeaderClick = (e) => {
    if (e.target.tagName === 'BUTTON' || e.target.closest('button') || e.target.closest('.switch-container')) {
      return;
    }
    setIsExpanded(!isExpanded);
  };

  const handleToggle = async (e) => {
    if (isToggling) return;
    
    const newEnabled = e.target.checked;
    setIsToggling(true);
    
    try {
      if (onToggleEnabled) {
        await onToggleEnabled(itemKey, newEnabled);
        setIsEnabled(newEnabled);
      }
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className={`dynamic-item-card ${isExpanded ? 'expanded' : ''} ${!isEnabled ? 'disabled' : ''}`}>
      <div className="dynamic-item-header" onClick={handleHeaderClick}>
        <div className="dynamic-item-header-left">
          <button
            type="button"
            className="expand-btn"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            title={isExpanded ? '折叠' : '展开'}
          >
            {isExpanded ? '[−]' : '[+]'}
          </button>
          <span className="dynamic-item-title">{title}</span>
          {!isEnabled && <span className="disabled-badge">DISABLED</span>}
        </div>
        <div className="dynamic-item-header-right">
          {showEnabledSwitch && onToggleEnabled && (
            <label className="switch-container" onClick={(e) => e.stopPropagation()}>
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={handleToggle}
                disabled={isToggling}
              />
              <span className="switch-slider"></span>
            </label>
          )}
          <button
            type="button"
            className="delete-btn"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(itemKey);
            }}
            title="删除"
          >
            [×]
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="dynamic-item-content" onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  );
}

export default DynamicItemCard;
