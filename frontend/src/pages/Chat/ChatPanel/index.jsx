import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare } from 'lucide-react';
import InstanceList from './components/InstanceList/index.jsx';
import MessageList from '@components/MessageList/index.jsx';
import ChatInput from './components/ChatInput/index.jsx';
import ImageModal from './components/Modals/ImageModal.jsx';
import GenerateImageModal from './components/Modals/GenerateImageModal.jsx';
import WorkspaceFilePreviewModal from './components/Modals/WorkspaceFilePreviewModal.jsx';
import { useMessageRenderer } from '@hooks/useMessageRenderer';
import { useInstances } from './hooks/useInstances';
import { useMessages } from './hooks/useMessages';
import { useFileUpload } from './hooks/useFileUpload';
import { useTTS } from './hooks/useTTS';
import { API_BASE } from '../../../config/constants';
import './ChatPanel.css';
import '../../../components/ui/ImageModal.css';

function ChatPanel({
  sendWSMessage,
  connectionStatus,
  onSendMessage,
  onStopGeneration,
  isProcessing,
  streamingContent,
  currentChatInstanceId,
  toolCalls,
  toolCallAssistantContents,
  ttsAudio,
  onTtsPlayed,
  lastElapsedMs,
  lastTokenUsage,
  liveTokenUsage,
  onElapsedMsUpdate,
  onTokenUsageUpdate,
  refreshInstanceId,
  onInstanceIdUpdate,
  hasToolCallsInCurrentRun,
}) {
  const { t } = useTranslation();
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [modalImage, setModalImage] = useState(null);
  const { renderMessageContent, renderPlainContent, workspacePreviewPath, setWorkspacePreviewPath } = useMessageRenderer();
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState('');
  const [generateSize, setGenerateSize] = useState('1024x1024');
  const [generateQuality, setGenerateQuality] = useState('standard');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const [contextStats, setContextStats] = useState(null);

  const messagesEndRef = useRef(null);
  const prevStreamingContentRef = useRef('');
  const prevIsProcessingRef = useRef(false);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const hasAutoSelectedRef = useRef(false);
  const scrollRafRef = useRef(null);
  const lastScrollHeightRef = useRef(0);

  const {
    instances,
    loading,
    initialLoading,
    error,
    instancesHasMore,
    isLoadingMore,
    fetchInstances,
    loadMoreInstances,
    deleteInstance
  } = useInstances(sendWSMessage, connectionStatus);

  const {
    messages,
    loading: messagesLoading,
    fetchInstanceMessages,
    clearMessages,
    addMessage,
    setMessages
  } = useMessages(sendWSMessage, selectedInstance);

  const {
    pendingImages,
    pendingFiles,
    isUploading,
    setIsUploading,
    addPendingImage,
    addPendingFile,
    removePendingImage,
    removePendingFile,
    uploadImage,
    uploadFile,
    clearPendingFiles
  } = useFileUpload(sendWSMessage, selectedInstance);

  const {
    messageTtsMap,
    clearTTS,
    loadTTSFromMessages
  } = useTTS(ttsAudio, messages, selectedInstance, onTtsPlayed);

  useEffect(() => {
    const autoSelectFirstInstance = async () => {
      if (
        !hasAutoSelectedRef.current &&
        !initialLoading &&
        instances.length > 0 &&
        !selectedInstance &&
        !isCreatingNew &&
        sendWSMessage
      ) {
// Removed debug log
        hasAutoSelectedRef.current = true;
        
        try {
          await sendWSMessage('session_set_active', { instance_id: instances[0].id }, 5000);
        } catch (err) {
          console.error('Failed to set active instance:', err);
        }
        
        setSelectedInstance({ ...instances[0], is_active: true });
        setIsCreatingNew(false);
        setShouldAutoScroll(true);
        fetchInstanceMessages(instances[0].id);
      }
    };
    
    autoSelectFirstInstance();
  }, [instances, initialLoading, selectedInstance, isCreatingNew, sendWSMessage, fetchInstanceMessages]);

  useEffect(() => {
    if (!shouldAutoScroll || !messagesEndRef.current) return;
    if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current);
    scrollRafRef.current = requestAnimationFrame(() => {
      const el = messagesEndRef.current;
      if (!el) return;
      if (el.scrollHeight !== lastScrollHeightRef.current) {
        lastScrollHeightRef.current = el.scrollHeight;
        el.scrollTop = el.scrollHeight;
      }
      scrollRafRef.current = null;
    });
    return () => {
      if (scrollRafRef.current) {
        cancelAnimationFrame(scrollRafRef.current);
        scrollRafRef.current = null;
      }
    };
  }, [messages, streamingContent, shouldAutoScroll]);

  const fetchInstanceTokenUsage = useCallback(async (instanceId) => {
    if (!sendWSMessage || !instanceId) return;
    try {
      const response = await sendWSMessage('token_get_usage', {
        scope: 'instance',
        instance_id: instanceId,
      }, 5000);
      if (response.data?.summary) {
        onTokenUsageUpdate(response.data.summary);
      }
    } catch (err) {
      console.error('Failed to fetch instance token usage:', err);
    }
  }, [sendWSMessage, onTokenUsageUpdate]);

  useEffect(() => {
    const wasStreaming = prevStreamingContentRef.current && prevStreamingContentRef.current.length > 0;
    const isDone = !streamingContent || streamingContent.length === 0;
    if (wasStreaming && isDone && selectedInstance) {
// Removed debug log
      fetchInstanceMessages(selectedInstance.id);
    }
    prevStreamingContentRef.current = streamingContent || '';
  }, [streamingContent, selectedInstance]);

  useEffect(() => {
    if (prevIsProcessingRef.current && !isProcessing && selectedInstance) {
// Removed debug log
      fetchInstanceMessages(selectedInstance.id);
      fetchInstanceTokenUsage(selectedInstance.id);
    }
    prevIsProcessingRef.current = isProcessing;
  }, [isProcessing, selectedInstance, fetchInstanceMessages, fetchInstanceTokenUsage]);

  // 监听 refreshInstanceId 变化，在迭代完成时刷新消息和 token 统计
  useEffect(() => {
    if (refreshInstanceId) {
// Removed debug log
      fetchInstanceMessages(refreshInstanceId);
      fetchInstanceTokenUsage(refreshInstanceId);
    }
  }, [refreshInstanceId, fetchInstanceMessages, fetchInstanceTokenUsage]);

  // 获取/刷新当前 instance 的 context 统计
  useEffect(() => {
    if (selectedInstance?.id) {
      fetchContextStats(selectedInstance.id);
    } else {
      setContextStats(null);
    }
  }, [selectedInstance?.id]);

  // 消息变化后 also refresh context stats
  useEffect(() => {
    if (selectedInstance?.id && !isProcessing && !isCompressing) {
      fetchContextStats(selectedInstance.id);
    }
  }, [messages.length]);

  // 同步 selectedInstance 到 App 层，让 App 层正确跟踪当前聊天的 instance ID
  useEffect(() => {
    onInstanceIdUpdate?.(selectedInstance?.id ?? null);
  }, [selectedInstance?.id]);

  // 从消息中恢复 elapsed_ms（token_usage 改为走持久化查询，见 fetchInstanceTokenUsage）
  useEffect(() => {
    if (!messages || messages.length === 0) return;

    // 从后往前找最后一条 assistant 消息
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant') {
        const metadata = msg.metadata || {};
        const elapsedMs = metadata.elapsed_ms;

        if (elapsedMs != null && elapsedMs > 0) {
          onElapsedMsUpdate(elapsedMs);
        }
        break;
      }
    }
  }, [messages]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && modalImage) {
        setModalImage(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalImage]);

  const handleScroll = useCallback(() => {
    if (!messagesEndRef.current) return;
    const el = messagesEndRef.current;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isNearBottom = distanceToBottom < 80;
    if (isNearBottom && !shouldAutoScroll) {
      setShouldAutoScroll(true);
    } else if (!isNearBottom && shouldAutoScroll) {
      setShouldAutoScroll(false);
    }
  }, [shouldAutoScroll]);

  const handleSelectInstance = async (instance) => {
    if (!sendWSMessage) return;

    try {
      await sendWSMessage('session_set_active', { instance_id: instance.id }, 5000);
    } catch (err) {
      console.error('Failed to set active instance:', err);
    }

    setSelectedInstance({ ...instance, is_active: true });
    setIsCreatingNew(false);
    setShouldAutoScroll(true);
    fetchInstanceMessages(instance.id);
    fetchInstanceTokenUsage(instance.id);

    fetchInstances();
  };

  const handleCreateNewChat = async () => {
    if (!sendWSMessage) return;

    try {
      const response = await sendWSMessage('session_create', {
        channel: 'desktop',
        instance_name: 'New Chat'
      }, 5000);

      if (response.data?.instance) {
        const newInstance = response.data.instance;
        await fetchInstances(false, false);
        setSelectedInstance({
          ...newInstance,
          session_key: response.data.session?.session_key,
          chat_id: response.data.session?.chat_id
        });
        setIsCreatingNew(false);
        clearMessages();
      }
    } catch (err) {
      console.error('Failed to create new chat:', err);
      setIsCreatingNew(true);
      setSelectedInstance(null);
      clearMessages();
    }
  };

  const handleDeleteInstance = async (instanceId, e) => {
    e.stopPropagation();
    const success = await deleteInstance(instanceId);
    if (success && selectedInstance?.id === instanceId) {
      setSelectedInstance(null);
      clearMessages();
    }
  };

  const fetchContextStats = useCallback(async (instanceId) => {
    if (!sendWSMessage || !instanceId) return;
    try {
      const res = await sendWSMessage('session_get_context_stats', { instance_id: instanceId }, 5000);
      if (res.data) {
        setContextStats(res.data);
      }
    } catch (err) {
      console.error('Failed to fetch context stats:', err);
    }
  }, [sendWSMessage]);

  const handleCompress = async () => {
    if (!sendWSMessage || !selectedInstance) return;
    const instanceId = selectedInstance.id;
    setIsCompressing(true);
    try {
      await sendWSMessage('session_compress_context', { instance_id: instanceId }, 120000);
      await fetchInstanceMessages(instanceId);
      await fetchContextStats(instanceId);
    } catch (err) {
      console.error('Failed to compress context:', err);
      alert(t('chat.compressFailed') + ': ' + err.message);
    } finally {
      setIsCompressing(false);
    }
  };

  const [slashCommands, setSlashCommands] = useState([]);

  useEffect(() => {
    if (!sendWSMessage || connectionStatus !== 'connected') return;
    sendWSMessage('get_slash_commands', {}, 5000)
      .then(res => {
        const backendCommands = res.data?.slash_commands || [];
        // Merge backend commands with local action handlers
        const commandMap = {
          new: () => {
            setInputValue('');
            handleCreateNewChat();
          },
          clear: () => {
            setInputValue('');
            clearMessages();
          },
          compress: () => {
            setInputValue('');
            handleCompress();
          },
          image: () => {
            setInputValue('');
            setShowGenerateModal(true);
          },
        };
        const merged = backendCommands.map(cmd => ({
          ...cmd,
          action: commandMap[cmd.name] || undefined,
        }));
        setSlashCommands(merged);
      })
      .catch(err => console.error('Failed to get slash commands:', err));
  }, [sendWSMessage, connectionStatus]);

  const handleSend = async () => {
    const hasText = inputValue.trim();
    const hasImages = pendingImages.length > 0;
    const hasFiles = pendingFiles.length > 0;

    if (!hasText && !hasImages && !hasFiles) return;

    const content = inputValue;
    setInputValue('');
    setShouldAutoScroll(true);

    let uploadedImages = [];
    if (hasImages) {
      setIsUploading(true);
      try {
        for (const image of pendingImages) {
          const uploaded = await uploadImage(image);
          uploadedImages.push(uploaded);
        }
      } catch (err) {
        alert(t('chat.uploadImageFailed') + ': ' + err.message);
        setIsUploading(false);
        return;
      }
      clearPendingFiles();
    }
    
    let uploadedFiles = [];
    if (hasFiles) {
      setIsUploading(true);
      try {
        for (const file of pendingFiles) {
          const uploaded = await uploadFile(file);
          uploadedFiles.push(uploaded);
        }
      } catch (err) {
        alert(t('chat.uploadFileFailed') + ': ' + err.message);
        setIsUploading(false);
        return;
      }
      clearPendingFiles();
    }
    
    setIsUploading(false);

    const messageData = {
      content: content,
      images: uploadedImages.map(img => ({
        path: img.path,
        name: img.name
      })),
      files: uploadedFiles.map(file => ({
        path: file.path,
        name: file.name,
        originalName: file.originalName,
        mime_type: file.mimeType,
        size: file.size
      }))
    };

    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: content || '',
      timestamp: new Date().toISOString(),
      metadata: {
        images: uploadedImages,
        files: uploadedFiles
      }
    };
    addMessage(tempUserMessage);

    if (isCreatingNew || !selectedInstance) {
      await onSendMessage?.(messageData);
      setTimeout(() => {
        fetchInstances();
      }, 1000);
    } else {
      await onSendMessage?.(messageData, selectedInstance.id);
      setTimeout(() => {
        fetchInstanceMessages(selectedInstance.id);
      }, 1500);
    }
  };

  const handleGenerateImage = async ({ prompt, size, quality }) => {
    setIsGenerating(true);
    try {
      const response = await sendWSMessage('image_generate', {
        prompt,
        size,
        quality
      }, 120000);

      if (response.data?.success) {
        const generatedImage = {
          id: `generated-${Date.now()}`,
          path: response.data.file_path,
          name: response.data.file_path.split('/').pop(),
          preview: `${API_BASE}/workspace/${response.data.file_path}`,
          isGenerated: true
        };
        setPendingImages(prev => [...prev, generatedImage]);
      } else {
        alert(t('chat.generateImageFailed') + ': ' + (response.data?.error || 'Unknown error'));
      }
    } catch (err) {
      alert(t('chat.generateImageFailed') + ': ' + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  // renderMessageContent / workspacePreviewPath provided by useMessageRenderer

  return (
    <div className="chat-layout">
      <InstanceList
        instances={instances}
        selectedInstance={selectedInstance}
        loading={loading}
        initialLoading={initialLoading}
        error={error}
        hasMore={instancesHasMore}
        isLoadingMore={isLoadingMore}
        sendWSMessage={sendWSMessage}
        onSelect={handleSelectInstance}
        onDelete={handleDeleteInstance}
        onCreateNew={handleCreateNewChat}
        onRefresh={() => fetchInstances(true, false)}
        isCreatingNew={isCreatingNew}
        onScrollEnd={loadMoreInstances}
      />

      <div className="chat-main">
        <div className="window-header">
          {/* 窗口控制按钮已在全局 App titlebar 提供，此处不重复渲染 */}
          <span className="window-title">
            {isCreatingNew
              ? 'NEW CONVERSATION'
              : selectedInstance
                ? `CHAT - ${selectedInstance.instance_name}`
                : 'SELECT A CHAT'}
          </span>
        </div>

        {isCompressing && (
          <div className="compressing-banner">
            <div className="compressing-spinner" />
            <span>{t('chat.compressing')}</span>
          </div>
        )}

        <div
          className="chat-messages"
          ref={messagesEndRef}
          onScroll={handleScroll}
        >
          {!selectedInstance && !isCreatingNew ? (
            <div className="empty-state">
              <MessageSquare size={48} className="empty-icon" />
              <p>{t('chat.emptySelect')}</p>
            </div>
          ) : messages.length === 0 && !streamingContent ? (
            <div className="empty-state">
              <MessageSquare size={48} className="empty-icon" />
              <p>
                {isCreatingNew
                  ? t('chat.emptyNew')
                  : t('chat.emptyNone')}
              </p>
            </div>
          ) : (
            <MessageList
              messages={messages}
              streamingContent={streamingContent}
              isProcessing={isProcessing}
              toolCalls={toolCalls}
              toolCallAssistantContents={toolCallAssistantContents}
              messageTtsMap={messageTtsMap}
              selectedInstance={selectedInstance}
              currentChatInstanceId={currentChatInstanceId}
              onImageClick={setModalImage}
              renderMessageContent={renderMessageContent}
              renderPlainContent={renderPlainContent}
              lastElapsedMs={lastElapsedMs}
              lastTokenUsage={lastTokenUsage}
              liveTokenUsage={liveTokenUsage}
              hasToolCallsInCurrentRun={hasToolCallsInCurrentRun}
            />
          )}
        </div>

        <ChatInput
          inputValue={inputValue}
          onInputChange={setInputValue}
          onSend={handleSend}
          onStop={onStopGeneration}
          isProcessing={isProcessing}
          isUploading={isUploading}
          disabled={!isCreatingNew && !selectedInstance}
          pendingImages={pendingImages}
          pendingFiles={pendingFiles}
          onRemoveImage={removePendingImage}
          onRemoveFile={removePendingFile}
          onImageClick={setModalImage}
          onSelectImage={addPendingImage}
          onSelectFile={addPendingFile}
          onGenerateImage={() => setShowGenerateModal(true)}
          placeholder={isCreatingNew || selectedInstance ? t('chat.placeholderActive') : t('chat.placeholderSelect')}
          onCompress={handleCompress}
          isCompressing={isCompressing}
          contextStats={contextStats}
          slashCommands={slashCommands}
        />
      </div>

      {modalImage && (
        <ImageModal
          image={modalImage}
          onClose={() => setModalImage(null)}
        />
      )}

      <GenerateImageModal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        onGenerate={handleGenerateImage}
      />

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

export default ChatPanel;
