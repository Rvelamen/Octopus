/**
 * WorkflowHub 侧边导航
 */
import React from 'react';
import {
  GitBranch,
  History,
  LayoutTemplate,
  Database,
  Settings,
} from 'lucide-react';

const NAV_ITEMS = [
  { key: 'workflows', label: '流程列表', icon: GitBranch },
  { key: 'history', label: '运行历史', icon: History },
  { key: 'templates', label: '模板市场', icon: LayoutTemplate },
  { key: 'database', label: '数据表', icon: Database },
];

const SidebarNav = ({ activeKey, onChange }) => {
  return (
    <nav className="wf-hub-sidebar">
      <div className="wf-hub-sidebar-brand">
        <GitBranch size={20} />
        <span>Workflow</span>
      </div>

      <div className="wf-hub-sidebar-nav">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`wf-hub-nav-item ${activeKey === key ? 'active' : ''}`}
            onClick={() => onChange(key)}
          >
            <Icon size={18} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      <div className="wf-hub-sidebar-footer">
        <button className="wf-hub-nav-item">
          <Settings size={18} />
          <span>设置</span>
        </button>
      </div>
    </nav>
  );
};

export default SidebarNav;
