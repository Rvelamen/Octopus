import React, { useState, useMemo, useEffect } from 'react';
import { X, Plus, Search, Check, RefreshCw } from 'lucide-react';

const ModelSelectPopup = ({ isOpen, onClose, models, onAddModel, provider, existingModels }) => {
  const [searchText, setSearchText] = useState('');
  const [addedModels, setAddedModels] = useState(new Set());
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setAddedModels(new Set());
      setSearchText('');
    }
  }, [isOpen]);

  const existingModelIds = useMemo(() => {
    return new Set((existingModels || []).map(m => m.modelId));
  }, [existingModels]);

  const filteredModels = useMemo(() => {
    if (!searchText.trim()) return models;
    return models.filter(m =>
      m.displayName?.toLowerCase().includes(searchText.toLowerCase()) ||
      m.modelId?.toLowerCase().includes(searchText.toLowerCase())
    );
  }, [searchText, models]);

  const handleAdd = async (model) => {
    if (existingModelIds.has(model.modelId)) {
      alert(`Model ${model.modelId} already exists in database`);
      return;
    }

    if (addedModels.has(model.modelId)) {
      return;
    }

    setAdding(true);
    try {
      await onAddModel(model);
      setAddedModels(prev => new Set(prev).add(model.modelId));
    } catch (error) {
      console.error('Failed to add model:', error);
      alert(`Failed to add model: ${error.message}`);
    } finally {
      setAdding(false);
    }
  };

  const handleAddAll = async () => {
    const remainingModels = filteredModels.filter(m => 
      !existingModelIds.has(m.modelId) && !addedModels.has(m.modelId)
    );
    
    if (remainingModels.length === 0) {
      alert('No new models to add');
      return;
    }

    setAdding(true);
    for (const model of remainingModels) {
      try {
        await onAddModel(model);
        setAddedModels(prev => new Set(prev).add(model.modelId));
      } catch (error) {
        console.error(`Failed to add model ${model.modelId}:`, error);
      }
    }
    setAdding(false);
  };

  const getModelStatus = (model) => {
    if (existingModelIds.has(model.modelId)) {
      return 'existing';
    }
    if (addedModels.has(model.modelId)) {
      return 'added';
    }
    return 'available';
  };

  const getAvailableCount = () => {
    return filteredModels.filter(m => !existingModelIds.has(m.modelId) && !addedModels.has(m.modelId)).length;
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-container model-select-modal">
        <div className="modal-header">
          <h3>Select Models from API - {provider?.displayName || provider?.name}</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="model-select-toolbar">
            <div className="search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Search models..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleAddAll}
              disabled={adding || getAvailableCount() === 0}
            >
              {adding ? <RefreshCw size={14} className="spin" /> : <Plus size={14} />}
              Add All ({getAvailableCount()})
            </button>
          </div>

          <div className="model-select-list">
            {filteredModels.length === 0 ? (
              <div className="empty-state">
                <p>No models available from API</p>
              </div>
            ) : (
              <table className="models-table">
                <thead>
                  <tr>
                    <th>Model ID</th>
                    <th>Display Name</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredModels.map((model) => {
                    const status = getModelStatus(model);
                    return (
                      <tr key={model.modelId} className={status === 'added' ? 'added' : status === 'existing' ? 'existing' : ''}>
                        <td className="model-id">{model.modelId}</td>
                        <td>{model.displayName}</td>
                        <td>
                          {status === 'existing' ? (
                            <span className="status-badge existing">
                              <Check size={12} /> In Database
                            </span>
                          ) : status === 'added' ? (
                            <span className="status-badge added">
                              <Check size={12} /> Added
                            </span>
                          ) : (
                            <span className="status-badge available">Available</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => handleAdd(model)}
                            disabled={status === 'existing' || status === 'added' || adding}
                          >
                            {status === 'existing' ? (
                              <>
                                <Check size={14} />
                                Exists
                              </>
                            ) : status === 'added' ? (
                              <>
                                <Check size={14} />
                                Added
                              </>
                            ) : (
                              <>
                                <Plus size={14} />
                                Add
                              </>
                            )}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <span className="model-count">
            {addedModels.size} added / {filteredModels.length} total
            {existingModelIds.size > 0 && ` (${existingModelIds.size} already in database)`}
          </span>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default ModelSelectPopup;
