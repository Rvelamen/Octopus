import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Brain, Bot, Radio, Plus, Save, Image, Search, Settings, Trash2, Edit, Check, X, ChevronDown, ChevronRight, RefreshCw, QrCode, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { InputField, PasswordField, SelectField, SwitchField } from '../forms';
import { ConfigCard, DynamicItemCard, AddItemDialog } from '../config';
import WindowDots from '../WindowDots';
import ImageProviderPanel from './ImageProviderPanel';
import { ProviderSetting } from './ProviderSetting';

const CONFIG_TABS = [
  { key: 'providers', label: 'PROVIDERS', Icon: Brain },
  { key: 'agents', label: 'AGENT', Icon: Bot },
  { key: 'channels', label: 'CHANNELS', Icon: Radio },
  { key: 'images', label: 'IMAGES', Icon: Image }
];

function ConfigPanel({ config, setConfig, onSave, isSaving, sendWSMessage }) {
  const [configTab, setConfigTab] = useState('providers');
  const [addDialog, setAddDialog] = useState({
    isOpen: false,
    type: '',
    title: '',
    placeholder: ''
  });

  // Agent Defaults State (from database)
  const [agentDefaults, setAgentDefaults] = useState(null);
  const [enabledModels, setEnabledModels] = useState([]);
  const [isLoadingAgentDefaults, setIsLoadingAgentDefaults] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const hasLoadedAgentDefaults = useRef(false);

  // Channel Configs State (from database)
  const [channelConfigs, setChannelConfigs] = useState([]);
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);

  // Tool Configs State (from database)
  const [toolConfigs, setToolConfigs] = useState([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);

  // WeChat QR Code State
  const [wechatQrCodeUrl, setWechatQrCodeUrl] = useState(null);
  const [wechatQrToken, setWechatQrToken] = useState(null);
  const [wechatStatus, setWechatStatus] = useState(null);
  const [isWechatPolling, setIsWechatPolling] = useState(false);
  const [qrCountdown, setQrCountdown] = useState(300);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successUserInfo, setSuccessUserInfo] = useState(null);
  const [expandedChannels, setExpandedChannels] = useState({});
  const wechatPollingRef = useRef(null);
  const wechatPollingActiveRef = useRef(false);
  const qrCountdownRef = useRef(null);

  const loadConfig = useCallback(async (force = false) => {
    if (hasLoadedAgentDefaults.current && !force) return;
    try {
      const response = await sendWSMessage('get_config', {}, 5000);
      const loadedConfig = response.data || {};
      setConfig(loadedConfig);
    } catch (err) {
      console.error("Failed to load config", err);
    }
  }, [sendWSMessage, setConfig]);

  // Load Agent Defaults from database
  const loadAgentDefaults = useCallback(async () => {
    setIsLoadingAgentDefaults(true);
    try {
      const response = await sendWSMessage('agent_defaults_get', {}, 5000);
      const defaults = response.data;
      setAgentDefaults(defaults);
      hasLoadedAgentDefaults.current = true;
    } catch (err) {
      console.error("Failed to load agent defaults", err);
    } finally {
      setIsLoadingAgentDefaults(false);
    }
  }, [sendWSMessage]);

  // Load enabled models from all enabled providers
  const loadEnabledModels = useCallback(async () => {
    setIsLoadingModels(true);
    try {
      const response = await sendWSMessage('get_enabled_models', {}, 5000);
      const models = response.data?.models || [];
      setEnabledModels(models);
    } catch (err) {
      console.error("Failed to load enabled models", err);
      setEnabledModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, [sendWSMessage]);

  // Load channel configs from database
  const loadChannelConfigs = useCallback(async () => {
    setIsLoadingChannels(true);
    try {
      const response = await sendWSMessage('channel_get_list', {}, 5000);
      const channels = response.data?.channels || [];
      setChannelConfigs(channels);
    } catch (err) {
      console.error("Failed to load channel configs", err);
      setChannelConfigs([]);
    } finally {
      setIsLoadingChannels(false);
    }
  }, [sendWSMessage]);

  // Load tool configs from database
  const loadToolConfigs = useCallback(async () => {
    setIsLoadingTools(true);
    try {
      const response = await sendWSMessage('tool_get_config', {}, 5000);
      const tools = response.data?.tools || [];
      setToolConfigs(tools);
    } catch (err) {
      console.error("Failed to load tool configs", err);
      setToolConfigs([]);
    } finally {
      setIsLoadingTools(false);
    }
  }, [sendWSMessage]);

  useEffect(() => {
    loadConfig();
    loadAgentDefaults();
    loadEnabledModels();
    loadChannelConfigs();
    loadToolConfigs();
  }, []);

  // Handle tab switch with data refresh
  const handleTabSwitch = useCallback((tabKey) => {
    setConfigTab(tabKey);
    // Refresh data based on selected tab
    switch (tabKey) {
      case 'providers':
        // ProviderSetting component handles its own data loading
        break;
      case 'agents':
        loadAgentDefaults();
        loadEnabledModels();
        break;
      case 'channels':
        loadChannelConfigs();
        break;
      case 'images':
        // ImageProviderPanel component handles its own data loading
        break;
      default:
        break;
    }
  }, [loadAgentDefaults, loadEnabledModels, loadChannelConfigs]);

  const handleSave = async () => {
    try {
      // Save config file (for backward compatibility)
      await onSave(config);

      // Save agent defaults to database
      if (agentDefaults) {
        await sendWSMessage('agent_defaults_update', {
          defaultProviderId: agentDefaults.defaultProviderId,
          defaultModelId: agentDefaults.defaultModelId,
          workspacePath: agentDefaults.workspacePath,
          maxTokens: agentDefaults.maxTokens,
          temperature: agentDefaults.temperature,
          maxIterations: agentDefaults.maxIterations,
          contextCompressionEnabled: agentDefaults.contextCompressionEnabled,
          contextCompressionTurns: agentDefaults.contextCompressionTurns,
        }, 5000);
      }

      await loadConfig(true);
      await loadAgentDefaults();
    } catch (e) {
      alert("Failed to save configuration: " + e.message);
    }
  };

  // Update agent defaults field
  const updateAgentDefaultField = (field, value) => {
    setAgentDefaults(prev => prev ? { ...prev, [field]: value } : null);
  };

  // Handle model selection - updates both provider and model
  const handleModelChange = (modelValue) => {
    const selectedModel = enabledModels.find(m => m.value === modelValue);
    if (selectedModel) {
      setAgentDefaults(prev => prev ? {
        ...prev,
        defaultProviderId: selectedModel.providerId,
        defaultProviderName: selectedModel.providerName,
        defaultProviderDisplayName: selectedModel.providerDisplayName,
        defaultModelId: selectedModel.modelDbId,
        defaultModelName: selectedModel.modelId,
        defaultModelDisplayName: selectedModel.modelDisplayName,
      } : null);
    }
  };

  // Update channel config in database
  const updateChannelConfig = async (channelName, updates) => {
    const channel = channelConfigs.find(c => c.channelName === channelName);
    if (!channel) return;

    setChannelConfigs(prev => prev.map(c =>
      c.channelName === channelName
        ? { ...c, ...updates }
        : c
    ));

    try {
      await sendWSMessage('channel_update', {
        channelName: channelName,
        channelType: channel.channelType,
        enabled: updates.enabled !== undefined ? updates.enabled : channel.enabled,
        appId: updates.appId !== undefined ? updates.appId : channel.appId,
        appSecret: updates.appSecret !== undefined ? updates.appSecret : channel.appSecret,
        encryptKey: updates.encryptKey !== undefined ? updates.encryptKey : channel.encryptKey,
        verificationToken: updates.verificationToken !== undefined ? updates.verificationToken : channel.verificationToken,
        allowFrom: updates.allowFrom !== undefined ? updates.allowFrom : channel.allowFrom,
      }, 5000);
    } catch (err) {
      console.error("Failed to update channel config", err);
      setChannelConfigs(prev => prev.map(c =>
        c.channelName === channelName ? channel : c
      ));
      alert("Failed to update channel: " + err.message);
    }
  };

  // Update tool config in database
  const updateToolConfig = async (toolName, updates) => {
    const tool = toolConfigs.find(t => t.toolName === toolName);
    if (!tool) return;

    try {
      await sendWSMessage('tool_update_config', {
        toolName: toolName,
        enabled: updates.enabled !== undefined ? updates.enabled : tool.enabled,
        timeout: updates.timeout !== undefined ? updates.timeout : tool.timeout,
        restrictToWorkspace: updates.restrictToWorkspace !== undefined ? updates.restrictToWorkspace : tool.restrictToWorkspace,
        searchApiKey: updates.searchApiKey !== undefined ? updates.searchApiKey : tool.searchApiKey,
        searchMaxResults: updates.searchMaxResults !== undefined ? updates.searchMaxResults : tool.searchMaxResults,
      }, 5000);

      // Reload tool configs
      await loadToolConfigs();
    } catch (err) {
      console.error("Failed to update tool config", err);
      alert("Failed to update tool: " + err.message);
    }
  };

  const openAddDialog = (type) => {
    const titles = { provider: '添加 Provider', channel: '添加 Channel' };
    const placeholders = { provider: '例如: deepseek, openai, anthropic', channel: '例如: feishu, slack, discord' };
    setAddDialog({ isOpen: true, type, title: titles[type], placeholder: placeholders[type] });
  };

  const handleAddConfirm = (name) => {
    switch (addDialog.type) {
      case 'channel':
        // Create new channel in database
        sendWSMessage('channel_update', {
          channelName: name,
          channelType: name,
          enabled: false,
          appId: '',
          appSecret: '',
          encryptKey: '',
          verificationToken: '',
          allowFrom: [],
        }, 5000).then(() => loadChannelConfigs());
        break;
    }
  };

  const renderAgentDefaults = () => {
    if (isLoadingAgentDefaults || !agentDefaults) {
      return (
        <ConfigCard title="AGENT DEFAULTS" icon="[BOT]">
          <div className="empty-config">
            <span>Loading...</span>
          </div>
        </ConfigCard>
      );
    }

    // Current model value for the select field
    const currentModelValue = agentDefaults.defaultProviderId && agentDefaults.defaultModelName
      ? `${agentDefaults.defaultProviderId}/${agentDefaults.defaultModelName}`
      : '';

    return (
      <ConfigCard title="AGENT DEFAULTS" icon="[BOT]">
        {/* Model Selection - Shows all enabled models from all enabled providers */}
        <SelectField
          label="Default Model"
          value={currentModelValue}
          onChange={handleModelChange}
          options={enabledModels}
          disabled={isLoadingModels || enabledModels.length === 0}
        />
        {enabledModels.length === 0 && !isLoadingModels && (
          <div className="form-hint" style={{ color: '#ff6b6b', marginTop: '-10px', marginBottom: '10px' }}>
            No enabled models found. Please enable providers and models in the PROVIDERS tab.
          </div>
        )}

        <InputField
          label="Workspace Path"
          value={agentDefaults.workspacePath || ''}
          onChange={(v) => updateAgentDefaultField('workspacePath', v)}
          placeholder="/path/to/workspace"
        />

        <InputField
          label="Max Tokens"
          type="number"
          value={agentDefaults.maxTokens || 8192}
          onChange={(v) => updateAgentDefaultField('maxTokens', parseInt(v) || 8192)}
          placeholder="8192"
        />

        <InputField
          label="Temperature"
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={agentDefaults.temperature || 0.7}
          onChange={(v) => updateAgentDefaultField('temperature', parseFloat(v) || 0.7)}
          placeholder="0.7"
        />

        <InputField
          label="Max Iterations"
          type="number"
          value={agentDefaults.maxIterations || 20}
          onChange={(v) => updateAgentDefaultField('maxIterations', parseInt(v) || 20)}
          placeholder="20"
        />

        <SwitchField
          label="Context Compression"
          checked={agentDefaults.contextCompressionEnabled || false}
          onChange={(v) => updateAgentDefaultField('contextCompressionEnabled', v)}
        />

        {agentDefaults.contextCompressionEnabled && (
          <InputField
            label="Compression Turns"
            type="number"
            value={agentDefaults.contextCompressionTurns || 10}
            onChange={(v) => updateAgentDefaultField('contextCompressionTurns', parseInt(v) || 10)}
            placeholder="10"
          />
        )}
      </ConfigCard>
    );
  };

  const renderFeishuConfig = (channel) => {
    const isEnabled = channel.enabled === true;
    return (
      <>
        <SwitchField
          label="Enabled"
          checked={isEnabled}
          onChange={(v) => updateChannelConfig(channel.channelName, { enabled: v })}
        />
        <InputField
          label="App ID"
          value={channel.appId || ''}
          onChange={(v) => updateChannelConfig(channel.channelName, { appId: v })}
          placeholder="cli_xxxxxxxxxxxxxxxx"
        />
        <PasswordField
          label="App Secret"
          value={channel.appSecret || ''}
          onChange={(v) => updateChannelConfig(channel.channelName, { appSecret: v })}
          placeholder="xxxxxxxxxxxxxxxx"
        />
        <InputField
          label="Encrypt Key"
          value={channel.encryptKey || ''}
          onChange={(v) => updateChannelConfig(channel.channelName, { encryptKey: v })}
          placeholder="(optional)"
        />
        <InputField
          label="Verification Token"
          value={channel.verificationToken || ''}
          onChange={(v) => updateChannelConfig(channel.channelName, { verificationToken: v })}
          placeholder="(optional)"
        />
        <div className="form-field">
          <label className="form-label">Allow From (JSON Array)</label>
          <textarea
            value={JSON.stringify(channel.allowFrom || [], null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                updateChannelConfig(channel.channelName, { allowFrom: parsed });
              } catch (err) {}
            }}
            className="pixel-input form-input json-textarea"
            rows={3}
            spellCheck={false}
          />
        </div>
      </>
    );
  };

  const startQrCountdown = () => {
    stopQrCountdown();
    setQrCountdown(300);
    qrCountdownRef.current = setInterval(() => {
      setQrCountdown(prev => {
        if (prev <= 1) {
          stopQrCountdown();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const stopQrCountdown = () => {
    if (qrCountdownRef.current) {
      clearInterval(qrCountdownRef.current);
      qrCountdownRef.current = null;
    }
  };

  const formatCountdown = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const reconnectWechat = async (channelName) => {
    if (!window.confirm('确定要断开当前微信连接并重新扫描吗？')) {
      return;
    }
    
    setExpandedChannels(prev => ({ ...prev, [channelName]: true }));
    
    try {
      const response = await sendWSMessage('wechat_clear_token', { channelName }, 10000);
      if (response.data?.success) {
        setWechatQrCodeUrl(null);
        setWechatQrToken(null);
        setWechatStatus(null);
        setQrCountdown(300);
        stopQrCountdown();
        await loadChannelConfigs();
      }
    } catch (err) {
      console.error('Reconnect WeChat error:', err);
      alert('重新连接失败: ' + err.message);
    }
  };

  const getWechatQrCode = async (channelName) => {
    try {
      const response = await sendWSMessage('wechat_get_qrcode', { channelName }, 30000);
      if (response.data?.success) {
        setWechatQrCodeUrl(response.data.qrcode_img_content);
        setWechatQrToken(response.data.qrcode_token);
        setWechatStatus('waiting');
        startQrCountdown();
        startWechatPolling(response.data.qrcode_token, channelName);
      } else {
        alert('获取二维码失败: ' + (response.data?.error || '未知错误'));
      }
    } catch (err) {
      console.error('Get QR code error:', err);
      alert('获取二维码失败: ' + err.message);
    }
  };

  const startWechatPolling = (qrcodeToken, channelName) => {
    setIsWechatPolling(true);
    wechatPollingActiveRef.current = true;
    console.log('WeChat polling started, token:', qrcodeToken);
    
    const poll = async () => {
      if (!wechatPollingActiveRef.current) {
        console.log('WeChat polling stopped');
        return;
      }
      
      try {
        console.log('WeChat polling for status...');
        const response = await sendWSMessage('wechat_check_status', { 
          qrcode_token: qrcodeToken, 
          channelName 
        }, 10000);
        
        console.log('WeChat poll response:', response);
        
        if (response.data?.success) {
          const status = response.data.status;
          setWechatStatus(status);
          console.log('WeChat status:', status);
          
          if (status === 'confirmed') {
            setIsWechatPolling(false);
            wechatPollingActiveRef.current = false;
            stopQrCountdown();
            setSuccessUserInfo({
              botId: response.data.ilink_bot_id,
              userId: response.data.ilink_user_id,
              channelName: channelName
            });
            setShowSuccessModal(true);
            return;
          } else if (status === 'expired' || status === 'cancelled') {
            setIsWechatPolling(false);
            wechatPollingActiveRef.current = false;
            stopQrCountdown();
            setWechatQrCodeUrl(null);
            setWechatQrToken(null);
            return;
          }
        }
        
        if (wechatPollingActiveRef.current) {
          wechatPollingRef.current = setTimeout(poll, 1000);
        }
      } catch (err) {
        console.error('WeChat polling error:', err);
        if (wechatPollingActiveRef.current) {
          wechatPollingRef.current = setTimeout(poll, 2000);
        }
      }
    };
    
    wechatPollingRef.current = setTimeout(poll, 1000);
  };

  const stopWechatPolling = () => {
    setIsWechatPolling(false);
    wechatPollingActiveRef.current = false;
    if (wechatPollingRef.current) {
      clearTimeout(wechatPollingRef.current);
      wechatPollingRef.current = null;
    }
    stopQrCountdown();
  };

  const handleConfirmSuccess = async () => {
    setShowSuccessModal(false);
    setWechatQrCodeUrl(null);
    setWechatQrToken(null);
    setSuccessUserInfo(null);
    await loadChannelConfigs();
  };

  useEffect(() => {
    return () => {
      stopWechatPolling();
    };
  }, []);

  useEffect(() => {
    if (qrCountdown <= 0 && wechatStatus === 'waiting') {
      setWechatStatus('expired');
      stopWechatPolling();
    }
  }, [qrCountdown, wechatStatus]);

  const renderWechatConfig = (channel) => {
    const isEnabled = channel.enabled === true;
    const isConnected = !!channel.appSecret;
    
    return (
      <>
        <SwitchField
          label="Enabled"
          checked={isEnabled}
          onChange={(v) => updateChannelConfig(channel.channelName, { enabled: v })}
        />
        
        {isConnected ? (
          <div className="form-field">
            <div style={{
              padding: '12px',
              background: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid rgba(34, 197, 94, 0.3)',
              borderRadius: 'var(--r-md)',
              color: '#22c55e',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontFamily: 'var(--font-sans)',
              fontSize: '14px'
            }}>
              <Check size={16} />
              <span>已连接微信</span>
            </div>
            <button
              className="pixel-button"
              onClick={() => reconnectWechat(channel.channelName)}
              style={{
                marginTop: '10px',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <RefreshCw size={14} />
              重新连接
            </button>
          </div>
        ) : (
          <>
            {!wechatQrCodeUrl ? (
              <div className="form-field">
                <button
                  className="pixel-button"
                  onClick={() => getWechatQrCode(channel.channelName)}
                  style={{ 
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px'
                  }}
                >
                  <QrCode size={16} />
                  获取二维码
                </button>
              </div>
            ) : (
              <div className="form-field">
                <div style={{ 
                  textAlign: 'center',
                  padding: '16px',
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--r-lg)'
                }}>
                  <img 
                    src={wechatQrCodeUrl} 
                    alt="WeChat QR Code" 
                    style={{ 
                      width: '200px', 
                      height: '200px',
                      imageRendering: 'pixelated',
                      borderRadius: 'var(--r-md)'
                    }}
                  />
                  
                  <div style={{
                    marginTop: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    color: qrCountdown <= 60 ? 'var(--danger)' : 'var(--text-2)',
                    fontSize: '14px',
                    fontWeight: '600',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    <Clock size={16} />
                    <span>{formatCountdown(qrCountdown)}</span>
                  </div>
                  
                  <p style={{ 
                    marginTop: '10px', 
                    color: 'var(--text-2)',
                    fontSize: '13px',
                    fontFamily: 'var(--font-sans)'
                  }}>
                    {wechatStatus === 'waiting' && '请使用微信扫描二维码...'}
                    {wechatStatus === 'scaned' && (
                      <span style={{ 
                        color: 'var(--warn)', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        gap: '6px' 
                      }}>
                        <CheckCircle size={14} />
                        已扫描，请在手机上确认...
                      </span>
                    )}
                    {wechatStatus === 'expired' && (
                      <span style={{ 
                        color: 'var(--danger)', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        gap: '6px' 
                      }}>
                        <AlertCircle size={14} />
                        二维码已过期，请重新获取
                      </span>
                    )}
                    {wechatStatus === 'cancelled' && '已取消，请重新扫描'}
                  </p>
                  {(wechatStatus === 'expired' || wechatStatus === 'cancelled') && (
                    <button
                      className="pixel-button"
                      onClick={() => getWechatQrCode(channel.channelName)}
                      style={{ 
                        marginTop: '10px',
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px'
                      }}
                    >
                      <RefreshCw size={14} />
                      重新获取二维码
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
        
        <div className="form-field">
          <label className="form-label">Allow From (JSON Array)</label>
          <textarea
            value={JSON.stringify(channel.allowFrom || [], null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                updateChannelConfig(channel.channelName, { allowFrom: parsed });
              } catch (err) {}
            }}
            className="pixel-input form-input json-textarea"
            rows={3}
            spellCheck={false}
          />
        </div>
      </>
    );
  };

  const renderGenericChannelConfig = (channel) => (
    <>
      <SwitchField
        label="Enabled"
        checked={channel.enabled === true}
        onChange={(v) => updateChannelConfig(channel.channelName, { enabled: v })}
      />
      <div className="form-field">
        <label className="form-label">Config (JSON)</label>
        <textarea
          value={JSON.stringify(channel.configJson || {}, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              updateChannelConfig(channel.channelName, { configJson: parsed });
            } catch (err) {}
          }}
          className="pixel-input form-input json-textarea"
          rows={6}
          spellCheck={false}
        />
      </div>
    </>
  );

  const renderChannels = () => {
    if (isLoadingChannels) {
      return (
        <ConfigCard title="CHANNELS" icon="[CHNL]">
          <div className="empty-config">
            <span>Loading...</span>
          </div>
        </ConfigCard>
      );
    }

    return (
      <ConfigCard
        title="CHANNELS"
        icon="[CHNL]"
      >
        {channelConfigs.length === 0 ? (
          <div className="empty-config">
            <span>暂无 Channel</span>
          </div>
        ) : (
          <div className="dynamic-items-list">
            {channelConfigs.map((channel) => (
              <DynamicItemCard
                key={channel.channelName}
                title={channel.channelName}
                itemKey={channel.channelName}
                defaultExpanded={expandedChannels[channel.channelName] || false}
              >
                {channel.channelName === 'feishu'
                  ? renderFeishuConfig(channel)
                  : channel.channelName === 'wechat'
                    ? renderWechatConfig(channel)
                    : renderGenericChannelConfig(channel)
                }
              </DynamicItemCard>
            ))}
          </div>
        )}
        
        {showSuccessModal && (
          <div className="modal-overlay" style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            backdropFilter: 'blur(4px)'
          }}>
            <div className="modal-content" style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r-xl)',
              padding: '32px',
              maxWidth: '420px',
              width: '90%',
              textAlign: 'center',
              boxShadow: 'var(--shadow-3)',
              animation: 'modalFadeIn 0.3s ease-out'
            }}>
              <div style={{
                width: '72px',
                height: '72px',
                margin: '0 auto 24px',
                borderRadius: '50%',
                background: 'rgba(34, 197, 94, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                animation: 'successPulse 1.5s ease-in-out infinite'
              }}>
                <CheckCircle size={40} style={{ color: '#22c55e' }} />
              </div>
              
              <h3 style={{ 
                color: 'var(--text)', 
                marginBottom: '16px', 
                fontSize: '20px',
                fontWeight: '600',
                fontFamily: 'var(--font-sans)'
              }}>
                微信连接成功
              </h3>
              
              {successUserInfo && (
                <div style={{
                  background: 'var(--surface-2)',
                  padding: '16px',
                  borderRadius: 'var(--r-md)',
                  marginBottom: '24px',
                  textAlign: 'left',
                  border: '1px solid var(--border)'
                }}>
                  <p style={{ 
                    color: 'var(--text-2)', 
                    fontSize: '13px', 
                    marginBottom: '8px',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    <strong style={{ color: 'var(--text-3)', fontFamily: 'var(--font-sans)' }}>Bot ID:</strong> {successUserInfo.botId}
                  </p>
                  <p style={{ 
                    color: 'var(--text-2)', 
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    <strong style={{ color: 'var(--text-3)', fontFamily: 'var(--font-sans)' }}>User ID:</strong> {successUserInfo.userId}
                  </p>
                </div>
              )}
              
              <p style={{ 
                color: 'var(--text-3)', 
                fontSize: '14px', 
                marginBottom: '24px',
                fontFamily: 'var(--font-sans)'
              }}>
                您现在可以通过微信与助手进行对话了
              </p>
              
              <button
                className="pixel-button"
                onClick={handleConfirmSuccess}
                style={{
                  width: '100%',
                  padding: '12px 24px',
                  fontSize: '14px',
                  fontWeight: '600',
                  margin: 0
                }}
              >
                确认
              </button>
            </div>
          </div>
        )}
      </ConfigCard>
    );
  };

  const renderTools = () => {
    if (isLoadingTools) {
      return (
        <ConfigCard title="TOOLS" icon="[TOOL]">
          <div className="empty-config">
            <span>Loading...</span>
          </div>
        </ConfigCard>
      );
    }

    const execTool = toolConfigs.find(t => t.toolName === 'exec');
    const webSearchTool = toolConfigs.find(t => t.toolName === 'web_search');

    return (
      <ConfigCard title="TOOLS" icon="[TOOL]">
        {/* Exec Tool Config */}
        {execTool && (
          <>
            <h4 style={{ marginTop: '10px', marginBottom: '10px', color: '#00f0ff' }}>Exec Tool</h4>
            <SwitchField
              label="Enabled"
              checked={execTool.enabled !== false}
              onChange={(v) => updateToolConfig('exec', { enabled: v })}
            />
            <InputField
              label="Timeout (seconds)"
              type="number"
              value={execTool.timeout || 60}
              onChange={(v) => updateToolConfig('exec', { timeout: parseInt(v) || 60 })}
              placeholder="60"
            />
            <SwitchField
              label="Restrict to Workspace"
              checked={execTool.restrictToWorkspace !== false}
              onChange={(v) => updateToolConfig('exec', { restrictToWorkspace: v })}
            />
          </>
        )}

        {/* Web Search Tool Config */}
        {webSearchTool && (
          <>
            <h4 style={{ marginTop: '20px', marginBottom: '10px', color: '#00f0ff' }}>Web Search Tool</h4>
            <SwitchField
              label="Enabled"
              checked={webSearchTool.enabled !== false}
              onChange={(v) => updateToolConfig('web_search', { enabled: v })}
            />
            <PasswordField
              label="Search API Key"
              value={webSearchTool.searchApiKey || ''}
              onChange={(v) => updateToolConfig('web_search', { searchApiKey: v })}
              placeholder="API key for web search"
            />
            <InputField
              label="Max Results"
              type="number"
              value={webSearchTool.searchMaxResults || 5}
              onChange={(v) => updateToolConfig('web_search', { searchMaxResults: parseInt(v) || 5 })}
              placeholder="5"
            />
          </>
        )}
      </ConfigCard>
    );
  };

  const renderContent = () => {
    switch (configTab) {
      case 'providers': return <ProviderSetting sendWSMessage={sendWSMessage} />;
      case 'agents': return renderAgentDefaults();
      case 'channels': return renderChannels();
      case 'images': return <ImageProviderPanel sendWSMessage={sendWSMessage} />;
      default: return <ProviderSetting sendWSMessage={sendWSMessage} />;
    }
  };

  return (
    <div className="config-form-container">
      <div className="config-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">SYSTEM CONFIGURATION</span>
        </div>
        <div className="toolbar-right">
          <button className="pixel-button small save-btn" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'SAVING...' : <Save size={14} />}
          </button>
        </div>
      </div>

      <div className="config-with-tabs">
        <div className="config-tabs">
          {CONFIG_TABS.map((tab) => (
            <button key={tab.key} className={`config-tab ${configTab === tab.key ? 'active' : ''}`} onClick={() => handleTabSwitch(tab.key)}>
              <tab.Icon size={14} />
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </div>
        <div className="config-tab-content">
          {renderContent()}
        </div>
      </div>

      <AddItemDialog
        isOpen={addDialog.isOpen}
        onClose={() => setAddDialog({ ...addDialog, isOpen: false })}
        onConfirm={handleAddConfirm}
        title={addDialog.title}
        placeholder={addDialog.placeholder}
      />
    </div>
  );
}

export default ConfigPanel;
