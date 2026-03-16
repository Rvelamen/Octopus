import React, { useState, useEffect } from 'react';
import { Image, Eye, Info, Check } from 'lucide-react';
import './ImageProviderPanel.css';

const ImageProviderPanel = ({ sendWSMessage }) => {
  const [activeTab, setActiveTab] = useState('understanding'); // 'understanding' | 'generation'
  const [understandingModels, setUnderstandingModels] = useState([]);
  const [generationModels, setGenerationModels] = useState([]);
  const [defaultUnderstandingModel, setDefaultUnderstandingModel] = useState(null);
  const [defaultGenerationModel, setDefaultGenerationModel] = useState(null);
  const [defaultSize, setDefaultSize] = useState('1024x1024');
  const [defaultQuality, setDefaultQuality] = useState('standard');
  const [loading, setLoading] = useState(false);

  // Load providers on mount
  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    setLoading(true);
    try {
      // Load all image providers from database
      const res = await sendWSMessage('image_get_providers', {}, 10000);
      if (res.data) {
        setUnderstandingModels(res.data.understanding?.availableModels || []);
        setGenerationModels(res.data.generation?.availableModels || []);
        setDefaultUnderstandingModel(res.data.understanding?.defaultModel || null);
        setDefaultGenerationModel(res.data.generation?.defaultModel || null);
        setDefaultSize(res.data.generation?.defaultSize || '1024x1024');
        setDefaultQuality(res.data.generation?.defaultQuality || 'standard');
      }
    } catch (err) {
      console.error('Failed to load providers:', err);
    } finally {
      setLoading(false);
    }
  };

  const setDefaultModel = async (modelId, configType) => {
    try {
      await sendWSMessage('image_set_default_provider', {
        modelId,
        configType,
        defaultSize: configType === 'generation' ? defaultSize : undefined,
        defaultQuality: configType === 'generation' ? defaultQuality : undefined,
      }, 5000);
      // Reload providers
      await loadProviders();
    } catch (err) {
      console.error('Failed to set default model:', err);
      alert('设置默认模型失败: ' + err.message);
    }
  };

  const getProviderTypeLabel = (type) => {
    const typeLabels = {
      'kimi': 'Kimi (Moonshot)',
      'openai': 'OpenAI',
      'anthropic': 'Anthropic (Claude)',
      'gemini': 'Google Gemini',
      'stability': 'Stability AI'
    };
    return typeLabels[type] || type;
  };

  const currentModels = activeTab === 'understanding' ? understandingModels : generationModels;
  const currentDefault = activeTab === 'understanding' ? defaultUnderstandingModel : defaultGenerationModel;

  return (
    <div className="image-provider-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <Image size={20} />
          图片服务配置
        </h2>
      </div>

      {/* Info Banner */}
      <div className="info-banner">
        <Info size={16} />
        <span>
          图片服务使用已启用 Provider 的模型。请在「PROVIDERS」Tab 中启用支持图片功能的 Provider 和模型。
        </span>
      </div>

      {/* Tabs */}
      <div className="provider-tabs">
        <button
          className={`tab-btn ${activeTab === 'understanding' ? 'active' : ''}`}
          onClick={() => setActiveTab('understanding')}
        >
          <Eye size={16} />
          图片理解
        </button>
        <button
          className={`tab-btn ${activeTab === 'generation' ? 'active' : ''}`}
          onClick={() => setActiveTab('generation')}
        >
          <Image size={16} />
          图片生成
        </button>
      </div>

      {/* Model List */}
      <div className="provider-list">
        <div className="provider-list-header">
          <h3>
            {activeTab === 'understanding' ? '图片理解模型' : '图片生成模型'}
            <span className="provider-count">({currentModels.length})</span>
          </h3>
        </div>

        {loading ? (
          <div className="loading-state">加载中...</div>
        ) : currentModels.length === 0 ? (
          <div className="empty-state">
            <Image size={48} className="empty-icon" />
            <p>
              暂无可用的 {activeTab === 'understanding' ? '图片理解' : '图片生成'} 模型
            </p>
            <p className="empty-hint">
              请在「PROVIDERS」Tab 中启用以下类型的 Provider 和模型：
              <br />
              {activeTab === 'understanding'
                ? 'Kimi, OpenAI, Anthropic, Gemini'
                : 'OpenAI, Stability'}
            </p>
          </div>
        ) : (
          <div className="provider-cards">
            {currentModels.map((model, index) => (
              <div
                key={index}
                className={`provider-card ${currentDefault?.modelDbId === model.modelDbId ? 'is-default' : ''}`}
              >
                <div className="provider-card-header">
                  <div className="provider-info">
                    <h4 className="provider-name">
                      {model.modelDisplayName}
                      {currentDefault?.modelDbId === model.modelDbId && (
                        <span className="default-badge">
                          默认
                        </span>
                      )}
                    </h4>
                    <span className="provider-type">
                      {getProviderTypeLabel(model.providerType)}
                    </span>
                  </div>
                  <div className="provider-actions">
                    {currentDefault?.modelDbId !== model.modelDbId && (
                      <button
                        className="set-default-btn"
                        onClick={() => setDefaultModel(model.modelDbId, activeTab)}
                        title="设为默认"
                      >
                        <Check size={14} />
                        设为默认
                      </button>
                    )}
                  </div>
                </div>

                <div className="provider-details">
                  <div className="detail-row">
                    <span className="detail-label">模型 ID:</span>
                    <span className="detail-value">{model.modelId}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Provider:</span>
                    <span className="detail-value">{model.providerDisplayName}</span>
                  </div>
                  {model.supportsVision && (
                    <div className="detail-row">
                      <span className="detail-label">支持:</span>
                      <span className="detail-value vision-badge">👁️ Vision</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Generation Settings */}
      {activeTab === 'generation' && currentDefault && (
        <div className="generation-settings">
          <h4>生成设置</h4>
          <div className="form-field">
            <label className="form-label">默认尺寸</label>
            <select
              value={defaultSize}
              onChange={(e) => setDefaultSize(e.target.value)}
              className="pixel-input"
            >
              <option value="1024x1024">1024x1024</option>
              <option value="1024x1792">1024x1792</option>
              <option value="1792x1024">1792x1024</option>
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">默认质量</label>
            <select
              value={defaultQuality}
              onChange={(e) => setDefaultQuality(e.target.value)}
              className="pixel-input"
            >
              <option value="standard">标准</option>
              <option value="hd">高清</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageProviderPanel;
