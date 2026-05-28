/**
 * WorkflowHub — 快捷操作区（最近编辑 + 快速新建）
 */
import React from 'react';
import { Plus, Clock, Zap, ArrowRight } from 'lucide-react';

const TEMPLATES = [
  { id: 'simple-chat', name: '简单对话', desc: '用户输入 → AI 回复', icon: '💬' },
  { id: 'conditional-branch', name: '条件分支', desc: '分类 → 条件判断', icon: '🔀' },
  { id: 'loop-process', name: '循环处理', desc: '批量数据迭代', icon: '🔄' },
  { id: 'http-api', name: 'API 调用', desc: 'HTTP 请求 → 处理', icon: '🌐' },
];

const QuickStart = ({ recentWorkflows = [], onCreate, onEdit, onUseTemplate }) => {
  return (
    <div className="wf-hub-quickstart">
      {/* 新建卡片 */}
      <div className="wf-hub-quick-card create" onClick={onCreate}>
        <div className="wf-hub-quick-icon">
          <Plus size={24} />
        </div>
        <div className="wf-hub-quick-info">
          <h3>新建工作流</h3>
          <p>从零开始搭建</p>
        </div>
      </div>

      {/* 最近编辑 */}
      {recentWorkflows.slice(0, 2).map((wf) => (
        <div
          key={wf.id}
          className="wf-hub-quick-card"
          onClick={() => onEdit?.(wf.id)}
        >
          <div className="wf-hub-quick-icon muted">
            <Clock size={20} />
          </div>
          <div className="wf-hub-quick-info">
            <h3>{wf.name}</h3>
            <p>继续编辑</p>
          </div>
          <ArrowRight size={16} className="wf-hub-quick-arrow" />
        </div>
      ))}

      {/* 模板快捷入口 */}
      <div className="wf-hub-quick-templates">
        <div className="wf-hub-quick-templates-header">
          <Zap size={14} />
          <span>快速开始</span>
        </div>
        <div className="wf-hub-quick-template-list">
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              className="wf-hub-template-chip"
              onClick={() => onUseTemplate?.(t.id)}
            >
              <span>{t.icon}</span>
              <span>{t.name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default QuickStart;
