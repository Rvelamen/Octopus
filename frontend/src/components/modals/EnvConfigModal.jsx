import React, { useState, useEffect } from 'react';
import { X, Package, AlertCircle, Check, ChevronDown } from 'lucide-react';
import './EnvConfigModal.css';

/**
 * 环境变量配置弹窗组件 - Pixel Style
 * 用于 plugin 类型 Extension 安装时收集环境变量
 */
const EnvConfigModal = ({ visible, extension, configParams, onConfirm, onCancel }) => {
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState({});

  // 当 extension 变化时，重置表单
  useEffect(() => {
    if (visible) {
      // Support both pre-install (env_config) and post-install (configParams/fields) formats
      const fields = configParams?.fields || extension?.env_config?.fields || [];
      if (fields.length > 0) {
        const initialValues = {};
        fields.forEach(field => {
          if (field.default !== undefined) {
            initialValues[field.name] = field.default;
          } else {
            initialValues[field.name] = '';
          }
        });
        setFormData(initialValues);
        setErrors({});
        setShowPassword({});
      }
    }
  }, [visible, extension, configParams]);

  // 处理字段值变化
  const handleChange = (name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
    // 清除错误
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  // 切换密码显示
  const togglePasswordVisibility = (name) => {
    setShowPassword(prev => ({ ...prev, [name]: !prev[name] }));
  };

  // 渲染表单字段
  const renderField = (field) => {
    const { name, label, type, hint, options } = field;
    const value = formData[name] ?? '';
    const error = errors[name];

    const commonProps = {
      placeholder: hint || `请输入 ${label}`,
      className: `pixel-form-input ${error ? 'error' : ''}`
    };

    switch (type) {
      case 'password':
        return (
          <div className="password-input-wrapper">
            <input
              {...commonProps}
              type={showPassword[name] ? 'text' : 'password'}
              value={value}
              onChange={(e) => handleChange(name, e.target.value)}
              autoComplete="new-password"
            />
            <button
              type="button"
              className="toggle-password-btn"
              onClick={() => togglePasswordVisibility(name)}
            >
              {showPassword[name] ? '隐藏' : '显示'}
            </button>
          </div>
        );

      case 'select':
        return (
          <div className="pixel-select-wrapper">
            <select
              {...commonProps}
              value={value}
              onChange={(e) => handleChange(name, e.target.value)}
              className={`pixel-form-input pixel-select ${error ? 'error' : ''}`}
            >
              <option value="">请选择...</option>
              {options?.map(option => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <ChevronDown className="select-arrow" size={14} />
          </div>
        );

      case 'number':
        return (
          <input
            {...commonProps}
            type="number"
            value={value}
            onChange={(e) => handleChange(name, e.target.value)}
          />
        );

      case 'textarea':
        return (
          <textarea
            {...commonProps}
            rows={4}
            value={value}
            onChange={(e) => handleChange(name, e.target.value)}
            className={`pixel-form-textarea ${error ? 'error' : ''}`}
          />
        );

      case 'boolean':
      case 'switch':
        return (
          <button
            type="button"
            className={`pixel-switch ${value ? 'active' : ''}`}
            onClick={() => handleChange(name, !value)}
          >
            <span className="switch-indicator">{value ? 'ON' : 'OFF'}</span>
          </button>
        );

      case 'radio':
        return (
          <div className="pixel-radio-group">
            {options?.map(option => (
              <label key={option} className="pixel-radio-label">
                <input
                  type="radio"
                  name={name}
                  value={option}
                  checked={value === option}
                  onChange={(e) => handleChange(name, e.target.value)}
                  className="pixel-radio"
                />
                <span className="radio-text">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'checkbox':
        return (
          <div className="pixel-checkbox-group">
            {options?.map(option => {
              const isChecked = Array.isArray(value) && value.includes(option);
              return (
                <label key={option} className="pixel-checkbox-label">
                  <input
                    type="checkbox"
                    value={option}
                    checked={isChecked}
                    onChange={(e) => {
                      const currentValues = Array.isArray(value) ? value : [];
                      if (e.target.checked) {
                        handleChange(name, [...currentValues, option]);
                      } else {
                        handleChange(name, currentValues.filter(v => v !== option));
                      }
                    }}
                    className="pixel-checkbox"
                  />
                  <span className="checkbox-text">{option}</span>
                </label>
              );
            })}
          </div>
        );

      case 'string':
      default:
        return (
          <input
            {...commonProps}
            type="text"
            value={value}
            onChange={(e) => handleChange(name, e.target.value)}
          />
        );
    }
  };

  // 验证表单
  const validateForm = () => {
    const newErrors = {};
    const fields = configParams?.fields || extension?.env_config?.fields || [];

    fields.forEach(field => {
      if (field.required) {
        const value = formData[field.name];
        if (value === undefined || value === null || value === '' ||
            (Array.isArray(value) && value.length === 0)) {
          newErrors[field.name] = `请填写 ${field.label}`;
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理确认
  const handleOk = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      
      // 转换值为字符串格式（用于环境变量）
      const envVars = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          if (Array.isArray(value)) {
            envVars[key] = value.join(',');
          } else {
            envVars[key] = String(value);
          }
        }
      });

      await onConfirm(envVars);
      setFormData({});
    } catch (error) {
      console.error('Error submitting form:', error);
    } finally {
      setLoading(false);
    }
  };

  // 处理取消
  const handleCancel = () => {
    setFormData({});
    setErrors({});
    onCancel();
  };

  // 获取配置页面信息 (support both pre-install and post-install formats)
  const configPage = configParams || extension?.env_config?.config_page || {};
  const title = configPage.title || `配置 ${extension?.name || configParams?.extension || 'Extension'}`;
  const description = configPage.description || '请填写以下配置信息以完成安装';
  const fields = configParams?.fields || extension?.env_config?.fields || [];

  if (!visible) return null;

  return (
    <div className="env-config-overlay">
      <div className="env-config-modal">
        {/* Window Header with Dots */}
        <div className="env-config-header">
          <div className="card-window-dots">
            <div className="card-dot red"></div>
            <div className="card-dot yellow"></div>
            <div className="card-dot green"></div>
          </div>
          <div className="window-title">
            <Package size={14} />
            <span>{title}</span>
          </div>
          <button className="detail-close-btn" onClick={handleCancel}>
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="env-config-body">
          {/* Description */}
          <div className="env-config-description">
            <AlertCircle size={16} />
            <span>{description}</span>
          </div>

          {/* Extension Info */}
          {extension && (
            <div className="env-config-extension-info">
              <div className="info-row">
                <span className="info-label">名称:</span>
                <span className="info-value code-font">{extension.name}</span>
              </div>
              <div className="info-row">
                <span className="info-label">类型:</span>
                <span className={`info-value type-badge ${extension.type}`}>
                  {extension.type?.toUpperCase()}
                </span>
              </div>
              {extension.version && (
                <div className="info-row">
                  <span className="info-label">版本:</span>
                  <span className="info-value code-font">{extension.version}</span>
                </div>
              )}
            </div>
          )}

          {/* Form Fields */}
          <div className="env-config-form">
            {fields.map(field => (
              <div key={field.name} className="form-field">
                <label className="form-label">
                  {field.label}
                  {field.required && <span className="required-mark">*</span>}
                </label>
                {field.description && (
                  <div className="field-description">{field.description}</div>
                )}
                {renderField(field)}
                {errors[field.name] && (
                  <div className="field-error">
                    <AlertCircle size={12} />
                    <span>{errors[field.name]}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="env-config-footer">
          <button 
            className="pixel-button secondary" 
            onClick={handleCancel}
            disabled={loading}
          >
            取消
          </button>
          <button 
            className={`pixel-button primary ${loading ? 'loading' : ''}`}
            onClick={handleOk}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="loading-spinner-small"></span>
                <span>安装中...</span>
              </>
            ) : (
              <>
                <Check size={16} />
                <span>确认安装</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EnvConfigModal;
