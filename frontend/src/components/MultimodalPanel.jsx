import React, { useState, useEffect } from 'react';
import { Image, Eye, Volume2, Info, Check } from 'lucide-react';
import './MultimodalPanel.css';

const MultimodalPanel = ({ sendWSMessage }) => {
  const [activeTab, setActiveTab] = useState('understanding');
  const [understandingModels, setUnderstandingModels] = useState([]);
  const [generationModels, setGenerationModels] = useState([]);
  const [defaultUnderstandingModel, setDefaultUnderstandingModel] = useState(null);
  const [defaultGenerationModel, setDefaultGenerationModel] = useState(null);
  const [defaultSize, setDefaultSize] = useState('1024x1024');
  const [defaultQuality, setDefaultQuality] = useState('standard');
  const [loading, setLoading] = useState(false);

  const [ttsModels, setTtsModels] = useState([]);
  const [defaultTtsModel, setDefaultTtsModel] = useState(null);
  const [defaultTtsVoice, setDefaultTtsVoice] = useState('alloy');
  const [defaultTtsFormat, setDefaultTtsFormat] = useState('mp3');
  const [loadingTTS, setLoadingTTS] = useState(false);

  useEffect(() => {
    loadProviders();
    loadTTSConfig();
  }, []);

  const loadProviders = async () => {
    setLoading(true);
    try {
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

  const loadTTSConfig = async () => {
    setLoadingTTS(true);
    try {
      const response = await sendWSMessage('tts_get_defaults', {}, 5000);
      setTtsModels(response.data?.availableModels || []);
      setDefaultTtsModel(response.data?.defaultModel || null);
      setDefaultTtsVoice(response.data?.defaultVoice || 'alloy');
      setDefaultTtsFormat(response.data?.defaultFormat || 'mp3');
    } catch (err) {
      console.error('Failed to load TTS config:', err);
    } finally {
      setLoadingTTS(false);
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
      await loadProviders();
    } catch (err) {
      console.error('Failed to set default model:', err);
      alert('设置默认模型失败: ' + err.message);
    }
  };

  const handleSetDefaultTtsModel = async (modelId) => {
    try {
      await sendWSMessage('tts_set_defaults', {
        modelId,
        defaultVoice: defaultTtsVoice,
        defaultFormat: defaultTtsFormat,
      }, 5000);
      await loadTTSConfig();
    } catch (err) {
      console.error('Failed to set default TTS model:', err);
      alert('设置默认 TTS 模型失败: ' + err.message);
    }
  };

  const updateTTSDefaults = async (updates) => {
    try {
      await sendWSMessage('tts_set_defaults', updates, 5000);
      if (updates.defaultVoice !== undefined) setDefaultTtsVoice(updates.defaultVoice);
      if (updates.defaultFormat !== undefined) setDefaultTtsFormat(updates.defaultFormat);
    } catch (err) {
      console.error('Failed to update TTS defaults:', err);
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

  const renderUnderstandingContent = () => {
    return (
      <div className="provider-list">
        <div className="provider-list-header">
          <h3>
            图片理解模型
            <span className="provider-count">({understandingModels.length})</span>
          </h3>
        </div>

        {loading ? (
          <div className="loading-state">加载中...</div>
        ) : understandingModels.length === 0 ? (
          <div className="empty-state">
            <Eye size={48} className="empty-icon" />
            <p>暂无可用的图片理解模型</p>
            <p className="empty-hint">
              请在「PROVIDERS」Tab 中启用以下类型的 Provider 和模型：
              <br />
              Kimi, OpenAI, Anthropic, Gemini
            </p>
          </div>
        ) : (
          <div className="provider-cards">
            {understandingModels.map((model, index) => (
              <div
                key={index}
                className={`provider-card ${defaultUnderstandingModel?.modelDbId === model.modelDbId ? 'is-default' : ''}`}
              >
                <div className="provider-card-header">
                  <div className="provider-info">
                    <h4 className="provider-name">
                      {model.modelDisplayName}
                      {defaultUnderstandingModel?.modelDbId === model.modelDbId && (
                        <span className="default-badge">默认</span>
                      )}
                    </h4>
                    <span className="provider-type">
                      {getProviderTypeLabel(model.providerType)}
                    </span>
                  </div>
                  <div className="provider-actions">
                    {defaultUnderstandingModel?.modelDbId !== model.modelDbId && (
                      <button
                        className="set-default-btn"
                        onClick={() => setDefaultModel(model.modelDbId, 'understanding')}
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
    );
  };

  const renderGenerationContent = () => {
    return (
      <>
        <div className="provider-list">
          <div className="provider-list-header">
            <h3>
              图片生成模型
              <span className="provider-count">({generationModels.length})</span>
            </h3>
          </div>

          {loading ? (
            <div className="loading-state">加载中...</div>
          ) : generationModels.length === 0 ? (
            <div className="empty-state">
              <Image size={48} className="empty-icon" />
              <p>暂无可用的图片生成模型</p>
              <p className="empty-hint">
                请在「PROVIDERS」Tab 中启用以下类型的 Provider 和模型：
                <br />
                OpenAI, Stability
              </p>
            </div>
          ) : (
            <div className="provider-cards">
              {generationModels.map((model, index) => (
                <div
                  key={index}
                  className={`provider-card ${defaultGenerationModel?.modelDbId === model.modelDbId ? 'is-default' : ''}`}
                >
                  <div className="provider-card-header">
                    <div className="provider-info">
                      <h4 className="provider-name">
                        {model.modelDisplayName}
                        {defaultGenerationModel?.modelDbId === model.modelDbId && (
                          <span className="default-badge">默认</span>
                        )}
                      </h4>
                      <span className="provider-type">
                        {getProviderTypeLabel(model.providerType)}
                      </span>
                    </div>
                    <div className="provider-actions">
                      {defaultGenerationModel?.modelDbId !== model.modelDbId && (
                        <button
                          className="set-default-btn"
                          onClick={() => setDefaultModel(model.modelDbId, 'generation')}
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
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {defaultGenerationModel && (
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
      </>
    );
  };

  const renderTTSContent = () => {
    return (
      <div className="provider-list">
        <div className="provider-list-header">
          <h3>
            TTS 模型
            <span className="provider-count">({ttsModels.length})</span>
          </h3>
        </div>

        {loadingTTS ? (
          <div className="loading-state">加载中...</div>
        ) : ttsModels.length === 0 ? (
          <div className="empty-state">
            <Volume2 size={48} className="empty-icon" />
            <p>暂无可用的 TTS 模型</p>
            <p className="empty-hint">
              请在「PROVIDERS」Tab 中启用支持 TTS 的 Provider 和模型：
              <br />
              OpenAI (tts-1, tts-1-hd)
            </p>
          </div>
        ) : (
          <div className="provider-cards">
            {ttsModels.map((model, index) => (
              <div
                key={index}
                className={`provider-card ${defaultTtsModel?.modelDbId === model.modelDbId ? 'is-default' : ''}`}
              >
                <div className="provider-card-header">
                  <div className="provider-info">
                    <h4 className="provider-name">
                      {model.label || model.modelId}
                      {defaultTtsModel?.modelDbId === model.modelDbId && (
                        <span className="default-badge">默认</span>
                      )}
                    </h4>
                    <span className="provider-type">
                      {getProviderTypeLabel(model.providerType)}
                    </span>
                  </div>
                  <div className="provider-actions">
                    {defaultTtsModel?.modelDbId !== model.modelDbId && (
                      <button
                        className="set-default-btn"
                        onClick={() => handleSetDefaultTtsModel(model.modelDbId)}
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
                  {model.defaultVoice && (
                    <div className="detail-row">
                      <span className="detail-label">默认声音:</span>
                      <span className="detail-value">{model.defaultVoice}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {defaultTtsModel && (
          <div className="generation-settings">
            <h4>TTS 设置</h4>
            <div className="form-field">
              <label className="form-label">默认声音</label>
              <select
                value={defaultTtsVoice}
                onChange={(e) => updateTTSDefaults({ defaultVoice: e.target.value })}
                className="pixel-input"
              >
                <option value="alloy">Alloy (中性)</option>
                <option value="echo">Echo (男声)</option>
                <option value="fable">Fable (中性)</option>
                <option value="onyx">Onyx (男声)</option>
                <option value="nova">Nova (女声)</option>
                <option value="shimmer">Shimmer (女声)</option>
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">输出格式</label>
              <select
                value={defaultTtsFormat}
                onChange={(e) => updateTTSDefaults({ defaultFormat: e.target.value })}
                className="pixel-input"
              >
                <option value="mp3">MP3 (推荐)</option>
                <option value="wav">WAV</option>
              </select>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'understanding':
        return renderUnderstandingContent();
      case 'generation':
        return renderGenerationContent();
      case 'tts':
        return renderTTSContent();
      default:
        return renderUnderstandingContent();
    }
  };

  return (
    <div className="multimodal-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <Image size={20} />
          多模态服务配置
        </h2>
      </div>

      <div className="info-banner">
        <Info size={16} />
        <span>
          多模态服务使用已启用 Provider 的模型。请在「PROVIDERS」Tab 中启用支持相应功能的 Provider 和模型。
        </span>
      </div>

      <div className="service-tabs">
        <button
          className={`service-tab-btn ${activeTab === 'understanding' ? 'active' : ''}`}
          onClick={() => setActiveTab('understanding')}
        >
          <Eye size={16} />
          图片理解
        </button>
        <button
          className={`service-tab-btn ${activeTab === 'generation' ? 'active' : ''}`}
          onClick={() => setActiveTab('generation')}
        >
          <Image size={16} />
          图片生成
        </button>
        <button
          className={`service-tab-btn ${activeTab === 'tts' ? 'active' : ''}`}
          onClick={() => setActiveTab('tts')}
        >
          <Volume2 size={16} />
          语音合成
        </button>
      </div>

      {renderContent()}
    </div>
  );
};

export default MultimodalPanel;
