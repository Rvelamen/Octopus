import React from 'react';
import WindowDots from '@components/layout/WindowDots';

/**
 * ConfigCard 组件 - 配置卡片容器
 */
function ConfigCard({ title, children, icon = '', actions = null, showDots = true }) {
  return (
    <div className="config-card pixel-border">
      <div className="config-card-header">
        {showDots && <WindowDots />}
        <div className="card-header-left">
          <span className="card-icon">{icon}</span>
          <span className="card-title">{title}</span>
        </div>
        {actions && <div className="card-header-actions">{actions}</div>}
      </div>
      <div className="config-card-content">
        {children}
      </div>
    </div>
  );
}

export default ConfigCard;
