import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Activity, Calendar, RefreshCw, Database,
  DollarSign, Clock, Gauge, BarChart3, Layers, AlertTriangle,
  Server, Wallet, Timer, TrendingUp, TrendingDown, Zap, Flame
} from 'lucide-react';
import WindowDots from '@components/layout/WindowDots';

const formatNumber = (num) => {
  if (num === null || num === undefined) return '—';
  if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
};

const formatCurrency = (num) => {
  if (num === null || num === undefined) return '—';
  if (num >= 1) return '$' + num.toFixed(2);
  return '$' + num.toFixed(4);
};

const formatPercent = (num) => {
  if (num === null || num === undefined) return '—';
  return (num * 100).toFixed(1) + '%';
};

const formatDuration = (ms) => {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return Math.round(ms) + 'ms';
  return (ms / 1000).toFixed(1) + 's';
};

const TAB_CONFIG = [
  { key: 'overview', label: 'Overview', icon: Activity },
  { key: 'efficiency', label: 'Efficiency', icon: Gauge },
  { key: 'cost', label: 'Cost', icon: DollarSign },
  { key: 'models', label: 'Models', icon: BarChart3 },
  { key: 'heatmap', label: 'Heatmap', icon: Flame },
];

const TokenUsagePanel = ({ sendWSMessage }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  // Overview data
  const [globalUsage, setGlobalUsage] = useState({
    total_prompt_tokens: 0, total_completion_tokens: 0,
    total_cached_tokens: 0, total_cache_creation_tokens: 0,
    total_tokens: 0, total_cost_usd: 0, request_count: 0, avg_response_time_ms: null,
  });
  const [byProvider, setByProvider] = useState([]);
  const [byModel, setByModel] = useState([]);
  const [byRequestType, setByRequestType] = useState([]);
  const [dailyUsage, setDailyUsage] = useState([]);

  // Efficiency data
  const [efficiency, setEfficiency] = useState(null);

  // Cost data
  const [costTrend, setCostTrend] = useState([]);
  const [costGranularity, setCostGranularity] = useState('daily');

  // Models data
  const [modelComparison, setModelComparison] = useState([]);

  // Heatmap data
  const [heatmap, setHeatmap] = useState({ calendar: { data: [], max_tokens: 1 }, hourly: { matrix: [], max_tokens: 1 }, months: 6 });

  const fetchOverview = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('token_get_usage', { scope: 'global', days });
      if (response.data) {
        setGlobalUsage(response.data.summary || {});
        setByProvider(response.data.by_provider || []);
        setByModel(response.data.by_model || []);
        setByRequestType(response.data.by_request_type || []);
        setDailyUsage(response.data.daily || []);
      }
    } catch (err) {
      console.error('Failed to fetch token usage:', err);
    }
  }, [sendWSMessage, days]);

  const fetchEfficiency = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('token_get_efficiency', { days });
      if (response.data) setEfficiency(response.data);
    } catch (err) {
      console.error('Failed to fetch efficiency:', err);
    }
  }, [sendWSMessage, days]);

  const fetchCostTrend = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('token_get_cost_trend', { days: 30, granularity: costGranularity });
      if (response.data) setCostTrend(response.data.trend || []);
    } catch (err) {
      console.error('Failed to fetch cost trend:', err);
    }
  }, [sendWSMessage, costGranularity]);

  const fetchModelComparison = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('token_get_model_comparison', { days: 30 });
      if (response.data) setModelComparison(response.data.models || []);
    } catch (err) {
      console.error('Failed to fetch model comparison:', err);
    }
  }, [sendWSMessage]);

  const fetchHeatmap = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('token_get_heatmap', { months: 6 });
      if (response.data) setHeatmap(response.data);
    } catch (err) {
      console.error('Failed to fetch heatmap:', err);
    }
  }, [sendWSMessage]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      fetchOverview(),
      fetchEfficiency(),
      fetchCostTrend(),
      fetchModelComparison(),
      fetchHeatmap(),
    ]);
    setLoading(false);
  }, [fetchOverview, fetchEfficiency, fetchCostTrend, fetchModelComparison, fetchHeatmap]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (!loading) {
      fetchOverview();
      fetchEfficiency();
    }
  }, [days]);

  useEffect(() => {
    if (!loading) fetchCostTrend();
  }, [costGranularity]);

  const maxDailyTokens = Math.max(...dailyUsage.map(d => d.total_tokens || 0), 1);
  const subagentUsage = useMemo(() => {
    const subagent = byRequestType.find(t => t.request_type === 'subagent');
    return subagent || { total_tokens: 0, prompt_tokens: 0, completion_tokens: 0, request_count: 0 };
  }, [byRequestType]);

  // ===== Overview Tab =====
  const renderOverview = () => (
    <>
      <div className="usage-summary">
        <div className="summary-card total">
          <div className="card-icon"><Activity size={24} /></div>
          <div className="card-content">
            <div className="card-label">Total Tokens</div>
            <div className="card-value">{formatNumber(globalUsage.total_tokens)}</div>
            <div className="card-sub">{globalUsage.request_count} requests</div>
          </div>
        </div>
        <div className="summary-card cost">
          <div className="card-icon"><DollarSign size={24} /></div>
          <div className="card-content">
            <div className="card-label">Total Cost</div>
            <div className="card-value">{formatCurrency(globalUsage.total_cost_usd)}</div>
            <div className="card-sub">{formatCurrency(globalUsage.total_cost_usd / (globalUsage.total_tokens || 1) * 1000)} / 1K tokens</div>
          </div>
        </div>
        <div className="summary-card prompt">
          <div className="card-icon"><TrendingUp size={24} /></div>
          <div className="card-content">
            <div className="card-label">Prompt Tokens</div>
            <div className="card-value">{formatNumber(globalUsage.total_prompt_tokens)}</div>
            <div className="card-sub">Input + Cache hits</div>
          </div>
        </div>
        <div className="summary-card completion">
          <div className="card-icon"><TrendingDown size={24} /></div>
          <div className="card-content">
            <div className="card-label">Completion Tokens</div>
            <div className="card-value">{formatNumber(globalUsage.total_completion_tokens)}</div>
            <div className="card-sub">Output / Download</div>
          </div>
        </div>
        <div className="summary-card cache">
          <div className="card-icon"><Database size={24} /></div>
          <div className="card-content">
            <div className="card-label">Cache Hit Tokens</div>
            <div className="card-value">{formatNumber(globalUsage.total_cached_tokens)}</div>
            <div className="card-sub">{globalUsage.total_cache_creation_tokens ? `+${formatNumber(globalUsage.total_cache_creation_tokens)} created` : 'Prompt cache hits'}</div>
          </div>
        </div>
        <div className="summary-card latency">
          <div className="card-icon"><Clock size={24} /></div>
          <div className="card-content">
            <div className="card-label">Avg Latency</div>
            <div className="card-value">{formatDuration(globalUsage.avg_response_time_ms)}</div>
            <div className="card-sub">Per request</div>
          </div>
        </div>
      </div>

      <hr className="section-divider" />

      <div className="usage-section">
        <div className="section-header">
          <h3><Calendar size={14} /> Daily Usage ({days} days)</h3>
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
                  <div className="daily-bar prompt" style={{ width: `${((day.prompt_tokens || 0) / maxDailyTokens) * 100}%` }} title={`Prompt: ${day.prompt_tokens}`} />
                  <div className="daily-bar cache" style={{ width: `${((day.cached_tokens || 0) / maxDailyTokens) * 100}%` }} title={`Cache: ${day.cached_tokens}`} />
                  <div className="daily-bar completion" style={{ width: `${((day.completion_tokens || 0) / maxDailyTokens) * 100}%` }} title={`Completion: ${day.completion_tokens}`} />
                </div>
                <div className="daily-value">
                  <div>{formatNumber(day.total_tokens)}</div>
                  {day.cost_usd > 0 && <div className="daily-cost">{formatCurrency(day.cost_usd)}</div>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <hr className="section-divider" />

      <div className="usage-sections-row">
        <div className="usage-section">
          <h3>By Provider</h3>
          <div className="usage-table">
            {byProvider.length === 0 ? <div className="empty-state">No data</div> : (
              <table>
                <thead><tr><th>Provider</th><th>Tokens</th><th>Cost</th><th>Reqs</th></tr></thead>
                <tbody>
                  {byProvider.map((item, i) => (
                    <tr key={i}>
                      <td>{item.provider_name}</td>
                      <td>{formatNumber((item.total_tokens || 0) + (item.cached_tokens || 0))}</td>
                      <td>{formatCurrency(item.cost_usd)}</td>
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
            {byModel.length === 0 ? <div className="empty-state">No data</div> : (
              <table>
                <thead><tr><th>Model</th><th>Tokens</th><th>Cost</th><th>Reqs</th></tr></thead>
                <tbody>
                  {byModel.map((item, i) => (
                    <tr key={i}>
                      <td><span className="model-provider">{item.provider_name}/</span>{item.model_id}</td>
                      <td>{formatNumber((item.total_tokens || 0) + (item.cached_tokens || 0))}</td>
                      <td>{formatCurrency(item.cost_usd)}</td>
                      <td>{item.request_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );

  // ===== Efficiency Tab =====
  const renderEfficiency = () => {
    if (!efficiency) return <div className="empty-state">No efficiency data</div>;
    return (
      <>
        <div className="efficiency-grid">
          <div className="eff-card">
            <div className="eff-icon"><Database size={20} /></div>
            <div className="eff-value">{formatPercent(efficiency.cache_hit_rate)}</div>
            <div className="eff-label">Cache Hit Rate</div>
            <div className="eff-sub">{formatNumber(efficiency.total_cached_tokens)} cached / {formatNumber(efficiency.total_tokens)} total</div>
          </div>
          <div className="eff-card">
            <div className="eff-icon"><Timer size={20} /></div>
            <div className="eff-value">{formatDuration(efficiency.avg_response_time_ms)}</div>
            <div className="eff-label">Avg Latency</div>
            <div className="eff-sub">Per request</div>
          </div>
          <div className="eff-card">
            <div className="eff-icon"><Zap size={20} /></div>
            <div className="eff-value">{formatNumber(efficiency.avg_tokens_per_second)}/s</div>
            <div className="eff-label">Tokens/sec</div>
            <div className="eff-sub">Throughput</div>
          </div>
          <div className="eff-card">
            <div className="eff-icon"><AlertTriangle size={20} /></div>
            <div className="eff-value">{formatPercent(efficiency.error_rate)}</div>
            <div className="eff-label">Error Rate</div>
            <div className="eff-sub">{efficiency.error_count} / {efficiency.request_count} requests</div>
          </div>
          <div className="eff-card">
            <div className="eff-icon"><Wallet size={20} /></div>
            <div className="eff-value">{formatCurrency(efficiency.cost_per_1k_tokens)}</div>
            <div className="eff-label">Cost / 1K tokens</div>
            <div className="eff-sub">Average across all calls</div>
          </div>
          <div className="eff-card">
            <div className="eff-icon"><DollarSign size={20} /></div>
            <div className="eff-value">{formatCurrency(efficiency.cost_per_request)}</div>
            <div className="eff-label">Cost / Request</div>
            <div className="eff-sub">Average across all calls</div>
          </div>
        </div>

        <hr className="section-divider" />

        <div className="usage-section">
          <h3><Layers size={14} /> Request Type Breakdown</h3>
          <div className="usage-table">
            {byRequestType.length === 0 ? <div className="empty-state">No data</div> : (
              <table>
                <thead>
                  <tr>
                    <th>Type</th><th>Tokens</th><th>Cost</th><th>Reqs</th><th>% of Total</th>
                  </tr>
                </thead>
                <tbody>
                  {byRequestType.map((item, i) => {
                    const pct = globalUsage.total_tokens > 0 ? ((item.total_tokens || 0) / globalUsage.total_tokens) : 0;
                    return (
                      <tr key={i}>
                        <td><span className={`type-badge ${item.request_type}`}>{item.request_type}</span></td>
                        <td>{formatNumber((item.total_tokens || 0) + (item.cached_tokens || 0))}</td>
                        <td>{formatCurrency(item.cost_usd)}</td>
                        <td>{item.request_count}</td>
                        <td>
                          <div className="pct-bar">
                            <div className="pct-fill" style={{ width: `${pct * 100}%` }} />
                            <span>{formatPercent(pct)}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </>
    );
  };

  // ===== Cost Tab =====
  const renderCost = () => {
    const totalCost = costTrend.reduce((sum, d) => sum + (d.cost_usd || 0), 0);
    const maxCost = Math.max(...costTrend.map(d => d.cost_usd || 0), 0.01);

    return (
      <>
        <div className="usage-summary">
          <div className="summary-card cost">
            <div className="card-icon"><Wallet size={24} /></div>
            <div className="card-content">
              <div className="card-label">Total Cost (30d)</div>
              <div className="card-value">{formatCurrency(totalCost)}</div>
              <div className="card-sub">{costTrend.length} periods</div>
            </div>
          </div>
          <div className="summary-card">
            <div className="card-icon"><TrendingUp size={24} /></div>
            <div className="card-content">
              <div className="card-label">Avg Daily</div>
              <div className="card-value">{formatCurrency(totalCost / Math.max(costTrend.length, 1))}</div>
              <div className="card-sub">Per day</div>
            </div>
          </div>
          <div className="summary-card">
            <div className="card-icon"><AlertTriangle size={24} /></div>
            <div className="card-content">
              <div className="card-label">Peak Day</div>
              <div className="card-value">{formatCurrency(maxCost)}</div>
              <div className="card-sub">Highest spend</div>
            </div>
          </div>
        </div>

        <hr className="section-divider" />

        <div className="usage-section">
          <div className="section-header">
            <h3><DollarSign size={14} /> Cost Trend</h3>
            <select value={costGranularity} onChange={(e) => setCostGranularity(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="hourly">Hourly (today)</option>
            </select>
          </div>
          <div className="daily-chart">
            {costTrend.length === 0 ? (
              <div className="empty-state">No cost data available</div>
            ) : (
              costTrend.map((day, index) => {
                const height = maxCost > 0 ? ((day.cost_usd || 0) / maxCost) * 100 : 0;
                return (
                  <div key={index} className="daily-bar-container">
                    <div className="daily-label">{day.period}</div>
                    <div className="daily-bar-wrapper">
                      <div className="daily-bar cost-bar" style={{ width: `${height}%` }} title={`Cost: ${formatCurrency(day.cost_usd)}`} />
                    </div>
                    <div className="daily-value">
                      <div>{formatCurrency(day.cost_usd)}</div>
                      <div className="daily-cost">{day.request_count} reqs</div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </>
    );
  };

  // ===== Models Tab =====
  const renderModels = () => (
    <div className="usage-section">
      <h3><Server size={14} /> Model Comparison (30 days)</h3>
      <div className="usage-table model-table">
        {modelComparison.length === 0 ? <div className="empty-state">No model data</div> : (
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Provider</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Reqs</th>
                <th>Error Rate</th>
                <th>Avg Latency</th>
                <th>Cost/1K</th>
              </tr>
            </thead>
            <tbody>
              {modelComparison.map((m, i) => (
                <tr key={i}>
                  <td className="model-name">{m.model_id}</td>
                  <td>{m.provider_name}</td>
                  <td>{formatNumber(m.total_tokens)}</td>
                  <td>{formatCurrency(m.cost_usd)}</td>
                  <td>{m.request_count}</td>
                  <td>
                    <span className={m.error_rate > 0.05 ? 'error-high' : m.error_rate > 0 ? 'error-low' : ''}>
                      {formatPercent(m.error_rate)}
                    </span>
                  </td>
                  <td>{formatDuration(m.avg_response_time_ms)}</td>
                  <td>{formatCurrency(m.cost_per_1k_tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );

  // ===== Heatmap Tab =====
  const renderHeatmap = () => {
    const { calendar, hourly } = heatmap;
    const maxTokens = calendar.max_tokens || 1;

    // Build calendar grid: group by month, each month is a grid
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const weekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const hourLabels = Array.from({ length: 24 }, (_, i) => i);

    const getColor = (value, max) => {
      if (!max || max <= 0) return 'var(--surface-3)';
      const ratio = value / max;
      if (ratio === 0) return 'var(--surface-3)';
      if (ratio < 0.15) return 'rgba(59, 130, 246, 0.15)';
      if (ratio < 0.30) return 'rgba(59, 130, 246, 0.30)';
      if (ratio < 0.50) return 'rgba(59, 130, 246, 0.50)';
      if (ratio < 0.70) return 'rgba(59, 130, 246, 0.70)';
      return 'rgba(59, 130, 246, 0.90)';
    };

    // Group calendar data by month for display
    const byMonth = {};
    calendar.data.forEach(d => {
      const [y, m] = d.date.split('-');
      const key = `${y}-${m}`;
      if (!byMonth[key]) byMonth[key] = [];
      byMonth[key].push(d);
    });

    const monthKeys = Object.keys(byMonth).sort();

    return (
      <>
        <div className="usage-section">
          <h3><Flame size={14} /> Usage Calendar</h3>
          <div className="calendar-heatmap">
            {monthKeys.map(monthKey => {
              const [year, month] = monthKey.split('-');
              const days = byMonth[monthKey];
              const monthStart = new Date(Number(year), Number(month) - 1, 1);
              const startWeekday = monthStart.getDay(); // 0 = Sunday

              return (
                <div key={monthKey} className="calendar-month">
                  <div className="calendar-month-label">{monthNames[Number(month) - 1]} {year}</div>
                  <div className="calendar-grid">
                    {weekdayLabels.map((label, i) => (
                      <div key={i} className="calendar-weekday-label">{label}</div>
                    ))}
                    {Array.from({ length: startWeekday }).map((_, i) => (
                      <div key={`pad-${i}`} className="calendar-day empty" />
                    ))}
                    {days.map((day, i) => (
                      <div
                        key={i}
                        className="calendar-day"
                        style={{ background: getColor(day.total_tokens, maxTokens) }}
                        title={`${day.date}: ${formatNumber(day.total_tokens)} tokens, ${formatCurrency(day.cost_usd)}`}
                      >
                        <span className="calendar-day-num">{day.date.split('-')[2]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="calendar-legend">
            <span className="legend-label">Less</span>
            {[
              'var(--surface-3)',
              'rgba(59, 130, 246, 0.15)',
              'rgba(59, 130, 246, 0.30)',
              'rgba(59, 130, 246, 0.50)',
              'rgba(59, 130, 246, 0.70)',
              'rgba(59, 130, 246, 0.90)',
            ].map((color, i) => (
              <div key={i} className="legend-box" style={{ background: color }} />
            ))}
            <span className="legend-label">More</span>
          </div>
        </div>

        <hr className="section-divider" />

        <div className="usage-section">
          <h3><Clock size={14} /> Hourly Usage Pattern</h3>
          <div className="hourly-heatmap">
            <div className="hourly-header">
              <div className="hourly-cell corner" />
              {hourLabels.map(h => (
                <div key={h} className="hourly-cell header">{h}</div>
              ))}
            </div>
            {hourly.matrix.map((row, wd) => (
              <div key={wd} className="hourly-row">
                <div className="hourly-cell row-label">{weekdayLabels[wd]}</div>
                {row.map((value, hr) => (
                  <div
                    key={hr}
                    className="hourly-cell"
                    style={{ background: getColor(value, hourly.max_tokens || 1) }}
                    title={`${weekdayLabels[wd]} ${hr}:00: ${formatNumber(value)} tokens`}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </>
    );
  };

  return (
    <div className="panel token-usage-panel">
      <div className="window-header">
        <WindowDots />
        <span className="window-title">TOKEN USAGE STATISTICS</span>
        <button className="refresh-btn" onClick={fetchAll} disabled={loading} title="Refresh">
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="tab-bar">
        {TAB_CONFIG.map(tab => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="panel-content">
        {loading && <div className="loading-inline">Loading...</div>}
        {!loading && activeTab === 'overview' && renderOverview()}
        {!loading && activeTab === 'efficiency' && renderEfficiency()}
        {!loading && activeTab === 'cost' && renderCost()}
        {!loading && activeTab === 'models' && renderModels()}
        {!loading && activeTab === 'heatmap' && renderHeatmap()}
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

        .window-header {
          display: flex;
          align-items: center;
          gap: var(--s-3);
          padding: var(--s-3) var(--s-4);
          border-bottom: 1px solid var(--border);
          flex-shrink: 0;
        }

        .window-title {
          flex: 1;
          font-size: 13px;
          font-weight: 600;
          color: var(--text);
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

        .tab-bar {
          display: flex;
          gap: var(--s-1);
          padding: var(--s-2) var(--s-4);
          background: var(--surface);
          border-bottom: 1px solid var(--board);
          flex-shrink: 0;
        }

        .tab-btn {
          display: flex;
          align-items: center;
          gap: var(--s-1);
          padding: var(--s-2) var(--s-3);
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: 6px;
          color: var(--text-2);
          font-family: var(--font-sans);
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .tab-btn:hover {
          background: var(--border);
          color: var(--text);
        }

        .tab-btn.active {
          background: var(--accent);
          border-color: var(--accent);
          color: var(--text-invert);
        }

        .panel-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--s-5);
        }

        .loading-inline {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--s-6);
          color: var(--text-2);
          font-size: 13px;
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

        .summary-card.total .card-icon { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .summary-card.prompt .card-icon { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .summary-card.cache .card-icon { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
        .summary-card.completion .card-icon { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
        .summary-card.subagent .card-icon { background: rgba(210, 105, 30, 0.2); color: #d2691e; }
        .summary-card.cost .card-icon { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .summary-card.latency .card-icon { background: rgba(99, 102, 241, 0.2); color: #6366f1; }

        .card-icon {
          width: 48px;
          height: 48px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .card-content {
          flex: 1;
          min-width: 0;
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
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .card-sub {
          font-size: 11px;
          color: var(--text-3);
          margin-top: 4px;
        }

        .section-divider {
          border: none;
          height: 1px;
          background-color: var(--border);
          margin: var(--s-4) 0;
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
          grid-template-columns: 100px 1fr 90px;
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

        .daily-bar.prompt { background: #10b981; }
        .daily-bar.cache { background: #8b5cf6; }
        .daily-bar.completion { background: #f59e0b; }
        .daily-bar.cost-bar { background: #22c55e; }

        .daily-value {
          font-size: 11px;
          color: var(--text);
          text-align: right;
          font-family: var(--font-mono);
          line-height: 1.4;
        }

        .daily-cost {
          font-size: 10px;
          color: var(--text-3);
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

        /* Efficiency */
        .efficiency-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: var(--s-4);
          margin-bottom: var(--s-4);
        }

        @media (max-width: 900px) {
          .efficiency-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        .eff-card {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: var(--s-4);
          text-align: center;
        }

        .eff-icon {
          width: 40px;
          height: 40px;
          border-radius: 8px;
          background: rgba(59, 130, 246, 0.1);
          color: #3b82f6;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto var(--s-2);
        }

        .eff-value {
          font-size: 22px;
          font-weight: 700;
          color: var(--text);
        }

        .eff-label {
          font-size: 12px;
          color: var(--text-2);
          margin-top: 4px;
        }

        .eff-sub {
          font-size: 11px;
          color: var(--text-3);
          margin-top: 2px;
        }

        .type-badge {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 500;
          text-transform: uppercase;
          background: var(--surface-3);
          color: var(--text-2);
        }

        .type-badge.chat { background: rgba(16, 185, 129, 0.15); color: #10b981; }
        .type-badge.subagent { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
        .type-badge.compression { background: rgba(139, 92, 246, 0.15); color: #8b5cf6; }
        .type-badge.observation { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }

        .pct-bar {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .pct-fill {
          height: 6px;
          background: #3b82f6;
          border-radius: 3px;
          min-width: 2px;
          transition: width 0.3s ease;
        }

        .error-high { color: #ef4444; font-weight: 600; }
        .error-low { color: #f59e0b; }

        .model-name {
          font-family: var(--font-mono);
          font-size: 11px;
        }

        .model-table th,
        .model-table td {
          font-size: 11px;
          padding: var(--s-2);
        }

        /* Calendar Heatmap */
        .calendar-heatmap {
          display: flex;
          flex-wrap: nowrap;
          gap: var(--s-5);
          padding: var(--s-3);
          overflow-x: auto;
        }

        .calendar-month {
          flex: 0 0 auto;
        }

        .calendar-month-label {
          font-size: 12px;
          font-weight: 600;
          color: var(--text);
          margin-bottom: var(--s-2);
          font-family: var(--font-mono);
        }

        .calendar-grid {
          display: grid;
          grid-template-columns: repeat(7, 28px);
          gap: 3px;
        }

        .calendar-weekday-label {
          font-size: 10px;
          color: var(--text-3);
          text-align: center;
          line-height: 20px;
        }

        .calendar-day {
          width: 28px;
          height: 28px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          cursor: pointer;
          transition: transform 0.1s ease;
        }

        .calendar-day:hover {
          transform: scale(1.15);
          z-index: 1;
          box-shadow: 0 0 4px rgba(0,0,0,0.2);
        }

        .calendar-day.empty {
          background: transparent !important;
        }

        .calendar-day-num {
          font-size: 10px;
          color: var(--text-2);
        }

        .calendar-legend {
          display: flex;
          align-items: center;
          gap: 4px;
          margin-top: var(--s-3);
          padding-left: var(--s-3);
        }

        .legend-label {
          font-size: 11px;
          color: var(--text-3);
        }

        .legend-box {
          width: 12px;
          height: 12px;
          border-radius: 2px;
        }

        /* Hourly Heatmap */
        .hourly-heatmap {
          overflow-x: auto;
          padding: var(--s-2);
        }

        .hourly-header {
          display: flex;
        }

        .hourly-row {
          display: flex;
        }

        .hourly-cell {
          width: 36px;
          height: 28px;
          border-radius: 3px;
          margin: 1px;
          flex-shrink: 0;
          cursor: pointer;
          transition: transform 0.1s ease;
        }

        .hourly-cell:hover {
          transform: scale(1.2);
          z-index: 1;
          box-shadow: 0 0 4px rgba(0,0,0,0.2);
        }

        .hourly-cell.corner {
          width: 48px;
          background: transparent;
        }

        .hourly-cell.header {
          font-size: 10px;
          color: var(--text-3);
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
        }

        .hourly-cell.row-label {
          width: 48px;
          font-size: 11px;
          color: var(--text-2);
          display: flex;
          align-items: center;
          justify-content: flex-end;
          padding-right: 8px;
          background: transparent;
        }
      `}</style>
    </div>
  );
};

export default TokenUsagePanel;
