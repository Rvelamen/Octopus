import React, { useState, useEffect, useCallback } from 'react';
import { Server, Wrench, Activity, Plus, RefreshCw, Eye, Search, Pencil, X, Check, ChevronDown, ChevronRight, Cpu, Plug, BarChart3 } from 'lucide-react';
import WindowDots from '../WindowDots';
import { ConfigCard, DynamicItemCard } from '../config';
import { SwitchField, InputField } from '../forms';
import { ToastContainer } from '../Toast';

/**
 * MCPPanel 组件 - MCP管理面板
 * 使用标准 MCP 格式: { command, args, env }
 */
function MCPPanel({ sendWSMessage }) {
  const [mcpTab, setMcpTab] = useState('servers');
  const [mcpStatus, setMcpStatus] = useState(null);
  const [servers, setServers] = useState([]);
  const [selectedServer, setSelectedServer] = useState(null);
  const [serverTools, setServerTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedTools, setExpandedTools] = useState(new Set());

  // Discover loading state
  const [discoveringServer, setDiscoveringServer] = useState(null);

  // Toast notifications state
  const [toasts, setToasts] = useState([]);

  // Add/Edit server dialog state
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editingServerName, setEditingServerName] = useState(null);
  const [isJsonMode, setIsJsonMode] = useState(false);

  // New server form state (标准 MCP 格式)
  const [newServer, setNewServer] = useState({
    name: '',
    command: '',
    args: '',
    env: ''
  });

  // JSON input state
  const [jsonInput, setJsonInput] = useState('');

  // MCP tabs
const MCP_TABS = [
  { key: 'servers', label: 'SERVERS', Icon: Server },
  { key: 'tools', label: 'TOOLS', Icon: Wrench },
  { key: 'status', label: 'STATUS', Icon: Activity },
];

  // Toast helper functions
  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // 加载MCP状态
  const loadMCPStatus = useCallback(async () => {
    try {
      const response = await sendWSMessage('mcp_get_status', {}, 5000);
      setMcpStatus(response.data);
    } catch (err) {
      console.error('Failed to load MCP status:', err);
      setError('Failed to load MCP status: ' + err.message);
    }
  }, [sendWSMessage]);

  // 加载服务器列表
  const loadServers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await sendWSMessage('mcp_get_servers', {}, 5000);
      setServers(response.data?.servers || []);
    } catch (err) {
      console.error('Failed to load MCP servers:', err);
      setError('Failed to load MCP servers: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // 加载服务器工具
  const loadServerTools = useCallback(async (serverName, switchTab = false) => {
    if (!serverName) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('mcp_get_server_tools', { server_name: serverName }, 5000);
      setServerTools(response.data?.tools || []);
      // 合并服务器信息，保留连接状态
      const serverInfo = response.data?.server;
      if (serverInfo) {
        // 从servers列表中获取最新的连接状态
        const currentServer = servers.find(s => s.name === serverName);
        setSelectedServer({
          ...serverInfo,
          connected: currentServer?.connected || false,
          protocol: currentServer?.protocol || 'stdio'
        });
      }
      // 如果需要，切换到TOOLS标签页
      if (switchTab) {
        setMcpTab('tools');
      }
    } catch (err) {
      console.error('Failed to load server tools:', err);
      setError('Failed to load server tools: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, servers]);

  // 初始加载
  useEffect(() => {
    loadMCPStatus();
    loadServers();
  }, [loadMCPStatus, loadServers]);

  // 更新服务器启用状态
  const toggleServer = async (serverName, enabled) => {
    const server = servers.find(s => s.name === serverName);
    if (server && server.enabled === enabled) {
      return;
    }
    
    try {
      addToast(`${enabled ? 'Enabling' : 'Disabling'} server "${serverName}"...`, 'info', 2000);
      const response = await sendWSMessage('mcp_update_server', { name: serverName, enabled }, 5000);
      
      if (response.data?.success) {
        await loadServers();
        await loadMCPStatus();
        addToast(`Server "${serverName}" ${enabled ? 'enabled' : 'disabled'} successfully`, 'success', 3000);
      } else {
        throw new Error(response.data?.error || 'Update failed');
      }
    } catch (err) {
      setError('Failed to update server: ' + err.message);
      addToast(`Failed to update server: ${err.message}`, 'error', 5000);
      await loadServers();
    }
  };

  // 删除服务器
  const deleteServer = async (serverName) => {
    try {
      await sendWSMessage('mcp_delete_server', { name: serverName }, 5000);
      await loadServers();
      await loadMCPStatus();
      if (selectedServer?.name === serverName) {
        setSelectedServer(null);
        setServerTools([]);
      }
    } catch (err) {
      setError('Failed to delete server: ' + err.message);
    }
  };

  // 打开添加对话框
  const openAddDialog = () => {
    setIsEditMode(false);
    setEditingServerName(null);
    setNewServer({
      name: '',
      command: '',
      args: '',
      env: ''
    });
    setJsonInput(JSON.stringify({
      "server-name": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"],
        "env": {
          "API_KEY": "your-api-key"
        }
      }
    }, null, 2));
    setIsJsonMode(false);
    setShowAddDialog(true);
  };

  // 打开编辑对话框
  const openEditDialog = (server) => {
    setIsEditMode(true);
    setEditingServerName(server.name);
    setNewServer({
      name: server.name,
      command: server.command || '',
      args: server.args ? server.args.join(' ') : '',
      env: server.env ? JSON.stringify(server.env, null, 2) : ''
    });
    setJsonInput(JSON.stringify({
      [server.name]: {
        command: server.command || '',
        args: server.args || [],
        env: server.env || {}
      }
    }, null, 2));
    setIsJsonMode(false);
    setShowAddDialog(true);
  };

  // 解析 args 字符串为数组
  const parseArgs = (argsStr) => {
    if (!argsStr.trim()) return [];
    // 支持逗号分隔或空格分隔
    if (argsStr.includes(',')) {
      return argsStr.split(',').map(s => s.trim()).filter(Boolean);
    }
    return argsStr.split(/\s+/).filter(Boolean);
  };

  // 解析 env 字符串为对象
  const parseEnv = (envStr) => {
    if (!envStr.trim()) return {};
    try {
      return JSON.parse(envStr);
    } catch {
      // 尝试 KEY=value 格式
      const env = {};
      envStr.split(/\n|;/).forEach(line => {
        const match = line.match(/^([^=]+)=(.*)$/);
        if (match) {
          env[match[1].trim()] = match[2].trim();
        }
      });
      return env;
    }
  };

  // 检测服务器类型
  const detectServerType = (serverData) => {
    if (serverData.url && !serverData.command) {
      return 'http';
    }
    return 'stdio';
  };

  // 添加/编辑服务器
  const doAddServer = async () => {
    let serverData;

    if (isJsonMode) {
      try {
        const parsed = JSON.parse(jsonInput);
        // 标准格式: { "server-name": { command, args, env } }
        const serverName = Object.keys(parsed)[0];
        const serverConfig = parsed[serverName];
        serverData = {
          name: serverName,
          ...serverConfig
        };
      } catch (err) {
        setError('Invalid JSON: ' + err.message);
        return;
      }
    } else {
      if (!newServer.name.trim() || !newServer.command.trim()) {
        setError('Server name and command are required');
        return;
      }
      serverData = {
        name: newServer.name,
        command: newServer.command,
        args: parseArgs(newServer.args),
        env: parseEnv(newServer.env)
      };
    }

    if (!serverData.name || !serverData.name.trim()) {
      setError('Server name is required');
      return;
    }

    // 检测服务器类型并验证必需字段
    const serverType = detectServerType(serverData);
    if (serverType === 'stdio') {
      if (!serverData.command || !serverData.command.trim()) {
        setError('Command is required for stdio servers');
        return;
      }
      // 设置默认协议
      if (!serverData.protocol) {
        serverData.protocol = 'stdio';
      }
    } else if (serverType === 'http') {
      if (!serverData.url || !serverData.url.trim()) {
        setError('URL is required for HTTP/SSE/WebSocket servers');
        return;
      }
      // 设置默认协议为 sse（如果没有指定）
      if (!serverData.protocol) {
        serverData.protocol = 'sse';
      }
    }

    try {
      if (isEditMode && editingServerName) {
        // 编辑模式：先删除旧服务器，再添加新配置
        await sendWSMessage('mcp_delete_server', { name: editingServerName }, 5000);
      }
      const response = await sendWSMessage('mcp_add_server', serverData, 30000);
      const result = response.data || {};
      
      // 更新服务器列表和状态
      await loadServers();
      await loadMCPStatus();
      
      // 如果有工具返回，自动加载工具列表并切换到工具标签页
      if (result.tools && result.tools.length > 0) {
        setSelectedServer({
          ...result.server,
          connected: result.connected || false,
          protocol: serverData.protocol || 'stdio'
        });
        setServerTools(result.tools);
        setMcpTab('tools'); // 切换到工具标签页
        addToast(`Successfully discovered ${result.discovered_count || result.tools.length} tool(s)`, 'success', 3000);
      } else if (result.connected) {
        // 连接成功但没有工具，尝试加载工具列表
        await loadServerTools(serverData.name, true);
        setMcpTab('tools');
      }
      
      // 关闭对话框
      setShowAddDialog(false);
    } catch (err) {
      setError('Failed to add server: ' + err.message);
    }
  };

  // Reconnect to server
  const reconnectServer = async (serverName) => {
    addToast(`Reconnecting to "${serverName}"...`, 'info', 2000);
    try {
      const response = await sendWSMessage('mcp_reconnect_server', { name: serverName }, 30000);
      if (response.data?.success) {
        addToast(`Successfully reconnected to "${serverName}"`, 'success', 3000);
        await loadServers();
        await loadMCPStatus();
      } else {
        addToast(`Failed to reconnect to "${serverName}": ${response.data?.error || 'Unknown error'}`, 'error', 5000);
      }
    } catch (err) {
      addToast(`Failed to reconnect to "${serverName}": ${err.message}`, 'error', 5000);
    }
  };

  // 发现工具
  const discoverTools = async (serverName) => {
    setDiscoveringServer(serverName);
    addToast(`Discovering tools from "${serverName}"...`, 'info', 2000);
    try {
      const response = await sendWSMessage('mcp_discover_tools', { server_name: serverName }, 30000);
      const discoveredCount = response.data?.discovered_count || 0;
      await loadServerTools(serverName);
      await loadMCPStatus();
      addToast(
        discoveredCount > 0
          ? `Successfully discovered ${discoveredCount} tool(s) from "${serverName}"`
          : `No new tools discovered from "${serverName}"`,
        discoveredCount > 0 ? 'success' : 'info',
        4000
      );
    } catch (err) {
      const errorMsg = err.message || 'Unknown error';
      setError('Failed to discover tools: ' + errorMsg);
      addToast(`Failed to discover tools: ${errorMsg}`, 'error', 5000);
    } finally {
      setDiscoveringServer(null);
    }
  };

  // 更新工具启用状态
  const toggleTool = async (toolName, serverName, enabled) => {
    try {
      await sendWSMessage('mcp_update_tool', { name: toolName, server_name: serverName, enabled }, 5000);
      if (selectedServer) {
        await loadServerTools(selectedServer.name);
      }
      await loadMCPStatus();
    } catch (err) {
      setError('Failed to update tool: ' + err.message);
    }
  };

  // 切换tool card展开/折叠状态
  const toggleToolExpanded = (toolName) => {
    setExpandedTools(prev => {
      const newSet = new Set(prev);
      if (newSet.has(toolName)) {
        newSet.delete(toolName);
      } else {
        newSet.add(toolName);
      }
      return newSet;
    });
  };

  // 渲染状态面板
  const renderStatus = () => {
    if (!mcpStatus) {
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
              <span className={`status-value ${mcpStatus.enabled ? 'enabled' : 'disabled'}`}>
                {mcpStatus.enabled ? 'YES' : 'NO'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">Initialized:</span>
              <span className={`status-value ${mcpStatus.initialized ? 'enabled' : 'disabled'}`}>
                {mcpStatus.initialized ? 'YES' : 'NO'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">Running:</span>
              <span className={`status-value ${mcpStatus.running ? 'enabled' : 'disabled'}`}>
                {mcpStatus.running ? 'YES' : 'NO'}
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
              <span className="status-value">{mcpStatus.connections?.total || 0}</span>
            </div>
            <div className="status-row">
              <span className="status-label">Connected:</span>
              <span className="status-value enabled">{mcpStatus.connections?.connected || 0}</span>
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
              <span className="status-value">{mcpStatus.tools?.total || 0}</span>
            </div>
            <div className="status-row">
              <span className="status-label">Enabled:</span>
              <span className="status-value enabled">{mcpStatus.tools?.enabled || 0}</span>
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
              <span className="status-value">{mcpStatus.metrics?.total_requests || 0}</span>
            </div>
            <div className="status-row">
              <span className="status-label">Successful:</span>
              <span className="status-value enabled">{mcpStatus.metrics?.successful_requests || 0}</span>
            </div>
            <div className="status-row">
              <span className="status-label">Failed:</span>
              <span className="status-value disabled">{mcpStatus.metrics?.failed_requests || 0}</span>
            </div>
            <div className="status-row">
              <span className="status-label">Avg Latency:</span>
              <span className="status-value">{mcpStatus.metrics?.average_latency_ms?.toFixed(2) || 0} ms</span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // 渲染服务器列表（使用 DynamicItemCard 样式）
  const renderServers = () => {
    return (
      <ConfigCard
        title="MCP SERVERS"
        icon={<Server size={14} />}
        actions={
          <button className="add-btn" onClick={openAddDialog} title="添加 Server">
            <Plus size={14} />
          </button>
        }
      >
        {servers.length === 0 ? (
          <div className="empty-config">
            <span>暂无 MCP Server，点击 [+] 添加</span>
          </div>
        ) : (
          <div className="dynamic-items-list">
            {servers.map((server) => (
              <DynamicItemCard
                key={server.name}
                title={server.name}
                itemKey={server.name}
                onDelete={deleteServer}
                defaultExpanded={false}
                enabled={server.enabled !== false}
                onToggleEnabled={toggleServer}
                showEnabledSwitch={true}
              >
                <div className="server-detail-content">
                  <div className="server-meta-row">
                    <span className="server-tools-badge">Tools: {server.tools?.length || 0}</span>
                    <span className={`server-status-badge ${server.connected ? 'connected' : 'disconnected'}`}>
                      {server.connected ? 'CONNECTED' : 'DISCONNECTED'}
                    </span>
                    <span className="server-protocol-badge">{server.protocol?.toUpperCase() || 'STDIO'}</span>
                  </div>
                  {server.protocol === 'stdio' || !server.protocol ? (
                    <>
                      <InputField
                        label="Command"
                        value={server.command || ''}
                        disabled={true}
                      />
                      {server.args && server.args.length > 0 && (
                        <div className="form-field">
                          <label className="form-label">Arguments</label>
                          <div className="args-display">
                            {server.args.map((arg, idx) => (
                              <span key={idx} className="arg-tag">{arg}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <InputField
                        label="URL"
                        value={server.url || ''}
                        disabled={true}
                      />
                      <InputField
                        label="Protocol"
                        value={server.protocol || ''}
                        disabled={true}
                      />
                    </>
                  )}
                  {server.env && Object.keys(server.env).length > 0 && (
                    <div className="form-field">
                      <label className="form-label">Environment Variables</label>
                      <div className="env-display">
                        {Object.keys(server.env).map((key) => (
                          <span key={key} className="env-tag">{key}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="server-actions-row">
                    <button
                      className="pixel-button small secondary"
                      onClick={() => loadServerTools(server.name, true)}
                      title="View Tools"
                    >
                      <Eye size={14} />
                    </button>
                    <button
                      className={`pixel-button small ${discoveringServer === server.name ? 'loading' : ''}`}
                      onClick={() => discoverTools(server.name)}
                      disabled={discoveringServer === server.name}
                      title="Discover Tools"
                    >
                      {discoveringServer === server.name ? '...' : <Search size={14} />}
                    </button>
                    <button
                      className="pixel-button small"
                      onClick={() => reconnectServer(server.name)}
                      title="Reconnect"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button
                      className="pixel-button small secondary"
                      onClick={() => openEditDialog(server)}
                      title="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                  </div>
                </div>
              </DynamicItemCard>
            ))}
          </div>
        )}
      </ConfigCard>
    );
  };

  // 渲染添加服务器对话框
  const renderAddDialog = () => {
    if (!showAddDialog) return null;

    return (
      <div className="dialog-overlay" onClick={() => setShowAddDialog(false)}>
        <div className="dialog-content mcp-add-dialog" onClick={(e) => e.stopPropagation()}>
          <div className="dialog-header">
            <div className="dialog-header-left">
              <button
                className={`mode-toggle-btn ${!isJsonMode ? 'active' : ''}`}
                onClick={() => setIsJsonMode(false)}
              >
                Form
              </button>
              <button
                className={`mode-toggle-btn ${isJsonMode ? 'active' : ''}`}
                onClick={() => setIsJsonMode(true)}
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
                  <label className="form-label">Server Config (JSON)</label>
                  <textarea
                    value={jsonInput}
                    onChange={(e) => setJsonInput(e.target.value)}
                    className="pixel-input form-input json-textarea"
                    rows={14}
                    spellCheck={false}
                    placeholder={`{
  "stdio-server": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    "env": { "API_KEY": "xxx" }
  },
  "http-server": {
    "url": "https://mcp.example.com/mcp",
    "protocol": "sse"
  }
}`}
                  />
                </div>
              </div>
            ) : (
              <div className="form-mode-content">
                <InputField
                  label="Server Name"
                  value={newServer.name}
                  onChange={(v) => setNewServer({ ...newServer, name: v })}
                  placeholder="例如: filesystem, github, slack"
                  disabled={isEditMode}
                />
                <InputField
                  label="Command"
                  value={newServer.command}
                  onChange={(v) => setNewServer({ ...newServer, command: v })}
                  placeholder="例如: npx, node, python"
                />
                <div className="form-field">
                  <label className="form-label">Arguments (空格或逗号分隔)</label>
                  <input
                    type="text"
                    value={newServer.args}
                    onChange={(e) => setNewServer({ ...newServer, args: e.target.value })}
                    className="pixel-input form-input"
                    placeholder="-y @modelcontextprotocol/server-filesystem /path"
                  />
                </div>
                <div className="form-field">
                  <label className="form-label">Environment Variables (JSON 或 KEY=value 每行)</label>
                  <textarea
                    value={newServer.env}
                    onChange={(e) => setNewServer({ ...newServer, env: e.target.value })}
                    className="pixel-input form-input"
                    rows={4}
                    placeholder={`{ "API_KEY": "your-key" }\n或\nAPI_KEY=your-key\nSECRET=xxx`}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="dialog-footer">
            <button className="pixel-button small secondary" onClick={() => setShowAddDialog(false)}>
              <X size={14} /> Cancel
            </button>
            <button className="pixel-button small" onClick={doAddServer}>
              {isEditMode ? <><Check size={14} /> Save</> : <><Plus size={14} /> Add</>}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // 渲染工具列表
  const renderTools = () => {
    return (
      <div className="mcp-tools-container">
        <div className="mcp-tools-sidebar">
          <div className="tools-sidebar-header">
            <WindowDots />
            <span>SERVERS</span>
          </div>
          <div className="tools-server-list">
            {servers.map((server) => (
              <button
                key={server.name}
                className={`tools-server-item ${selectedServer?.name === server.name ? 'active' : ''}`}
                onClick={() => loadServerTools(server.name)}
              >
                <span className="server-item-name">{server.name}</span>
                <span className={`server-item-status ${server.connected ? 'connected' : 'disconnected'}`}>
                  {server.connected ? '●' : '○'}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="mcp-tools-content">
          {selectedServer ? (
            <>
              <div className="tools-content-header">
                <WindowDots />
                <span className="tools-server-title">{selectedServer.name}</span>
                <span className={`tools-server-badge ${selectedServer.connected ? 'connected' : 'disconnected'}`}>
                  {selectedServer.connected ? 'CONNECTED' : 'DISCONNECTED'}
                </span>
              </div>
              {serverTools.length === 0 ? (
                <div className="mcp-empty">
                  <span>No tools found for this server</span>
                  <button
                className="pixel-button"
                onClick={() => discoverTools(selectedServer.name)}
              >
                <Search size={14} /> Discover
              </button>
                </div>
              ) : (
                <div className="mcp-tools-list">
                  {serverTools.map((tool) => {
                    const isExpanded = expandedTools.has(tool.name);
                    return (
                      <div key={tool.name} className={`mcp-tool-card ${isExpanded ? 'expanded' : 'collapsed'}`}>
                        <div className="tool-header">
                          <button
                            className="tool-expand-btn"
                            onClick={() => toggleToolExpanded(tool.name)}
                            title={isExpanded ? 'Collapse' : 'Expand'}
                          >
                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            <span className="tool-name">{tool.name}</span>
                          </button>
                          <SwitchField
                            label=""
                            checked={tool.enabled}
                            onChange={(v) => toggleTool(tool.name, selectedServer.name, v)}
                          />
                        </div>
                        {isExpanded && (
                          <>
                            <div className="tool-description">
                              {tool.description || 'No description'}
                            </div>
                            {tool.parameters && (
                              <div className="tool-params">
                                <span className="params-label">Parameters:</span>
                                <pre className="params-json">
                                  {JSON.stringify(tool.parameters, null, 2)}
                                </pre>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <div className="mcp-empty">
              <span>Select a server to view its tools</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderContent = () => {
    switch (mcpTab) {
      case 'servers':
        return renderServers();
      case 'tools':
        return renderTools();
      case 'status':
        return renderStatus();
      default:
        return renderServers();
    }
  };

  return (
    <div className="mcp-panel-container">
      <div className="mcp-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">MCP MANAGEMENT</span>
        </div>
        <div className="toolbar-right">
          <button
            className="pixel-button small"
            onClick={() => {
              loadMCPStatus();
              loadServers();
            }}
            disabled={loading}
          >
            {loading ? '...' : <RefreshCw size={14} />}
          </button>
        </div>
      </div>

      <div className="mcp-content-with-tabs">
        <div className="mcp-tabs">
          {MCP_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`mcp-tab ${mcpTab === tab.key ? 'active' : ''}`}
              onClick={() => setMcpTab(tab.key)}
            >
              <tab.Icon size={14} />
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </div>
        <div className="mcp-tab-content">
          {error && (
            <div className="mcp-error-banner">
              <span>{error}</span>
              <button className="error-close" onClick={() => setError(null)}><X size={14} /></button>
            </div>
          )}
          {renderContent()}
        </div>
      </div>

      {renderAddDialog()}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default MCPPanel;
