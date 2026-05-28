/**
 * WorkflowHub — 工作流管理首页
 * 替代原来直接打开编辑器的入口，提供：
 *   - 流程列表（卡片网格管理视图）
 *   - 运行历史（跨工作流全局视图）
 *   - 模板市场
 *   - 数据表管理
 *
 * 点击编辑后通过 onEnterEditor 回调进入编辑器。
 */

import React, { useState, useCallback, useEffect } from 'react';
import SidebarNav from './components/SidebarNav';
import WorkflowGrid from './components/WorkflowGrid';
import QuickStart from './components/QuickStart';
import StatsCards from './components/StatsCards';
import RunHistory from '../../workflow/components/WorkflowManager/RunHistory';
import DatabasePanel from '../WorkflowWindow/DatabasePanel';
import PromptDialog from '../../workflow/components/common/PromptDialog';
import { useWorkflowAPI } from '../../workflow/services/workflowApi';
import { WORKFLOW_TEMPLATES } from '../../workflow/templates';
import './WorkflowHub.css';

const WorkflowHub = ({ onEnterEditor }) => {
  const [activeNav, setActiveNav] = useState('workflows');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [recentWorkflows, setRecentWorkflows] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const api = useWorkflowAPI();

  // 加载最近编辑的工作流和运行记录（用于 QuickStart 和统计展示）
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getWorkflowList(), api.getRunList({ limit: 100 })]).then(
      ([list, runs]) => {
        if (!cancelled) {
          setRecentWorkflows(list.slice(0, 3));
          setRecentRuns(runs);
        }
      }
    );
    return () => { cancelled = true; };
  }, [api]);

  const handleCreateWorkflow = useCallback(async (form) => {
    const name = form?.name?.trim();
    if (!name) return;
    try {
      const newWf = await api.saveWorkflow({
        name,
        description: form?.description?.trim() || '',
        category: 'general',
      });
      // 获取初始版本
      const versions = await api.getVersionList(newWf.id);
      const versionId = versions[0]?.id || null;
      setIsCreateOpen(false);
      // 直接进入编辑器
      onEnterEditor?.({ workflowId: newWf.id, versionId, workflowName: newWf.name });
    } catch (err) {
      alert('创建失败: ' + (err.message || '未知错误'));
    }
  }, [api, onEnterEditor]);

  const handleEditWorkflow = useCallback(async (workflowId) => {
    try {
      const wf = await api.getWorkflow(workflowId);
      const versions = await api.getVersionList(workflowId);
      const targetVersion = versions.find((v) => v.status === 'draft') || versions[0];
      onEnterEditor?.({
        workflowId,
        versionId: targetVersion?.id || null,
        workflowName: wf?.name || '未命名',
      });
    } catch (err) {
      console.error('[WorkflowHub] enter editor error:', err);
    }
  }, [api, onEnterEditor]);

  const renderContent = () => {
    switch (activeNav) {
      case 'workflows':
        return (
          <>
            <StatsCards workflows={recentWorkflows} runs={recentRuns} />
            <QuickStart
              recentWorkflows={recentWorkflows}
              onCreate={() => setIsCreateOpen(true)}
              onEdit={handleEditWorkflow}
              onUseTemplate={async (templateId) => {
                const tpl = WORKFLOW_TEMPLATES.find((t) => t.id === templateId);
                if (!tpl) return;
                try {
                  const newWf = await api.saveWorkflow({
                    name: tpl.name,
                    description: tpl.description || '',
                    category: tpl.category || 'general',
                  });
                  const versions = await api.getVersionList(newWf.id);
                  const versionId = versions[0]?.id || null;
                  if (versionId) {
                    await api.saveDefinition(versionId, tpl.nodes || [], tpl.edges || [], []);
                  }
                  onEnterEditor?.({ workflowId: newWf.id, versionId, workflowName: newWf.name });
                } catch (err) {
                  alert('从模板创建失败: ' + (err.message || '未知错误'));
                }
              }}
            />
            <WorkflowGrid
              onEditWorkflow={handleEditWorkflow}
              onCreateWorkflow={() => setIsCreateOpen(true)}
            />
          </>
        );
      case 'history':
        return (
          <div className="wf-hub-panel">
            <div className="wf-hub-panel-body">
              <RunHistory
                standalone
                onViewWorkflow={(workflowId) => handleEditWorkflow(workflowId)}
              />
            </div>
          </div>
        );
      case 'templates':
        return (
          <div className="wf-hub-panel">
            <div className="wf-hub-panel-header">
              <div className="wf-hub-panel-title">
                <h2>模板市场</h2>
              </div>
            </div>
            <div className="wf-hub-panel-body">
              <div className="wf-hub-empty">
                <p>模板市场即将上线，敬请期待</p>
              </div>
            </div>
          </div>
        );
      case 'database':
        return (
          <div className="wf-hub-panel">
            <div className="wf-hub-panel-header">
              <div className="wf-hub-panel-title">
                <h2>数据表</h2>
              </div>
            </div>
            <div className="wf-hub-panel-body">
              <DatabasePanel />
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="wf-hub">
      <SidebarNav activeKey={activeNav} onChange={setActiveNav} />
      <main className="wf-hub-main">
        {renderContent()}
      </main>

      <PromptDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onConfirm={handleCreateWorkflow}
        title="新建工作流"
        fields={[
          { key: 'name', label: '名称', placeholder: '输入工作流名称', required: true },
          { key: 'description', label: '描述', placeholder: '简要描述工作流用途', required: false },
        ]}
        confirmText="创建"
        cancelText="取消"
      />
    </div>
  );
};

export default WorkflowHub;
