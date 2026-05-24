/**
 * WorkflowWindow — 独立的 Workflow 编辑器窗口
 * 包含标签页：Workflow / Database
 */

import React, { useState, useEffect } from 'react';
import { Tabs } from 'antd';
import { GitBranch, Database } from 'lucide-react';
import WorkflowPage from '../Workflow';
import './WorkflowWindow.css';

import DatabasePanel from './DatabasePanel';

const DatabaseContent = () => (
  <DatabasePanel />
);

export default function WorkflowWindow() {
  const [activeKey, setActiveKey] = useState('workflow');
  const [initialWorkflowId, setInitialWorkflowId] = useState(null);
  const [isReady, setIsReady] = useState(false);

  // 解析 URL hash 参数（Electron 通过 hash 传参）
  // 必须在 WorkflowPage 渲染前完成，否则 auto-load 会抢先加载第一个工作流
  useEffect(() => {
    const hash = window.location.hash;
    const queryIndex = hash.indexOf('?');
    if (queryIndex !== -1) {
      const search = hash.slice(queryIndex + 1);
      const params = new URLSearchParams(search);
      const wfId = params.get('workflowId');
      if (wfId) {
        setInitialWorkflowId(wfId);
      }
    }
    setIsReady(true);
  }, []);

  const items = [
    {
      key: 'workflow',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <GitBranch size={14} />
          Workflow
        </span>
      ),
      children: <WorkflowPage style={{ width: '100%', height: '100%' }} initialWorkflowId={initialWorkflowId} />,
    },
    {
      key: 'database',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Database size={14} />
          Database
        </span>
      ),
      children: <DatabaseContent />,
    },
  ];

  if (!isReady) {
    return (
      <div className="workflow-window" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#9ca3af', fontSize: 14 }}>Loading...</span>
      </div>
    );
  }

  return (
    <div className="workflow-window">
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        type="card"
        size="small"
        items={items}
      />
    </div>
  );
}
