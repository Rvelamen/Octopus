import { Cpu, Plug, Wrench, BarChart3 } from 'lucide-react';

export default function MCPStatusPanel({ status }) {
  if (!status) {
    return (
      <div className="mcp-empty">
        <span>Loading MCP status...</span>
      </div>
    );
  }

  return (
    <div className="mcp-status-grid">
      <div className="mcp-status-card">
        <div className="status-header">
          <Cpu size={14} />
          <span className="status-title">SYSTEM</span>
        </div>
        <div className="status-content">
          <div className="status-row">
            <span className="status-label">Enabled:</span>
            <span className={`status-value ${status.enabled ? 'enabled' : 'disabled'}`}>
              {status.enabled ? 'YES' : 'NO'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-label">Initialized:</span>
            <span className={`status-value ${status.initialized ? 'enabled' : 'disabled'}`}>
              {status.initialized ? 'YES' : 'NO'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-label">Running:</span>
            <span className={`status-value ${status.running ? 'enabled' : 'disabled'}`}>
              {status.running ? 'YES' : 'NO'}
            </span>
          </div>
        </div>
      </div>

      <div className="mcp-status-card">
        <div className="status-header">
          <Plug size={14} />
          <span className="status-title">CONNECTIONS</span>
        </div>
        <div className="status-content">
          <div className="status-row">
            <span className="status-label">Total:</span>
            <span className="status-value">{status.connections?.total || 0}</span>
          </div>
          <div className="status-row">
            <span className="status-label">Connected:</span>
            <span className="status-value enabled">{status.connections?.connected || 0}</span>
          </div>
        </div>
      </div>

      <div className="mcp-status-card">
        <div className="status-header">
          <Wrench size={14} />
          <span className="status-title">TOOLS</span>
        </div>
        <div className="status-content">
          <div className="status-row">
            <span className="status-label">Total:</span>
            <span className="status-value">{status.tools?.total || 0}</span>
          </div>
          <div className="status-row">
            <span className="status-label">Enabled:</span>
            <span className="status-value enabled">{status.tools?.enabled || 0}</span>
          </div>
        </div>
      </div>

      <div className="mcp-status-card wide">
        <div className="status-header">
          <BarChart3 size={14} />
          <span className="status-title">METRICS</span>
        </div>
        <div className="status-content">
          <div className="status-row">
            <span className="status-label">Total Requests:</span>
            <span className="status-value">{status.metrics?.total_requests || 0}</span>
          </div>
          <div className="status-row">
            <span className="status-label">Successful:</span>
            <span className="status-value enabled">{status.metrics?.successful_requests || 0}</span>
          </div>
          <div className="status-row">
            <span className="status-label">Failed:</span>
            <span className="status-value disabled">{status.metrics?.failed_requests || 0}</span>
          </div>
          <div className="status-row">
            <span className="status-label">Avg Latency:</span>
            <span className="status-value">{status.metrics?.average_latency_ms?.toFixed(2) || 0} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
}
