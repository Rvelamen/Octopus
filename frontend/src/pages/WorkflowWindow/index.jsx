/**
 * WorkflowWindow — 独立的 Workflow 窗口
 * 采用 Hub → Editor 的两层架构：
 *   - Hub:   WorkflowHub 管理首页（列表/历史/模板/数据表）
 *   - Editor: Workflow 画布编辑器
 */

import React, { useState, useEffect, useCallback } from 'react';
import WorkflowHub from '../WorkflowHub';
import WorkflowPage from '../Workflow';
import './WorkflowWindow.css';

export default function WorkflowWindow() {
  const [view, setView] = useState('hub'); // 'hub' | 'editor'
  const [editorParams, setEditorParams] = useState(null);
  const [isReady, setIsReady] = useState(false);

  // 解析 URL hash 参数（Electron 通过 hash 传参）
  useEffect(() => {
    const hash = window.location.hash;
    const queryIndex = hash.indexOf('?');
    if (queryIndex !== -1) {
      const search = hash.slice(queryIndex + 1);
      const params = new URLSearchParams(search);
      const wfId = params.get('workflowId');
      if (wfId) {
        setEditorParams({ workflowId: wfId });
        setView('editor');
      }
    }
    setIsReady(true);
  }, []);

  const handleEnterEditor = useCallback((params) => {
    setEditorParams(params);
    setView('editor');
  }, []);

  const handleBackToHub = useCallback(() => {
    setView('hub');
    setEditorParams(null);
  }, []);

  if (!isReady) {
    return (
      <div className="workflow-window" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#9ca3af', fontSize: 14 }}>Loading...</span>
      </div>
    );
  }

  return (
    <div className="workflow-window">
      {view === 'hub' && (
        <WorkflowHub onEnterEditor={handleEnterEditor} />
      )}
      {view === 'editor' && (
        <WorkflowPage
          style={{ width: '100%', height: '100%' }}
          initialWorkflowId={editorParams?.workflowId}
          initialVersionId={editorParams?.versionId}
          initialWorkflowName={editorParams?.workflowName}
          onBack={handleBackToHub}
        />
      )}
    </div>
  );
}
