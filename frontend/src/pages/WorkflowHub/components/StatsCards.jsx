/**
 * WorkflowHub — 统计卡片区域
 * 展示工作流相关的核心指标
 */
import React, { useMemo } from 'react';
import { GitBranch, Play, CheckCircle, Clock, TrendingUp, Zap } from 'lucide-react';

const StatsCards = ({ workflows = [], runs = [] }) => {
  const stats = useMemo(() => {
    const totalWorkflows = workflows.length;

    // 本周运行次数
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const weekRuns = runs.filter((r) => {
      const d = new Date(r.started_at || r.startTime);
      return d >= weekAgo;
    });
    const weekRunCount = weekRuns.length;

    // 成功率
    const successRuns = runs.filter(
      (r) => r.status === 'success' || r.status === 'completed'
    );
    const successRate = runs.length > 0 ? Math.round((successRuns.length / runs.length) * 100) : 0;

    // 活跃工作流（本周有运行的）
    const activeWorkflowIds = new Set(weekRuns.map((r) => r.workflow_id || r.workflowId));
    const activeCount = activeWorkflowIds.size;

    // 平均耗时（最近10次成功运行）
    const recentSuccess = runs
      .filter((r) => r.status === 'success' || r.status === 'completed')
      .slice(0, 10);
    const avgDuration =
      recentSuccess.length > 0
        ? Math.round(
            recentSuccess.reduce((sum, r) => sum + (r.duration_ms || r.duration || 0), 0) /
              recentSuccess.length
          )
        : 0;

    const formatDuration = (ms) => {
      if (!ms) return '-';
      if (ms < 1000) return `${ms}ms`;
      if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
      return `${(ms / 60000).toFixed(1)}m`;
    };

    return [
      {
        label: '工作流总数',
        value: totalWorkflows,
        icon: GitBranch,
        color: '#6366f1',
        bg: '#eef2ff',
      },
      {
        label: '本周运行',
        value: weekRunCount,
        icon: Play,
        color: '#3b82f6',
        bg: '#eff6ff',
      },
      {
        label: '成功率',
        value: `${successRate}%`,
        icon: CheckCircle,
        color: '#22c55e',
        bg: '#f0fdf4',
      },
      {
        label: '活跃工作流',
        value: activeCount,
        icon: Zap,
        color: '#f59e0b',
        bg: '#fffbeb',
      },
      {
        label: '平均耗时',
        value: formatDuration(avgDuration),
        icon: Clock,
        color: '#8b5cf6',
        bg: '#f5f3ff',
      },
      {
        label: '总运行次数',
        value: runs.length,
        icon: TrendingUp,
        color: '#ec4899',
        bg: '#fdf2f8',
      },
    ];
  }, [workflows, runs]);

  return (
    <div className="wf-hub-stats">
      {stats.map((s) => (
        <div key={s.label} className="wf-hub-stat-card">
          <div
            className="wf-hub-stat-icon"
            style={{ background: s.bg, color: s.color }}
          >
            <s.icon size={18} />
          </div>
          <div className="wf-hub-stat-info">
            <div className="wf-hub-stat-value" style={{ color: s.color }}>
              {s.value}
            </div>
            <div className="wf-hub-stat-label">{s.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default StatsCards;
