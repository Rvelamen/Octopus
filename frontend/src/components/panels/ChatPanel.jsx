import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MessageSquare, RefreshCw, Trash2, Wrench, ChevronUp, ChevronDown, Plus, Image, X, Upload, Check, Loader2, Copy, FileText, Maximize2, Minimize2, Send, CirclePause, GripVertical } from 'lucide-react';
import WindowDots from '../WindowDots';
import { parseLinks } from '../../utils/linkUtils';
import octopusAvatar from '../../assets/images/octopus.png';

const API_BASE = 'http://localhost:18791';

/**
 * ChatPanel 组件 - 聊天面板（Desktop Channel 专用）
 * 左侧直接显示 Instance 列表，右侧显示消息
 */
function ChatPanel({
  sendWSMessage,
  onSendMessage,
  onStopGeneration,
  isProcessing,
  streamingContent,
  currentChatInstanceId,
  toolCalls,
  toolCallAssistantContents
}) {
  // ===== 状态 =====
  const [instances, setInstances] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedTools, setExpandedTools] = useState(new Set());
  const [inputValue, setInputValue] = useState('');
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [pendingImages, setPendingImages] = useState([]); // 待发送的图片列表
  const [isUploading, setIsUploading] = useState(false);
  const [isInputExpanded, setIsInputExpanded] = useState(false); // 编辑区域是否展开
  const [inputHeight, setInputHeight] = useState(120); // 编辑区域高度

  // 分页状态
  const [instancesPage, setInstancesPage] = useState(0);
  const [instancesHasMore, setInstancesHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const PAGE_SIZE = 20;

  const messagesEndRef = useRef(null);
  const isComponentMounted = useRef(true);
  const fileInputRef = useRef(null);
  const dropZoneRef = useRef(null);
  const instanceListRef = useRef(null);
  const textareaRef = useRef(null);

  // ===== 获取 Desktop Channel 的所有 Instances =====
  const fetchInstances = useCallback(async (showError = true, isInitialLoad = false, append = false) => {
    if (!sendWSMessage) return;

    if (isInitialLoad) {
      setInitialLoading(true);
      setInstancesPage(0);
      setInstancesHasMore(true);
    } else if (!append) {
      setLoading(true);
    } else {
      setIsLoadingMore(true);
    }

    if (showError) setError(null);
    try {
      const offset = append ? (instancesPage * PAGE_SIZE) : 0;
      const response = await sendWSMessage('session_get_instances', {
        channel: 'desktop',
        limit: PAGE_SIZE,
        offset: offset
      }, 5000);

      const newInstances = response.data?.instances || [];
      const hasMore = response.data?.has_more ?? false;

      if (append) {
        setInstances(prev => [...prev, ...newInstances]);
      } else {
        setInstances(newInstances);
      }

      setInstancesHasMore(hasMore);
      setInstancesPage(append ? instancesPage + 1 : 1);
    } catch (err) {
      console.error('Failed to fetch instances:', err);
      if (showError) {
        setError(err.message);
      }
    } finally {
      if (isInitialLoad) {
        setInitialLoading(false);
      } else if (!append) {
        setLoading(false);
      } else {
        setIsLoadingMore(false);
      }
    }
  }, [sendWSMessage, instancesPage]);

  // ===== 加载更多 Instances =====
  const loadMoreInstances = useCallback(() => {
    if (!instancesHasMore || isLoadingMore || loading) return;
    fetchInstances(false, false, true);
  }, [instancesHasMore, isLoadingMore, loading, fetchInstances]);

  // ===== 滚动监听 =====
  const handleInstanceListScroll = useCallback((e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    if (scrollHeight - scrollTop - clientHeight < 50) {
      loadMoreInstances();
    }
  }, [loadMoreInstances]);

  // ===== 获取 Instance 的消息 =====
  const fetchInstanceMessages = useCallback(async (instanceId) => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('session_get_messages', { instance_id: instanceId, limit: 1000 }, 5000);
      console.log('fetchInstanceMessages response:', response.data);
      if (response.data?.messages) {
        console.log('Fetched messages:', response.data.messages);
        // Merge with existing messages to preserve optimistic update images
        const fetchedMessages = response.data.messages;
        setMessages(prev => {
          // Create a map of existing messages by role+content for quick lookup
          const existingMap = new Map();
          prev.forEach(msg => {
            const key = `${msg.role}:${msg.content}`;
            existingMap.set(key, msg);
          });

          // Merge fetched messages with existing ones
          return fetchedMessages.map(msg => {
            const key = `${msg.role}:${msg.content}`;
            const existing = existingMap.get(key);

            // Get images from both - handle nested structure
            const existingImages = existing?.metadata?.images || existing?.metadata?.metadata?.images;
            const fetchedImages = msg.metadata?.images || msg.metadata?.metadata?.images;
            const hasFetchedImages = fetchedImages && fetchedImages.length > 0;

            console.log('Existing images:', existingImages);
            console.log('Fetched images:', fetchedImages);

            // If existing message has images but fetched doesn't have valid images, merge them
            if (existingImages && existingImages.length > 0 && !hasFetchedImages) {
              console.log('Merging images from optimistic update:', existingImages);
              // Preserve existing metadata structure but add images
              return {
                ...msg,
                metadata: {
                  ...msg.metadata,
                  images: existingImages
                }
              };
            }
            return msg;
          });
        });
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // ===== 初始加载 =====
  useEffect(() => {
    isComponentMounted.current = true;
    // 页面一加载就显示loading并开始获取数据
    fetchInstances(false, true);
    return () => {
      isComponentMounted.current = false;
    };
  }, []);

  // ===== WebSocket 连接建立后重新加载数据 =====
  useEffect(() => {
    if (sendWSMessage && isComponentMounted.current && initialLoading) {
      // WebSocket 连接成功后重新尝试获取数据
      fetchInstances(false, false);
    }
  }, [sendWSMessage]);

  // ===== 定期重试加载数据（处理 F5 刷新时 WebSocket 未就绪的情况） =====
  useEffect(() => {
    if (instances.length === 0 && !initialLoading && !error && sendWSMessage) {
      // 如果没有数据且初始加载已完成，每 2 秒重试一次
      const retryTimer = setInterval(() => {
        if (isComponentMounted.current) {
          fetchInstances(false, true);
        }
      }, 2000);

      // 10 秒后停止重试
      const stopTimer = setTimeout(() => {
        clearInterval(retryTimer);
      }, 10000);

      return () => {
        clearInterval(retryTimer);
        clearTimeout(stopTimer);
      };
    }
  }, [instances.length, initialLoading, error, sendWSMessage, fetchInstances]);

  // ===== 自动滚动到最新消息 =====
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollTop = messagesEndRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  // ===== Streaming 结束时刷新消息 =====
  const prevStreamingContentRef = useRef('');
  useEffect(() => {
    // 当 streamingContent 从有内容变为空时，说明回复已完成，刷新消息列表
    const wasStreaming = prevStreamingContentRef.current && prevStreamingContentRef.current.length > 0;
    const isDone = !streamingContent || streamingContent.length === 0;
    if (wasStreaming && isDone && selectedInstance) {
      console.log('Streaming finished, refreshing messages for instance:', selectedInstance.id);
      fetchInstanceMessages(selectedInstance.id);
    }
    prevStreamingContentRef.current = streamingContent || '';
  }, [streamingContent, selectedInstance]);

  // ===== 选择 Instance 查看消息 =====
  const handleSelectInstance = async (instance) => {
    if (!sendWSMessage) return;

    // 设置为 active
    try {
      await sendWSMessage('session_set_active', { instance_id: instance.id }, 5000);
    } catch (err) {
      console.error('Failed to set active instance:', err);
    }

    // 更新选中状态
    setSelectedInstance({ ...instance, is_active: true });
    setIsCreatingNew(false);
    fetchInstanceMessages(instance.id);

    // 更新 instances 列表中的 active 状态（全局只有一个active）
    setInstances(prev => prev.map(inst => ({
      ...inst,
      is_active: inst.id === instance.id
    })));
  };

  // ===== 创建新对话 =====
  const handleCreateNewChat = async () => {
    if (!sendWSMessage) return;

    try {
      // 调用API创建新session和instance
      const response = await sendWSMessage('session_create', {
        channel: 'desktop',
        instance_name: 'New Chat'
      }, 5000);

      if (response.data?.instance) {
        const newInstance = response.data.instance;
        // 刷新instance列表（不显示错误，不显示loading）
        await fetchInstances(false, false);
        // 选中新创建的instance
        setSelectedInstance({
          ...newInstance,
          session_key: response.data.session?.session_key,
          chat_id: response.data.session?.chat_id
        });
        setIsCreatingNew(false);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to create new chat:', err);
      // 如果创建失败，仍然进入新对话模式
      setIsCreatingNew(true);
      setSelectedInstance(null);
      setMessages([]);
    }
  };

  // ===== 删除 Instance =====
  const deleteInstance = async (instanceId, e) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this session instance? This will also delete all messages in it.')) {
      return;
    }

    try {
      await sendWSMessage('session_delete_instance', { instance_id: instanceId }, 5000);
      // 如果删除的是当前选中的 instance，清空消息
      if (selectedInstance?.id === instanceId) {
        setSelectedInstance(null);
        setMessages([]);
      }
      // 刷新 instances 列表
      fetchInstances();
    } catch (err) {
      console.error('Failed to delete instance:', err);
      alert('Failed to delete instance: ' + err.message);
    }
  };

  // ===== 发送消息 =====
  const handleSend = async () => {
    const hasText = inputValue.trim();
    const hasImages = pendingImages.length > 0;

    if (!hasText && !hasImages) return;

    const content = inputValue;
    setInputValue('');

    // 如果有图片，先上传
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
      setIsUploading(false);
      setPendingImages([]); // 清空待发送图片
    }

    // 构建消息数据
    const messageData = {
      content: content,
      images: uploadedImages.map(img => ({
        path: img.path,
        name: img.name
      }))
    };

    // 立即显示用户消息到界面（ optimistic update ）
    // Note: content should match what backend saves (text_content from multimodal message)
    const displayContent = content || '';
    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: displayContent,
      timestamp: new Date().toISOString(),
      metadata: {
        images: uploadedImages
      }
    };
    setMessages(prev => [...prev, tempUserMessage]);

    // 如果是新对话，先创建
    if (isCreatingNew || !selectedInstance) {
      // 新对话的消息会由后端自动创建 session 和 instance
      // 这里只需要发送消息，然后刷新列表
      await onSendMessage?.(messageData);
      // 刷新 instances 列表以获取新创建的 instance
      setTimeout(() => {
        fetchInstances();
      }, 1000);
    } else {
      // 继续现有对话，传递 instance_id
      await onSendMessage?.(messageData, selectedInstance.id);
      // 延迟刷新消息列表，确保后端已保存消息
      setTimeout(() => {
        fetchInstanceMessages(selectedInstance.id);
      }, 1500);
    }
  };

  const handleKeyDown = (e) => {
    // 检查是否在输入法组合状态（如拼音输入）
    if (e.nativeEvent?.isComposing || e.isComposing) {
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ===== 图片处理函数 =====

  // 选择文件
  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    processFiles(files);
    // 清空 input 以便可以重复选择同一文件
    e.target.value = '';
  };

  // 处理文件列表
  const processFiles = async (files) => {
    const imageFiles = files.filter(file => file.type.startsWith('image/'));
    if (imageFiles.length === 0) {
      alert('请选择图片文件');
      return;
    }

    for (const file of imageFiles) {
      await addPendingImage(file);
    }
  };

  // 添加待发送图片
  const addPendingImage = (file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const newImage = {
          id: `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file: file,
          preview: e.target.result,
          name: file.name,
          type: file.type,
          size: file.size
        };
        setPendingImages(prev => [...prev, newImage]);
        resolve();
      };
      reader.readAsDataURL(file);
    });
  };

  // 移除待发送图片
  const removePendingImage = (imageId) => {
    setPendingImages(prev => prev.filter(img => img.id !== imageId));
  };

  // 上传单张图片到服务器
  const uploadImage = async (image) => {
    try {
      const response = await sendWSMessage('image_upload', {
        image_data: image.preview,
        file_name: image.name,
        mime_type: image.type,
        session_instance_id: selectedInstance?.id
      }, 30000);

      if (response.data?.success) {
        return {
          path: response.data.file_path,
          name: response.data.file_name,
          full_path: response.data.full_path
        };
      }
      throw new Error(response.data?.error || 'Upload failed');
    } catch (err) {
      console.error('Failed to upload image:', err);
      throw err;
    }
  };

  // 处理粘贴事件
  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageItems = Array.from(items).filter(item => item.type.startsWith('image/'));
    if (imageItems.length > 0) {
      e.preventDefault();
      imageItems.forEach(item => {
        const file = item.getAsFile();
        if (file) {
          addPendingImage(file);
        }
      });
    }
  };

  // 拖拽处理
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropZoneRef.current) {
      dropZoneRef.current.style.display = 'flex';
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // 检查是否真的离开了元素（而不是进入了子元素）
    if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) {
      if (dropZoneRef.current) {
        dropZoneRef.current.style.display = 'none';
      }
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropZoneRef.current) {
      dropZoneRef.current.style.display = 'none';
    }

    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length > 0) {
      processFiles(files);
    }
  };

  // ===== 渲染带链接的消息内容 =====
  const renderMessageContent = (content) => {
    if (!content) return null;
    return content.split('\n').map((line, lineIdx) => {
      const parts = parseLinks(line);
      return (
        <div key={lineIdx}>
          {parts.map((part, partIdx) => {
            if (part.type === 'link') {
              return (
                <a
                  key={partIdx}
                  href={part.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="message-link"
                >
                  {part.displayText}
                </a>
              );
            }
            return <span key={partIdx}>{part.content}</span>;
          })}
        </div>
      );
    });
  };

  // ===== 渲染消息中的图片 =====
  const renderMessageImages = (metadata) => {
    console.log('renderMessageImages metadata:', metadata);
    // Handle nested metadata structure: metadata.metadata.images
    const images = metadata?.images || metadata?.metadata?.images;
    console.log('renderMessageImages images:', images);
    if (!images || images.length === 0) return null;

    return (
      <div className="message-images">
        {images.map((img, idx) => (
          <div key={idx} className="message-image-item" onClick={() => openImageModal(img)}>
            <img
              src={img.path ? `${API_BASE}/workspace/${img.path}` : ''}
              alt={img.name || `Image ${idx + 1}`}
              onError={(e) => {
                console.log('Image load error, path:', img.path);
                e.target.src = '';
                e.target.style.display = 'none';
              }}
            />
            {img.name && <span className="message-image-name">{img.name}</span>}
          </div>
        ))}
      </div>
    );
  };

  // ===== 图片放大查看 =====
  const [modalImage, setModalImage] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);

  const openImageModal = (image) => {
    setModalImage(image);
    setImageLoading(true);
  };

  const closeImageModal = () => {
    setModalImage(null);
    setImageLoading(false);
  };

  // ESC 键关闭 modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && modalImage) {
        closeImageModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalImage]);

  // ===== 图片生成对话框 =====
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState('');
  const [generateSize, setGenerateSize] = useState('1024x1024');
  const [generateQuality, setGenerateQuality] = useState('standard');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateImage = async () => {
    if (!generatePrompt.trim()) return;

    setIsGenerating(true);
    try {
      const response = await sendWSMessage('image_generate', {
        prompt: generatePrompt,
        size: generateSize,
        quality: generateQuality
      }, 120000);

      if (response.data?.success) {
        // 将生成的图片添加到待发送列表
        const generatedImage = {
          id: `generated-${Date.now()}`,
          path: response.data.file_path,
          name: response.data.file_path.split('/').pop(),
          preview: `${API_BASE}/workspace/${response.data.file_path}`,
          isGenerated: true
        };
        setPendingImages(prev => [...prev, generatedImage]);
        setShowGenerateModal(false);
        setGeneratePrompt('');
      } else {
        alert('图片生成失败: ' + (response.data?.error || 'Unknown error'));
      }
    } catch (err) {
      alert('图片生成失败: ' + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  // ===== 切换工具消息展开状态 =====
  const toggleToolExpand = (toolCallId) => {
    const newExpanded = new Set(expandedTools);
    if (newExpanded.has(toolCallId)) {
      newExpanded.delete(toolCallId);
    } else {
      newExpanded.add(toolCallId);
    }
    setExpandedTools(newExpanded);
  };

  // ===== 将消息列表中的 tool_call 和 tool_result 配对 =====
  // hideToolPairs: 当正在 streaming 或有活跃的 tool calls 时，隐藏消息列表中的 tool pairs
  // 避免与实时显示的 tool calls 重复
  const pairToolMessages = (messages, hideToolPairs = false) => {
    const pairs = [];
    const toolResults = new Map();
    const seenMessages = new Set();

    messages.forEach(msg => {
      const toolCallId = msg.metadata?.tool_call_id || msg.tool_call_id;
      if (toolCallId && (msg.role === 'tool' || msg.message_type === 'tool_result')) {
        toolResults.set(toolCallId, msg);
      }
    });

    messages.forEach(msg => {
      const msgKey = `${msg.role}:${msg.content}:${msg.timestamp}`;
      if (seenMessages.has(msgKey)) {
        return;
      }
      seenMessages.add(msgKey);

      // Check for compression summary message
      if (msg.metadata?.is_summary || msg.metadata?.message_type === 'context_summary') {
        pairs.push({
          type: 'compression_summary',
          message: msg,
          compressionInfo: msg.metadata?.compression_info || {}
        });
        return;
      }

      const toolCalls = msg.metadata?.tool_calls || msg.tool_calls;
      if (toolCalls && toolCalls.length > 0) {
        // 如果正在 streaming 或有活跃的 tool calls，跳过消息列表中的 tool pairs
        // 因为它们会在实时区域显示
        if (hideToolPairs) {
          return;
        }
        // 支持多个 tool calls - 每个 tool call 单独配对
        toolCalls.forEach((tc, index) => {
          const callId = tc?.id;
          const result = toolResults.get(callId);
          pairs.push({
            type: 'tool_pair',
            call: msg,
            result: result,
            toolCallId: callId,
            toolName: tc?.function?.name,
            toolCall: tc,
            toolIndex: index,
            totalTools: toolCalls.length
          });
        });
      } else if (!msg.metadata?.tool_call_id && !msg.tool_call_id) {
        pairs.push({ type: 'normal', message: msg });
      }
    });

    return pairs;
  };

  // ===== 渲染 Tool Card - 通用函数，实时和历史消息共用 =====
  const renderToolCard = ({ 
    toolCallId, 
    toolName, 
    args, 
    result, 
    status, 
    assistantContent, 
    toolIndex = 0, 
    totalTools = 1 
  }) => {
    const isExpanded = expandedTools.has(toolCallId);

    // 解析参数为对象用于表格展示
    const parsedArgs = typeof args === 'string' ? (() => {
      try {
        return JSON.parse(args);
      } catch {
        return {};
      }
    })() : (args || {});

    // 解析结果为字符串
    const parseResult = () => {
      if (!result) return null;
      try {
        const parsed = JSON.parse(result);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      }
    };

    const resultContent = parseResult();

    return (
      <div className="tool-card">
        {/* Assistant Content - 只在第一个 tool call 时展示，避免重复 */}
        {assistantContent && toolIndex === 0 && (
          <div className="tool-card-assistant-content">
            {renderMessageContent(assistantContent)}
          </div>
        )}
        
        {/* Tool Card Header */}
        <div
          className={`tool-card-header ${status}`}
          onClick={() => toggleToolExpand(toolCallId)}
        >
          <div className="tool-card-header-left">
            <div className={`tool-status-indicator ${status}`}>
              {status === 'completed' ? (
                <Check size={12} />
              ) : (
                <Loader2 size={12} className="spin" />
              )}
            </div>
            <Wrench size={14} className="tool-icon" />
            <span className="tool-card-name">{toolName || 'unknown'}</span>
            {totalTools > 1 && (
              <span className="tool-card-index">({toolIndex + 1}/{totalTools})</span>
            )}
          </div>
          <div className="tool-card-header-right">
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </div>

        {/* Tool Card Body - 展开显示详情 */}
        {isExpanded && (
          <div className="tool-card-body">
            {/* Parameters Table */}
            {Object.keys(parsedArgs).length > 0 && (
              <div className="tool-card-section">
                <div className="tool-card-section-title">Parameters</div>
                <table className="tool-params-table">
                  <tbody>
                    {Object.entries(parsedArgs).map(([key, value]) => (
                      <tr key={key}>
                        <td className="tool-param-key">{key}</td>
                        <td className="tool-param-value">
                          <code>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Result */}
            <div className="tool-card-section">
              <div className="tool-card-section-header">
                <div className="tool-card-section-title">Result</div>
                {resultContent && (
                  <button 
                    className="tool-copy-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(resultContent);
                    }}
                    title="Copy result"
                  >
                    <Copy size={12} />
                  </button>
                )}
              </div>
              {resultContent ? (
                <pre className="tool-card-code">{resultContent}</pre>
              ) : (
                <div className="tool-card-pending">
                  <Loader2 size={14} className="spin" />
                  <span>Waiting for result...</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  // ===== 渲染配对的 tool 消息（call + result）- 使用通用 Tool Card =====
  const renderPairedToolMessage = (pair) => {
    const { call, result, toolCallId, toolName, toolCall, toolIndex, totalTools } = pair;
    const tc = toolCall || (call.metadata?.tool_calls || call.tool_calls)?.[0];
    const status = result ? 'completed' : 'pending';

    return renderToolCard({
      toolCallId,
      toolName,
      args: tc?.function?.arguments || '{}',
      result: result?.content,
      status,
      assistantContent: call.content,
      toolIndex,
      totalTools
    });
  };

  // ===== 格式化时间 =====
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // ===== 格式化相对时间 =====
  const formatRelativeTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="chat-layout">
      {/* Left Sidebar: Instance List */}
      <div className="chat-sidebar">
        <div className="window-header">
          <WindowDots />
          <span className="window-title">CHATS</span>
          <button
            className="refresh-btn"
            onClick={() => fetchInstances(true, false)}
            disabled={loading || !sendWSMessage}
            title={!sendWSMessage ? 'WebSocket not connected' : 'Refresh'}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="new-chat-section">
          <button
            className={`new-chat-btn ${isCreatingNew ? 'active' : ''}`}
            onClick={handleCreateNewChat}
          >
            <Plus size={16} />
            <span>NEW CHAT</span>
          </button>
        </div>

        <div 
          className="chat-instance-list" 
          ref={instanceListRef}
          onScroll={handleInstanceListScroll}
        >
          {initialLoading && (
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <div className="loading-text">Loading chats...</div>
            </div>
          )}
          {error && !initialLoading && (
            <div className="empty-state-small" style={{ color: 'var(--error)', fontSize: '11px' }}>
              Error: {error}
            </div>
          )}
          {!sendWSMessage && !initialLoading && (
            <div className="empty-state-small" style={{ color: 'var(--warning)', fontSize: '11px' }}>
              WebSocket not connected
            </div>
          )}
          {instances.length === 0 && !error && sendWSMessage && !initialLoading && (
            <div className="empty-state-small">
              No chats found
            </div>
          )}

          {instances.map((instance) => (
            <div
              key={instance.id}
              className={`instance-row ${selectedInstance?.id === instance.id ? 'selected' : ''}`}
              onClick={() => handleSelectInstance(instance)}
            >
              <div className="instance-info">
                <div className="instance-name-row">
                  <span className="instance-indicator"></span>
                  <span className="instance-name" title={instance.instance_name}>
                    {instance.instance_name}
                  </span>
                  {instance.is_active === true && <span className="active-badge">active</span>}
                </div>
                <div className="instance-meta">
                  <span className="instance-time">{formatRelativeTime(instance.created_at)}</span>
                </div>
              </div>
              <button
                className="delete-instance-btn"
                onClick={(e) => deleteInstance(instance.id, e)}
                title="Delete this chat"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}

          {isLoadingMore && (
            <div className="loading-more">
              <div className="loading-spinner-small"></div>
              <span>Loading more...</span>
            </div>
          )}

          {!instancesHasMore && instances.length > 0 && !initialLoading && (
            <div className="no-more-data">
              No more chats
            </div>
          )}
        </div>
      </div>

      {/* Right: Chat Messages */}
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
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* 拖拽提示遮罩 */}
          <div
            ref={dropZoneRef}
            className="drop-zone-overlay"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0, 255, 65, 0.1)',
              border: '2px dashed var(--primary)',
              display: 'none',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 100,
              pointerEvents: 'none'
            }}
          >
            <div style={{ textAlign: 'center', color: 'var(--primary)' }}>
              <Upload size={48} />
              <p>拖拽图片到此处上传</p>
            </div>
          </div>

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
            <div className="messages-list">
              {(() => {
                const isStreaming = streamingContent && streamingContent.length > 0;
                const hasActiveToolCalls = toolCalls && toolCalls.length > 0 && selectedInstance?.id === currentChatInstanceId;
                return pairToolMessages(messages, isStreaming || hasActiveToolCalls).map((pair, idx) => {
                  if (pair.type === 'compression_summary') {
                    const msg = pair.message;
                    const compressionInfo = pair.compressionInfo;
                    return (
                      <div key={msg.id || idx} className="compression-summary-wrapper">
                        <div className="compression-summary-card">
                          <div className="compression-summary-header">
                            <FileText size={16} />
                            <span>对话摘要</span>
                            {compressionInfo.compressed_count && (
                              <span className="compression-badge">
                                已压缩 {compressionInfo.compressed_count} 条消息
                              </span>
                            )}
                          </div>
                          <div className="compression-summary-content">
                            {renderMessageContent(msg.content)}
                          </div>
                          {compressionInfo.compressed_at && (
                            <div className="compression-summary-footer">
                              <span>压缩时间: {formatTime(compressionInfo.compressed_at)}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  } else if (pair.type === 'tool_pair') {
                    const { toolCallId } = pair;
                    return (
                      <div
                        key={toolCallId || idx}
                        className="tool-message-wrapper"
                      >
                        {renderPairedToolMessage(pair)}
                      </div>
                    );
                  } else {
                    const msg = pair.message;
                    const isUser = msg.role === 'user';
                    return (
                      <div
                        key={msg.id || idx}
                        className={`message-row ${isUser ? 'message-row-user' : 'message-row-assistant'}`}
                      >
                        <div className={`message-bubble ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}`}>
                          <div className="message-bubble-header">
                            <div className="message-bubble-avatar">
                              {isUser ? (
                                <div className="avatar-user">U</div>
                              ) : (
                                <img src={octopusAvatar} className="avatar-assistant-img" alt="Octopus" />
                              )}
                            </div>
                            <div className="message-bubble-meta">
                              <span className="message-bubble-author">{isUser ? 'You' : 'Octopus'}</span>
                              <span className="message-bubble-time">{formatTime(msg.timestamp)}</span>
                            </div>
                          </div>
                          <div className="message-bubble-content">
                            {msg.content ? renderMessageContent(msg.content) : (
                              msg.metadata?.images ? <span className="image-placeholder">[图片]</span> : null
                            )}
                          </div>
                          {renderMessageImages(msg.metadata)}
                        </div>
                      </div>
                    );
                  }
                });
              })()}

              {/* 实时工具调用显示 - 使用与历史消息相同的 Tool Card 样式 */}
              {(() => {
                if (!toolCalls || toolCalls.length === 0 || selectedInstance?.id !== currentChatInstanceId) {
                  return null;
                }
                
                // 按 iteration 分组
                const iterationGroups = {};
                toolCalls.forEach(tc => {
                  const iter = tc.iteration || 1;
                  if (!iterationGroups[iter]) {
                    iterationGroups[iter] = [];
                  }
                  iterationGroups[iter].push(tc);
                });
                
                // 渲染每个 iteration 的 tool calls
                return Object.entries(iterationGroups).map(([iteration, calls]) => (
                  <div key={`iteration-${iteration}`} className="tool-iteration-group">
                    {calls.map((toolCall, idx) => (
                      <div key={toolCall.id || idx} className="tool-message-wrapper">
                        {renderToolCard({
                          toolCallId: `live-${toolCall.id}`,
                          toolName: toolCall.tool,
                          args: toolCall.args,
                          result: toolCall.result,
                          status: toolCall.status === 'completed' ? 'completed' : 'pending',
                          assistantContent: idx === 0 ? toolCallAssistantContents[iteration] : null,
                          toolIndex: idx,
                          totalTools: calls.length
                        })}
                      </div>
                    ))}
                  </div>
                ));
              })()}

              {/* Streaming message preview - 只在当前选中的 instance 是当前聊天的 instance 时显示 */}
              {streamingContent && selectedInstance?.id === currentChatInstanceId && (
                <div className="message-row message-row-assistant streaming">
                  <div className="message-bubble message-bubble-assistant">
                    <div className="message-bubble-header">
                      <div className="message-bubble-avatar">
                        <img src={octopusAvatar} className="avatar-assistant-img" alt="Octopus" />
                      </div>
                      <div className="message-bubble-meta">
                        <span className="message-bubble-author">Octopus</span>
                        <span className="message-bubble-time streaming-indicator">
                          <span className="blink">streaming</span>
                        </span>
                      </div>
                    </div>
                    <div className="message-bubble-content">
                      {renderMessageContent(streamingContent)}
                      <span className="cursor-blink">_</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="chat-input-wrapper">
          {/* 图片预览区域 */}
          {pendingImages.length > 0 && (
            <div className="pending-images-container">
              {pendingImages.map((image) => (
                <div key={image.id} className="pending-image-item" onClick={() => openImageModal(image)}>
                  <img
                    src={image.preview}
                    alt={image.name}
                    className="pending-image-preview"
                  />
                  <button
                    className="remove-image-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      removePendingImage(image.id);
                    }}
                    title="移除图片"
                  >
                    <X size={12} />
                  </button>
                  <span className="pending-image-name" title={image.name}>
                    {image.name.length > 15 ? image.name.substring(0, 12) + '...' : image.name}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className={`inputbar-container ${isInputExpanded ? 'expanded' : ''}`}>
            {/* 拖拽调整高度把手 */}
            <div 
              className="inputbar-drag-handle"
              onMouseDown={(e) => {
                const startY = e.clientY;
                const startHeight = inputHeight;
                const handleMouseMove = (moveEvent) => {
                  const deltaY = startY - moveEvent.clientY;
                  const newHeight = Math.max(60, Math.min(300, startHeight + deltaY));
                  setInputHeight(newHeight);
                };
                const handleMouseUp = () => {
                  document.removeEventListener('mousemove', handleMouseMove);
                  document.removeEventListener('mouseup', handleMouseUp);
                };
                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
              }}
            >
              <GripVertical size={14} />
            </div>

            {/* 输入区域 */}
            <div className="inputbar-textarea-wrapper">
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={isCreatingNew || selectedInstance ? "输入消息... (Shift+Enter 换行，支持粘贴图片)" : "选择一个对话开始聊天..."}
                className="inputbar-textarea"
                disabled={isProcessing || isUploading || (!isCreatingNew && !selectedInstance)}
                autoFocus
                style={{ height: isInputExpanded ? inputHeight : 60 }}
              />
            </div>

            {/* 底部工具栏 */}
            <div className="inputbar-bottom-bar">
              <div className="inputbar-left-tools">
                {/* 展开/收起按钮 */}
                <button
                  className="inputbar-tool-btn"
                  onClick={() => setIsInputExpanded(!isInputExpanded)}
                  title={isInputExpanded ? "收起编辑区" : "展开编辑区"}
                >
                  {isInputExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>
                {/* 图片上传按钮 */}
                <button
                  className="inputbar-tool-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing || isUploading || (!isCreatingNew && !selectedInstance)}
                  title="上传图片"
                >
                  <Image size={16} />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFileSelect}
                  style={{ display: 'none' }}
                />
                {/* 图片生成按钮 */}
                <button
                  className="inputbar-tool-btn"
                  onClick={() => setShowGenerateModal(true)}
                  disabled={isProcessing || isUploading || (!isCreatingNew && !selectedInstance)}
                  title="生成图片"
                >
                  <FileText size={16} />
                </button>
              </div>
              <div className="inputbar-right-tools">
                {/* 字符计数 */}
                {inputValue.length > 0 && (
                  <span className="inputbar-char-count">{inputValue.length}</span>
                )}
                {/* 发送/暂停按钮 */}
                {isProcessing ? (
                  <button
                    className="inputbar-send-btn pause"
                    onClick={onStopGeneration}
                    title="停止生成"
                  >
                    <CirclePause size={18} />
                  </button>
                ) : (
                  <button
                    className="inputbar-send-btn"
                    onClick={handleSend}
                    disabled={isUploading || (!isCreatingNew && !selectedInstance) || (!inputValue.trim() && pendingImages.length === 0)}
                    title="发送消息"
                  >
                    <Send size={18} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 图片放大查看 Modal */}
      {modalImage && (
        <div className="image-modal-overlay" onClick={closeImageModal}>
          <div className="image-modal-content" onClick={e => e.stopPropagation()}>
            <button className="image-modal-close" onClick={closeImageModal}>
              <X size={24} />
            </button>
            {imageLoading && (
              <div className="image-modal-loading">
                <div className="loading-spinner-large"></div>
                <span>加载中...</span>
              </div>
            )}
            <img
              src={modalImage.preview || (modalImage.path ? `${API_BASE}/workspace/${modalImage.path}` : '')}
              alt={modalImage.name || 'Image'}
              className={`image-modal-img ${imageLoading ? 'loading' : 'loaded'}`}
              onLoad={() => setImageLoading(false)}
              onError={() => setImageLoading(false)}
            />
            {modalImage.name && (
              <div className="image-modal-name">{modalImage.name}</div>
            )}
          </div>
        </div>
      )}

      {/* 图片生成 Modal */}
      {showGenerateModal && (
        <div className="image-modal-overlay" onClick={() => setShowGenerateModal(false)}>
          <div className="image-modal-content generate-modal" onClick={e => e.stopPropagation()}>
            <div className="generate-modal-header">
              <h3>生成图片</h3>
              <button className="image-modal-close" onClick={() => setShowGenerateModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="generate-modal-body">
              <div className="form-group">
                <label>描述提示词</label>
                <textarea
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                  placeholder="描述你想要生成的图片，例如：一只可爱的橘猫在草地上玩耍..."
                  rows={4}
                  className="pixel-textarea"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>尺寸</label>
                  <select
                    value={generateSize}
                    onChange={(e) => setGenerateSize(e.target.value)}
                    className="pixel-select"
                  >
                    <option value="1024x1024">1024x1024 (方形)</option>
                    <option value="1024x1792">1024x1792 (竖版)</option>
                    <option value="1792x1024">1792x1024 (横版)</option>
                    <option value="512x512">512x512 (小图)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>质量</label>
                  <select
                    value={generateQuality}
                    onChange={(e) => setGenerateQuality(e.target.value)}
                    className="pixel-select"
                  >
                    <option value="standard">Standard (标准)</option>
                    <option value="hd">HD (高清)</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="generate-modal-footer">
              <button
                className="pixel-button secondary"
                onClick={() => setShowGenerateModal(false)}
                disabled={isGenerating}
              >
                取消
              </button>
              <button
                className="pixel-button primary"
                onClick={handleGenerateImage}
                disabled={isGenerating || !generatePrompt.trim()}
              >
                {isGenerating ? (
                  <>
                    <span className="loading-spinner-small"></span>
                    生成中...
                  </>
                ) : (
                  <>
                    <Image size={16} />
                    生成图片
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatPanel;
