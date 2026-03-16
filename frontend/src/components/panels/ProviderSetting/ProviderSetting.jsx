import React, { useState, useEffect, useCallback } from 'react';
import { ProviderList, ProviderDetail } from './index';
import './ProviderSetting.css';

const ProviderSetting = ({ sendWSMessage }) => {
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [togglingProviders, setTogglingProviders] = useState({});
  const [notification, setNotification] = useState(null);

  const showNotification = useCallback((message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  }, []);

  const loadProviders = useCallback(async () => {
    setLoading(true);
    try {
      const response = await sendWSMessage('provider_get_all', {}, 5000);
      const providerList = response.data?.providers || [];
      setProviders(providerList);

      // Only set default provider on initial load (when providers is empty)
      if (providerList.length > 0 && !selectedProvider) {
        setSelectedProvider(providerList[0]);
      }
    } catch (error) {
      console.error('Failed to load providers:', error);
      showNotification('Failed to load providers', 'error');
    } finally {
      setLoading(false);
    }
    // Note: selectedProvider is intentionally not in dependencies to avoid re-loading when selecting
  }, [sendWSMessage, showNotification]);

  const loadModels = useCallback(async (providerId) => {
    if (!providerId) {
      setModels([]);
      return;
    }
    try {
      const response = await sendWSMessage('model_get_all', { providerId }, 5000);
      setModels(response.data?.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  }, [sendWSMessage]);



  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    if (selectedProvider) {
      loadModels(selectedProvider.id);
    }
  }, [selectedProvider, loadModels]);

  const handleSelectProvider = useCallback((provider) => {
    setSelectedProvider(provider);
  }, []);

  const handleToggleProviderEnabled = useCallback(async (providerId, enabled) => {
    // Prevent toggling if already in progress
    if (togglingProviders[providerId]) return;

    setTogglingProviders(prev => ({ ...prev, [providerId]: true }));

    try {
      await sendWSMessage('provider_enable', { id: providerId, enabled }, 5000);

      // Update local state
      setProviders(prev =>
        prev.map(p => p.id === providerId ? { ...p, enabled } : p)
      );

      // Update selected provider if it's the one being toggled
      if (selectedProvider?.id === providerId) {
        setSelectedProvider(prev => ({ ...prev, enabled }));
      }

      showNotification(`Provider ${enabled ? 'enabled' : 'disabled'} successfully`, 'success');
    } catch (error) {
      console.error('Failed to toggle provider:', error);
      showNotification(`Failed to ${enabled ? 'enable' : 'disable'} provider`, 'error');
    } finally {
      setTogglingProviders(prev => ({ ...prev, [providerId]: false }));
    }
  }, [sendWSMessage, selectedProvider, togglingProviders, showNotification]);

  const handleUpdateProvider = useCallback(async (providerId, updates) => {
    setSaving(true);
    try {
      await sendWSMessage('provider_update', { id: providerId, ...updates }, 5000);
      await loadProviders();

      const updatedProvider = providers.find(p => p.id === providerId);
      if (updatedProvider) {
        setSelectedProvider({ ...updatedProvider, ...updates });
      }
      showNotification('Provider updated successfully', 'success');
    } catch (error) {
      console.error('Failed to update provider:', error);
      showNotification('Failed to update provider', 'error');
    } finally {
      setSaving(false);
    }
  }, [sendWSMessage, providers, loadProviders, showNotification]);

  const handleDeleteProvider = useCallback(async (providerId) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;

    try {
      await sendWSMessage('provider_delete', { id: providerId }, 5000);
      await loadProviders();
      setSelectedProvider(null);
      showNotification('Provider deleted successfully', 'success');
    } catch (error) {
      console.error('Failed to delete provider:', error);
      showNotification('Failed to delete provider', 'error');
    }
  }, [sendWSMessage, loadProviders, showNotification]);

  const handleAddProvider = useCallback(async (providerData) => {
    try {
      await sendWSMessage('provider_add', {
        name: providerData.name,
        displayName: providerData.displayName,
        providerType: providerData.providerType,
        apiKey: providerData.apiKey,
        apiHost: providerData.apiHost,
        enabled: true
      }, 5000);
      await loadProviders();
      showNotification('Provider added successfully', 'success');
    } catch (error) {
      console.error('Failed to add provider:', error);
      showNotification('Failed to add provider', 'error');
    }
  }, [sendWSMessage, loadProviders, showNotification]);

  const handleAddModel = useCallback(async (modelData) => {
    if (!selectedProvider) return;

    try {
      await sendWSMessage('model_add', {
        providerId: modelData.providerId || selectedProvider.id,
        modelId: modelData.modelId,
        displayName: modelData.displayName,
        modelType: modelData.modelType || 'chat',
        groupName: modelData.groupName || 'Chat Models',
        enabled: modelData.enabled !== false
      }, 5000);
      await loadModels(selectedProvider.id);
      showNotification('Model added successfully', 'success');
    } catch (error) {
      console.error('Failed to add model:', error);
      showNotification('Failed to add model', 'error');
    }
  }, [sendWSMessage, selectedProvider, loadModels, showNotification]);

  const handleUpdateModel = useCallback(async (modelId, modelData) => {
    try {
      await sendWSMessage('model_update', {
        id: modelId,
        ...modelData
      }, 5000);
      if (selectedProvider) {
        await loadModels(selectedProvider.id);
      }
      showNotification('Model updated successfully', 'success');
    } catch (error) {
      console.error('Failed to update model:', error);
      showNotification('Failed to update model', 'error');
      throw error;
    }
  }, [sendWSMessage, selectedProvider, loadModels, showNotification]);

  const handleDeleteModel = useCallback(async (modelId) => {
    if (!confirm('Are you sure you want to delete this model?')) return;

    try {
      await sendWSMessage('model_delete', { id: modelId }, 5000);
      if (selectedProvider) {
        await loadModels(selectedProvider.id);
      }
      showNotification('Model deleted successfully', 'success');
    } catch (error) {
      console.error('Failed to delete model:', error);
      showNotification('Failed to delete model', 'error');
    }
  }, [sendWSMessage, selectedProvider, loadModels, showNotification]);

  const handleSetDefaultModel = useCallback(async (modelId) => {
    try {
      await sendWSMessage('model_set_default', { id: modelId }, 5000);
      if (selectedProvider) {
        await loadModels(selectedProvider.id);
      }
      showNotification('Default model set successfully', 'success');
    } catch (error) {
      console.error('Failed to set default model:', error);
      showNotification('Failed to set default model', 'error');
    }
  }, [sendWSMessage, selectedProvider, loadModels, showNotification]);

  const handleToggleModel = useCallback(async (modelId, enabled) => {
    try {
      await sendWSMessage('model_update', { id: modelId, enabled }, 5000);
      if (selectedProvider) {
        await loadModels(selectedProvider.id);
      }
    } catch (error) {
      console.error('Failed to toggle model:', error);
      showNotification('Failed to toggle model', 'error');
    }
  }, [sendWSMessage, selectedProvider, loadModels, showNotification]);

  const filteredProviders = providers.filter(p =>
    p.displayName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="provider-setting-container">
      {notification && (
        <div className={`provider-notification ${notification.type}`}>
          {notification.message}
        </div>
      )}
      <div className="provider-setting-list">
        <ProviderList
          providers={filteredProviders}
          selectedProvider={selectedProvider}
          onSelect={handleSelectProvider}
          onAdd={handleAddProvider}
          onToggleEnabled={handleToggleProviderEnabled}
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          loading={loading}
          togglingProviders={togglingProviders}
        />
      </div>
      <div className="provider-setting-detail">
        <ProviderDetail
          provider={selectedProvider}
          models={models}
          onUpdate={handleUpdateProvider}
          onDelete={handleDeleteProvider}
          onAddModel={handleAddModel}
          onUpdateModel={handleUpdateModel}
          onDeleteModel={handleDeleteModel}
          onSetDefaultModel={handleSetDefaultModel}
          onToggleModel={handleToggleModel}
          loading={loading}
          saving={saving}
        />
      </div>
    </div>
  );
};

export default ProviderSetting;
