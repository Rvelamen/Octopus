import React, { useState, useEffect, useCallback } from 'react';
import { ExternalLink, RefreshCw, Check, Settings, Trash2, Plus, Search, Activity, Save, Zap } from 'lucide-react';
import ModelList from './ModelList';
import ModelSelectPopup from './ModelSelectPopup';
import EditModelPopup from './EditModelPopup';
import AddModelPopup from './AddModelPopup';
import { getProviderLogo } from '../../../utils/providerLogos';

const PROVIDER_DOCS = {
  openai: 'https://platform.openai.com/api-keys',
  anthropic: 'https://console.anthropic.com/settings/keys',
  deepseek: 'https://platform.deepseek.com/api-keys',
  zhipu: 'https://open.bigmodel.cn/setupapi',
  google: 'https://aistudio.google.com/app/apikey',
  azure: 'https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/RegisteredApps',
  ollama: 'https://ollama.com',
  default: 'https://platform.openai.com/api-keys'
};

const ProviderDetail = ({
  provider,
  models,
  onUpdate,
  onDelete,
  onAddModel,
  onUpdateModel,
  onDeleteModel,
  onSetDefaultModel,
  onToggleModel,
  loading,
  saving
}) => {
  const [localProvider, setLocalProvider] = useState(provider);
  const [apiKey, setApiKey] = useState('');
  const [apiHost, setApiHost] = useState('');
  const [apiVersion, setApiVersion] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [modelSearch, setModelSearch] = useState('');
  const [isModelSelectOpen, setIsModelSelectOpen] = useState(false);
  const [fetchedModels, setFetchedModels] = useState([]);
  const [checkingModels, setCheckingModels] = useState(false);
  const [isEditModelOpen, setIsEditModelOpen] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const [isAddModelOpen, setIsAddModelOpen] = useState(false);

  useEffect(() => {
    setLocalProvider(provider);
    setApiKey(provider?.apiKey || '');
    setApiHost(provider?.apiHost || '');
    setApiVersion(provider?.apiVersion || '');
  }, [provider]);

  const handleSave = useCallback(async () => {
    if (!localProvider) return;
    await onUpdate(localProvider.id, {
      apiKey,
      apiHost,
      apiVersion
    });
  }, [localProvider, apiKey, apiHost, apiVersion, onUpdate]);

  const handleToggleEnabled = async () => {
    if (!localProvider) return;
    await onUpdate(localProvider.id, {
      enabled: !localProvider.enabled
    });
  };

  const handleTestConnection = async () => {
    if (!apiHost || !apiKey) {
      setTestResult({ success: false, message: 'Please configure API Host and API Key first' });
      return;
    }

    // 验证 apiKey 格式，防止错误的数据
    if (apiKey.trim().startsWith('{') || apiKey.trim().startsWith('[')) {
      setTestResult({ success: false, message: 'Invalid API Key format. Please re-enter your API key.' });
      return;
    }

    // 清理 apiKey，移除非 ISO-8859-1 字符
    const cleanApiKey = apiKey.replace(/[^\x00-\xFF]/g, '').trim();
    
    if (!cleanApiKey) {
      setTestResult({ success: false, message: 'API Key contains invalid characters. Please re-enter your API key.' });
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      const providerType = localProvider?.providerType || 'openai';
      const baseUrl = apiHost.replace(/\/$/, '');

      // 优先使用默认模型（不需要检查enabled），如果没有则使用第一个启用的模型
      const testModel = models.find(m => m.isDefault)
        || models.find(m => m.enabled)
        || { modelId: 'gpt-3.5-turbo' };

      let response;

      switch (providerType) {
        case 'gemini':
          response = await testGeminiConnection(baseUrl, cleanApiKey, testModel.modelId);
          break;
        case 'anthropic':
          response = await testAnthropicConnection(baseUrl, cleanApiKey, testModel.modelId);
          break;
        case 'azure-openai':
          response = await testAzureOpenAIConnection(baseUrl, cleanApiKey, testModel.modelId, apiVersion);
          break;
        case 'ollama':
          response = await testOllamaConnection(baseUrl, testModel.modelId);
          break;
        case 'openai-response':
          response = await testOpenAIResponseConnection(baseUrl, cleanApiKey, testModel.modelId);
          break;
        case 'openai':
        case 'new-api':
        case 'cherryln':
        default:
          response = await testOpenAIConnection(baseUrl, cleanApiKey, testModel.modelId);
          break;
      }

      setTestResult({ success: true, message: `Connection successful! Response: "${response}"` });

      if (localProvider?.id) {
        await onUpdate(localProvider.id, {
          apiKey: cleanApiKey,
          apiHost
        });
      }
    } catch (error) {
      setTestResult({ success: false, message: error.message });
    } finally {
      setTesting(false);
    }
  };

  // OpenAI 标准格式测试
  const testOpenAIConnection = async (baseUrl, apiKey, modelId) => {
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: modelId,
        messages: [
          { role: 'system', content: 'test' },
          { role: 'user', content: 'hi' }
        ],
        stream: false,
        max_tokens: 10
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content?.trim() || 'OK';
  };

  // OpenAI Response API 格式测试
  const testOpenAIResponseConnection = async (baseUrl, apiKey, modelId) => {
    const response = await fetch(`${baseUrl}/responses`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: modelId,
        input: [
          { role: 'system', content: 'test' },
          { role: 'user', content: 'hi' }
        ],
        max_output_tokens: 10
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.output_text || data.output?.[0]?.content?.[0]?.text || 'OK';
  };

  // Gemini API 格式测试
  const testGeminiConnection = async (baseUrl, apiKey, modelId) => {
    const modelName = modelId.startsWith('models/') ? modelId : `models/${modelId}`;
    const response = await fetch(`${baseUrl}/${modelName}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        contents: [
          { role: 'user', parts: [{ text: 'hi' }] }
        ],
        generationConfig: {
          maxOutputTokens: 10
        }
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || 'OK';
  };

  // Anthropic API 格式测试
  const testAnthropicConnection = async (baseUrl, apiKey, modelId) => {
    const response = await fetch(`${baseUrl}/v1/messages`, {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
        'http-referer': 'https://cherry-ai.com',
        'x-title': 'Octopus',
        'priority': 'u=1, i'
      },
      body: JSON.stringify({
        model: modelId,
        messages: [
          { role: 'user', content: 'hi' }
        ],
        max_tokens: 10,
        system: 'test'
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.content?.[0]?.text?.trim() || 'OK';
  };

  // Azure OpenAI API 格式测试
  const testAzureOpenAIConnection = async (baseUrl, apiKey, modelId, apiVersion) => {
    const version = apiVersion || '2024-02-01';
    const response = await fetch(`${baseUrl}/openai/deployments/${modelId}/chat/completions?api-version=${version}`, {
      method: 'POST',
      headers: {
        'api-key': apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [
          { role: 'system', content: 'test' },
          { role: 'user', content: 'hi' }
        ],
        max_tokens: 10
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content?.trim() || 'OK';
  };

  // Ollama API 格式测试
  const testOllamaConnection = async (baseUrl, modelId) => {
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: modelId,
        messages: [
          { role: 'system', content: 'test' },
          { role: 'user', content: 'hi' }
        ],
        stream: false
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    const data = await response.json();
    return data.message?.content?.trim() || 'OK';
  };

  const handleResetHost = () => {
    const defaultHost = PROVIDER_DOCS[localProvider?.name] || PROVIDER_DOCS.default;
    setApiHost(defaultHost);
  };

  const handleCheckModels = async () => {
    if (!apiHost) {
      alert('Please configure API Host first');
      return;
    }

    setCheckingModels(true);
    try {
      const providerType = localProvider?.providerType || 'openai';
      const baseUrl = apiHost.replace(/\/$/, '');

      let formattedModels = [];

      switch (providerType) {
        case 'gemini':
          formattedModels = await fetchGeminiModels(baseUrl, apiKey);
          break;
        case 'ollama':
          formattedModels = await fetchOllamaModels(baseUrl);
          break;
        case 'anthropic':
          // Anthropic 没有 models API，使用硬编码列表
          formattedModels = [
            { id: 'claude-3-opus-20240229', modelId: 'claude-3-opus-20240229', displayName: 'Claude 3 Opus', modelType: 'chat', groupName: 'Chat Models', enabled: true },
            { id: 'claude-3-sonnet-20240229', modelId: 'claude-3-sonnet-20240229', displayName: 'Claude 3 Sonnet', modelType: 'chat', groupName: 'Chat Models', enabled: true },
            { id: 'claude-3-haiku-20240307', modelId: 'claude-3-haiku-20240307', displayName: 'Claude 3 Haiku', modelType: 'chat', groupName: 'Chat Models', enabled: true }
          ];
          break;
        case 'openai':
        case 'openai-response':
        case 'azure-openai':
        case 'new-api':
        case 'cherryln':
        default:
          formattedModels = await fetchOpenAIModels(baseUrl, apiKey);
          break;
      }

      setFetchedModels(formattedModels);
      setIsModelSelectOpen(true);
    } catch (error) {
      console.error('Failed to fetch models:', error);
      alert(`Failed to fetch models: ${error.message}`);
    } finally {
      setCheckingModels(false);
    }
  };

  // 获取 OpenAI 格式模型列表
  const fetchOpenAIModels = async (baseUrl, apiKey) => {
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`;
    }

    const response = await fetch(`${baseUrl}/models`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const modelsList = data.data || data.models || [];

    return modelsList.map(m => ({
      id: m.id,
      modelId: m.id,
      displayName: m.id,
      modelType: 'chat',
      groupName: 'Chat Models',
      enabled: true
    }));
  };

  // 获取 Gemini 模型列表
  const fetchGeminiModels = async (baseUrl, apiKey) => {
    const response = await fetch(`${baseUrl}/models?key=${apiKey}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const modelsList = data.models || [];

    return modelsList
      .filter(m => m.name.includes('gemini'))
      .map(m => ({
        id: m.name,
        modelId: m.name,
        displayName: m.displayName || m.name.replace('models/', ''),
        modelType: 'chat',
        groupName: 'Chat Models',
        enabled: true
      }));
  };

  // 获取 Ollama 模型列表
  const fetchOllamaModels = async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/tags`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const modelsList = data.models || [];

    return modelsList.map(m => ({
      id: m.name,
      modelId: m.name,
      displayName: m.name,
      modelType: 'chat',
      groupName: 'Chat Models',
      enabled: true
    }));
  };

  const handleAddFetchedModel = async (model) => {
    try {
      await onAddModel({
        providerId: localProvider.id,
        modelId: model.modelId,
        displayName: model.displayName,
        modelType: model.modelType || 'chat',
        groupName: model.groupName || 'Chat Models',
        enabled: true
      });
      setFetchedModels(prev => prev.filter(m => m.modelId !== model.modelId));
    } catch (error) {
      console.error('Failed to add model:', error);
    }
  };

  const handleEditModel = (modelId) => {
    const model = models.find(m => m.id === modelId);
    if (model) {
      setEditingModel(model);
      setIsEditModelOpen(true);
    }
  };

  const handleSaveModel = async (modelData) => {
    try {
      await onUpdateModel(modelData.id, modelData);
      setIsEditModelOpen(false);
      setEditingModel(null);
    } catch (error) {
      console.error('Failed to update model:', error);
    }
  };

  const filteredModels = models?.filter(m =>
    m.displayName?.toLowerCase().includes(modelSearch.toLowerCase()) ||
    m.modelId?.toLowerCase().includes(modelSearch.toLowerCase())
  ) || [];

  const modelGroups = filteredModels.reduce((acc, model) => {
    const group = model.groupName || 'Chat Models';
    if (!acc[group]) acc[group] = [];
    acc[group].push(model);
    return acc;
  }, {});

  if (!provider || !localProvider) {
    return (
      <div className="provider-detail-empty">
        <Settings size={48} className="empty-icon" />
        <p>Select a provider to view details</p>
      </div>
    );
  }

  // Only use provider name to get logo, not providerType
  const providerLogo = getProviderLogo(localProvider?.name);
  // Get first letter as fallback avatar
  const firstLetter = (localProvider?.displayName || localProvider?.name || '?').charAt(0).toUpperCase();

  return (
    <div className="provider-detail-container">
      <div className="provider-detail-header">
        <div className="provider-header-info">
          {providerLogo ? (
            <img 
              src={providerLogo} 
              alt="" 
              className="provider-detail-avatar"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          ) : (
            <div className="provider-detail-avatar provider-avatar-fallback">
              {firstLetter}
            </div>
          )}
          <h2 className="provider-title">{localProvider?.displayName || localProvider?.name}</h2>
          <a
            href={PROVIDER_DOCS[localProvider?.name] || PROVIDER_DOCS.default}
            target="_blank"
            rel="noopener noreferrer"
            className="provider-docs-link"
          >
            <ExternalLink size={12} />
            <span>Official Docs</span>
          </a>
        </div>
        <div className="provider-header-actions">
          <label className="switch-label">
            <input
              type="checkbox"
              checked={localProvider?.enabled}
              onChange={handleToggleEnabled}
              disabled={saving}
            />
            <span className="switch-slider" />
          </label>
        </div>
      </div>

      <div className="provider-detail-content">
        <div className="provider-section">
          <label className="section-label">API Key</label>
          <div className="api-key-input-row">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter API key..."
              className="api-key-input"
            />
            <button
              className="action-btn test-btn"
              onClick={handleTestConnection}
              disabled={testing || !apiKey}
              title="Test"
            >
              {testing ? <RefreshCw size={14} className="spin" /> : <Zap size={14} />}
            </button>
            <button
              className="action-btn settings-btn"
              onClick={handleSave}
              disabled={saving}
              title="Save"
            >
              {saving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
            </button>
          </div>
          <div className="api-key-help">
            <a
              href={PROVIDER_DOCS[localProvider?.name] || PROVIDER_DOCS.default}
              target="_blank"
              rel="noopener noreferrer"
            >
              Get API Key
            </a>
          </div>
          {testResult && (
            <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
              {testResult.message}
            </div>
          )}
        </div>

        <div className="provider-section">
          <label className="section-label">API Host</label>
          <div className="api-host-input-row">
            <input
              type="text"
              value={apiHost}
              onChange={(e) => setApiHost(e.target.value)}
              placeholder="https://api.example.com"
              className="api-host-input"
            />
            <button
              className="action-btn reset-btn"
              onClick={handleResetHost}
              title="Reset to default"
            >
              <RefreshCw size={14} />
            </button>
          </div>
          {apiHost && (
            <div className="api-host-preview">
              {apiHost.replace(/\/$/, '')}/chat/completions
            </div>
          )}
        </div>

        {localProvider?.providerType === 'azure-openai' && (
          <div className="provider-section">
            <label className="section-label">API Version</label>
            <input
              type="text"
              value={apiVersion}
              onChange={(e) => setApiVersion(e.target.value)}
              placeholder="2024-02-01"
              className="api-version-input"
            />
          </div>
        )}

        <div className="provider-section models-section">
          <div className="models-section-header">
            <label className="section-label">Models</label>
            <div className="models-actions">
              <div className="model-search">
                <Search size={14} />
                <input
                  type="text"
                  placeholder="Search models..."
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                />
              </div>
              <button 
                className="action-btn check-models-btn" 
                title="Check Models from API"
                onClick={handleCheckModels}
                disabled={checkingModels}
              >
                {checkingModels ? <RefreshCw size={14} className="spin" /> : <Activity size={14} />}
              </button>
            </div>
          </div>

          <ModelList
            models={filteredModels}
            modelGroups={modelGroups}
            onUpdateModel={handleEditModel}
            onDeleteModel={onDeleteModel}
            onSetDefault={onSetDefaultModel}
            provider={localProvider}
          />

          <div className="models-section-footer">
            <button className="model-action-btn" onClick={() => setIsAddModelOpen(true)}>
              <Plus size={14} />
              Add Model
            </button>
            {/* <button className="model-action-btn primary" onClick={handleCheckModels} disabled={checkingModels}>
              <Activity size={14} />
              Check Models from API
            </button> */}
          </div>
        </div>

        <div className="provider-detail-footer">
          {!localProvider?.isSystem && (
            <button
              className="delete-provider-btn"
              onClick={() => onDelete(localProvider?.id)}
            >
              <Trash2 size={14} />
              Delete Provider
            </button>
          )}
        </div>
      </div>

      <ModelSelectPopup
        isOpen={isModelSelectOpen}
        onClose={() => setIsModelSelectOpen(false)}
        models={fetchedModels}
        onAddModel={handleAddFetchedModel}
        provider={provider}
        existingModels={models}
      />

      <EditModelPopup
        isOpen={isEditModelOpen}
        onClose={() => {
          setIsEditModelOpen(false);
          setEditingModel(null);
        }}
        model={editingModel}
        onSave={handleSaveModel}
      />

      <AddModelPopup
        isOpen={isAddModelOpen}
        onClose={() => setIsAddModelOpen(false)}
        onAdd={onAddModel}
        provider={localProvider}
      />
    </div>
  );
};

export default ProviderDetail;
