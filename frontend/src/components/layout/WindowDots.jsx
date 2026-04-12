import React from 'react';

/**
 * WindowDots 组件 - 窗口控制按钮（红绿灯样式）
 * 用于窗口头部显示关闭、最小化、最大化按钮的视觉效果
 */
function WindowDots() {
  return (
    <div className="window-dots">
      <span className="dot red"></span>
      <span className="dot yellow"></span>
      <span className="dot green"></span>
    </div>
  );
}

export default WindowDots;
