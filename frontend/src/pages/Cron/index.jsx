import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock, Play, Pause, Trash2, RefreshCw, Plus, X, Check, AlertCircle, Calendar } from 'lucide-react';
import WindowDots from '@components/layout/WindowDots';
import Toast from '@components/ui/Toast';
import './CronPanel.css';

/**
 * CronPanel Component - 定时任务管理面板
 */
const CronPanel = ({ sendWSMessage }) => {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [toasts, setToasts] = useState([]);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    scheduleType: 'cron',
    cronExpr: '0 9 * * *',
    intervalValue: 60,
    intervalUnit: 'minutes',
    message: '',
    deliver: false,
    channel: '',
    to: ''
  });

  // Add toast notification
  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type, duration }]);
  }, []);

  // Remove toast
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Fetch jobs
  const fetchJobs = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      setLoading(true);
      const response = await sendWSMessage('cron_get_jobs', { include_disabled: true });
      if (response.data?.jobs) {
        setJobs(response.data.jobs);
      }
    } catch (err) {
      console.error('Failed to fetch cron jobs:', err);
      addToast(t('cron.fetchFailed'), 'error');
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, addToast, t]);

  // Load jobs on mount
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Enable/disable job
  const toggleJob = async (jobId, enabled) => {
    try {
      await sendWSMessage('cron_toggle_job', { job_id: jobId, enabled });
      addToast(enabled ? t('cron.jobEnabled') : t('cron.jobDisabled'), 'success');
      fetchJobs();
    } catch (err) {
      addToast(enabled ? t('cron.enableFailed') : t('cron.disableFailed'), 'error');
    }
  };

  // Run job manually
  const runJob = async (jobId) => {
    try {
      await sendWSMessage('cron_run_job', { job_id: jobId });
      addToast(t('cron.jobExecuted'), 'success');
    } catch (err) {
      addToast(t('cron.runFailed'), 'error');
    }
  };

  // Delete job
  const deleteJob = async (jobId) => {
    try {
      await sendWSMessage('cron_delete_job', { job_id: jobId });
      addToast(t('cron.jobDeleted'), 'success');
      fetchJobs();
    } catch (err) {
      addToast(t('cron.deleteFailed'), 'error');
    }
  };

  // Add new job
  const addJob = async () => {
    try {
      let schedule;
      if (formData.scheduleType === 'cron') {
        schedule = { kind: 'cron', expr: formData.cronExpr };
      } else if (formData.scheduleType === 'every') {
        const ms = formData.intervalUnit === 'seconds' ? formData.intervalValue * 1000 :
                   formData.intervalUnit === 'minutes' ? formData.intervalValue * 60 * 1000 :
                   formData.intervalValue * 60 * 60 * 1000;
        schedule = { kind: 'every', every_ms: ms };
      }

      await sendWSMessage('cron_add_job', {
        name: formData.name,
        schedule: schedule,
        message: formData.message,
        deliver: formData.deliver,
        channel: formData.channel || undefined,
        to: formData.to || undefined
      });

      addToast(t('cron.jobAdded'), 'success');
      setShowAddDialog(false);
      setFormData({
        name: '',
        scheduleType: 'cron',
        cronExpr: '0 9 * * *',
        intervalValue: 60,
        intervalUnit: 'minutes',
        message: '',
        deliver: false,
        channel: '',
        to: ''
      });
      fetchJobs();
    } catch (err) {
      addToast(t('cron.addFailed'), 'error');
    }
  };

  // Format schedule display
  const formatSchedule = (job) => {
    const s = job.schedule;
    if (s.kind === 'cron') {
      return t('cron.scheduleCron', { expr: s.expr });
    } else if (s.kind === 'every') {
      const ms = s.every_ms;
      if (ms < 60000) return t('cron.scheduleEverySeconds', { value: ms / 1000 });
      if (ms < 3600000) return t('cron.scheduleEveryMinutes', { value: ms / 60000 });
      return t('cron.scheduleEveryHours', { value: ms / 3600000 });
    } else if (s.kind === 'at') {
      return t('cron.scheduleAt', { time: new Date(s.at_ms).toLocaleString() });
    }
    return t('cron.scheduleUnknown');
  };

  // Format next run time
  const formatNextRun = (ms) => {
    if (!ms) return t('cron.never');
    const date = new Date(ms);
    const now = new Date();
    const diff = date - now;

    if (diff < 0) return t('cron.overdue');
    if (diff < 60000) return t('cron.inLessThanMinute');
    if (diff < 3600000) return t('cron.inMinutes', { count: Math.floor(diff / 60000) });
    if (diff < 86400000) return t('cron.inHours', { count: Math.floor(diff / 3600000) });
    return date.toLocaleDateString();
  };

  return (
    <div className="cron-panel-container">
      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>

      {/* Toolbar */}
      <div className="cron-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">{t('title.cron')}</span>
          <span className="job-count">({jobs.length})</span>
        </div>
        <div className="toolbar-right">
          <button className="pixel-button secondary" onClick={fetchJobs}>
            <RefreshCw size={14} />
            {t('cron.refresh')}
          </button>
          <button className="pixel-button" onClick={() => setShowAddDialog(true)}>
            <Plus size={14} />
            {t('cron.addJob')}
          </button>
        </div>
      </div>

      {/* Jobs List */}
      <div className="cron-content">
        {loading ? (
          <div className="cron-loading">
            <div className="loading-spinner"></div>
            <span>{t('cron.loading')}</span>
          </div>
        ) : jobs.length === 0 ? (
          <div className="cron-empty">
            <Clock size={48} />
            <span>{t('cron.empty')}</span>
            <button className="pixel-button" onClick={() => setShowAddDialog(true)}>
              {t('cron.createFirst')}
            </button>
          </div>
        ) : (
          <div className="jobs-list">
            {jobs.map(job => (
              <div key={job.id} className={`job-card ${!job.enabled ? 'disabled' : ''}`}>
                <div className="job-card-header">
                  <div className="job-status">
                    <div className={`status-dot ${job.enabled ? 'active' : 'inactive'}`}></div>
                    <span className="job-name">{job.name}</span>
                  </div>
                  <div className="job-actions">
                    <button
                      className="job-action-btn"
                      onClick={() => toggleJob(job.id, !job.enabled)}
                      title={job.enabled ? t('cron.disable') : t('cron.enable')}
                    >
                      {job.enabled ? <Pause size={14} /> : <Play size={14} />}
                    </button>
                    <button
                      className="job-action-btn"
                      onClick={() => runJob(job.id)}
                      title={t('cron.runNow')}
                    >
                      <Play size={14} />
                    </button>
                    <button
                      className="job-action-btn danger"
                      onClick={() => deleteJob(job.id)}
                      title={t('cron.delete')}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <div className="job-card-body">
                  <div className="job-schedule">
                    <Calendar size={14} />
                    <span>{formatSchedule(job)}</span>
                  </div>
                  <div className="job-next-run">
                    <Clock size={14} />
                    <span>{t('cron.nextRun', { value: formatNextRun(job.next_run_at_ms) })}</span>
                  </div>
                  <div className="job-message">
                    <span className="message-label">{t('cron.message')}:</span>
                    <span className="message-content">{job.payload?.message || '-'}</span>
                  </div>
                  {job.payload?.deliver && (
                    <div className="job-delivery">
                      <span className="delivery-label">{t('cron.deliverTo')}</span>
                      <span className="delivery-content">{job.payload.channel} / {job.payload.to}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Job Dialog */}
      {showAddDialog && (
        <div className="cron-dialog-overlay">
          <div className="cron-dialog pixel-border">
            <div className="dialog-header">
              <WindowDots />
              <span className="window-title">{t('cron.dialogTitle')}</span>
              <button className="dialog-close" onClick={() => setShowAddDialog(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="dialog-body">
              <div className="form-group">
                <label>{t('cron.jobName')}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={t('cron.jobNamePlaceholder')}
                  className="pixel-input"
                />
              </div>

              <div className="form-group">
                <label>{t('cron.scheduleType')}</label>
                <div className="schedule-type-selector">
                  <button
                    className={`type-btn ${formData.scheduleType === 'cron' ? 'active' : ''}`}
                    onClick={() => setFormData({ ...formData, scheduleType: 'cron' })}
                  >
                    {t('cron.cronExpression')}
                  </button>
                  <button
                    className={`type-btn ${formData.scheduleType === 'every' ? 'active' : ''}`}
                    onClick={() => setFormData({ ...formData, scheduleType: 'every' })}
                  >
                    {t('cron.interval')}
                  </button>
                </div>
              </div>

              {formData.scheduleType === 'cron' ? (
                <div className="form-group">
                  <label>{t('cron.cronExpression')}</label>
                  <input
                    type="text"
                    value={formData.cronExpr}
                    onChange={(e) => setFormData({ ...formData, cronExpr: e.target.value })}
                    placeholder="0 9 * * *"
                    className="pixel-input"
                  />
                  <span className="form-hint">{t('cron.cronFormatHint')}</span>
                </div>
              ) : (
                <div className="form-group">
                  <label>{t('cron.interval')}</label>
                  <div className="interval-inputs">
                    <input
                      type="number"
                      value={formData.intervalValue}
                      onChange={(e) => setFormData({ ...formData, intervalValue: parseInt(e.target.value) || 0 })}
                      className="pixel-input"
                      min="1"
                    />
                    <select
                      value={formData.intervalUnit}
                      onChange={(e) => setFormData({ ...formData, intervalUnit: e.target.value })}
                      className="pixel-select"
                    >
                      <option value="seconds">{t('cron.seconds')}</option>
                      <option value="minutes">{t('cron.minutes')}</option>
                      <option value="hours">{t('cron.hours')}</option>
                    </select>
                  </div>
                </div>
              )}

              <div className="form-group">
                <label>{t('cron.message')}</label>
                <textarea
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder={t('cron.messagePlaceholder')}
                  className="pixel-textarea"
                  rows="3"
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.deliver}
                    onChange={(e) => setFormData({ ...formData, deliver: e.target.checked })}
                  />
                  {t('cron.deliverResponse')}
                </label>
              </div>

              {formData.deliver && (
                <>
                  <div className="form-group">
                    <label>{t('cron.channel')}</label>
                    <input
                      type="text"
                      value={formData.channel}
                      onChange={(e) => setFormData({ ...formData, channel: e.target.value })}
                      placeholder={t('cron.channelPlaceholder')}
                      className="pixel-input"
                    />
                  </div>
                  <div className="form-group">
                    <label>{t('cron.toChatId')}</label>
                    <input
                      type="text"
                      value={formData.to}
                      onChange={(e) => setFormData({ ...formData, to: e.target.value })}
                      placeholder={t('cron.toPlaceholder')}
                      className="pixel-input"
                    />
                  </div>
                </>
              )}
            </div>
            <div className="dialog-footer">
              <button className="pixel-button secondary" onClick={() => setShowAddDialog(false)}>
                {t('common.cancel')}
              </button>
              <button className="pixel-button" onClick={addJob} disabled={!formData.name || !formData.message}>
                <Check size={14} />
                {t('cron.addJob')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CronPanel;
