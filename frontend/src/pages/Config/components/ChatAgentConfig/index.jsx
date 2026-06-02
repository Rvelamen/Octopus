import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Save, Check, ChevronDown } from 'lucide-react';
import { ConfigCard } from '@components/config';

function ChatAgentConfig({
  sendWSMessage,
  enabledModels,
  availableTools,
  agentName,
  title,
  defaultConfig,
  onSave,
}) {
  const [subagent, setSubagent] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showToolsDropdown, setShowToolsDropdown] = useState(false);

  const loadSubagent = useCallback(async () => {
    setIsLoading(true);
    try {
      const resp = await sendWSMessage('subagent_list', {}, 5000);
      const list = resp.data?.subagents || [];
      const found = list.find((s) => s.name === agentName);
      if (found) {
        setSubagent(found);
      } else {
        setSubagent({ ...defaultConfig, name: agentName });
      }
    } catch (err) {
      console.error(`Failed to load ${agentName} subagent:`, err);
      setSubagent({ ...defaultConfig, name: agentName });
    } finally {
      setIsLoading(false);
    }
  }, [sendWSMessage, agentName, defaultConfig]);

  useEffect(() => {
    loadSubagent();
  }, [loadSubagent]);

  const handleSave = useCallback(async () => {
    if (!subagent) return;
    setIsSaving(true);
    try {
      await sendWSMessage('subagent_save', {
        id: subagent.id || undefined,
        name: subagent.name,
        description: subagent.description,
        provider_id: subagent.provider_id,
        model_id: subagent.model_id,
        tools: subagent.tools,
        extensions: subagent.extensions,
        max_iterations: subagent.max_iterations,
        temperature: subagent.temperature,
        system_prompt: subagent.system_prompt,
        enabled: subagent.enabled,
      }, 10000);
      await loadSubagent();
      if (onSave) onSave();
    } catch (err) {
      console.error(`Failed to save ${agentName} subagent:`, err);
    } finally {
      setIsSaving(false);
    }
  }, [subagent, sendWSMessage, loadSubagent, agentName]);

  const updateField = (field, value) => {
    setSubagent((prev) => (prev ? { ...prev, [field]: value } : null));
  };

  const toggleTool = (toolName) => {
    setSubagent((prev) => {
      if (!prev) return prev;
      const tools = prev.tools || [];
      if (tools.includes(toolName)) {
        return { ...prev, tools: tools.filter((t) => t !== toolName) };
      }
      return { ...prev, tools: [...tools, toolName] };
    });
  };

  if (isLoading || !subagent) {
    return (
      <ConfigCard title={title} icon="[BOT]">
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 16 }}>Loading...</div>
      </ConfigCard>
    );
  }

  const currentModelValue = subagent.provider_id && subagent.model_id
    ? enabledModels.find(m => m.modelDbId === subagent.model_id)?.value || ''
    : '';

  const handleModelChange = (e) => {
    const selectedModel = enabledModels.find(m => m.value === e.target.value);
    if (selectedModel) {
      updateField('provider_id', selectedModel.providerId);
      updateField('model_id', selectedModel.modelDbId);
    } else {
      updateField('provider_id', null);
      updateField('model_id', null);
    }
  };

  return (
    <ConfigCard title={title} icon="[BOT]">
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Model</label>
        <select
          value={currentModelValue}
          onChange={handleModelChange}
          className="pixel-input form-input"
          style={{ width: '100%', cursor: 'pointer' }}
        >
          <option value="">Default (from Agent Defaults)</option>
          {enabledModels.map((m) => (
            <option key={m.value} value={m.value}>
              {m.providerDisplayName} — {m.modelDisplayName}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>System Prompt</label>
        <textarea
          value={subagent.system_prompt || ''}
          onChange={(e) => updateField('system_prompt', e.target.value)}
          rows={4}
          className="pixel-input form-input"
          style={{ width: '100%', resize: 'vertical', fontFamily: 'inherit' }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Max Iterations</label>
        <input
          type="number"
          value={subagent.max_iterations || 10}
          onChange={(e) => updateField('max_iterations', parseInt(e.target.value) || 10)}
          className="pixel-input form-input"
          style={{ width: '100%' }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Temperature</label>
        <input
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={subagent.temperature || 0.5}
          onChange={(e) => updateField('temperature', parseFloat(e.target.value) || 0.5)}
          className="pixel-input form-input"
          style={{ width: '100%' }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
          Tools ({(subagent.tools || []).length} selected)
        </label>
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowToolsDropdown(!showToolsDropdown)}
            className="pixel-input form-input"
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <span>
              {(subagent.tools || []).length > 0
                ? (subagent.tools || []).slice(0, 3).join(', ') + ((subagent.tools || []).length > 3 ? '...' : '')
                : 'No tools selected'}
            </span>
            <ChevronDown size={14} />
          </button>
          {showToolsDropdown && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 4,
              marginTop: 4,
              zIndex: 10,
              maxHeight: 240,
              overflow: 'auto',
            }}>
              {availableTools.map((tool) => (
                <div
                  key={tool.name}
                  onClick={() => toggleTool(tool.name)}
                  style={{
                    padding: '6px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 13,
                    background: (subagent.tools || []).includes(tool.name) ? 'var(--accent-soft)' : 'transparent',
                  }}
                >
                  <span style={{ width: 16, display: 'flex', alignItems: 'center' }}>
                    {(subagent.tools || []).includes(tool.name) && <Check size={12} />}
                  </span>
                  <span>{tool.display_name || tool.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={isSaving}
        className="pixel-button"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '8px 16px',
          opacity: isSaving ? 0.6 : 1,
        }}
      >
        <Save size={14} />
        {isSaving ? 'Saving...' : 'Save'}
      </button>
    </ConfigCard>
  );
}

export default ChatAgentConfig;
