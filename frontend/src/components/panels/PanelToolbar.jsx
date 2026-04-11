import React from "react";
import "./PanelToolbar.css";

/**
 * 通用面板顶栏：左侧「图标 + 标题」，右侧放按钮/操作区
 */
const PanelToolbar = ({ icon, title, children }) => {
  return (
    <div className="panel-toolbar">
      <div className="panel-toolbar-left">
        {icon && <span className="panel-toolbar-icon">{icon}</span>}
        {title && <span className="panel-toolbar-title">{title}</span>}
      </div>
      {children && <div className="panel-toolbar-right">{children}</div>}
    </div>
  );
};

PanelToolbar.defaultProps = {
  icon: null,
  title: "",
  children: null,
};

export default PanelToolbar;
