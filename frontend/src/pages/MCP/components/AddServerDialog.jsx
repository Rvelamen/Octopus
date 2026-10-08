import React from 'react';
import { Plus, Check, X } from 'lucide-react';
import { InputField } from '@components/forms';

const PROTOCOL_OPTIONS = [
  { value: 'stdio', label: 'stdio (local subprocess)' },
  { value: 'sse', label: 'sse (legacy HTTP SSE)' },
  { value: 'streamable_http', label: 'streamable_http (MCP 2025-03-26)' },
  { value: 'websocket', label: 'websocket' },
];

function parseArgs(argsStr) {
  if (!argsStr || !argsStr.trim()) return [];
  if (argsStr.includes(',')) {
    return argsStr.split(',').map((s) => s.trim()).filter(Boolean);
  }
  return argsStr.split(/\s+/).filter(Boolean);
}

function parseEnv(envStr) {
  if (!envStr || !envStr.trim()) return {};
  try {
    return JSON.parse(envStr);
  } catch {
    const env = {};
    envStr.split(/\n|;/).forEach((line) => {
      const match = line.match(/^([^=]+)=(.*)$/);
      if (match) env[match[1].trim()] = match[2].trim();
    });
    return env;
  }
}

function parseHeaders(headersStr) {
  if (!headersStr || !headersStr.trim()) return {};
  try {
    return JSON.parse(headersStr);
  } catch {
    const headers = {};
    headersStr.split(/\n|;/).forEach((line) => {
      const match = line.match(/^([^:]+):\s*(.*)$/);
      if (match) headers[match[1].trim()] = match[2].trim();
    });
    return headers;
  }
}

function isStdio(protocol) {
  return !protocol || protocol === 'stdio';
}

export default function AddServerDialog({
  show,
  isEditMode,
  isJsonMode,
  isAdding,
  newServer,
  jsonInput,
  onClose,
  onSubmit,
  onToggleJsonMode,
  onNewServerChange,
  onJsonInputChange,
}) {
  if (!show) return null;

  const protocol = newServer.protocol || 'stdio';
  const showStdioFields = isStdio(protocol);

  // Pull apart env/headers for the form; re-serialize on submit via parent
  const handleSubmit = () => {
    let payload = { ...newServer };
    if (showStdioFields) {
      payload = {
        ...payload,
        args: typeof payload.args === 'string' ? parseArgs(payload.args) : payload.args || [],
        env: typeof payload.env === 'string' ? parseEnv(payload.env) : payload.env || {},
      };
    } else {
      payload = {
        ...payload,
        headers: typeof payload.headers === 'string' ? parseHeaders(payload.headers) : payload.headers || {},
      };
    }
    onNewServerChange(payload);
    onSubmit();
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content mcp-add-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-header-left">
            <button
              className={`mode-toggle-btn ${!isJsonMode ? 'active' : ''}`}
              onClick={() => onToggleJsonMode(false)}
            >
              Form
            </button>
            <button
              className={`mode-toggle-btn ${isJsonMode ? 'active' : ''}`}
              onClick={() => onToggleJsonMode(true)}
            >
              JSON
            </button>
          </div>
          <span className="dialog-title">{isEditMode ? 'EDIT MCP SERVER' : 'ADD MCP SERVER'}</span>
        </div>

        <div className="dialog-body">
          {isJsonMode ? (
            <div className="json-mode-content">
              <div className="form-field">
                <label className="form-label">Server Config (JSON) - 标准 mcpServers 格式</label>
                <textarea
                  value={jsonInput}
                  onChange={(e) => onJsonInputChange(e.target.value)}
                  className="pixel-input form-input json-textarea"
                  rows={16}
                  spellCheck={false}
                  placeholder={`{\n  "mcpServers": {\n    "amap-maps": {\n      "type": "streamable-http",\n      "url": "https://mcp.amap.com/mcp?key=YOUR_KEY"\n    },\n    "stdio-server": {\n      "command": "npx",\n      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]\n    },\n    "remote-sse": {\n      "type": "sse",\n      "url": "https://example.com/sse",\n      "headers": { "Authorization": "Bearer ..." }\n    }\n  }\n}\n(同时支持 protocol / type 字段;streamable-http 会被自动归一化)`}
                />
              </div>
            </div>
          ) : (
            <div className="form-mode-content">
              <InputField
                label="Server Name"
                value={newServer.name}
                onChange={(v) => onNewServerChange({ ...newServer, name: v })}
                placeholder="例如: filesystem, github, amap-maps"
                disabled={isEditMode}
              />

              <div className="form-field">
                <label className="form-label">Protocol</label>
                <select
                  className="pixel-input form-input"
                  value={protocol}
                  onChange={(e) => onNewServerChange({ ...newServer, protocol: e.target.value })}
                  disabled={isEditMode}
                >
                  {PROTOCOL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {showStdioFields ? (
                <>
                  <InputField
                    label="Command"
                    value={newServer.command || ''}
                    onChange={(v) => onNewServerChange({ ...newServer, command: v })}
                    placeholder="例如: npx, node, python"
                  />
                  <div className="form-field">
                    <label className="form-label">Arguments (空格或逗号分隔)</label>
                    <input
                      type="text"
                      value={typeof newServer.args === 'string' ? newServer.args : (newServer.args || []).join(' ')}
                      onChange={(e) => onNewServerChange({ ...newServer, args: e.target.value })}
                      className="pixel-input form-input"
                      placeholder="-y @modelcontextprotocol/server-filesystem /path"
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-label">Environment Variables (JSON 或 KEY=value 每行)</label>
                    <textarea
                      value={typeof newServer.env === 'string' ? newServer.env : JSON.stringify(newServer.env || {}, null, 2)}
                      onChange={(e) => onNewServerChange({ ...newServer, env: e.target.value })}
                      className="pixel-input form-input"
                      rows={4}
                      placeholder={`{ "API_KEY": "your-key" }\n或\nAPI_KEY=your-key\nSECRET=xxx`}
                    />
                  </div>
                </>
              ) : (
                <>
                  <InputField
                    label="URL"
                    value={newServer.url || ''}
                    onChange={(v) => onNewServerChange({ ...newServer, url: v })}
                    placeholder="例如: https://mcp.example.com/mcp"
                  />
                  <InputField
                    label="Auth Token (可选,作为 Bearer 头发送)"
                    value={newServer.authToken || ''}
                    onChange={(v) => onNewServerChange({ ...newServer, authToken: v })}
                    placeholder="your-bearer-token"
                    type="password"
                  />
                  <div className="form-field">
                    <label className="form-label">Headers (JSON 或 Header: value 每行,可选)</label>
                    <textarea
                      value={typeof newServer.headers === 'string' ? newServer.headers : JSON.stringify(newServer.headers || {}, null, 2)}
                      onChange={(e) => onNewServerChange({ ...newServer, headers: e.target.value })}
                      className="pixel-input form-input"
                      rows={3}
                      placeholder={`{ "X-Api-Key": "xxx" }\n或\nX-Api-Key: xxx`}
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="dialog-footer">
          <button className="pixel-button small secondary" onClick={onClose} disabled={isAdding}>
            <X size={14} /> Cancel
          </button>
          <button
            className={`pixel-button small ${isAdding ? 'loading' : ''}`}
            onClick={handleSubmit}
            disabled={isAdding}
          >
            {isAdding ? (
              <>...</>
            ) : isEditMode ? (
              <><Check size={14} /> Save</>
            ) : (
              <><Plus size={14} /> Add</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
