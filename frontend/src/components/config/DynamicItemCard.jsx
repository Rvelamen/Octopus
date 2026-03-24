import React, { useState, useEffect } from 'react';
import WindowDots from '../WindowDots';

/**
 * DynamicItemCard 组件 - 动态配置项卡片（可折叠）
 */
function DynamicItemCard({ title, children, onDelete, itemKey, defaultExpanded = false, showDots = true }) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  useEffect(() => {
    if (defaultExpanded && !isExpanded) {
      setIsExpanded(true);
    }
  }, [defaultExpanded]);

  const handleHeaderClick = (e) => {
    // 如果点击的是按钮，不触发折叠/展开
    if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
      return;
    }
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={`dynamic-item-card ${isExpanded ? 'expanded' : ''}`}>
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
        </div>
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
      {isExpanded && (
        <div className="dynamic-item-content" onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  );
}

export default DynamicItemCard;
