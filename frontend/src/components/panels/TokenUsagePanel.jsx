import React, { useState, useEffect, useCallback } from 'react';
import { Zap, TrendingUp, TrendingDown, Activity, Calendar, RefreshCw, Database } from 'lucide-react';
import WindowDots from '../WindowDots';

const formatNumber = (num) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(2) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};

const TokenUsagePanel = ({ sendWSMessage }) => {
  const [globalUsage, setGlobalUsage] = useState({
    total_prompt_tokens: 0,
    total_completion_tokens: 0,
    total_cached_tokens: 0,
    total_tokens: 0,
    request_count: 0,
  });
  const [byProvider, setByProvider] = useState([]);
  const [byModel, setByModel] = useState([]);
  const [dailyUsage, setDailyUsage] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  const fetchTokenUsage = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      setLoading(true);
      const response = await sendWSMessage('token_get_usage', { scope: 'global', days });
      if (response.data) {
        setGlobalUsage(response.data.summary || {});
        setByProvider(response.data.by_provider || []);
        setByModel(response.data.by_model || []);
        setDailyUsage(response.data.daily || []);
      }
    } catch (err) {
      console.error('Failed to fetch token usage:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, days]);

  useEffect(() => {
    fetchTokenUsage();
  }, [fetchTokenUsage]);

  const maxDailyTokens = Math.max(...dailyUsage.map(d => d.total_tokens || 0), 1);

  return (
    <div className="panel token-usage-panel">
      <div className="window-header">
        <WindowDots />
        <span className="window-title">TOKEN USAGE STATISTICS</span>
        <button
          className="refresh-btn"
          onClick={fetchTokenUsage}
          disabled={loading}
          title="Refresh"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="panel-content">
        {loading && <div className="loading-overlay">Loading...</div>}

        <div className="usage-summary">
          <div className="summary-card total">
            <div className="card-icon">
              <Activity size={24} />
            </div>
            <div className="card-content">
              <div className="card-label">Total Tokens</div>
              <div className="card-value">
                {formatNumber(globalUsage.total_tokens + (globalUsage.total_cached_tokens || 0))}
              </div>
              <div className="card-sub">{globalUsage.request_count} requests</div>
            </div>
          </div>

          <div className="summary-card prompt">
            <div className="card-icon">
              <TrendingUp size={24} />
            </div>
            <div className="card-content">
              <div className="card-label">Prompt Tokens</div>
              <div className="card-value">
                {formatNumber(globalUsage.total_prompt_tokens + (globalUsage.total_cached_tokens || 0))}
              </div>
              <div className="card-sub">Input / Upload (incl. cache)</div>
            </div>
          </div>

          <div className="summary-card cache">
            <div className="card-icon">
              <Database size={24} />
            </div>
            <div className="card-content">
              <div className="card-label">Cache Hit Tokens</div>
              <div className="card-value">{formatNumber(globalUsage.total_cached_tokens || 0)}</div>
              <div className="card-sub">Prompt cache hits</div>
            </div>
          </div>

          <div className="summary-card completion">
            <div className="card-icon">
              <TrendingDown size={24} />
            </div>
            <div className="card-content">
              <div className="card-label">Completion Tokens</div>
              <div className="card-value">{formatNumber(globalUsage.total_completion_tokens)}</div>
              <div className="card-sub">Output / Download</div>
            </div>
          </div>
        </div>
        <hr className="section-divider" style={{ border: 'none', height: '1px', backgroundColor: '#ced0d3' }} />
        <div className="usage-section">
          <div className="section-header">
            <h3>
              <Calendar size={14} />
              Daily Usage ({days} days)
            </h3>
            <select value={days} onChange={(e) => setDays(parseInt(e.target.value))}>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </div>

          <div className="daily-chart">
            {dailyUsage.length === 0 ? (
              <div className="empty-state">No data available</div>
            ) : (
              dailyUsage.map((day, index) => (
                <div key={index} className="daily-bar-container">
                  <div className="daily-label">{day.date}</div>
                  <div className="daily-bar-wrapper">
                    <div
                      className="daily-bar prompt"
                      style={{
                        width: `${((day.prompt_tokens || 0) / maxDailyTokens) * 100}%`
                      }}
                      title={`Prompt: ${day.prompt_tokens}`}
                    />
                    <div
                      className="daily-bar cache"
                      style={{
                        width: `${((day.cached_tokens || 0) / maxDailyTokens) * 100}%`
                      }}
                      title={`Cache: ${day.cached_tokens}`}
                    />
                    <div
                      className="daily-bar completion"
                      style={{
                        width: `${((day.completion_tokens || 0) / maxDailyTokens) * 100}%`
                      }}
                      title={`Completion: ${day.completion_tokens}`}
                    />
                  </div>
                  <div className="daily-value">{formatNumber((day.total_tokens || 0) + (day.cached_tokens || 0))}</div>
                </div>
              ))
            )}
          </div>
        </div>
        <hr className="section-divider" style={{ border: 'none', height: '1px', backgroundColor: '#ced0d3' }} />
        <div className="usage-sections-row">
          <div className="usage-section">
            <h3>By Provider</h3>
            <div className="usage-table">
              {byProvider.length === 0 ? (
                <div className="empty-state">No data available</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th>Prompt</th>
                      <th>Cache</th>
                      <th>Completion</th>
                      <th>Total</th>
                      <th>Requests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byProvider.map((item, index) => (
                      <tr key={index}>
                        <td>{item.provider_name}</td>
                        <td>{formatNumber((item.prompt_tokens || 0) + (item.cached_tokens || 0))}</td>
                        <td>{formatNumber(item.cached_tokens || 0)}</td>
                        <td>{formatNumber(item.completion_tokens)}</td>
                        <td>{formatNumber((item.total_tokens || 0) + (item.cached_tokens || 0))}</td>
                        <td>{item.request_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="usage-section">
            <h3>By Model</h3>
            <div className="usage-table">
              {byModel.length === 0 ? (
                <div className="empty-state">No data available</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Prompt</th>
                      <th>Cache</th>
                      <th>Completion</th>
                      <th>Total</th>
                      <th>Requests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byModel.map((item, index) => (
                      <tr key={index}>
                        <td>
                          <span className="model-provider">{item.provider_name}/</span>
                          {item.model_id}
                        </td>
                        <td>{formatNumber((item.prompt_tokens || 0) + (item.cached_tokens || 0))}</td>
                        <td>{formatNumber(item.cached_tokens || 0)}</td>
                        <td>{formatNumber(item.completion_tokens)}</td>
                        <td>{formatNumber((item.total_tokens || 0) + (item.cached_tokens || 0))}</td>
                        <td>{item.request_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .token-usage-panel {
          height: 100%;
          display: flex;
          flex-direction: column;
          background: var(--surface);
          border: 1px solid var(--board);
          border-radius: var(--r-lg);
          overflow: hidden;
        }

        .refresh-btn {
          background: transparent;
          border: 1px solid var(--border);
          padding: 6px;
          border-radius: var(--r-sm);
          cursor: pointer;
          color: var(--text-2);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .refresh-btn:hover {
          background: var(--surface-2);
        }

        .refresh-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .panel-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--s-5);
        }

        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text);
          z-index: 10;
        }

        .usage-summary {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--s-4);
          margin-bottom: var(--s-6);
        }

        @media (max-width: 1100px) {
          .usage-summary {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        .summary-card {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: var(--s-4);
          display: flex;
          gap: var(--s-3);
        }

        .summary-card.total .card-icon {
          background: rgba(59, 130, 246, 0.2);
          color: #3b82f6;
        }

        .summary-card.prompt .card-icon {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .summary-card.cache .card-icon {
          background: rgba(139, 92, 246, 0.2);
          color: #8b5cf6;
        }

        .summary-card.completion .card-icon {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .card-icon {
          width: 48px;
          height: 48px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .card-content {
          flex: 1;
        }

        .card-label {
          font-size: 12px;
          color: var(--text-2);
          margin-bottom: 4px;
        }

        .card-value {
          font-size: 24px;
          font-weight: 700;
          color: var(--text);
        }

        .card-sub {
          font-size: 11px;
          color: var(--text-3);
          margin-top: 4px;
        }

        .usage-section {
          margin-bottom: var(--s-6);
        }

        .usage-section h3 {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          font-size: 14px;
          font-weight: 600;
          color: var(--text);
          margin: 0 0 var(--s-3) 0;
        }

        .section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--s-3);
        }

        .section-header h3 {
          margin: 0;
        }

        .section-header select {
          background: var(--surface-2);
          border: 1px solid var(--border);
          color: var(--text);
          padding: var(--s-1) var(--s-2);
          border-radius: var(--r-sm);
          font-size: 12px;
        }

        .daily-chart {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: var(--s-3);
        }

        .daily-bar-container {
          display: grid;
          grid-template-columns: 100px 1fr 80px;
          gap: 8px;
          align-items: center;
          margin-bottom: 8px;
        }

        .daily-bar-container:last-child {
          margin-bottom: 0;
        }

        .daily-label {
          font-size: 11px;
          color: var(--text-2);
          font-family: var(--font-mono);
        }

        .daily-bar-wrapper {
          height: 16px;
          background: var(--surface-3);
          border-radius: var(--r-sm);
          display: flex;
          overflow: hidden;
        }

        .daily-bar {
          height: 100%;
          transition: width 0.3s ease;
        }

        .daily-bar.prompt {
          background: #10b981;
        }

        .daily-bar.cache {
          background: #8b5cf6;
        }

        .daily-bar.completion {
          background: #f59e0b;
        }

        .daily-value {
          font-size: 11px;
          color: var(--text);
          text-align: right;
          font-family: var(--font-mono);
        }

        .usage-sections-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--s-4);
        }

        .usage-table {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          overflow: hidden;
        }

        .usage-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
        }

        .usage-table th {
          background: var(--surface-3);
          padding: var(--s-2) var(--s-3);
          text-align: left;
          font-weight: 600;
          color: var(--text-2);
          border-bottom: 1px solid var(--border);
        }

        .usage-table td {
          padding: var(--s-2) var(--s-3);
          border-bottom: 1px solid var(--border);
          color: var(--text);
        }

        .usage-table tr:last-child td {
          border-bottom: none;
        }

        .usage-table tr:hover td {
          background: var(--surface-3);
        }

        .model-provider {
          color: var(--text-3);
          font-size: 10px;
        }

        .empty-state {
          padding: var(--s-6);
          text-align: center;
          color: var(--text-3);
          font-size: 13px;
        }
      `}</style>
    </div>
  );
};

export default TokenUsagePanel;
