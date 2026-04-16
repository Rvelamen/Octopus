import React, { useState, useEffect, useRef, useCallback } from 'react';
import { History, MessageSquare, ChevronRight, ChevronDown, RefreshCw, Hash, Trash2 } from 'lucide-react';
import WindowDots from '@components/layout/WindowDots';
import MessageList from '@components/MessageList/index.jsx';
import ImageModal from '../Chat/ChatPanel/components/Modals/ImageModal.jsx';
import WorkspaceFilePreviewModal from '../Chat/ChatPanel/components/Modals/WorkspaceFilePreviewModal.jsx';
import { useMessageRenderer } from '@hooks/useMessageRenderer.jsx';
import './HistoryPanel.css';

/**
 * HistoryPanel 组件 - 查看所有 Channel 的消息历史
 */
function HistoryPanel({ sendWSMessage }) {
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [channelSessions, setChannelSessions] = useState({}); // 按channel存储sessions
  const [sessionInstances, setSessionInstances] = useState({}); // 按session_key存储instances
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedChannels, setExpandedChannels] = useState(new Set());
  const [expandedSessions, setExpandedSessions] = useState(new Set());
  const [filterType, setFilterType] = useState('all'); // "all", "normal"
  const [modalImage, setModalImage] = useState(null);
  const messagesEndRef = useRef(null);
  const isComponentMounted = useRef(true);

  // 获取所有 Channel 列表
  const fetchChannels = useCallback(async () => {
    if (!sendWSMessage) return;
    setLoading(true);
    setError(null);
    try {
      const response = await sendWSMessage('session_get_channels', {}, 5000);
      if (response.data?.channels) {
        setChannels(response.data.channels);
      }
    } catch (err) {
      console.error('Failed to fetch channels:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // 获取指定 Channel 的所有 Sessions
  const fetchChannelSessions = useCallback(async (channel) => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('session_get_channel_sessions', { channel }, 5000);
      if (response.data?.sessions) {
        setChannelSessions(prev => ({
          ...prev,
          [channel]: response.data.sessions
        }));
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // 获取 Session 详情（包含 Instances）
  const fetchSessionDetail = useCallback(async (channel, chatId) => {
    if (!sendWSMessage) return;
    try {
      const response = await sendWSMessage('session_get_session_detail', { channel, chat_id: chatId }, 5000);
      if (response.data?.instances) {
        const sessionKey = `${channel}:${chatId}`;
        setSessionInstances(prev => ({
          ...prev,
          [sessionKey]: response.data.instances
        }));
      }
    } catch (err) {
      console.error('Failed to fetch session detail:', err);
    }
  }, [sendWSMessage]);

  // 获取 Instance 的消息
  const fetchInstanceMessages = useCallback(async (instanceId) => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('session_get_messages', { instance_id: instanceId, limit: 1000 }, 5000);
      if (response.data?.messages) {
        setMessages(response.data.messages);
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // 初始加载
  useEffect(() => {
    isComponentMounted.current = true;
    fetchChannels();
    return () => {
      isComponentMounted.current = false;
    };
  }, [fetchChannels]);

  // 删除 Instance
  const deleteInstance = async (instanceId, e) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this session instance? This will also delete all messages in it.')) {
      return;
    }

    try {
      await sendWSMessage('session_delete_instance', { instance_id: instanceId }, 5000);
      // 如果删除的是当前选中的instance，清空消息
      if (selectedInstance?.id === instanceId) {
        setSelectedInstance(null);
        setMessages([]);
      }
      // 刷新当前session的instances
      if (selectedSession) {
        const sessionKey = `${selectedSession.channel}:${selectedSession.chat_id}`;
        const updatedInstances = sessionInstances[sessionKey]?.filter(inst => inst.id !== instanceId) || [];
        setSessionInstances(prev => ({
          ...prev,
          [sessionKey]: updatedInstances
        }));
      }
    } catch (err) {
      console.error('Failed to delete instance:', err);
      alert('Failed to delete instance: ' + err.message);
    }
  };

  // 自动滚动到最新消息
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollTop = messagesEndRef.current.scrollHeight;
    }
  }, [messages]);

  const { renderMessageContent, workspacePreviewPath, setWorkspacePreviewPath } = useMessageRenderer();

  // 切换 Channel 展开状态
  const toggleChannel = (channel) => {
    const newExpanded = new Set(expandedChannels);
    if (newExpanded.has(channel)) {
      newExpanded.delete(channel);
    } else {
      newExpanded.add(channel);
      setSelectedChannel(channel);
      // 如果还没有加载过这个channel的sessions，则加载
      if (!channelSessions[channel]) {
        fetchChannelSessions(channel);
      }
    }
    setExpandedChannels(newExpanded);
  };

  // 切换 Session 展开状态
  const toggleSession = (session) => {
    const newExpanded = new Set(expandedSessions);
    const sessionKey = `${session.channel}:${session.chat_id}`;

    if (newExpanded.has(sessionKey)) {
      newExpanded.delete(sessionKey);
    } else {
      newExpanded.add(sessionKey);
      // 如果还没有加载过这个session的instances，则加载
      if (!sessionInstances[sessionKey]) {
        fetchSessionDetail(session.channel, session.chat_id);
      }
    }
    setExpandedSessions(newExpanded);
  };

  // 选择 Instance 查看消息
  const handleSelectInstance = (instance) => {
    setSelectedInstance(instance);
    fetchInstanceMessages(instance.id);
  };

  // 刷新所有展开的 session 的 instances
  const refreshExpandedSessions = useCallback(async () => {
    if (!sendWSMessage) return;

    const expandedSessionList = [];
    expandedSessions.forEach(sessionKey => {
      const [channel, ...chatIdParts] = sessionKey.split(':');
      const chatId = chatIdParts.join(':'); // 处理 chatId 中包含冒号的情况
      if (channel && chatId) {
        expandedSessionList.push({ channel, chatId, sessionKey });
      }
    });

    // 并行刷新所有展开的 session
    await Promise.all(
      expandedSessionList.map(async ({ channel, chatId, sessionKey }) => {
        try {
          const response = await sendWSMessage('session_get_session_detail', { channel, chat_id: chatId }, 5000);
          if (response.data?.instances) {
            setSessionInstances(prev => ({
              ...prev,
              [sessionKey]: response.data.instances
            }));
          }
        } catch (err) {
          console.error(`Failed to refresh session ${sessionKey}:`, err);
        }
      })
    );
  }, [sendWSMessage, expandedSessions]);

  // 处理刷新按钮点击
  const handleRefresh = useCallback(async () => {
    // 先刷新 channels
    await fetchChannels();
    // 然后刷新所有展开的 session 的 instances
    await refreshExpandedSessions();
  }, [fetchChannels, refreshExpandedSessions]);

  // Message rendering is delegated to MessageList; no inline tool pairing needed.

  // 获取当前选中的session
  const selectedSession = selectedChannel && channelSessions[selectedChannel]?.find(
    s => expandedSessions.has(`${s.channel}:${s.chat_id}`)
  );

  return (
    <div className="history-layout">
      {/* Left Sidebar: Channel & Session Tree */}
      <div className="history-sidebar">
        <div className="window-header">
          <WindowDots />
          <span className="window-title">SESSIONS</span>
          <button
            className="refresh-btn"
            onClick={handleRefresh}
            disabled={loading || !sendWSMessage}
            title={!sendWSMessage ? 'WebSocket not connected' : 'Refresh'}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
        <div className="history-tree">
          {error && (
            <div className="empty-state-small" style={{ color: 'var(--error)', fontSize: '11px' }}>
              Error: {error}
            </div>
          )}
          {!sendWSMessage && (
            <div className="empty-state-small" style={{ color: 'var(--warning)', fontSize: '11px' }}>
              WebSocket not connected
            </div>
          )}
          {channels.length === 0 && !error && sendWSMessage && (
            <div className="empty-state-small">
              No channels found
            </div>
          )}
          {channels.map((channel) => (
            <div key={channel} className="tree-node">
              <div
                className={`tree-item channel-item ${selectedChannel === channel ? 'selected' : ''}`}
                onClick={() => toggleChannel(channel)}
              >
                {expandedChannels.has(channel) ? (
                  <ChevronDown size={14} />
                ) : (
                  <ChevronRight size={14} />
                )}
                <Hash size={14} className="icon-channel" />
                <span className="channel-name">{channel}</span>
              </div>

              {expandedChannels.has(channel) && (
                <div className="tree-children">
                  {!channelSessions[channel] ? (
                    <div className="empty-state-small">Loading...</div>
                  ) : channelSessions[channel].length === 0 ? (
                    <div className="empty-state-small">No sessions</div>
                  ) : (
                    channelSessions[channel].map((session) => {
                      const sessionKey = `${session.channel}:${session.chat_id}`;
                      return (
                        <div key={session.id}>
                          <div
                            className={`tree-item session-item ${expandedSessions.has(sessionKey) ? 'selected' : ''}`}
                            onClick={() => toggleSession(session)}
                          >
                            {expandedSessions.has(sessionKey) ? (
                              <ChevronDown size={12} />
                            ) : (
                              <ChevronRight size={12} />
                            )}
                            <MessageSquare size={12} className="icon-session" />
                            <span className="session-name" title={session.chat_id}>
                              {session.chat_id.length > 20
                                ? session.chat_id.substring(0, 20) + '...'
                                : session.chat_id}
                            </span>
                          </div>

                          {expandedSessions.has(sessionKey) && (
                            <div className="tree-children">
                              {!sessionInstances[sessionKey] ? (
                                <div className="empty-state-small">Loading...</div>
                              ) : sessionInstances[sessionKey].length === 0 ? (
                                <div className="empty-state-small">No instances</div>
                              ) : (
                                sessionInstances[sessionKey].map((instance) => (
                                  <div
                                    key={instance.id}
                                    className={`tree-item instance-item ${selectedInstance?.id === instance.id ? 'selected' : ''}`}
                                  >
                                    <span
                                      className="instance-indicator"
                                      onClick={() => handleSelectInstance(instance)}
                                    ></span>
                                    <span
                                      className="instance-name"
                                      onClick={() => handleSelectInstance(instance)}
                                    >
                                      {instance.instance_name}
                                      {instance.is_active && <span className="active-badge">active</span>}
                                    </span>
                                    <button
                                      className="delete-instance-btn"
                                      onClick={(e) => deleteInstance(instance.id, e)}
                                      title="Delete this instance"
                                    >
                                      <Trash2 size={12} />
                                    </button>
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Right: Message History */}
      <div className="history-content">
        <div className="window-header">
          <WindowDots />
          <span className="window-title">
            {selectedInstance
              ? `MESSAGES - ${selectedChannel} / ${selectedSession?.chat_id?.substring(0, 20)}... / ${selectedInstance.instance_name}`
              : 'MESSAGE HISTORY'
            }
          </span>
          {selectedInstance && (
            <select
              className="filter-select"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              title="Filter messages by type"
            >
              <option value="all">All Messages</option>
              <option value="normal">Normal Only</option>
            </select>
          )}
        </div>
        <div className="history-messages" ref={messagesEndRef}>
          {!selectedInstance ? (
            <div className="empty-state">
              <History size={48} className="empty-icon" />
              <p>Select a channel, session, and instance to view messages</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="empty-state">
              <MessageSquare size={48} className="empty-icon" />
              <p>No messages in this session</p>
            </div>
          ) : (
            <MessageList
              messages={messages.filter((msg) => {
                if (filterType === 'all') return true;
                const msgType = msg.metadata?.message_type || 'normal';
                return msgType === filterType;
              })}
              messageTtsMap={{}}
              onImageClick={setModalImage}
              renderMessageContent={renderMessageContent}
              selectedInstance={selectedInstance}
            />
          )}
        </div>
      </div>

      {modalImage && (
        <ImageModal image={modalImage} onClose={() => setModalImage(null)} />
      )}

      {workspacePreviewPath && (
        <WorkspaceFilePreviewModal
          sendWSMessage={sendWSMessage}
          pathInput={workspacePreviewPath}
          onClose={() => setWorkspacePreviewPath(null)}
        />
      )}
    </div>
  );
}

export default HistoryPanel;
