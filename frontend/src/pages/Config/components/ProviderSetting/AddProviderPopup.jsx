import React, { useState } from 'react';
import { X, Plus, ChevronDown } from 'lucide-react';

// 只支持图片中的8种类型
const PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI', defaultHost: 'https://api.openai.com/v1' },
  { value: 'openai-response', label: 'OpenAI-Response', defaultHost: 'https://api.openai.com/v1' },
  { value: 'gemini', label: 'Gemini', defaultHost: 'https://generativelanguage.googleapis.com/v1beta' },
  { value: 'anthropic', label: 'Anthropic', defaultHost: 'https://api.anthropic.com' },
  { value: 'azure-openai', label: 'Azure OpenAI', defaultHost: '' },
  { value: 'new-api', label: 'New API', defaultHost: '' },
  { value: 'cherryln', label: 'CherryIN', defaultHost: '' },
  { value: 'ollama', label: 'Ollama', defaultHost: 'http://localhost:11434' }
];

const AddProviderPopup = ({ isOpen, onClose, onAdd }) => {
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [providerType, setProviderType] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [apiHost, setApiHost] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const selectedType = PROVIDER_TYPES.find(t => t.value === providerType);

  const handleTypeChange = (type) => {
    setProviderType(type.value);
    setApiHost(type.defaultHost);
    setIsDropdownOpen(false);
    
    // Auto-fill name if empty
    if (!name) {
      setName(type.value);
    }
    // Auto-fill display name if empty
    if (!displayName) {
      setDisplayName(type.label);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) {
      alert('Provider name is required');
      return;
    }
    
    onAdd({
      name: name.trim(),
      displayName: displayName.trim() || name.trim(),
      providerType,
      apiKey: apiKey.trim(),
      apiHost: apiHost.trim(),
      enabled: true
    });
    
    // Reset form
    setName('');
    setDisplayName('');
    setProviderType('openai');
    setApiKey('');
    setApiHost('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-container add-provider-modal">
        <div className="modal-header">
          <h3>添加提供商</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Provider Type Selection */}
            <div className="form-group">
              <label className="form-label">提供商类型</label>
              <div className="dropdown-container">
                <button
                  type="button"
                  className="dropdown-trigger"
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                >
                  <span>{selectedType?.label}</span>
                  <ChevronDown size={16} className={isDropdownOpen ? 'open' : ''} />
                </button>
                {isDropdownOpen && (
                  <div className="dropdown-menu">
                    {PROVIDER_TYPES.map((type) => (
                      <div
                        key={type.value}
                        className={`dropdown-item ${providerType === type.value ? 'selected' : ''}`}
                        onClick={() => handleTypeChange(type)}
                      >
                        {type.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Provider Name */}
            <div className="form-group">
              <label className="form-label">提供商名称</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如 OpenAI"
                className="form-input"
                required
              />
            </div>

            {/* Display Name */}
            <div className="form-group">
              <label className="form-label">显示名称</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="例如 My OpenAI"
                className="form-input"
              />
            </div>

            {/* API Key */}
            <div className="form-group">
              <label className="form-label">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="form-input"
              />
            </div>

            {/* API Host */}
            <div className="form-group">
              <label className="form-label">API Host</label>
              <input
                type="text"
                value={apiHost}
                onChange={(e) => setApiHost(e.target.value)}
                placeholder="https://api.example.com"
                className="form-input"
              />
              <span className="form-hint">
                默认: {selectedType?.defaultHost || '自定义'}
              </span>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary">
              <Plus size={14} />
              添加
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddProviderPopup;
