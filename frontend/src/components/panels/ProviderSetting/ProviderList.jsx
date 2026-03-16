import React, { useState } from 'react';
import { Search, Plus } from 'lucide-react';
import AddProviderPopup from './AddProviderPopup';
import { getProviderLogo } from '../../../utils/providerLogos';

const ProviderList = ({
  providers,
  selectedProvider,
  onSelect,
  onAdd,
  onToggleEnabled,
  searchTerm,
  onSearchChange,
  loading,
  togglingProviders
}) => {
  const [isAddPopupOpen, setIsAddPopupOpen] = useState(false);

  const filteredProviders = providers.filter(p =>
    p.displayName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleToggleClick = (e, provider) => {
    e.stopPropagation();
    if (onToggleEnabled && !togglingProviders?.[provider.id]) {
      onToggleEnabled(provider.id, !provider.enabled);
    }
  };

  const renderProviderItem = (provider) => {
    const logo = getProviderLogo(provider.name);
    const firstLetter = (provider.displayName || provider.name || '?').charAt(0).toUpperCase();
    const isToggling = togglingProviders?.[provider.id];

    return (
      <div
        key={provider.id}
        className={`provider-list-item ${selectedProvider?.id === provider.id ? 'selected' : ''}`}
        onClick={() => onSelect(provider)}
      >
        <div className="provider-item-info">
          {logo ? (
            <img
              src={logo}
              alt=""
              className="provider-avatar"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          ) : (
            <div className="provider-avatar provider-avatar-fallback">
              {firstLetter}
            </div>
          )}
          <span className="provider-name">{provider.displayName || provider.name}</span>
        </div>
        <div className="provider-item-actions">
          <label
            className={`switch-label ${isToggling ? 'switch-label-loading' : ''}`}
            onClick={(e) => handleToggleClick(e, provider)}
            title={provider.enabled ? 'Disable provider' : 'Enable provider'}
          >
            <input
              type="checkbox"
              checked={provider.enabled}
              onChange={() => {}}
              disabled={isToggling}
            />
            <span className="switch-slider">
              {isToggling && <span className="switch-spinner" />}
            </span>
          </label>
        </div>
      </div>
    );
  };

  return (
    <div className="provider-list-container">
      <div className="provider-list-search">
        <Search size={14} className="search-icon" />
        <input
          type="text"
          placeholder="Search providers..."
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          className="search-input"
        />
      </div>

      <div className="provider-list-content">
        {loading ? (
          <div className="provider-list-loading">
            <span>Loading...</span>
          </div>
        ) : (
          <>
            <div className="provider-group-items">
              {filteredProviders.map(renderProviderItem)}
              <button className="add-provider-btn" onClick={() => setIsAddPopupOpen(true)}>
                <Plus size={14} />
                <span>Add Provider</span>
              </button>
            </div>
          </>
        )}
      </div>

      <AddProviderPopup
        isOpen={isAddPopupOpen}
        onClose={() => setIsAddPopupOpen(false)}
        onAdd={onAdd}
      />
    </div>
  );
};

export default ProviderList;
