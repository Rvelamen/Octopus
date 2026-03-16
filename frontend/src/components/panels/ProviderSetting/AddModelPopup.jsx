import React, { useState, useEffect } from 'react';
import { X, Check, AlertCircle } from 'lucide-react';

const MODEL_TYPES = [
  { value: 'chat', label: 'Chat', description: '对话模型，用于文本生成和对话' },
  { value: 'completion', label: 'Completion', description: '补全模型，用于文本补全任务' },
  { value: 'embedding', label: 'Embedding', description: '嵌入模型，用于生成向量表示' },
  { value: 'image', label: 'Image', description: '图像模型，用于图像生成' },
  { value: 'audio', label: 'Audio', description: '音频模型，用于语音合成或识别' },
  { value: 'vision', label: 'Vision', description: '视觉模型，用于图像理解和分析' },
];

const AddModelPopup = ({ isOpen, onClose, onAdd, provider }) => {
  const [formData, setFormData] = useState({
    modelId: '',
    displayName: '',
    modelTypes: ['chat'],
    groupName: 'Chat Models',
    enabled: true,
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        modelId: '',
        displayName: '',
        modelTypes: ['chat'],
        groupName: 'Chat Models',
        enabled: true,
      });
      setErrors({});
      setIsSubmitting(false);
    }
  }, [isOpen]);

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.modelId.trim()) {
      newErrors.modelId = 'Model ID is required';
    }
    
    if (!formData.displayName.trim()) {
      newErrors.displayName = 'Display name is required';
    }
    
    if (formData.modelTypes.length === 0) {
      newErrors.modelTypes = 'At least one model type must be selected';
    }
    
    if (!formData.groupName.trim()) {
      newErrors.groupName = 'Group name is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    try {
      await onAdd({
        providerId: provider?.id,
        modelId: formData.modelId.trim(),
        displayName: formData.displayName.trim(),
        modelType: formData.modelTypes[0], // Primary type
        modelTypes: formData.modelTypes, // All selected types
        groupName: formData.groupName.trim(),
        enabled: formData.enabled,
      });
      onClose();
    } catch (error) {
      console.error('Failed to add model:', error);
      setErrors({ submit: error.message || 'Failed to add model' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleModelTypeToggle = (typeValue) => {
    setFormData(prev => {
      const currentTypes = prev.modelTypes;
      let newTypes;
      
      if (currentTypes.includes(typeValue)) {
        // Remove type if already selected (but keep at least one)
        newTypes = currentTypes.filter(t => t !== typeValue);
        if (newTypes.length === 0) {
          newTypes = [typeValue]; // Prevent empty selection
        }
      } else {
        // Add type
        newTypes = [...currentTypes, typeValue];
      }
      
      return {
        ...prev,
        modelTypes: newTypes,
      };
    });
    // Clear error when user makes selection
    if (errors.modelTypes) {
      setErrors(prev => ({ ...prev, modelTypes: null }));
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user types
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container add-model-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add New Model</h3>
          <button className="modal-close-btn" onClick={onClose} disabled={isSubmitting}>
            <X size={18} />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="add-model-form">
          {errors.submit && (
            <div className="error-banner">
              <AlertCircle size={16} />
              <span>{errors.submit}</span>
            </div>
          )}
          
          <div className="form-item">
            <label className="form-label required">Model ID</label>
            <input
              type="text"
              value={formData.modelId}
              onChange={(e) => handleChange('modelId', e.target.value)}
              placeholder="e.g., gpt-4o, claude-3-opus-20240229"
              className={`form-input ${errors.modelId ? 'error' : ''}`}
              disabled={isSubmitting}
              autoFocus
            />
            {errors.modelId && <span className="form-error">{errors.modelId}</span>}
            <span className="form-hint">The unique identifier for this model from the provider API</span>
          </div>
          
          <div className="form-item">
            <label className="form-label required">Display Name</label>
            <input
              type="text"
              value={formData.displayName}
              onChange={(e) => handleChange('displayName', e.target.value)}
              placeholder="e.g., GPT-4o, Claude 3 Opus"
              className={`form-input ${errors.displayName ? 'error' : ''}`}
              disabled={isSubmitting}
            />
            {errors.displayName && <span className="form-error">{errors.displayName}</span>}
            <span className="form-hint">A user-friendly name shown in the UI</span>
          </div>
          
          <div className="form-item">
            <label className="form-label required">Model Types (Multi-select)</label>
            <div className={`model-type-options multi-select ${errors.modelTypes ? 'error' : ''}`}>
              {MODEL_TYPES.map((type) => (
                <div
                  key={type.value}
                  className={`model-type-option ${formData.modelTypes.includes(type.value) ? 'selected' : ''}`}
                  onClick={() => handleModelTypeToggle(type.value)}
                >
                  <div className="model-type-checkbox">
                    {formData.modelTypes.includes(type.value) && <Check size={12} />}
                  </div>
                  <div className="model-type-content">
                    <span className="model-type-label">{type.label}</span>
                    <span className="model-type-desc">{type.description}</span>
                  </div>
                </div>
              ))}
            </div>
            {errors.modelTypes && <span className="form-error">{errors.modelTypes}</span>}
            <span className="form-hint">Select all capabilities this model supports</span>
          </div>
          
          <div className="form-item">
            <label className="form-label required">Group Name</label>
            <input
              type="text"
              value={formData.groupName}
              onChange={(e) => handleChange('groupName', e.target.value)}
              placeholder="e.g., Chat Models, Image Models"
              className={`form-input ${errors.groupName ? 'error' : ''}`}
              disabled={isSubmitting}
            />
            {errors.groupName && <span className="form-error">{errors.groupName}</span>}
            <span className="form-hint">Used to organize models into categories</span>
          </div>
          
          <div className="form-item">
            <label className="switch-row">
              <div className="switch-label-content">
                <span className="switch-label-text">Enabled</span>
                <span className="switch-label-desc">Enable this model for use immediately</span>
              </div>
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => handleChange('enabled', e.target.checked)}
                disabled={isSubmitting}
              />
              <span className="switch-slider"></span>
            </label>
          </div>
          
          <div className="form-actions">
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Creating...' : 'Create Model'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddModelPopup;
