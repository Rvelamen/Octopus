import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Routes,
  Route,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  MessageSquare,
  Settings,
  Server,
  Bot,
  Package,
  History,
  FolderOpen,
  Clock,
  Users,
  RotateCcw,
  Zap,
  Volume2,
  X,
  Play,
  Pause,
  PanelLeftClose,
  PanelRight,
} from "lucide-react";
import octopusLogo from "./assets/octopus-logo.png";
import WindowDots from "./components/WindowDots";
import {
  ConfigPanel,
  ChatPanel,
  MCPPanel,
  ExtensionsPanel,
  HistoryPanel,
  WorkspacePanel,
  CronPanel,
  AgentsPanel,
  TokenUsagePanel,
} from "./components/panels";

const WS_BASE = "ws://127.0.0.1:18791";

const APP_TITLE_BY_TAB = {
  chat: "TERMINAL_SESSION",
  config: "CONFIG_EDITOR",
  mcp: "MCP_SERVERS",
  extensions: "EXTENSIONS",
  cron: "CRON",
  agents: "AGENTS",
  workspace: "WORKSPACE_EXPLORER",
  history: "HISTORY",
  tokens: "TOKENS",
};

/**
 * 生成唯一请求 ID
 */
const generateRequestId = () => {
  return `req-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * TTS 音频播放器组件
 */
function TTSPlayer({ audioData, format, text, durationMs, onClose }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    if (audioRef.current && audioData) {
      audioRef.current.src = `data:audio/${format};base64,${audioData}`;
      audioRef.current.load();
    }
  }, [audioData, format]);

  const handlePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handlePlay = () => setIsPlaying(true);
  const handlePause = () => setIsPlaying(false);

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    if (audioRef.current) {
      audioRef.current.currentTime = percentage * duration;
    }
  };

  return (
    <div className="tts-player">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        onPlay={handlePlay}
        onPause={handlePause}
      />
      
      <div className="tts-player-content">
        <div className="tts-player-icon">
          <Volume2 size={18} />
        </div>
        
        <button className="tts-player-btn" onClick={handlePlayPause}>
          {isPlaying ? <Pause size={16} /> : <Play size={16} />}
        </button>
        
        <div className="tts-player-progress" onClick={handleSeek}>
          <div 
            className="tts-player-progress-bar" 
            style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
          />
        </div>
        
        <div className="tts-player-time">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
        
        {text && (
          <div className="tts-player-text" title={text}>
            {text.length > 30 ? text.substring(0, 30) + '...' : text}
          </div>
        )}
        
        <button className="tts-player-close" onClick={onClose}>
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

/**
 * App 主组件
 */
function App() {
  // ===== 状态 =====
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [config, setConfig] = useState({
    providers: {},
    agents: { defaults: { model: "deepseek-chat", workspace: "" } },
    tools: {},
    channels: {},
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const streamingContentRef = useRef("");
  const streamingFlushTimerRef = useRef(null);

  // 窗口焦点状态 - 用于控制交通灯颜色（失焦时变为灰色）
  const [isWindowFocused, setIsWindowFocused] = useState(true);

  const resetStreamingContent = useCallback(() => {
    if (streamingFlushTimerRef.current) {
      clearTimeout(streamingFlushTimerRef.current);
      streamingFlushTimerRef.current = null;
    }
    streamingContentRef.current = "";
    setStreamingContent("");
  }, []);

  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const appendStreamingContent = useCallback((text) => {
    streamingContentRef.current += text || "";
    if (!streamingFlushTimerRef.current) {
      streamingFlushTimerRef.current = setTimeout(() => {
        streamingFlushTimerRef.current = null;
        if (activeTabRef.current === 'chat') {
          setStreamingContent(streamingContentRef.current);
        }
      }, 80);
    }
  }, []);

  const [currentChatInstanceId, setCurrentChatInstanceId] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [isSaving, setIsSaving] = useState(false);
  const [toolCalls, _setToolCalls] = useState([]); // 实时工具调用（仅当前 instance）
  const [toolCallAssistantContents, _setToolCallAssistantContents] = useState({}); // 按 iteration 存储的 assistant content（仅当前 instance）
  const toolCallsByInstanceRef = useRef({}); // { [instanceId]: ToolCall[] }，全量缓存
  const assistantContentsByInstanceRef = useRef({}); // { [instanceId]: { [iteration]: content } }
  const currentChatInstanceIdRef = useRef(null);
  currentChatInstanceIdRef.current = currentChatInstanceId;
  const prevToolCallInstanceRef = useRef(null); // 切换前保存 toolCalls

  // 统一的 setter：同时写 ref（所有 instance 的数据）和 state（仅当前可见 instance 的数据）
  const setToolCalls = useCallback((updater) => {
    _setToolCalls((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = currentChatInstanceIdRef.current;
      if (id != null) toolCallsByInstanceRef.current[id] = next;
      return next;
    });
  }, []);

  const setToolCallAssistantContents = useCallback((updater) => {
    _setToolCallAssistantContents((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = currentChatInstanceIdRef.current;
      if (id != null) assistantContentsByInstanceRef.current[id] = next;
      return next;
    });
  }, []);

  // 切换 instance 时保存/恢复 toolCalls（与 useMessages 完全一致的模式）
  useEffect(() => {
    const newId = currentChatInstanceId;
    const prevId = prevToolCallInstanceRef.current;

    // 保存切出 instance 的 toolCalls
    if (prevId !== undefined && prevId !== null && prevId !== newId) {
      toolCallsByInstanceRef.current[prevId] = toolCallsByInstanceRef.current[prevId] || [];
    }
    prevToolCallInstanceRef.current = newId;

    // 恢复目标 instance 的 toolCalls（可能为 undefined，此时用空数组）
    if (newId !== null) {
      const restored = toolCallsByInstanceRef.current[newId];
      _setToolCalls(restored ?? []);
      _setToolCallAssistantContents(assistantContentsByInstanceRef.current[newId] ?? {});
    } else {
      _setToolCalls([]);
      _setToolCallAssistantContents({});
    }
  }, [currentChatInstanceId]);

  const [isRestarting, setIsRestarting] = useState(false);
  const [tokenUsage, setTokenUsage] = useState({
    global: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, request_count: 0 },
    currentSession: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, request_count: 0 },
  });
  const [ttsAudio, setTtsAudio] = useState(null); // { audioData, format, text, durationMs, instanceId, messageId }
  const [ttsAudioMap, setTtsAudioMap] = useState({}); // { messageId: { audioData, format, text, durationMs } }
  const [lastElapsedMs, setLastElapsedMs] = useState(null); // 最近一次 agent 运行的耗时（毫秒）
  const [lastTokenUsage, setLastTokenUsage] = useState(null); // 最近一次 agent 运行的 token 消耗
  const [liveTokenUsage, setLiveTokenUsage] = useState(null); // 当前运行中累计的 token 消耗（随 agent_iteration_complete 累加）
  const [refreshInstanceId, setRefreshInstanceId] = useState(null); // 需要刷新的 instance ID
  const [hasToolCallsInCurrentRun, setHasToolCallsInCurrentRun] = useState(false); // 当前 agent run 是否产生过 tool call

  // ===== Refs =====
  const ws = useRef(null);
  const pendingRequests = useRef(new Map());

  // ===== WebSocket 消息发送 =====
  const sendWSMessage = useCallback((type, data, timeout = 10000) => {
    return new Promise((resolve, reject) => {
      if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
        reject(new Error("WebSocket not connected"));
        return;
      }

      const requestId = generateRequestId();
      const message = { type, request_id: requestId, data };

      pendingRequests.current.set(requestId, { resolve, reject });
      ws.current.send(JSON.stringify(message));

      setTimeout(() => {
        if (pendingRequests.current.has(requestId)) {
          pendingRequests.current.delete(requestId);
          reject(new Error("Request timeout"));
        }
      }, timeout);
    });
  }, []);

  // ===== WebSocket 连接 =====
  useEffect(() => {
    let reconnectTimer = null;
    let isComponentMounted = true;

    const updateToolCallsForInstance = (instanceId, updater) => {
      if (instanceId == null) return;
      const prev = toolCallsByInstanceRef.current[instanceId] ?? [];
      const next = typeof updater === 'function' ? updater(prev) : updater;
      toolCallsByInstanceRef.current[instanceId] = next;
    };

    const updateAssistantContentsForInstance = (instanceId, updater) => {
      if (instanceId == null) return;
      const prev = assistantContentsByInstanceRef.current[instanceId] ?? {};
      const next = typeof updater === 'function' ? updater(prev) : updater;
      assistantContentsByInstanceRef.current[instanceId] = next;
    };

    const connectWS = () => {
      if (
        ws.current &&
        (ws.current.readyState === WebSocket.OPEN ||
          ws.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      ws.current = new WebSocket(`${WS_BASE}/ws`);

      ws.current.onopen = () => {
        if (isComponentMounted) setConnectionStatus("connected");
      };

      ws.current.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const { type, request_id, data } = payload;

        console.log('[WebSocket] Received message:', { type, request_id, data });

        // 处理待处理请求
        if (request_id && pendingRequests.current.has(request_id)) {
          const { resolve, reject } = pendingRequests.current.get(request_id);
          pendingRequests.current.delete(request_id);
          type === "error"
            ? reject(new Error(data?.error || "Unknown error"))
            : resolve({ type, data });
          return;
        }

        // 处理聊天相关事件
        if (!isComponentMounted) return;

        console.log('[WebSocket] Processing event:', type);

        const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
        const isCurrentInstance = eventInstanceId == null || eventInstanceId === currentChatInstanceIdRef.current;

        switch (type) {
          case "agent_token":
            if (!isCurrentInstance) return;
            appendStreamingContent(data.content || "");
            break;
          case "agent_chunk":
            if (!isCurrentInstance) return;
            console.log('[WebSocket] Agent chunk received:', data?.content?.substring(0, 50));
            appendStreamingContent(data.content || "");
            break;
          case "agent_start":
            if (!isCurrentInstance) {
              updateToolCallsForInstance(eventInstanceId, () => []);
              updateAssistantContentsForInstance(eventInstanceId, () => ({}));
              return;
            }
            resetStreamingContent();
            setToolCalls(() => []);
            setToolCallAssistantContents(() => ({}));
            setLiveTokenUsage(null);
            setHasToolCallsInCurrentRun(false);
            break;
          case "agent_thinking":
            if (!isCurrentInstance) return;
            setIsProcessing(true);
            resetStreamingContent();
            setToolCallAssistantContents((prev) => prev || {});
            break;
          case "chat_response":
            if (!isCurrentInstance) {
              updateToolCallsForInstance(eventInstanceId, () => []);
              updateAssistantContentsForInstance(eventInstanceId, () => ({}));
              return;
            }
            resetStreamingContent();
            setIsProcessing(false);
            setToolCalls(() => []);
            setToolCallAssistantContents(() => ({}));
            setLiveTokenUsage(null);
            break;
          case "error":
            if (!isCurrentInstance) {
              updateToolCallsForInstance(eventInstanceId, () => []);
              updateAssistantContentsForInstance(eventInstanceId, () => ({}));
              return;
            }
            resetStreamingContent();
            setIsProcessing(false);
            setToolCalls(() => []);
            setToolCallAssistantContents(() => ({}));
            setLiveTokenUsage(null);
            break;
          case "agent_finish":
            if (!isCurrentInstance) {
              updateToolCallsForInstance(eventInstanceId, () => []);
              updateAssistantContentsForInstance(eventInstanceId, () => ({}));
              return;
            }
            console.log('[WebSocket] Agent finish received:', data);
            console.log('[Debug] token_usage in data:', data.token_usage);
            resetStreamingContent();
            setIsProcessing(false);
            if (data.elapsed_ms != null) {
              setLastElapsedMs(data.elapsed_ms);
            }
            if (data.token_usage) {
              console.log('[Debug] Setting lastTokenUsage:', data.token_usage);
              setLastTokenUsage(data.token_usage);
              setLiveTokenUsage(data.token_usage);
            }
            setToolCalls(() => []);
            setToolCallAssistantContents(() => ({}));
            break;
          case "agent_tool_call_start": {
            const addToolCall = (prev) => [...prev, {
              id: data.tool_call_id || Date.now(),
              tool: data.tool,
              args: data.args || {},
              partialArgs: data.partial_args || data.args || {},
              status: 'pending',
              result: null,
              iteration: data.iteration || 1
            }];
            if (data.content) {
              const setContent = (prev) => ({ ...prev, [data.iteration]: data.content });
              if (isCurrentInstance) {
                setToolCallAssistantContents(setContent);
                resetStreamingContent();
              } else {
                updateAssistantContentsForInstance(eventInstanceId, setContent);
              }
            }
            if (isCurrentInstance) {
              setToolCalls(addToolCall);
              setHasToolCallsInCurrentRun(true);
            } else {
              updateToolCallsForInstance(eventInstanceId, addToolCall);
            }
            break;
          }
          case "agent_tool_call_streaming": {
            const updater = (prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, partialArgs: data.partial_args, status: 'streaming' }
                : tc
            );
            if (isCurrentInstance) setToolCalls(updater);
            else updateToolCallsForInstance(eventInstanceId, updater);
            break;
          }
          case "agent_tool_call_invoking": {
            const updater = (prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: tc.partialArgs || tc.args, status: 'invoking' }
                : tc
            );
            if (isCurrentInstance) setToolCalls(updater);
            else updateToolCallsForInstance(eventInstanceId, updater);
            break;
          }
          case "agent_tool_call_complete": {
            const updater = (prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: data.args || tc.partialArgs || tc.args, result: data.result, status: 'completed' }
                : tc
            );
            if (isCurrentInstance) setToolCalls(updater);
            else updateToolCallsForInstance(eventInstanceId, updater);
            break;
          }
          case "agent_tool_call_error": {
            const updater = (prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: data.args || tc.partialArgs || tc.args, error: data.error, status: 'error' }
                : tc
            );
            if (isCurrentInstance) setToolCalls(updater);
            else updateToolCallsForInstance(eventInstanceId, updater);
            break;
          }
          case "agent_tool_call": {
            const addToolCall = (prev) => [...prev, {
              id: data.tool_call_id || Date.now(),
              tool: data.tool,
              args: data.args,
              status: 'running',
              result: null,
              iteration: data.iteration
            }];
            if (data.content) {
              const setContent = (prev) => ({ ...prev, [data.iteration]: data.content });
              if (isCurrentInstance) setToolCallAssistantContents(setContent);
              else updateAssistantContentsForInstance(eventInstanceId, setContent);
            }
            if (isCurrentInstance) setToolCalls(addToolCall);
            else updateToolCallsForInstance(eventInstanceId, addToolCall);
            break;
          }
          case "agent_tool_result": {
            const updater = (prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, status: 'completed', result: data.result }
                : tc
            );
            if (isCurrentInstance) setToolCalls(updater);
            else updateToolCallsForInstance(eventInstanceId, updater);
            break;
          }
          case "subagent_tool_call": {
            console.log('[WebSocket] subagent_tool_call received:', JSON.stringify(data, null, 2));
            console.log('[WebSocket] Current toolCalls:', JSON.parse(JSON.stringify(toolCalls)));
            console.log('[WebSocket] isCurrentInstance:', isCurrentInstance, 'eventInstanceId:', eventInstanceId);
            const parentToolCallId = data.parent_tool_call_id;
            console.log('[WebSocket] parentToolCallId:', parentToolCallId);
            
            // 如果 parentToolCallId 不存在，创建一个新的 subagent container
            const subagentUpdater = (prev) => {
              const targetTc = prev.find(tc => tc.id === parentToolCallId);
              console.log('[WebSocket] Finding target toolCall with id:', parentToolCallId, 'found:', !!targetTc);
              
              if (targetTc) {
                return prev.map(tc =>
                  tc.id === parentToolCallId
                    ? {
                        ...tc,
                        subagentCalls: [...(tc.subagentCalls || []), {
                          id: data.tool_call_id,
                          tool: data.tool,
                          args: data.args,
                          status: 'running',
                          subagentId: data.subagent_id,
                          subagentLabel: data.subagent_label,
                        }]
                      }
                    : tc
                );
              }
              
              // 如果找不到父 toolCall，也添加到列表中
              console.log('[WebSocket] Parent toolCall not found, adding as standalone subagent');
              return [...prev, {
                id: parentToolCallId || `subagent-${Date.now()}`,
                tool: 'spawn',
                args: { task: 'subagent' },
                status: 'running',
                subagentCalls: [{
                  id: data.tool_call_id,
                  tool: data.tool,
                  args: data.args,
                  status: 'running',
                  subagentId: data.subagent_id,
                  subagentLabel: data.subagent_label,
                }],
                isSubagentContainer: true,
              }];
            };
            
            if (isCurrentInstance) setToolCalls(subagentUpdater);
            else updateToolCallsForInstance(eventInstanceId, subagentUpdater);
            break;
          }
          case "subagent_tool_result": {
            console.log('[WebSocket] subagent_tool_result received:', JSON.stringify(data, null, 2));
            console.log('[WebSocket] Current toolCalls:', JSON.parse(JSON.stringify(toolCalls)));
            const parentToolCallId = data.parent_tool_call_id;
            console.log('[WebSocket] parentToolCallId for result:', parentToolCallId);
            
            const subagentResultUpdater = (prev) => {
              // 尝试找到父 toolCall 并更新 subagentCalls
              const updated = prev.map(tc =>
                tc.id === parentToolCallId && tc.subagentCalls
                  ? {
                      ...tc,
                      subagentCalls: tc.subagentCalls?.map(sc =>
                        sc.id === data.tool_call_id
                          ? { ...sc, status: 'completed', result: data.result }
                          : sc
                      )
                    }
                  : tc
              );
              
              // 如果没有找到父 toolCall，检查是否有 standalone subagent
              const hasTarget = updated.some(tc => tc.id === parentToolCallId);
              if (!hasTarget) {
                // 添加一个包含 subagent 结果的容器
                return [...updated, {
                  id: parentToolCallId || `subagent-${Date.now()}`,
                  tool: 'spawn',
                  args: { task: 'subagent' },
                  status: 'completed',
                  subagentCalls: [{
                    id: data.tool_call_id,
                    tool: data.tool,
                    status: 'completed',
                    result: data.result,
                  }],
                  isSubagentContainer: true,
                }];
              }
              return updated;
            };
            
            if (isCurrentInstance) setToolCalls(subagentResultUpdater);
            else updateToolCallsForInstance(eventInstanceId, subagentResultUpdater);
            break;
          }
          case "agent_iteration_complete": {
            const targetId = data?.session_instance_id ?? currentChatInstanceIdRef.current;
            if (targetId) {
              setRefreshInstanceId(targetId);
            }
            if (isCurrentInstance && data?.token_usage) {
              setLiveTokenUsage(data.token_usage);
            }
            break;
          }
          case "mcp_state_change":
            // MCP state change event - can be used to update UI in real-time
            console.log("MCP state change:", data);
            break;
          case "token_usage":
            // Token usage response
            if (data.scope === "global") {
              setTokenUsage(prev => ({
                ...prev,
                global: data.summary || prev.global,
              }));
            } else if (data.scope === "instance") {
              setTokenUsage(prev => ({
                ...prev,
                currentSession: data.summary || prev.currentSession,
              }));
            }
            break;
          case "token_usage_update":
            // Real-time token usage update
            console.log("Token usage update:", data);
            break;
          case "tts_auto_reply":
            // TTS audio auto reply - store for player to display
            console.log("TTS auto reply received:", data?.instanceId);
            if (data?.audio && data?.format) {
              setTtsAudio({
                audioData: data.audio,
                format: data.format,
                text: data.text,
                durationMs: data.duration_ms,
                instanceId: data.instanceId
              });
            }
            break;

        }
      };

      ws.current.onclose = (event) => {
        if (isComponentMounted) {
          setConnectionStatus("disconnected");
          if (event.code !== 1000 && event.code !== 1001) {
            reconnectTimer = setTimeout(() => {
              if (isComponentMounted) connectWS();
            }, 3000);
          }
        }
      };

      ws.current.onerror = () => {
        if (isComponentMounted) setConnectionStatus("disconnected");
      };
    };

    connectWS();

    return () => {
      isComponentMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (streamingFlushTimerRef.current) {
        clearTimeout(streamingFlushTimerRef.current);
        streamingFlushTimerRef.current = null;
      }
      if (ws.current) {
        ws.current.close(1000, "Component unmounting");
        ws.current = null;
      }
    };
  }, []);

  // ===== 发送消息 =====
  const handleSendMessage = async (messageData, instanceId = null) => {
    setIsProcessing(true);
    resetStreamingContent();
    setLiveTokenUsage(null);
    // 同步更新 ref，确保 WS 事件到达时 currentChatInstanceIdRef 是发送时的 instance_id
    currentChatInstanceIdRef.current = instanceId;
    setCurrentChatInstanceId(instanceId);

    try {
      // 支持两种调用方式：
      // 1. 旧方式: handleSendMessage("文本内容", instanceId)
      // 2. 新方式: handleSendMessage({ content: "文本", images: [...] }, instanceId)
      let payload;
      if (typeof messageData === 'string') {
        payload = { content: messageData };
      } else {
        payload = {
          content: messageData.content || '',
          images: messageData.images || [],
          files: messageData.files || []
        };
      }

      if (instanceId) {
        payload.instance_id = instanceId;
      }
      await sendWSMessage("chat", payload, 5000);
    } catch (err) {
      setIsProcessing(false);
      setCurrentChatInstanceId(null);
      console.error("Failed to send message:", err);
    }
  };

  // ===== 停止生成 =====
  const handleStopGeneration = async () => {
    try {
      // 传递当前正在处理的 instance_id，以便后端精准停止对应任务
      await sendWSMessage("stop_agents", { 
        instance_id: currentChatInstanceId 
      }, 5000);
      setIsProcessing(false);
      resetStreamingContent();
      setToolCalls([]);
      setToolCallAssistantContents({});
      setLiveTokenUsage(null);
    } catch (err) {
      console.error("Failed to stop generation:", err);
      setIsProcessing(false);
    }
  };

  // ===== 保存配置 =====
  const handleSaveConfig = async (configToSave) => {
    setIsSaving(true);
    try {
      await sendWSMessage("save_config", { config: configToSave }, 5000);
      alert("Configuration saved successfully!");
    } finally {
      setIsSaving(false);
    }
  };

  // ===== 重启后端服务 =====
  const handleRestart = async () => {
    if (!confirm("确定要重启后端服务吗？\n\n注意：\n- 插件安装后需要重启才能生效\n- Provider配置更新后建议重启")) {
      return;
    }
    setIsRestarting(true);
    try {
      await sendWSMessage("restart_service", {}, 5000);
      alert("重启指令已发送，服务正在重启...");
    } catch (err) {
      console.error("Failed to restart service:", err);
      alert("重启请求失败: " + err.message);
    } finally {
      setIsRestarting(false);
    }
  };

  // ===== 路由导航 =====
  const navigate = useNavigate();
  const location = useLocation();

  // 同步 activeTab 与路由
  useEffect(() => {
    const path = location.pathname;
    if (path === '/chat') {
      setActiveTab('chat');
    } else if (path === '/config') {
      setActiveTab('config');
    } else if (path === '/mcp') {
      setActiveTab('mcp');
    } else if (path === '/extensions') {
      setActiveTab('extensions');
    } else if (path === '/cron') {
      setActiveTab('cron');
    } else if (path === '/agents') {
      setActiveTab('agents');
    } else if (path === '/workspace') {
      setActiveTab('workspace');
    } else if (path === '/history') {
      setActiveTab('history');
    } else if (path === '/tokens') {
      setActiveTab('tokens');
    }
  }, [location.pathname]);

  // 切回 chat tab 时，把 ref 中累积的 streamingContent 同步到 state
  useEffect(() => {
    if (activeTab === 'chat') {
      setStreamingContent(streamingContentRef.current);
    }
  }, [activeTab]);

  // 处理导航
  const handleNavClick = (tab) => {
    setActiveTab(tab);
    const routeMap = {
      chat: '/chat',
      config: '/config',
      mcp: '/mcp',
      extensions: '/extensions',
      cron: '/cron',
      agents: '/agents',
      workspace: '/workspace',
      history: '/history',
      tokens: '/tokens',
    };
    navigate(routeMap[tab] || '/chat');
  };

  const appTitleBarText = APP_TITLE_BY_TAB[activeTab] ?? "OCTOPUS";

  // ===== 渲染 =====
  return (
    <div className="app-container">
      {/* 整窗顶栏：品牌区（Logo+折叠）宽度与侧栏一致，右侧为当前页标题 */}
      <header className="app-titlebar">
        <div className="app-titlebar-brand">
          <div className="app-titlebar-logo-pill">
            <div className="logo app-titlebar-logo">
              <img src={octopusLogo} alt="Octopus" className="logo-icon" style={{ width: 24, height: 30, objectFit: 'contain' }} />
              <span className="logo-text">OCTOPUS</span>
            </div>
          </div>
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            {sidebarCollapsed ? <PanelRight size={14} /> : <PanelLeftClose size={14} />}
          </button>
        </div>
        <div className="app-titlebar-sep" aria-hidden />
        <div className="tab-title">
          <span>{appTitleBarText}</span>
        </div>
        <div className="top-actions" style={{ WebkitAppRegion: 'no-drag' }}>
          <button
            className="restart-btn"
            onClick={handleRestart}
            disabled={isRestarting || connectionStatus !== "connected"}
            title="重启后端服务"
            style={{ WebkitAppRegion: 'no-drag' }}
          >
            <RotateCcw size={12} className={isRestarting ? "spinning" : ""} />
            <span>{isRestarting ? "…" : "RESTART"}</span>
          </button>
          <div className={`status-indicator ${connectionStatus}`} style={{ WebkitAppRegion: 'no-drag' }}></div>
          <span className={`status-text ${connectionStatus}`} style={{ WebkitAppRegion: 'no-drag' }}>
            {connectionStatus === "connected"
              ? "ONLINE"
              : connectionStatus === "connecting"
                ? "CONNECTING..."
                : "OFFLINE"}
          </span>
        </div>
      </header>

      <div className={`app-body ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}>
      {/* Sidebar：仅导航，顶栏已上提 */}
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="sidebar-nav">
          <nav>
            <button
              className={`nav-item ${activeTab === "chat" ? "active" : ""}`}
              onClick={() => handleNavClick("chat")}
            >
              <Bot size={18} />
              <span>CHAT</span>
            </button>
            <button
              className={`nav-item ${activeTab === "config" ? "active" : ""}`}
              onClick={() => handleNavClick("config")}
            >
              <Settings size={18} />
              <span>SYSTEM</span>
            </button>
            <button
              className={`nav-item ${activeTab === "mcp" ? "active" : ""}`}
              onClick={() => handleNavClick("mcp")}
            >
              <Server size={18} />
              <span>SERVERS</span>
            </button>
            <button
              className={`nav-item ${activeTab === "extensions" ? "active" : ""}`}
              onClick={() => handleNavClick("extensions")}
            >
              <Package size={18} />
              <span>EXTENSIONS</span>
            </button>
            <button
              className={`nav-item ${activeTab === "cron" ? "active" : ""}`}
              onClick={() => handleNavClick("cron")}
            >
              <Clock size={18} />
              <span>CRON</span>
            </button>
            <button
              className={`nav-item ${activeTab === "agents" ? "active" : ""}`}
              onClick={() => handleNavClick("agents")}
            >
              <Users size={18} />
              <span>AGENTS</span>
            </button>
            <button
              className={`nav-item ${activeTab === "workspace" ? "active" : ""}`}
              onClick={() => handleNavClick("workspace")}
            >
              <FolderOpen size={18} />
              <span>WORKSPACE</span>
            </button>
            <button
              className={`nav-item ${activeTab === "history" ? "active" : ""}`}
              onClick={() => handleNavClick("history")}
            >
              <History size={18} />
              <span>HISTORY</span>
            </button>
            <button
              className={`nav-item ${activeTab === "tokens" ? "active" : ""}`}
              onClick={() => handleNavClick("tokens")}
            >
              <Zap size={18} />
              <span>TOKENS</span>
            </button>
          </nav>
          <div className="status-panel">
            <div className="status-line">VER: 1.0.0</div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <div className="content-area">
          <Routes>
            <Route path="/chat" element={
              <ChatPanel
                sendWSMessage={sendWSMessage}
                onSendMessage={handleSendMessage}
                onStopGeneration={handleStopGeneration}
                isProcessing={isProcessing}
                streamingContent={streamingContent}
                currentChatInstanceId={currentChatInstanceId}
                toolCalls={toolCalls}
                toolCallAssistantContents={toolCallAssistantContents}
                ttsAudio={ttsAudio}
                onTtsPlayed={() => setTtsAudio(null)}
                lastElapsedMs={lastElapsedMs}
                lastTokenUsage={lastTokenUsage}
                liveTokenUsage={liveTokenUsage}
                onElapsedMsUpdate={setLastElapsedMs}
                onTokenUsageUpdate={setLastTokenUsage}
                refreshInstanceId={refreshInstanceId}
                onInstanceIdUpdate={setCurrentChatInstanceId}
                hasToolCallsInCurrentRun={hasToolCallsInCurrentRun}
              />
            } />
            <Route path="/config" element={
              <ConfigPanel
                config={config}
                setConfig={setConfig}
                onSave={handleSaveConfig}
                isSaving={isSaving}
                sendWSMessage={sendWSMessage}
              />
            } />
            <Route path="/mcp" element={<MCPPanel sendWSMessage={sendWSMessage} />} />
            <Route path="/extensions" element={
              <ExtensionsPanel sendWSMessage={sendWSMessage} ws={ws.current} />
            } />
            <Route path="/workspace" element={
              <WorkspacePanel sendWSMessage={sendWSMessage} />
            } />
            <Route path="/history" element={
              <HistoryPanel sendWSMessage={sendWSMessage} />
            } />
            <Route path="/cron" element={<CronPanel sendWSMessage={sendWSMessage} />} />
            <Route path="/agents" element={<AgentsPanel sendWSMessage={sendWSMessage} />} />
            <Route path="/tokens" element={<TokenUsagePanel sendWSMessage={sendWSMessage} />} />
            <Route path="/" element={
              <ChatPanel
                sendWSMessage={sendWSMessage}
                onSendMessage={handleSendMessage}
                onStopGeneration={handleStopGeneration}
                isProcessing={isProcessing}
                streamingContent={streamingContent}
                currentChatInstanceId={currentChatInstanceId}
                toolCalls={toolCalls}
                toolCallAssistantContents={toolCallAssistantContents}
                ttsAudio={ttsAudio}
                onTtsPlayed={() => setTtsAudio(null)}
                lastElapsedMs={lastElapsedMs}
                lastTokenUsage={lastTokenUsage}
                liveTokenUsage={liveTokenUsage}
                onElapsedMsUpdate={setLastElapsedMs}
                onTokenUsageUpdate={setLastTokenUsage}
                refreshInstanceId={refreshInstanceId}
                hasToolCallsInCurrentRun={hasToolCallsInCurrentRun}
              />
            } />
          </Routes>
        </div>
      </main>
      </div>
    </div>
  );
}

export default App;
