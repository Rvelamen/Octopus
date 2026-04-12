import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Check, Edit, Trash2 } from 'lucide-react';
import { getModelLogoFromObject } from '@utils/modelLogos';
import { getProviderLogo } from '@utils/providerLogos';

const ModelList = ({
  models,
  modelGroups,
  onUpdateModel,
  onDeleteModel,
  onSetDefault,
  provider
}) => {
  const [expandedGroups, setExpandedGroups] = useState(
    Object.keys(modelGroups || {}).reduce((acc, key) => ({ ...acc, [key]: true }), {})
  );

  const toggleGroup = (group) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }));
  };

  if (!models || models.length === 0) {
    return (
      <div className="model-list-empty">
        <span>No models available</span>
      </div>
    );
  }

  return (
    <div className="model-list-container">
      {Object.entries(modelGroups || {}).map(([groupName, groupModels]) => (
        <div key={groupName} className="model-group">
          <div
            className="model-group-header"
            onClick={() => toggleGroup(groupName)}
          >
            {expandedGroups[groupName] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span className="model-group-name">{groupName}</span>
            <span className="model-group-count">({groupModels.length})</span>
          </div>

          {expandedGroups[groupName] && (
            <div className="model-group-items">
              {groupModels.map((model) => {
                // Try to get model logo first
                let logo = getModelLogoFromObject(model);
                let fallbackLetter = null;
                
                // If no model logo, use provider's avatar (same as provider list)
                if (!logo && provider) {
                  const providerLogo = getProviderLogo(provider.name);
                  if (providerLogo) {
                    logo = providerLogo;
                  } else {
                    // If provider also has no logo, use provider name first letter
                    fallbackLetter = (provider.displayName || provider.name || '?').charAt(0).toUpperCase();
                  }
                }
                
                return (
                  <div key={model.id} className="model-item">
                    <div className="model-item-info">
                      {logo ? (
                        <img 
                          src={logo} 
                          alt="" 
                          className="model-avatar"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                      ) : fallbackLetter ? (
                        <div className="model-avatar model-avatar-fallback">
                          {fallbackLetter}
                        </div>
                      ) : null}
                      <span className="model-display-name">{model.displayName}</span>
                      {model.isDefault && <span className="default-badge">Default</span>}
                    </div>
                    <div className="model-item-actions">
                      {!model.isDefault && (
                        <button
                          className="model-action-btn small"
                          onClick={() => onSetDefault(model.id)}
                          title="Set as default"
                        >
                          <Check size={12} />
                        </button>
                      )}
                      <button
                        className="model-action-btn small"
                        onClick={() => onUpdateModel(model.id)}
                        title="Edit model"
                      >
                        <Edit size={12} />
                      </button>
                      <button
                        className="model-action-btn small danger"
                        onClick={() => onDeleteModel(model.id)}
                        title="Delete model"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default ModelList;
