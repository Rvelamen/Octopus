import React from 'react';
import { Plus, Check, X } from 'lucide-react';
import { InputField } from '@components/forms';

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
                  rows={14}
                  spellCheck={false}
                  placeholder={`{\n  "mcpServers": {\n    "amap-maps": {\n      "url": "https://mcp.amap.com/mcp?key=YOUR_KEY"\n    },\n    "stdio-server": {\n      "command": "npx",\n      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]\n    }\n  }\n}`}
                />
              </div>
            </div>
          ) : (
            <div className="form-mode-content">
              <InputField
                label="Server Name"
                value={newServer.name}
                onChange={(v) => onNewServerChange({ ...newServer, name: v })}
                placeholder="例如: filesystem, github, slack"
                disabled={isEditMode}
              />
              <InputField
                label="Command"
                value={newServer.command}
                onChange={(v) => onNewServerChange({ ...newServer, command: v })}
                placeholder="例如: npx, node, python"
              />
              <div className="form-field">
                <label className="form-label">Arguments (空格或逗号分隔)</label>
                <input
                  type="text"
                  value={newServer.args}
                  onChange={(e) => onNewServerChange({ ...newServer, args: e.target.value })}
                  className="pixel-input form-input"
                  placeholder="-y @modelcontextprotocol/server-filesystem /path"
                />
              </div>
              <div className="form-field">
                <label className="form-label">Environment Variables (JSON 或 KEY=value 每行)</label>
                <textarea
                  value={newServer.env}
                  onChange={(e) => onNewServerChange({ ...newServer, env: e.target.value })}
                  className="pixel-input form-input"
                  rows={4}
                  placeholder={`{ "API_KEY": "your-key" }\n或\nAPI_KEY=your-key\nSECRET=xxx`}
                />
              </div>
            </div>
          )}
        </div>

        <div className="dialog-footer">
          <button className="pixel-button small secondary" onClick={onClose} disabled={isAdding}>
            <X size={14} /> Cancel
          </button>
          <button
            className={`pixel-button small ${isAdding ? 'loading' : ''}`}
            onClick={onSubmit}
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
