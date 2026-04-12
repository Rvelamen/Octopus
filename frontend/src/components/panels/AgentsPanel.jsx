import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Plus, Save, Trash2, RefreshCw, FileText, Folder, Settings, Code, ChevronDown, Check } from 'lucide-react';
import WindowDots from '../WindowDots';

function AgentsPanel({ sendWSMessage }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [systemFiles, setSystemFiles] = useState([]);
  const [selectedSystemFile, setSelectedSystemFile] = useState(null);
  const [systemFileContent, setSystemFileContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [newAgentName, setNewAgentName] = useState('');
  const [showNewAgentDialog, setShowNewAgentDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('agents');
  const [editMode, setEditMode] = useState('form');
  const [availableTools, setAvailableTools] = useState([]);
  const [availableExtensions, setAvailableExtensions] = useState([]);
  const [providers, setProviders] = useState([]);
  const [showToolsDropdown, setShowToolsDropdown] = useState(false);
  const [showExtensionsDropdown, setShowExtensionsDropdown] = useState(false);

  const [formData, setFormData] = useState({
    id: null,
    name: '',
    description: '',
    providerId: null,
    modelId: null,
    tools: [],
    extensions: [],
    maxIterations: 30,
    temperature: 0.7,
    systemPrompt: '',
    enabled: true,
  });

  const loadAgents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_list', {}, 5000);
      const agentList = response.data?.agents || [];
      setAgents(agentList);
      if (selectedAgent && !agentList.find(a => a.id === selectedAgent)) {
        setSelectedAgent(null);
        resetFormData();
      }
    } catch (err) {
      setError('Failed to load agents: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage, selectedAgent]);

  const loadSystemFiles = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_system_files', {}, 5000);
      const files = response.data?.files || [];
      setSystemFiles(files);
      if (files.length > 0 && !selectedSystemFile) {
        const firstFile = files[0];
        setSelectedSystemFile(firstFile.name);
        const contentResponse = await sendWSMessage('agent_get_system_file', { filename: firstFile.name }, 5000);
        setSystemFileContent(contentResponse.data?.content || '');
      }
    } catch (err) {
      setError('Failed to load system files: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage, selectedSystemFile]);

  const loadOptions = useCallback(async () => {
    try {
      const [toolsRes, extRes, providersRes] = await Promise.all([
        sendWSMessage('subagent_get_available_tools', {}, 5000),
        sendWSMessage('subagent_get_available_extensions', {}, 5000),
        sendWSMessage('subagent_get_provider_models', {}, 5000),
      ]);
      setAvailableTools(toolsRes.data?.tools || []);
      setAvailableExtensions(extRes.data?.extensions || []);
      setProviders(providersRes.data?.providers || []);
    } catch (err) {
      console.error('Failed to load options', err);
    }
  }, [sendWSMessage]);

  const resetFormData = () => {
    setFormData({
      id: null,
      name: '',
      description: '',
      providerId: null,
      modelId: null,
      tools: [],
      extensions: [],
      maxIterations: 30,
      temperature: 0.7,
      systemPrompt: '',
      enabled: true,
    });
  };

  const loadAgent = useCallback(async (agent) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_soul', { id: agent.id }, 5000);
      const data = response.data || {};
      setFormData({
        id: data.id || null,
        name: data.name || '',
        description: data.description || '',
        providerId: data.providerId || null,
        modelId: data.modelId || null,
        tools: data.tools || [],
        extensions: data.extensions || [],
        maxIterations: data.maxIterations || 30,
        temperature: data.temperature || 0.7,
        systemPrompt: data.systemPrompt || '',
        enabled: data.enabled !== false,
      });
      setSelectedAgent(agent.id);
      setSelectedSystemFile(null);
      setSystemFileContent('');
    } catch (err) {
      setError('Failed to load agent: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage]);

  const loadSystemFile = useCallback(async (filename) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('agent_get_system_file', { filename }, 5000);
      setSystemFileContent(response.data?.content || '');
      setSelectedSystemFile(filename);
      setSelectedAgent(null);
      resetFormData();
    } catch (err) {
      setError('Failed to load system file: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage]);

  const saveAgent = async () => {
    if (!formData.name) return;
    setIsSaving(true);
    setError(null);
    try {
      await sendWSMessage('agent_save_soul', {
        id: formData.id,
        name: formData.name,
        description: formData.description,
        providerId: formData.providerId,
        modelId: formData.modelId,
        tools: formData.tools,
        extensions: formData.extensions,
        maxIterations: formData.maxIterations,
        temperature: formData.temperature,
        systemPrompt: formData.systemPrompt,
        enabled: formData.enabled,
      }, 5000);
      await loadAgents();
    } catch (err) {
      setError('Failed to save: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const saveSystemFile = async () => {
    if (!selectedSystemFile) return;
    setIsSaving(true);
    setError(null);
    try {
      await sendWSMessage('agent_save_system_file', {
        filename: selectedSystemFile,
        content: systemFileContent
      }, 5000);
      await loadSystemFiles();
    } catch (err) {
      setError('Failed to save: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const createNewAgent = async () => {
    if (!newAgentName.trim()) return;
    setIsSaving(true);
    setError(null);
    try {
      await sendWSMessage('agent_save_soul', {
        name: newAgentName.trim(),
        description: 'A new agent for specific tasks',
        providerId: formData.providerId,
        modelId: formData.modelId,
        tools: formData.tools.length > 0 ? formData.tools : ['read', 'write', 'edit', 'list', 'exec', 'action', 'message'],
        extensions: formData.extensions,
        maxIterations: formData.maxIterations,
        temperature: formData.temperature,
        systemPrompt: formData.systemPrompt || `You are a specialized agent designed to handle specific tasks.\n\n## Your Role\n- Execute tasks assigned by the main agent\n- Use available tools to complete tasks\n- Report back with clear, concise summaries`,
        enabled: true,
      }, 5000);
      setShowNewAgentDialog(false);
      setNewAgentName('');
      resetFormData();
      await loadAgents();
    } catch (err) {
      setError('Failed to create agent: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteAgent = async (agent) => {
    if (!confirm(`Delete agent "${agent.name}"?`)) return;
    setIsLoading(true);
    setError(null);
    try {
      await sendWSMessage('agent_delete', { id: agent.id }, 5000);
      if (selectedAgent === agent.id) {
        setSelectedAgent(null);
        resetFormData();
      }
      await loadAgents();
    } catch (err) {
      setError('Failed to delete agent: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
    loadSystemFiles();
    loadOptions();
  }, [loadAgents, loadSystemFiles, loadOptions]);

  const toggleTool = (toolName) => {
    setFormData(prev => ({
      ...prev,
      tools: prev.tools.includes(toolName)
        ? prev.tools.filter(t => t !== toolName)
        : [...prev.tools, toolName]
    }));
  };

  const toggleExtension = (extName) => {
    setFormData(prev => ({
      ...prev,
      extensions: prev.extensions.includes(extName)
        ? prev.extensions.filter(e => e !== extName)
        : [...prev.extensions, extName]
    }));
  };

  const getSelectedProvider = () => providers.find(p => p.id === formData.providerId);

  const handleProviderChange = (providerId) => {
    const provider = providers.find(p => p.id === parseInt(providerId));
    setFormData(prev => ({
      ...prev,
      providerId: providerId ? parseInt(providerId) : null,
      modelId: provider?.models?.[0]?.id || null
    }));
  };

  const handleModelChange = (modelId) => {
    setFormData(prev => ({
      ...prev,
      modelId: modelId ? parseInt(modelId) : null
    }));
  };

  return (
    <div className="agents-panel">
      <div className="agents-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">AGENT MANAGEMENT</span>
        </div>
        <div className="toolbar-right">
          <button className="pixel-button small" onClick={() => activeTab === 'agents' ? loadAgents() : loadSystemFiles()} disabled={isLoading} title="Refresh">
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
          {activeTab === 'agents' && (
            <button className="pixel-button small add-btn" onClick={() => { resetFormData(); setShowNewAgentDialog(true); }}>
              <Plus size={14} />
              <span>NEW</span>
            </button>
          )}
        </div>
      </div>

      <div className="agents-tabs">
        <button className={`tab-button ${activeTab === 'agents' ? 'active' : ''}`} onClick={() => setActiveTab('agents')}>
          <Bot size={14} />
          <span>Agents ({agents.length})</span>
        </button>
        <button className={`tab-button ${activeTab === 'system' ? 'active' : ''}`} onClick={() => setActiveTab('system')}>
          <Folder size={14} />
          <span>System ({systemFiles.length})</span>
        </button>
      </div>

      <div className="agents-content">
        <div className="agents-sidebar">
          {activeTab === 'agents' ? (
            <>
              <div className="sidebar-header"><Bot size={16} /><span>AGENTS</span></div>
              <div className="agents-list">
                {agents.length === 0 && !isLoading && <div className="empty-state">No agents. Click [+] to create one.</div>}
                {agents.map((agent) => (
                  <div key={agent.id} className={`agent-item ${selectedAgent === agent.id ? 'active' : ''}`} onClick={() => loadAgent(agent)}>
                    <div className="agent-info">
                      <div className="agent-name">{agent.name}</div>
                      <div className="agent-desc">{agent.description}</div>
                    </div>
                    <Trash2
                      className="delete-btn"
                      size={16}
                      onClick={(e) => { e.stopPropagation(); deleteAgent(agent); }}
                      title="Delete"
                    />
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="sidebar-header"><Folder size={16} /><span>SYSTEM FILES</span></div>
              <div className="agents-list">
                {systemFiles.map((file) => (
                  <div key={file.name} className={`agent-item ${selectedSystemFile === file.name ? 'active' : ''}`} onClick={() => loadSystemFile(file.name)}>
                    <div className="agent-info">
                      <div className="agent-name"><FileText size={12} /> {file.name}</div>
                      <div className="agent-desc">{(file.size / 1024).toFixed(1)} KB</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="agent-editor">
          {activeTab === 'agents' ? (
            selectedAgent ? (
              <>
                <div className="editor-header">
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    className="name-input"
                    placeholder="Agent name"
                  />
                  <div className="editor-actions">
                    <button className="pixel-button small save-btn" onClick={saveAgent} disabled={isSaving}>
                      {isSaving ? 'SAVING...' : <><Save size={14} /> SAVE</>}
                    </button>
                  </div>
                </div>
                
                <div className="form-grid">
                  <div className="form-group">
                    <label>Description</label>
                    <input type="text" value={formData.description} onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))} placeholder="Brief description" />
                  </div>
                  
                  <div className="form-row-2">
                    <div className="form-group">
                      <label>Provider</label>
                      <select value={formData.providerId || ''} onChange={(e) => handleProviderChange(e.target.value)}>
                        <option value="">Select Provider</option>
                        {providers.filter(p => p.enabled).map(p => <option key={p.id} value={p.id}>{p.displayName || p.name}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Model</label>
                      <select value={formData.modelId || ''} onChange={(e) => handleModelChange(e.target.value)} disabled={!formData.providerId}>
                        <option value="">Select Model</option>
                        {getSelectedProvider()?.models?.filter(m => m.enabled).map(m => <option key={m.id} value={m.id}>{m.displayName || m.name}</option>)}
                      </select>
                    </div>
                  </div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label>Max Iterations</label>
                      <input type="number" value={formData.maxIterations} onChange={(e) => setFormData(prev => ({ ...prev, maxIterations: parseInt(e.target.value) || 30 }))} min="1" max="100" />
                    </div>
                    <div className="form-group">
                      <label>Temperature</label>
                      <input type="number" value={formData.temperature} onChange={(e) => setFormData(prev => ({ ...prev, temperature: parseFloat(e.target.value) || 0.7 }))} min="0" max="2" step="0.1" />
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Tools ({formData.tools.length} selected)</label>
                    <div className="dropdown-container">
                      <button className="dropdown-trigger" onClick={() => setShowToolsDropdown(!showToolsDropdown)}>
                        <span>{formData.tools.length > 0 ? formData.tools.slice(0, 3).join(', ') + (formData.tools.length > 3 ? '...' : '') : 'Select tools'}</span>
                        <ChevronDown size={14} />
                      </button>
                      {showToolsDropdown && (
                        <div className="dropdown-menu">
                          {availableTools.map(tool => (
                            <div key={tool.name} className={`dropdown-item ${formData.tools.includes(tool.name) ? 'selected' : ''}`} onClick={() => toggleTool(tool.name)}>
                              <span className="check">{formData.tools.includes(tool.name) && <Check size={12} />}</span>
                              <span>{tool.name}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Extensions ({formData.extensions.length} selected)</label>
                    <div className="dropdown-container">
                      <button className="dropdown-trigger" onClick={() => setShowExtensionsDropdown(!showExtensionsDropdown)}>
                        <span>{formData.extensions.length > 0 ? formData.extensions.join(', ') : 'Select extensions'}</span>
                        <ChevronDown size={14} />
                      </button>
                      {showExtensionsDropdown && (
                        <div className="dropdown-menu">
                          {availableExtensions.length > 0 ? availableExtensions.map(ext => (
                            <div key={ext.name} className={`dropdown-item ${formData.extensions.includes(ext.name) ? 'selected' : ''}`} onClick={() => toggleExtension(ext.name)}>
                              <span className="check">{formData.extensions.includes(ext.name) && <Check size={12} />}</span>
                              <span>{ext.name}</span>
                            </div>
                          )) : <div className="dropdown-item empty">No extensions available</div>}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="form-group full">
                    <label>System Prompt</label>
                    <textarea value={formData.systemPrompt} onChange={(e) => setFormData(prev => ({ ...prev, systemPrompt: e.target.value }))} placeholder="Enter system prompt..." spellCheck={false} />
                  </div>

                  <div className="form-group checkbox">
                    <label>
                      <input type="checkbox" checked={formData.enabled} onChange={(e) => setFormData(prev => ({ ...prev, enabled: e.target.checked }))} />
                      <span>Enabled</span>
                    </label>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-editor">
                <Bot size={48} />
                <p>Select an agent to edit</p>
              </div>
            )
          ) : (
            selectedSystemFile ? (
              <>
                <div className="editor-header">
                  <span className="file-title">system/{selectedSystemFile}</span>
                  <button className="pixel-button small save-btn" onClick={saveSystemFile} disabled={isSaving}>
                    {isSaving ? 'SAVING...' : <><Save size={14} /> SAVE</>}
                  </button>
                </div>
                <textarea className="raw-editor" value={systemFileContent} onChange={(e) => setSystemFileContent(e.target.value)} spellCheck={false} />
              </>
            ) : (
              <div className="empty-editor">
                <Folder size={48} />
                <p>Select a system file to edit</p>
              </div>
            )
          )}
        </div>
      </div>

      {error && <div className="error-toast">{error}<button onClick={() => setError(null)}>×</button></div>}

      {showNewAgentDialog && (
        <div className="dialog-overlay">
          <div className="dialog-box">
            <h3>Create New Agent</h3>
            <input type="text" value={newAgentName} onChange={(e) => setNewAgentName(e.target.value)} placeholder="Agent name" autoFocus onKeyDown={(e) => e.key === 'Enter' && createNewAgent()} />
            <div className="dialog-row">
              <select value={formData.providerId || ''} onChange={(e) => handleProviderChange(e.target.value)}>
                <option value="">Select Provider</option>
                {providers.filter(p => p.enabled).map(p => <option key={p.id} value={p.id}>{p.displayName || p.name}</option>)}
              </select>
              <select value={formData.modelId || ''} onChange={(e) => handleModelChange(e.target.value)} disabled={!formData.providerId}>
                <option value="">Select Model</option>
                {getSelectedProvider()?.models?.filter(m => m.enabled).map(m => <option key={m.id} value={m.id}>{m.displayName || m.name}</option>)}
              </select>
            </div>
            <div className="dialog-actions">
              <button className="pixel-button" onClick={() => { setShowNewAgentDialog(false); setNewAgentName(''); }}>CANCEL</button>
              <button className="pixel-button primary" onClick={createNewAgent} disabled={!newAgentName.trim() || isSaving}>{isSaving ? 'CREATING...' : 'CREATE'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentsPanel;
