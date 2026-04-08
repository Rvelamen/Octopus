import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MessageSquare } from 'lucide-react';
import WindowDots from '../../WindowDots';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import InstanceList from './components/InstanceList';
import MessageList from './components/MessageList';
import ChatInput from './components/ChatInput';
import ImageModal from './components/Modals/ImageModal';
import GenerateImageModal from './components/Modals/GenerateImageModal';
import WorkspaceFilePreviewModal from './components/Modals/WorkspaceFilePreviewModal';
import { looksLikeWorkspaceFilePath } from './utils/workspacePathUtils';
import { useInstances } from './hooks/useInstances';
import { useMessages } from './hooks/useMessages';
import { useFileUpload } from './hooks/useFileUpload';
import { useTTS } from './hooks/useTTS';
import './ChatPanel.css';

function ChatPanel({
  sendWSMessage,
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
  refreshInstanceId,
}) {
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [modalImage, setModalImage] = useState(null);
  const [workspacePreviewPath, setWorkspacePreviewPath] = useState(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState('');
  const [generateSize, setGenerateSize] = useState('1024x1024');
  const [generateQuality, setGenerateQuality] = useState('standard');
  const [isGenerating, setIsGenerating] = useState(false);

  const messagesEndRef = useRef(null);
  const prevStreamingContentRef = useRef('');
  const prevIsProcessingRef = useRef(false);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);

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
  } = useInstances(sendWSMessage);

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
    if (messagesEndRef.current && shouldAutoScroll) {
      messagesEndRef.current.scrollTop = messagesEndRef.current.scrollHeight;
    }
  }, [messages, streamingContent, shouldAutoScroll]);

  useEffect(() => {
    const wasStreaming = prevStreamingContentRef.current && prevStreamingContentRef.current.length > 0;
    const isDone = !streamingContent || streamingContent.length === 0;
    if (wasStreaming && isDone && selectedInstance) {
      console.log('Streaming finished, refreshing messages for instance:', selectedInstance.id);
      fetchInstanceMessages(selectedInstance.id);
    }
    prevStreamingContentRef.current = streamingContent || '';
  }, [streamingContent, selectedInstance]);

  useEffect(() => {
    if (prevIsProcessingRef.current && !isProcessing && selectedInstance) {
      console.log('Agent finished processing, refreshing messages for instance:', selectedInstance.id);
      fetchInstanceMessages(selectedInstance.id);
    }
    prevIsProcessingRef.current = isProcessing;
  }, [isProcessing, selectedInstance]);

  // 监听 refreshInstanceId 变化，在迭代完成时刷新消息
  useEffect(() => {
    if (refreshInstanceId) {
      console.log('Iteration complete, refreshing messages for instance:', refreshInstanceId);
      fetchInstanceMessages(refreshInstanceId);
    }
  }, [refreshInstanceId]);

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
        alert('图片上传失败: ' + err.message);
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
        alert('文件上传失败: ' + err.message);
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
          preview: `http://localhost:18791/workspace/${response.data.file_path}`,
          isGenerated: true
        };
        setPendingImages(prev => [...prev, generatedImage]);
      } else {
        alert('图片生成失败: ' + (response.data?.error || 'Unknown error'));
      }
    } catch (err) {
      alert('图片生成失败: ' + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const renderMessageContent = useCallback((content) => {
    if (!content) return null;
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="md-link"
            >
              {children}
            </a>
          ),
          code({ inline, className, children, ...props }) {
            if (inline) {
              const inlineText = String(children).trim();
              if (looksLikeWorkspaceFilePath(inlineText)) {
                return (
                  <button
                    type="button"
                    className="md-inline-workspace-path"
                    onClick={() => setWorkspacePreviewPath(inlineText)}
                    title="点击预览工作区文件"
                  >
                    {inlineText}
                  </button>
                );
              }
              return (
                <code className="md-inline-code" {...props}>
                  {children}
                </code>
              );
            }
            const text = String(children).replace(/\n$/, '').trim();
            if (looksLikeWorkspaceFilePath(text)) {
              return (
                <button
                  type="button"
                  className="md-code-block md-workspace-path-btn"
                  onClick={() => setWorkspacePreviewPath(text)}
                  title="点击预览工作区文件"
                >
                  <pre {...props}>
                    <code className={className}>{children}</code>
                  </pre>
                </button>
              );
            }
            return (
              <div className="md-code-block">
                <pre {...props}>
                  <code className={className}>{children}</code>
                </pre>
              </div>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
          table({ children }) {
            return (
              <div className="md-table-wrapper">
                <table className="md-table">{children}</table>
              </div>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    );
  }, []);

  const renderPlainContent = (content) => {
    if (!content) return null;
    return <span className="plain-text-content">{content}</span>;
  };

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
          <WindowDots />
          <span className="window-title">
            {isCreatingNew
              ? 'NEW CONVERSATION'
              : selectedInstance
                ? `CHAT - ${selectedInstance.instance_name}`
                : 'SELECT A CHAT'}
          </span>
        </div>

        <div
          className="chat-messages"
          ref={messagesEndRef}
          onScroll={handleScroll}
        >
          {!selectedInstance && !isCreatingNew ? (
            <div className="empty-state">
              <MessageSquare size={48} className="empty-icon" />
              <p>Select a chat or create a new one</p>
            </div>
          ) : messages.length === 0 && !streamingContent ? (
            <div className="empty-state">
              <MessageSquare size={48} className="empty-icon" />
              <p>
                {isCreatingNew
                  ? 'Start a new conversation...'
                  : 'No messages in this chat'}
              </p>
            </div>
          ) : (
            <MessageList
              messages={messages}
              streamingContent={streamingContent}
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
          placeholder={isCreatingNew || selectedInstance ? "输入消息... (Shift+Enter 换行，支持粘贴图片)" : "选择一个对话开始聊天..."}
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
