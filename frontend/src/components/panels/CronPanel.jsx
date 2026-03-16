import React, { useState, useEffect, useCallback } from 'react';
import { Clock, Play, Pause, Trash2, RefreshCw, Plus, X, Check, AlertCircle, Calendar } from 'lucide-react';
import WindowDots from '../WindowDots';
import Toast from '../Toast';

/**
 * CronPanel Component - 定时任务管理面板
 */
const CronPanel = ({ sendWSMessage }) => {
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
      addToast('Failed to fetch cron jobs', 'error');
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, addToast]);

  // Load jobs on mount
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Enable/disable job
  const toggleJob = async (jobId, enabled) => {
    try {
      await sendWSMessage('cron_toggle_job', { job_id: jobId, enabled });
      addToast(`Job ${enabled ? 'enabled' : 'disabled'}`, 'success');
      fetchJobs();
    } catch (err) {
      addToast(`Failed to ${enabled ? 'enable' : 'disable'} job`, 'error');
    }
  };

  // Run job manually
  const runJob = async (jobId) => {
    try {
      await sendWSMessage('cron_run_job', { job_id: jobId });
      addToast('Job executed', 'success');
    } catch (err) {
      addToast('Failed to run job', 'error');
    }
  };

  // Delete job
  const deleteJob = async (jobId) => {
    try {
      await sendWSMessage('cron_delete_job', { job_id: jobId });
      addToast('Job deleted', 'success');
      fetchJobs();
    } catch (err) {
      addToast('Failed to delete job', 'error');
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

      addToast('Job added successfully', 'success');
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
      addToast('Failed to add job', 'error');
    }
  };

  // Format schedule display
  const formatSchedule = (job) => {
    const s = job.schedule;
    if (s.kind === 'cron') {
      return `Cron: ${s.expr}`;
    } else if (s.kind === 'every') {
      const ms = s.every_ms;
      if (ms < 60000) return `Every ${ms / 1000}s`;
      if (ms < 3600000) return `Every ${ms / 60000}m`;
      return `Every ${ms / 3600000}h`;
    } else if (s.kind === 'at') {
      return `At: ${new Date(s.at_ms).toLocaleString()}`;
    }
    return 'Unknown';
  };

  // Format next run time
  const formatNextRun = (ms) => {
    if (!ms) return 'Never';
    const date = new Date(ms);
    const now = new Date();
    const diff = date - now;
    
    if (diff < 0) return 'Overdue';
    if (diff < 60000) return 'In < 1 min';
    if (diff < 3600000) return `In ${Math.floor(diff / 60000)}m`;
    if (diff < 86400000) return `In ${Math.floor(diff / 3600000)}h`;
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
          <div className="toolbar-icon"><Clock size={18} /></div>
          <span className="toolbar-title">CRON_JOBS</span>
          <span className="job-count">({jobs.length})</span>
        </div>
        <div className="toolbar-right">
          <button className="pixel-button secondary" onClick={fetchJobs}>
            <RefreshCw size={14} />
            Refresh
          </button>
          <button className="pixel-button" onClick={() => setShowAddDialog(true)}>
            <Plus size={14} />
            Add Job
          </button>
        </div>
      </div>

      {/* Jobs List */}
      <div className="cron-content">
        {loading ? (
          <div className="cron-loading">
            <div className="loading-spinner"></div>
            <span>Loading jobs...</span>
          </div>
        ) : jobs.length === 0 ? (
          <div className="cron-empty">
            <Clock size={48} />
            <span>No scheduled jobs</span>
            <button className="pixel-button" onClick={() => setShowAddDialog(true)}>
              Create your first job
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
                      title={job.enabled ? 'Disable' : 'Enable'}
                    >
                      {job.enabled ? <Pause size={14} /> : <Play size={14} />}
                    </button>
                    <button 
                      className="job-action-btn"
                      onClick={() => runJob(job.id)}
                      title="Run now"
                    >
                      <Play size={14} />
                    </button>
                    <button 
                      className="job-action-btn danger"
                      onClick={() => deleteJob(job.id)}
                      title="Delete"
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
                    <span>Next: {formatNextRun(job.next_run_at_ms)}</span>
                  </div>
                  <div className="job-message">
                    <span className="message-label">Message:</span>
                    <span className="message-content">{job.payload?.message || '-'}</span>
                  </div>
                  {job.payload?.deliver && (
                    <div className="job-delivery">
                      <span className="delivery-label">Deliver to:</span>
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
              <span className="window-title">ADD_CRON_JOB</span>
              <button className="dialog-close" onClick={() => setShowAddDialog(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="dialog-body">
              <div className="form-group">
                <label>Job Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Daily Report"
                  className="pixel-input"
                />
              </div>

              <div className="form-group">
                <label>Schedule Type</label>
                <div className="schedule-type-selector">
                  <button
                    className={`type-btn ${formData.scheduleType === 'cron' ? 'active' : ''}`}
                    onClick={() => setFormData({ ...formData, scheduleType: 'cron' })}
                  >
                    Cron Expression
                  </button>
                  <button
                    className={`type-btn ${formData.scheduleType === 'every' ? 'active' : ''}`}
                    onClick={() => setFormData({ ...formData, scheduleType: 'every' })}
                  >
                    Interval
                  </button>
                </div>
              </div>

              {formData.scheduleType === 'cron' ? (
                <div className="form-group">
                  <label>Cron Expression</label>
                  <input
                    type="text"
                    value={formData.cronExpr}
                    onChange={(e) => setFormData({ ...formData, cronExpr: e.target.value })}
                    placeholder="0 9 * * *"
                    className="pixel-input"
                  />
                  <span className="form-hint">Format: min hour day month weekday</span>
                </div>
              ) : (
                <div className="form-group">
                  <label>Interval</label>
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
                      <option value="seconds">Seconds</option>
                      <option value="minutes">Minutes</option>
                      <option value="hours">Hours</option>
                    </select>
                  </div>
                </div>
              )}

              <div className="form-group">
                <label>Message</label>
                <textarea
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="Task description for the agent..."
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
                  Deliver response to channel
                </label>
              </div>

              {formData.deliver && (
                <>
                  <div className="form-group">
                    <label>Channel</label>
                    <input
                      type="text"
                      value={formData.channel}
                      onChange={(e) => setFormData({ ...formData, channel: e.target.value })}
                      placeholder="e.g., feishu"
                      className="pixel-input"
                    />
                  </div>
                  <div className="form-group">
                    <label>To (Chat ID)</label>
                    <input
                      type="text"
                      value={formData.to}
                      onChange={(e) => setFormData({ ...formData, to: e.target.value })}
                      placeholder="e.g., user open_id"
                      className="pixel-input"
                    />
                  </div>
                </>
              )}
            </div>
            <div className="dialog-footer">
              <button className="pixel-button secondary" onClick={() => setShowAddDialog(false)}>
                Cancel
              </button>
              <button className="pixel-button" onClick={addJob} disabled={!formData.name || !formData.message}>
                <Check size={14} />
                Add Job
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CronPanel;
