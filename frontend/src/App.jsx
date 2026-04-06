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
  const [config, setConfig] = useState({
    providers: {},
    agents: { defaults: { model: "deepseek-chat", workspace: "" } },
    tools: {},
    channels: {},
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [currentChatInstanceId, setCurrentChatInstanceId] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [isSaving, setIsSaving] = useState(false);
  const [toolCalls, setToolCalls] = useState([]); // 实时工具调用状态
  const [toolCallAssistantContents, setToolCallAssistantContents] = useState({}); // 按 iteration 存储的 assistant content
  const [isRestarting, setIsRestarting] = useState(false); // 重启状态
  const [tokenUsage, setTokenUsage] = useState({
    global: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, request_count: 0 },
    currentSession: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, request_count: 0 },
  });
  const [ttsAudio, setTtsAudio] = useState(null); // { audioData, format, text, durationMs, instanceId, messageId }
  const [ttsAudioMap, setTtsAudioMap] = useState({}); // { messageId: { audioData, format, text, durationMs } }

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

        switch (type) {
          case "agent_token":
            // New: Real-time streaming token
            setStreamingContent((prev) => prev + (data.content || ""));
            break;
          case "agent_chunk":
            console.log('[WebSocket] Agent chunk received:', data?.content?.substring(0, 50));
            setStreamingContent((prev) => prev + (data.content || ""));
            break;
          case "agent_start":
            setStreamingContent("");
            setToolCalls([]); // 清空之前的工具调用
            setToolCallAssistantContents({}); // 清空 assistant content
            break;
          case "chat_response":
            setStreamingContent("");
            setIsProcessing(false);
            setToolCalls([]); // 清空工具调用
            setToolCallAssistantContents({}); // 清空 assistant content
            break;
          case "error":
            setStreamingContent("");
            setIsProcessing(false);
            setToolCalls([]); // 清空工具调用
            setToolCallAssistantContents({}); // 清空 assistant content
            break;
          case "agent_finish":
            console.log('[WebSocket] Agent finish received:', data);
            setStreamingContent("");
            setIsProcessing(false);
            setToolCalls([]); // 清空工具调用
            setToolCallAssistantContents({}); // 清空 assistant content
            break;
          case "agent_tool_call_start":
            // Tool call started
            setToolCalls((prev) => [...prev, {
              id: data.tool_call_id || Date.now(),
              tool: data.tool,
              args: {},
              partialArgs: {},
              status: 'pending',
              result: null,
              iteration: data.iteration || 1
            }]);
            break;
          case "agent_tool_call_streaming":
            // Tool call arguments streaming
            setToolCalls((prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, partialArgs: data.partial_args, status: 'streaming' }
                : tc
            ));
            break;
          case "agent_tool_call_invoking":
            // Tool call invoking (executing)
            setToolCalls((prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: tc.partialArgs || tc.args, status: 'invoking' }
                : tc
            ));
            break;
          case "agent_tool_call_complete":
            // Tool call completed
            setToolCalls((prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: tc.partialArgs || tc.args, result: data.result, status: 'completed' }
                : tc
            ));
            break;
          case "agent_tool_call_error":
            // Tool call error
            setToolCalls((prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, args: tc.partialArgs || tc.args, error: data.error, status: 'error' }
                : tc
            ));
            break;
          case "agent_tool_call":
            // Legacy: Tool call start (for backward compatibility)
            if (data.content) {
              setToolCallAssistantContents((prev) => ({
                ...prev,
                [data.iteration]: data.content
              }));
            }
            setToolCalls((prev) => [...prev, {
              id: data.tool_call_id || Date.now(),
              tool: data.tool,
              args: data.args,
              status: 'running',
              result: null,
              iteration: data.iteration
            }]);
            break;
          case "agent_tool_result":
            // Legacy: Tool call result (for backward compatibility)
            setToolCalls((prev) => prev.map(tc =>
              tc.id === data.tool_call_id
                ? { ...tc, status: 'completed', result: data.result }
                : tc
            ));
            break;
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
      if (ws.current) {
        ws.current.close(1000, "Component unmounting");
        ws.current = null;
      }
    };
  }, []);

  // ===== 发送消息 =====
  const handleSendMessage = async (messageData, instanceId = null) => {
    setIsProcessing(true);
    setStreamingContent("");
    setCurrentChatInstanceId(instanceId); // 记录当前聊天的 instance ID

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
      await sendWSMessage("stop_agents", {}, 5000);
      setIsProcessing(false);
      setStreamingContent("");
      setToolCalls([]);
      setToolCallAssistantContents({});
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

  // ===== 渲染 =====
  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar pixel-border">
        <div className="logo">
          <img src={octopusLogo} alt="Octopus" className="logo-icon" style={{ width: 30, height: 40, objectFit: 'contain' }} />
          OCTOPUS
        </div>
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
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="top-bar">
          <div className="tab-title">
            {/* <WindowDots /> */}
            <span>
              {activeTab === "chat"
                ? "TERMINAL_SESSION_ACTIVE"
                : "CONFIG_EDITOR"}
            </span>
          </div>
          <div className="top-actions" style={{ WebkitAppRegion: 'no-drag' }}>
            <button
              className="restart-btn"
              onClick={handleRestart}
              disabled={isRestarting || connectionStatus !== "connected"}
              title="重启后端服务"
              style={{ WebkitAppRegion: 'no-drag' }}
            >
              <RotateCcw size={14} className={isRestarting ? "spinning" : ""} />
              <span>{isRestarting ? "RESTARTING..." : "RESTART"}</span>
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
              />
            } />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default App;
