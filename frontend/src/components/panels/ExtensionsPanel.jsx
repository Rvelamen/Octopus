import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Download, User, Package, Filter, ChevronDown, ChevronUp, X, Star, Calendar, Play, Trash2, CheckCircle, Loader2, Tag, Folder, Code, Puzzle, Rocket } from 'lucide-react';
import { Modal } from 'antd';
import WindowDots from '../WindowDots';
import Toast from '../Toast';
import EnvConfigModal from '../modals/EnvConfigModal';

const API_BASE_URL = 'https://fanquanpintuan.cn/octopus';

// Extension 类型图标
const TYPE_ICONS = {
  skill: Code,
  plugin: Puzzle,
  worker: Rocket
};

// Extension 类型标签
const TYPE_LABELS = {
  skill: 'SKILL',
  plugin: 'PLUGIN',
  worker: 'WORKER'
};

/**
 * Card Window Dots Component
 */
const CardWindowDots = () => (
  <div className="card-window-dots">
    <div className="card-dot red"></div>
    <div className="card-dot yellow"></div>
    <div className="card-dot green"></div>
  </div>
);

/**
 * Extension Card Component
 */
const ExtensionCard = ({ extension, onClick, isSelected, isInstalled, isInstalling, onInstall, onRemove }) => {
  // Format date
  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    return date.toISOString().split('T')[0];
  };

  // Get type icon
  const TypeIcon = TYPE_ICONS[extension.type] || Code;

  // Handle install button click
  const handleInstallClick = (e) => {
    e.stopPropagation();
    onInstall(extension);
  };

  // Handle remove button click
  const handleRemove = (e) => {
    e.stopPropagation();
    Modal.confirm({
      title: '确认卸载',
      content: `确定要卸载 "${extension.name}" 吗？`,
      okText: '卸载',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        onRemove(extension);
      },
    });
  };

  return (
    <div
      className={`skill-card ${isSelected ? 'selected' : ''}`}
      onClick={() => onClick(extension)}
    >
      {/* Header with window dots and type */}
      <div className="skill-card-header">
        <div className="skill-card-header-left">
          <CardWindowDots />
          <span className="skill-filename" title={extension.id}>{extension.id}</span>
        </div>
        <div className="skill-card-stars">
          <TypeIcon size={12} className="type-icon" />
          <span className="stars-count">{TYPE_LABELS[extension.type] || extension.type?.toUpperCase()}</span>
        </div>
      </div>

      {/* Main content with line numbers */}
      <div className="skill-card-body-with-lines">
        {/* Line numbers */}
        <div className="line-numbers">
          <span>1</span>
          <span>2</span>
          <span>3</span>
          <span>4</span>
        </div>

        {/* Content */}
        <div className="skill-card-body">
          {/* Extension name as code style */}
          <div className="skill-code-name">
            <span className="code-keyword">{extension.author} </span>
            <span className="code-function">{extension.name}</span>
          </div>

          {/* Author info */}
          <div className="skill-author-info">
            <span className="code-from">version </span>
            <span className="code-string">"{extension.version || '0.0.0'}"</span>
          </div>

          {/* Description */}
          <div className="skill-desc-text">
            {extension.description || 'No description available'}
          </div>

          {/* Tags */}
          {extension.tags && extension.tags.length > 0 && (
            <div className="plugin-tags">
              {extension.tags.slice(0, 3).map((tag, idx) => (
                <span key={idx} className="plugin-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="skill-card-footer">
        <span className="skill-date">{formatDate(extension.updated_at)}</span>
        <div className="skill-card-actions">
          {isInstalled ? (
            <button className="skill-fav-btn danger" title="卸载Extension" onClick={handleRemove}>
              <Trash2 size={14} />
            </button>
          ) : (
            <button 
              className="skill-install-btn"
              onClick={handleInstallClick}
              disabled={isInstalling}
              title="Install Extension"
            >
              {isInstalling ? (
                <Loader2 size={14} className="spin" />
              ) : (
                <Download size={14} />
              )}
              {isInstalling ? 'Installing...' : 'Install'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Extension Detail Sidebar
 */
const ExtensionDetailSidebar = ({ extension, onClose, isInstalled, isInstalling, onInstall, onRun, onRemove }) => {
  if (!extension) return null;

  console.log('ExtensionDetailSidebar received:', extension.id, 'skill_md:', extension.skill_md ? 'present' : 'missing');

  const [runQuery, setRunQuery] = useState('');
  const [showRunInput, setShowRunInput] = useState(false);

  const TypeIcon = TYPE_ICONS[extension.type] || Code;

  const handleInstall = () => {
    onInstall(extension);
  };

  const handleRun = () => {
    if (!showRunInput) {
      setShowRunInput(true);
      return;
    }
    onRun(extension, runQuery);
    setShowRunInput(false);
    setRunQuery('');
  };

  const handleRemove = () => {
    Modal.confirm({
      title: '确认卸载',
      content: `确定要卸载 "${extension.name}" 吗？`,
      okText: '卸载',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        onRemove(extension);
      },
    });
  };

  return (
    <div className="skill-detail-sidebar">
      <div className="skill-detail-sidebar-header">
        <WindowDots />
        <span className="window-title">EXTENSION_DETAIL</span>
        <button className="detail-close-btn" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      
      <div className="skill-detail-sidebar-content">
        <div className="skill-detail-header">
          <div className="skill-detail-header-left">
            <div className="skill-author-avatar large">
              <div className="avatar-placeholder">
                <TypeIcon size={32} />
              </div>
            </div>
            <div className="skill-detail-meta">
              <h3>{extension.name}</h3>
              <span className="skill-author">@{extension.author}</span>
              <span className="plugin-version">v{extension.version || '0.0.0'}</span>
            </div>
          </div>
          <div className="skill-detail-header-right">
            {isInstalled ? (
              <>
                <button 
                  className="github-button danger"
                  onClick={handleRemove}
                >
                  <Trash2 size={14} />
                  Remove
                </button>
              </>
            ) : (
              <button 
                className="github-button install"
                onClick={handleInstall}
                disabled={isInstalling}
              >
                {isInstalling ? (
                  <Loader2 size={14} className="spin" />
                ) : (
                  <Download size={14} />
                )}
                {isInstalling ? 'Installing...' : 'Install'}
              </button>
            )}
          </div>
        </div>

        {/* Run Input */}
        {showRunInput && (
          <div className="skill-run-input">
            <input
              type="text"
              placeholder={`Enter your request for this ${extension.type}...`}
              value={runQuery}
              onChange={(e) => setRunQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRun()}
              autoFocus
            />
            <button className="pixel-button" onClick={handleRun}>
              <Play size={14} />
              Run
            </button>
            <button className="pixel-button secondary" onClick={() => setShowRunInput(false)}>
              Cancel
            </button>
          </div>
        )}
        
        <div className="skill-detail-stats">
          <div className="detail-stat">
            <Download size={14} className="stat-icon-download" />
            <span className="stat-label">downloads:</span>
            <span className="stat-value">{extension.download_count?.toLocaleString() || 0}</span>
          </div>
          <div className="detail-stat">
            <Star size={14} className="stat-icon-star" />
            <span className="stat-label">rating:</span>
            <span className="stat-value">{extension.rating?.toFixed(1) || '0.0'} ({extension.rating_count || 0})</span>
          </div>
          <div className="detail-stat">
            <Calendar size={14} className="stat-icon-calendar" />
            <span className="stat-label">updated:</span>
            <span className="stat-value">{extension.updated_at ? new Date(extension.updated_at * 1000).toLocaleString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}</span>
          </div>
        </div>

        {/* Tags */}
        {extension.tags && extension.tags.length > 0 && (
          <div className="plugin-detail-tags">
            <span className="detail-label">Tags:</span>
            <div className="tags-list">
              {extension.tags.map((tag, idx) => (
                <span key={idx} className="plugin-tag">{tag}</span>
              ))}
            </div>
          </div>
        )}
        
        <div className="skill-detail-description">
          {extension.description || 'No description available'}
        </div>

        {/* SKILL.md Content */}
        <div className="skill-content-section">
          <div className="skill-content-section-header">
            <WindowDots />
            <h4>SKILL.md</h4>
          </div>
          <div className="skill-md-markdown">
            {extension.skill_md && extension.skill_md.length > 0 ? (
              <pre className="skill-md-content">
                {extension.skill_md}
              </pre>
            ) : (
              <div className="skill-md-empty">
                <p>No SKILL.md content available.</p>
                <p className="hint">Content will be fetched from GitHub when needed.</p>
                {extension.type === 'skill' && extension.repository && (
                  <button 
                    className="pixel-button primary"
                    onClick={() => window.open(extension.repository, '_blank')}
                    style={{marginTop: '12px'}}
                  >
                    View on GitHub
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Manifest */}
        {extension.manifest && (
          <div className="skill-content-section">
            <div className="skill-content-section-header">
              <WindowDots />
              <h4>MANIFEST</h4>
            </div>
            <div className="plugin-manifest">
              <pre>{JSON.stringify(extension.manifest, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Type Filter Dropdown
 */
const TypeFilter = ({ types, selectedType, onSelect, onClear }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="author-filter">
      <button 
        className={`filter-toggle ${selectedType ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <Filter size={14} />
        <span>{selectedType ? TYPE_LABELS[selectedType] || selectedType.toUpperCase() : 'Filter by Type'}</span>
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      
      {isOpen && (
        <div className="filter-dropdown">
          {selectedType && (
            <button className="filter-clear" onClick={onClear}>
              Clear Filter
            </button>
          )}
          {types.map(type => {
            const TypeIcon = TYPE_ICONS[type];
            return (
              <button
                key={type}
                className={`filter-option ${selectedType === type ? 'active' : ''}`}
                onClick={() => {
                  onSelect(type);
                  setIsOpen(false);
                }}
              >
                {TypeIcon && <TypeIcon size={14} />}
                <span>{TYPE_LABELS[type] || type.toUpperCase()}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

/**
 * Stats Panel
 */
const StatsPanel = ({ stats, installedCount }) => {
  if (!stats) return null;

  return (
    <div className="skills-stats-panel">
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon"><Package size={20} /></div>
          <div className="stat-info">
            <span className="stat-value">{stats.total_extensions?.toLocaleString()}</span>
            <span className="stat-label">Total Extensions</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><CheckCircle size={20} /></div>
          <div className="stat-info">
            <span className="stat-value">{installedCount}</span>
            <span className="stat-label">Installed</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><Download size={20} /></div>
          <div className="stat-info">
            <span className="stat-value">{stats.total_downloads?.toLocaleString()}</span>
            <span className="stat-label">Total Downloads</span>
          </div>
        </div>
      </div>
      
      {stats.by_type && (
        <div className="top-authors">
          <h4>By Type</h4>
          <div className="authors-list">
            {Object.entries(stats.by_type).map(([type, count]) => {
              const TypeIcon = TYPE_ICONS[type];
              return (
                <div key={type} className="top-author-item">
                  {TypeIcon && <TypeIcon size={14} />}
                  <span className="author-name">{TYPE_LABELS[type] || type}</span>
                  <span className="author-skills">{count} items</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Extensions Panel Component
 */
const ExtensionsPanel = ({ sendWSMessage, ws }) => {
  const [extensions, setExtensions] = useState([]);
  const [stats, setStats] = useState(null);
  const [installedExtensions, setInstalledExtensions] = useState([]);
  const [installingExtensions, setInstallingExtensions] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedExtension, setSelectedExtension] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, total_pages: 1 });
  const [toasts, setToasts] = useState([]);

  // Environment config modal state
  const [envConfigVisible, setEnvConfigVisible] = useState(false);
  const [pendingInstall, setPendingInstall] = useState(null);
  const [postInstallConfig, setPostInstallConfig] = useState(null); // For config after installation

  // Refs for tracking installation state
  const pendingInstalls = useRef(new Map());

  // Add toast notification
  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type, duration }]);
  }, []);

  // Remove toast
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Refresh installed extensions list via WebSocket
  const refreshInstalledExtensions = useCallback(async () => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('extension_get_list', { type: 'installed' });
      if (response.data?.extensions) {
        setInstalledExtensions(response.data.extensions);
      }
    } catch (err) {
      console.error('Failed to refresh installed extensions:', err);
    }
  }, [sendWSMessage]);

  // Load installed extensions on mount
  useEffect(() => {
    if (!sendWSMessage) return;
    refreshInstalledExtensions();
  }, [sendWSMessage, refreshInstalledExtensions]);

  // Listen for WebSocket messages
  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { type, data } = payload;

        switch (type) {
          case 'extension_installing':
            if (data?.extension_id) {
              setInstallingExtensions(prev => new Set([...prev, data.extension_id]));
              pendingInstalls.current.set(data.extension_id, { 
                name: data.name || 'Unknown Extension',
                startTime: Date.now() 
              });
            }
            break;

          case 'extension_installed':
            if (data?.success) {
              const extensionName = data.name || 'Extension';
              const extensionId = data.extension_id;

              if (extensionId) {
                setInstallingExtensions(prev => {
                  const next = new Set(prev);
                  next.delete(extensionId);
                  return next;
                });
                pendingInstalls.current.delete(extensionId);
              }

              refreshInstalledExtensions();

              // Check if extension requires configuration after installation
              if (data.requires_config && data.config_params) {
                setPostInstallConfig({
                  extension_id: extensionId,
                  name: extensionName,
                  ...data.config_params
                });
                setEnvConfigVisible(true);
              } else {
                addToast(`Extension "${extensionName}" installed successfully!`, 'success');
              }
            }
            break;

          case 'extension_install_error':
            {
              const extensionName = data?.name || 'Extension';
              const extensionId = data?.extension_id;

              if (extensionId) {
                setInstallingExtensions(prev => {
                  const next = new Set(prev);
                  next.delete(extensionId);
                  return next;
                });
                pendingInstalls.current.delete(extensionId);
              }

              addToast(`Failed to install "${extensionName}": ${data?.error || 'Unknown error'}`, 'error');
            }
            break;

          case 'extension_uninstalled':
            {
              const extensionName = data?.name || 'Extension';
              refreshInstalledExtensions();
              addToast(`Extension "${extensionName}" removed successfully!`, 'success');
            }
            break;

          default:
            break;
        }
      } catch (err) {
        console.error('Error handling WebSocket message:', err);
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => {
      ws.removeEventListener('message', handleMessage);
    };
  }, [ws, addToast, refreshInstalledExtensions]);

  // Install extension
  const installExtension = useCallback(async (extension) => {
    if (!sendWSMessage) {
      addToast('WebSocket not connected', 'error');
      return;
    }

    // If plugin type with env_config, show config modal
    if (extension.type === 'plugin' && extension.env_config?.fields?.length > 0) {
      setPendingInstall(extension);
      setEnvConfigVisible(true);
      return;
    }

    const extensionId = extension.id;
    
    try {
      setInstallingExtensions(prev => new Set([...prev, extensionId]));
      pendingInstalls.current.set(extensionId, { 
        name: extension.name,
        startTime: Date.now() 
      });
      
      addToast(`Installing ${extension.name}...`, 'loading');
      
      await sendWSMessage('extension_install', {
        extension_id: extensionId,
        name: extension.name,
        type: extension.type
      }, 30000);
    } catch (err) {
      setInstallingExtensions(prev => {
        const next = new Set(prev);
        next.delete(extensionId);
        return next;
      });
      pendingInstalls.current.delete(extensionId);
      addToast(`Failed to start installation for "${extension.name}": ${err.message}`, 'error');
    }
  }, [sendWSMessage, addToast]);

  // Handle env config confirm (for pre-install config)
  const handleEnvConfigConfirm = useCallback(async (envVars) => {
    // If this is post-install config
    if (postInstallConfig) {
      try {
        await sendWSMessage('extension_config', {
          extension_id: postInstallConfig.extension_id,
          name: postInstallConfig.name,
          env_vars: envVars
        });

        setEnvConfigVisible(false);
        setPostInstallConfig(null);
        addToast(`Configuration saved for "${postInstallConfig.name}"!`, 'success');
      } catch (err) {
        addToast(`Failed to save configuration: ${err.message}`, 'error');
      }
      return;
    }

    // Pre-install config (existing logic)
    if (!pendingInstall || !sendWSMessage) return;

    const extensionId = pendingInstall.id;

    try {
      setInstallingExtensions(prev => new Set([...prev, extensionId]));
      pendingInstalls.current.set(extensionId, {
        name: pendingInstall.name,
        startTime: Date.now()
      });

      addToast(`Installing ${pendingInstall.name}...`, 'loading');

      await sendWSMessage('extension_install', {
        extension_id: extensionId,
        name: pendingInstall.name,
        type: pendingInstall.type,
        env_vars: envVars
      }, 30000);

      setEnvConfigVisible(false);
      setPendingInstall(null);
    } catch (err) {
      setInstallingExtensions(prev => {
        const next = new Set(prev);
        next.delete(extensionId);
        return next;
      });
      pendingInstalls.current.delete(extensionId);
      addToast(`Failed to start installation: ${err.message}`, 'error');
    }
  }, [pendingInstall, postInstallConfig, sendWSMessage, addToast]);

  // Remove extension
  const removeExtension = useCallback(async (extension) => {
    if (!sendWSMessage) {
      addToast('WebSocket not connected', 'error');
      return;
    }

    try {
      await sendWSMessage('extension_uninstall', {
        extension_id: extension.id,
        name: extension.name
      });
    } catch (err) {
      addToast(`Failed to remove "${extension.name}": ${err.message}`, 'error');
    }
  }, [sendWSMessage, addToast]);

  // Run extension
  const runExtension = useCallback(async (extension, query) => {
    if (!sendWSMessage) {
      addToast('WebSocket not connected', 'error');
      return;
    }

    try {
      await sendWSMessage('extension_run', {
        extension_id: extension.id,
        query: query || `Use the ${extension.name} ${extension.type}`
      });

      setSelectedExtension(null);
      addToast('Extension command sent to OCTOPUS', 'success');
    } catch (err) {
      addToast(`Failed to run extension: ${err.message}`, 'error');
    }
  }, [sendWSMessage, addToast]);

  // Check if extension is installed
  const isExtensionInstalled = useCallback((extension) => {
    return installedExtensions.some(e => e.id === extension.id || e.name === extension.name);
  }, [installedExtensions]);

  // Check if extension is being installed
  const isExtensionInstalling = useCallback((extension) => {
    return installingExtensions.has(extension.id);
  }, [installingExtensions]);

  // Fetch extensions from API
  const fetchExtensions = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page_index: page.toString(),
        page_size: '20',
        sort_by: sortBy,
        sort_order: sortOrder
      });

      if (selectedType) {
        params.append('type', selectedType);
      }

      if (searchQuery) {
        params.append('search', searchQuery);
      }

      const response = await fetch(`${API_BASE_URL}/api/extensions?${params}`);
      if (!response.ok) throw new Error('Failed to fetch extensions');

      const result = await response.json();
      const data = result.data || {};
      setExtensions(data.list || []);
      setPagination({
        total: data.total || 0,
        total_pages: Math.ceil((data.total || 0) / 20),
        has_prev: data.pre || false,
        has_next: data.next || false
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/extensions/stats/summary`);
      if (!response.ok) throw new Error('Failed to fetch stats');

      const result = await response.json();
      setStats(result.data || {});
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  // Fetch extension detail
  const fetchExtensionDetail = async (extension) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/extensions/${extension.id}`);
      if (!response.ok) throw new Error('Failed to fetch extension detail');

      const result = await response.json();
      console.log('Extension detail fetched:', result.data?.id, 'skill_md length:', result.data?.skill_md?.length || 0);
      setSelectedExtension(result.data || null);
    } catch (err) {
      console.error('Failed to fetch extension detail:', err);
      addToast('Failed to load extension details', 'error');
    }
  };

  // Effects
  useEffect(() => {
    fetchExtensions();
  }, [page, sortBy, sortOrder, selectedType]);

  useEffect(() => {
    fetchStats();
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchExtensions();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  return (
    <div className="skills-panel-container">
      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>

      {/* Toolbar */}
      <div className="skills-toolbar">
        <div className="toolbar-left">
          <div className="toolbar-icon">[]</div>
          <span className="toolbar-title">EXTENSIONS_MARKETPLACE</span>
        </div>
        <div className="toolbar-right">
          <div className="search-box">
            <Search size={16} />
            <input
              type="text"
              placeholder="Search extensions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <TypeFilter
            types={['skill', 'plugin', 'worker']}
            selectedType={selectedType}
            onSelect={setSelectedType}
            onClear={() => setSelectedType('')}
          />
          <select 
            className="sort-select"
            value={`${sortBy}-${sortOrder}`}
            onChange={(e) => {
              const [field, order] = e.target.value.split('-');
              setSortBy(field);
              setSortOrder(order);
            }}
          >
            <option value="created_at-desc">Newest</option>
            <option value="created_at-asc">Oldest</option>
            <option value="download_count-desc">Downloads ↓</option>
            <option value="download_count-asc">Downloads ↑</option>
            <option value="rating-desc">Rating ↓</option>
            <option value="rating-asc">Rating ↑</option>
            <option value="name-asc">Name A-Z</option>
            <option value="name-desc">Name Z-A</option>
          </select>
        </div>
      </div>

      {/* Main Content */}
      <div className="skills-content">
        {/* Stats Sidebar */}
        <div className="skills-sidebar">
          <StatsPanel stats={stats} installedCount={installedExtensions.length} />
        </div>

        {/* Extensions Grid */}
        <div className={`skills-main ${selectedExtension ? 'with-detail' : ''}`}>
          {loading ? (
            <div className="skills-loading">
              <div className="loading-spinner"></div>
              <span>Loading extensions...</span>
            </div>
          ) : error ? (
            <div className="skills-error">
              <span>Error: {error}</span>
              <button className="pixel-button" onClick={fetchExtensions}>Retry</button>
            </div>
          ) : extensions.length === 0 ? (
            <div className="skills-empty">
              <Package size={48} />
              <span>No extensions found</span>
            </div>
          ) : (
            <>
              <div className="skills-grid">
                {extensions.map(extension => (
                  <ExtensionCard 
                    key={extension.id} 
                    extension={extension} 
                    onClick={fetchExtensionDetail}
                    isSelected={selectedExtension?.id === extension.id}
                    isInstalled={isExtensionInstalled(extension)}
                    isInstalling={isExtensionInstalling(extension)}
                    onInstall={installExtension}
                    onRemove={removeExtension}
                  />
                ))}
              </div>
              
              {/* Pagination */}
              {(pagination.has_prev || pagination.has_next) && (
                <div className="skills-pagination">
                  <button
                    className="pixel-button secondary"
                    disabled={!pagination.has_prev}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span className="page-info">
                    Page {page} of {pagination.total_pages}
                  </span>
                  <button
                    className="pixel-button secondary"
                    disabled={!pagination.has_next}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Extension Detail Sidebar */}
        {selectedExtension && (
          <ExtensionDetailSidebar 
            extension={selectedExtension} 
            onClose={() => setSelectedExtension(null)}
            isInstalled={isExtensionInstalled(selectedExtension)}
            isInstalling={isExtensionInstalling(selectedExtension)}
            onInstall={installExtension}
            onRun={runExtension}
            onRemove={removeExtension}
          />
        )}
      </div>

      {/* Environment Config Modal */}
      <EnvConfigModal
        visible={envConfigVisible}
        extension={postInstallConfig || pendingInstall}
        configParams={postInstallConfig}
        onConfirm={handleEnvConfigConfirm}
        onCancel={() => {
          setEnvConfigVisible(false);
          setPendingInstall(null);
          setPostInstallConfig(null);
        }}
      />
    </div>
  );
};

export default ExtensionsPanel;
