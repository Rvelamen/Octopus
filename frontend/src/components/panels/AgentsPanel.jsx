import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Plus, Save, Trash2, RefreshCw, FileText, Folder } from 'lucide-react';
import WindowDots from '../WindowDots';

/**
 * AgentsPanel 组件 - Agent 管理面板
 * 用于查看和编辑 agents/<name>/SOUL.md 文件以及 agents/system/*.md 文件
 */
function AgentsPanel({ sendWSMessage }) {
  // 普通 Agents 状态
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [soulContent, setSoulContent] = useState('');

  // System Agent 状态
  const [systemFiles, setSystemFiles] = useState([]);
  const [selectedSystemFile, setSelectedSystemFile] = useState(null);
  const [systemFileContent, setSystemFileContent] = useState('');

  // 通用状态
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [newAgentName, setNewAgentName] = useState('');
  const [showNewAgentDialog, setShowNewAgentDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('agents'); // 'agents' | 'system'

  // 加载 Agent 列表
  const loadAgents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_list', {}, 5000);
      const agentList = response.data?.agents || [];
      setAgents(agentList);
      // 如果当前选中的 agent 不在列表中，清除选择
      if (selectedAgent && !agentList.find(a => a.name === selectedAgent)) {
        setSelectedAgent(null);
        setSoulContent('');
      }
    } catch (err) {
      setError('Failed to load agents: ' + err.message);
      console.error('Failed to load agents', err);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage, selectedAgent]);

  // 加载 System 文件列表
  const loadSystemFiles = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_system_files', {}, 5000);
      const files = response.data?.files || [];
      setSystemFiles(files);
      // 如果有文件且当前没有选中文件，自动选中第一个
      if (files.length > 0 && !selectedSystemFile) {
        const firstFile = files[0];
        setSelectedSystemFile(firstFile.name);
        const contentResponse = await sendWSMessage('agent_get_system_file', { filename: firstFile.name }, 5000);
        setSystemFileContent(contentResponse.data?.content || '');
      }
      // 如果当前选中的文件不在列表中，清除选择
      else if (selectedSystemFile && !files.find(f => f.name === selectedSystemFile)) {
        setSelectedSystemFile(null);
        setSystemFileContent('');
      }
    } catch (err) {
      setError('Failed to load system files: ' + err.message);
      console.error('Failed to load system files', err);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage, selectedSystemFile]);

  // 加载指定 Agent 的 SOUL.md 内容
  const loadAgentSoul = useCallback(async (agentName) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_soul', { name: agentName }, 5000);
      setSoulContent(response.data?.content || '');
      setSelectedAgent(agentName);
      // 清除 system 文件选择
      setSelectedSystemFile(null);
      setSystemFileContent('');
    } catch (err) {
      setError('Failed to load agent SOUL.md: ' + err.message);
      console.error('Failed to load agent SOUL.md', err);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage]);

  // 加载指定 System 文件内容
  const loadSystemFile = useCallback(async (filename) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_system_file', { filename }, 5000);
      setSystemFileContent(response.data?.content || '');
      setSelectedSystemFile(filename);
      // 清除 agent 选择
      setSelectedAgent(null);
      setSoulContent('');
    } catch (err) {
      setError('Failed to load system file: ' + err.message);
      console.error('Failed to load system file', err);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage]);

  // 保存 Agent 的 SOUL.md
  const saveAgentSoul = async () => {
    if (!selectedAgent) return;
    setIsSaving(true);
    setError(null);
    try {
      await sendWSMessage('agent_save_soul', {
        name: selectedAgent,
        content: soulContent
      }, 5000);
      // 刷新列表以获取可能的元数据更新
      await loadAgents();
    } catch (err) {
      setError('Failed to save: ' + err.message);
      console.error('Failed to save agent SOUL.md', err);
    } finally {
      setIsSaving(false);
    }
  };

  // 保存 System 文件
  const saveSystemFile = async () => {
    if (!selectedSystemFile) return;
    setIsSaving(true);
    setError(null);
    try {
      await sendWSMessage('agent_save_system_file', {
        filename: selectedSystemFile,
        content: systemFileContent
      }, 5000);
      // 刷新文件列表
      await loadSystemFiles();
    } catch (err) {
      setError('Failed to save: ' + err.message);
      console.error('Failed to save system file', err);
    } finally {
      setIsSaving(false);
    }
  };

  // 创建新 Agent
  const createNewAgent = async () => {
    if (!newAgentName.trim()) return;
    setIsSaving(true);
    setError(null);
    try {
      const defaultSoul = `---
name: ${newAgentName}
description: A new agent for specific tasks
tools:
  - read
  - write
  - edit
  - list
  - exec
  - action
  - message
extensions: []
provider: deepseek
model: deepseek-chat
max_iterations: 30
temperature: 0.7
---

You are a specialized agent designed to handle specific tasks.

## Your Role
- Execute tasks assigned by the main agent
- Use available tools to complete tasks
- Report back with clear, concise summaries

## Guidelines
1. Be efficient and focused in your work
2. Use tools appropriately to accomplish tasks
3. When sending messages to users, be helpful and professional
`;
      await sendWSMessage('agent_save_soul', {
        name: newAgentName.trim(),
        content: defaultSoul
      }, 5000);
      setShowNewAgentDialog(false);
      setNewAgentName('');
      await loadAgents();
      // 自动选中新创建的 agent
      await loadAgentSoul(newAgentName.trim());
    } catch (err) {
      setError('Failed to create agent: ' + err.message);
      console.error('Failed to create agent', err);
    } finally {
      setIsSaving(false);
    }
  };

  // 删除 Agent
  const deleteAgent = async (agentName) => {
    if (!confirm(`Are you sure you want to delete agent "${agentName}"?`)) return;
    setIsLoading(true);
    setError(null);
    try {
      await sendWSMessage('agent_delete', { name: agentName }, 5000);
      if (selectedAgent === agentName) {
        setSelectedAgent(null);
        setSoulContent('');
      }
      await loadAgents();
    } catch (err) {
      setError('Failed to delete agent: ' + err.message);
      console.error('Failed to delete agent', err);
    } finally {
      setIsLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadAgents();
    loadSystemFiles();
  }, [loadAgents, loadSystemFiles]);

  // 根据当前激活的标签页决定保存操作
  const handleSave = () => {
    if (activeTab === 'agents' && selectedAgent) {
      saveAgentSoul();
    } else if (activeTab === 'system' && selectedSystemFile) {
      saveSystemFile();
    }
  };

  // 判断是否可以保存
  const canSave = (activeTab === 'agents' && selectedAgent) || (activeTab === 'system' && selectedSystemFile);
  const currentContent = activeTab === 'agents' ? soulContent : systemFileContent;
  const setCurrentContent = activeTab === 'agents' ? setSoulContent : setSystemFileContent;

  return (
    <div className="agents-panel">
      <div className="agents-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">AGENT MANAGEMENT</span>
        </div>
        <div className="toolbar-right">
          <button
            className="pixel-button small"
            onClick={() => activeTab === 'agents' ? loadAgents() : loadSystemFiles()}
            disabled={isLoading}
            title="Refresh"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
          {activeTab === 'agents' && (
            <button
              className="pixel-button small add-btn"
              onClick={() => setShowNewAgentDialog(true)}
            >
              <Plus size={14} />
              <span>NEW</span>
            </button>
          )}
        </div>
      </div>

      {/* 标签页切换 */}
      <div className="agents-tabs">
        <button
          className={`tab-button ${activeTab === 'agents' ? 'active' : ''}`}
          onClick={() => setActiveTab('agents')}
        >
          <Bot size={14} />
          <span>Agents ({agents.length})</span>
        </button>
        <button
          className={`tab-button ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
        >
          <Folder size={14} />
          <span>System ({systemFiles.length})</span>
        </button>
      </div>

      <div className="agents-content">
        {/* 左侧边栏 */}
        <div className="agents-sidebar">
          {activeTab === 'agents' ? (
            <>
              <div className="sidebar-header">
                <Bot size={16} />
                <span>AGENTS ({agents.length})</span>
              </div>
              <div className="agents-list">
                {agents.length === 0 && !isLoading && (
                  <div className="empty-state">
                    No agents found.<br />
                    Click [+] to create one.
                  </div>
                )}
                {agents.map((agent) => (
                  <div
                    key={agent.name}
                    className={`agent-item ${selectedAgent === agent.name ? 'active' : ''}`}
                    onClick={() => loadAgentSoul(agent.name)}
                  >
                    <div className="agent-info agent-item-info">
                      <div className="agent-item-row">
                        <Bot size={14} className="agent-icon" />
                        <span className="agent-name">{agent.name}</span>
                      </div>
                      <span className="agent-desc">{agent.description}</span>
                    </div>
                    <button
                      className="delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteAgent(agent.name);
                      }}
                      title="Delete agent"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="sidebar-header">
                <Folder size={16} />
                <span>SYSTEM FILES ({systemFiles.length})</span>
              </div>
              <div className="agents-list">
                {systemFiles.length === 0 && !isLoading && (
                  <div className="empty-state">
                    No system files found.
                  </div>
                )}
                {systemFiles.map((file) => (
                  <div
                    key={file.name}
                    className={`agent-item ${selectedSystemFile === file.name ? 'active' : ''}`}
                    onClick={() => loadSystemFile(file.name)}
                  >
                    <div className="agent-info file-item-info">
                      <div className="file-item-row">
                        <FileText size={14} className="file-icon" />
                        <span className="agent-name">{file.name}</span>
                      </div>
                      <span className="agent-desc">
                        {(file.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* 编辑器 */}
        <div className="agent-editor">
          {activeTab === 'agents' ? (
            selectedAgent ? (
              <>
                <div className="editor-header">
                  <span className="editor-title">{selectedAgent}/SOUL.md</span>
                  <button
                    className="pixel-button small save-btn"
                    onClick={saveAgentSoul}
                    disabled={isSaving}
                  >
                    {isSaving ? 'SAVING...' : <><Save size={14} /> SAVE</>}
                  </button>
                </div>
                <textarea
                  className="soul-editor"
                  value={soulContent}
                  onChange={(e) => setSoulContent(e.target.value)}
                  spellCheck={false}
                  placeholder="Enter SOUL.md content here..."
                />
              </>
            ) : (
              <div className="empty-editor">
                <Bot size={48} className="empty-icon" />
                <p>Select an agent from the list to edit its SOUL.md</p>
                <p className="hint">Or click [+] to create a new agent</p>
              </div>
            )
          ) : (
            selectedSystemFile ? (
              <>
                <div className="editor-header">
                  <span className="editor-title">system/{selectedSystemFile}</span>
                  <button
                    className="pixel-button small save-btn"
                    onClick={saveSystemFile}
                    disabled={isSaving}
                  >
                    {isSaving ? 'SAVING...' : <><Save size={14} /> SAVE</>}
                  </button>
                </div>
                <textarea
                  className="soul-editor"
                  value={systemFileContent}
                  onChange={(e) => setSystemFileContent(e.target.value)}
                  spellCheck={false}
                  placeholder="Enter file content here..."
                />
              </>
            ) : (
              <div className="empty-editor">
                <Folder size={48} className="empty-icon" />
                <p>Select a system file from the list to edit</p>
                <p className="hint">System files are used for bootstrap configuration</p>
              </div>
            )
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="error-toast">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* 新建 Agent 对话框 */}
      {showNewAgentDialog && (
        <div className="dialog-overlay">
          <div className="dialog-box pixel-border">
            <h3>Create New Agent</h3>
            <input
              type="text"
              value={newAgentName}
              onChange={(e) => setNewAgentName(e.target.value)}
              placeholder="Agent name (e.g., code-reviewer)"
              className="pixel-input"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && createNewAgent()}
            />
            <div className="dialog-actions">
              <button
                className="pixel-button"
                onClick={() => {
                  setShowNewAgentDialog(false);
                  setNewAgentName('');
                }}
              >
                CANCEL
              </button>
              <button
                className="pixel-button primary"
                onClick={createNewAgent}
                disabled={!newAgentName.trim() || isSaving}
              >
                {isSaving ? 'CREATING...' : 'CREATE'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentsPanel;
