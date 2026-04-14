import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Routes,
  Route,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { createPortal } from "react-dom";
import {
  MessageSquare,
  Settings,
  Server,
  Bot,
  Package,
  History as HistoryIcon,
  FolderOpen,
  Clock,
  Users,
  RotateCcw,
  Zap,
  Volume2,
  Play,
  Pause,
  PanelLeftClose,
  PanelRight,
  BookOpen,
} from "lucide-react";
import octopusLogo from "./assets/octopus-logo.png";
import WindowDots from "./components/layout/WindowDots";
import Chat from "./pages/Chat/ChatPanel";
import Config from "./pages/Config";
import MCP from "./pages/MCP";
import Extensions from "./pages/Extensions";
import History from "./pages/History";
import Workspace from "./pages/Workspace";
import Cron from "./pages/Cron";
import Agents from "./pages/Agents";
import Tokens from "./pages/Tokens";
import Knowledge from "./pages/Knowledge";
import { useWebSocket } from "./contexts/WebSocketContext";
import { useChatState } from "./hooks/useChatState";

const APP_TITLE_BY_TAB = {
  chat: "TERMINAL_SESSION",
  config: "CONFIG_EDITOR",
  mcp: "MCP_SERVERS",
  extensions: "EXTENSIONS",
  cron: "CRON",
  agents: "AGENTS",
  workspaces: "WORKSPACE_EXPLORER",
  history: "HISTORY",
  tokens: "TOKENS",
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
          ×
        </button>
      </div>
    </div>
  );
}

/**
 * App 主组件
 */
function App() {
  const { sendMessage, connectionStatus, showLoadingOverlay, ws } = useWebSocket();
  const chat = useChatState();

  // ===== 状态 =====
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [config, setConfig] = useState({
    providers: {},
    agents: { defaults: { model: "deepseek-chat", workspace: "" } },
    tools: {},
    channels: {},
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);

  // 窗口焦点状态 - 用于控制交通灯颜色（失焦时变为灰色）
  const [isWindowFocused, setIsWindowFocused] = useState(true);

  useEffect(() => {
    const onFocus = () => setIsWindowFocused(true);
    const onBlur = () => setIsWindowFocused(false);
    window.addEventListener("focus", onFocus);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  // 切回 chat tab 时，把 ref 中累积的 streamingContent 同步到 state
  useEffect(() => {
    if (activeTab === 'chat') {
      chat.syncStreamingContent();
    }
  }, [activeTab, chat.syncStreamingContent]);

  // ===== 发送消息 =====
  const handleSendMessage = async (messageData, instanceId = null) => {
    chat.setIsProcessing(true);
    chat.resetStreamingContent();
    chat.setLiveTokenUsage(null);
    chat.setCurrentChatInstanceId(instanceId);

    try {
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
      await sendMessage("chat", payload, 5000);
    } catch (err) {
      chat.setIsProcessing(false);
      chat.setCurrentChatInstanceId(null);
      console.error("Failed to send message:", err);
    }
  };

  // ===== 停止生成 =====
  const handleStopGeneration = async () => {
    try {
      await sendMessage("stop_agents", { 
        instance_id: chat.currentChatInstanceId 
      }, 5000);
      chat.setIsProcessing(false);
      chat.resetStreamingContent();
      chat.setToolCalls([]);
      chat.setToolCallAssistantContents({});
      chat.setLiveTokenUsage(null);
    } catch (err) {
      console.error("Failed to stop generation:", err);
      chat.setIsProcessing(false);
    }
  };

  // ===== 保存配置 =====
  const handleSaveConfig = async (configToSave) => {
    setIsSaving(true);
    try {
      await sendMessage("save_config", { config: configToSave }, 5000);
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
      await sendMessage("restart_service", {}, 5000);
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
    const tabMap = {
      '/chat': 'chat',
      '/config': 'config',
      '/mcp': 'mcp',
      '/extensions': 'extensions',
      '/cron': 'cron',
      '/agents': 'agents',
      '/workspaces': 'workspaces',
      '/history': 'history',
      '/tokens': 'tokens',
      '/knowledge': 'knowledge',
    };
    setActiveTab(tabMap[path] || 'chat');
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
      workspaces: '/workspaces',
      history: '/history',
      tokens: '/tokens',
      knowledge: '/knowledge',
    };
    navigate(routeMap[tab] || '/chat');
  };

  const appTitleBarText = APP_TITLE_BY_TAB[activeTab] ?? "OCTOPUS";

  // ===== 全局 Loading 遮罩 =====
  const GlobalLoadingOverlay = () => {
    const overlayContent = (
      <div
        className="global-loading-overlay"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: '100vw',
          height: '100vh',
          background: 'var(--bg, #1a1a1a)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2147483647,
          gap: '32px',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
          <img src={octopusLogo} alt="Octopus" style={{ width: 64, height: 80, objectFit: 'contain' }} />
          <span style={{
            fontSize: '32px',
            fontWeight: 700,
            color: 'var(--text, #e0e0e0)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            letterSpacing: '2px'
          }}>OCTOPUS</span>
        </div>

        {/* 小球掉落动画 */}
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          gap: '12px',
          height: '80px',
        }}>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="bouncing-ball"
              style={{
                width: '16px',
                height: '16px',
                backgroundColor: '#ec5e37ff',
                borderRadius: '50%',
                animation: `bounce 0.6s ease-in-out infinite`,
                animationDelay: `${i * 0.12}s`,
              }}
            />
          ))}
        </div>

        {/* 小球动画样式 */}
        <style>{`
          @keyframes bounce {
            0%, 100% {
              transform: translateY(0);
            }
            50% {
              transform: translateY(-50px);
            }
          }
        `}</style>
      </div>
    );

    return createPortal(overlayContent, document.body);
  };

  // ===== 渲染 =====
  return (
    <div className="app-container">
      {/* WebSocket 未连接时显示全局 Loading */}
      {showLoadingOverlay && <GlobalLoadingOverlay />}
      
      {/* 整窗顶栏 */}
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
        {/* Sidebar */}
        <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
          <div className="sidebar-nav">
            <nav>
              {[
                { key: 'chat', icon: Bot, label: 'CHAT' },
                { key: 'config', icon: Settings, label: 'SYSTEM' },
                { key: 'mcp', icon: Server, label: 'SERVERS' },
                { key: 'extensions', icon: Package, label: 'EXTENSIONS' },
                { key: 'cron', icon: Clock, label: 'CRON' },
                { key: 'agents', icon: Users, label: 'AGENTS' },
                { key: 'workspaces', icon: FolderOpen, label: 'WORKSPACE' },
                { key: 'knowledge', icon: BookOpen, label: 'KNOWLEDGE' },
                { key: 'history', icon: HistoryIcon, label: 'HISTORY' },
                { key: 'tokens', icon: Zap, label: 'TOKENS' },
              ].map(({ key, icon: Icon, label }) => (
                <button
                  key={key}
                  className={`nav-item ${activeTab === key ? "active" : ""}`}
                  onClick={() => handleNavClick(key)}
                >
                  <Icon size={18} />
                  <span>{label}</span>
                </button>
              ))}
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
                <Chat
                  sendWSMessage={sendMessage}
                  onSendMessage={handleSendMessage}
                  onStopGeneration={handleStopGeneration}
                  isProcessing={chat.isProcessing}
                  streamingContent={chat.streamingContent}
                  currentChatInstanceId={chat.currentChatInstanceId}
                  toolCalls={chat.toolCalls}
                  toolCallAssistantContents={chat.toolCallAssistantContents}
                  ttsAudio={chat.ttsAudio}
                  onTtsPlayed={() => chat.setTtsAudio(null)}
                  lastElapsedMs={chat.lastElapsedMs}
                  lastTokenUsage={chat.lastTokenUsage}
                  liveTokenUsage={chat.liveTokenUsage}
                  onElapsedMsUpdate={chat.setLastElapsedMs}
                  onTokenUsageUpdate={chat.setLastTokenUsage}
                  refreshInstanceId={chat.refreshInstanceId}
                  onInstanceIdUpdate={chat.setCurrentChatInstanceId}
                  hasToolCallsInCurrentRun={chat.hasToolCallsInCurrentRun}
                />
              } />
              <Route path="/config" element={
                <Config
                  config={config}
                  setConfig={setConfig}
                  onSave={handleSaveConfig}
                  isSaving={isSaving}
                  sendWSMessage={sendMessage}
                />
              } />
              <Route path="/mcp" element={<MCP sendWSMessage={sendMessage} />} />
              <Route path="/extensions" element={
                <Extensions sendWSMessage={sendMessage} ws={ws.current} />
              } />
              <Route path="/workspaces" element={
                <Workspace sendWSMessage={sendMessage} />
              } />
              <Route path="/history" element={
                <History sendWSMessage={sendMessage} />
              } />
              <Route path="/cron" element={<Cron sendWSMessage={sendMessage} />} />
              <Route path="/agents" element={<Agents sendWSMessage={sendMessage} />} />
              <Route path="/tokens" element={<Tokens sendWSMessage={sendMessage} />} />
              <Route path="/knowledge" element={<Knowledge sendWSMessage={sendMessage} />} />
              <Route path="/" element={
                <Chat
                  sendWSMessage={sendMessage}
                  onSendMessage={handleSendMessage}
                  onStopGeneration={handleStopGeneration}
                  isProcessing={chat.isProcessing}
                  streamingContent={chat.streamingContent}
                  currentChatInstanceId={chat.currentChatInstanceId}
                  toolCalls={chat.toolCalls}
                  toolCallAssistantContents={chat.toolCallAssistantContents}
                  ttsAudio={chat.ttsAudio}
                  onTtsPlayed={() => chat.setTtsAudio(null)}
                  lastElapsedMs={chat.lastElapsedMs}
                  lastTokenUsage={chat.lastTokenUsage}
                  liveTokenUsage={chat.liveTokenUsage}
                  onElapsedMsUpdate={chat.setLastElapsedMs}
                  onTokenUsageUpdate={chat.setLastTokenUsage}
                  refreshInstanceId={chat.refreshInstanceId}
                  onInstanceIdUpdate={chat.setCurrentChatInstanceId}
                  hasToolCallsInCurrentRun={chat.hasToolCallsInCurrentRun}
                />
              } />
            </Routes>
          </div>
        </main>
      </div>

      {chat.ttsAudio && (
        <TTSPlayer
          audioData={chat.ttsAudio.audioData}
          format={chat.ttsAudio.format}
          text={chat.ttsAudio.text}
          durationMs={chat.ttsAudio.durationMs}
          onClose={() => chat.setTtsAudio(null)}
        />
      )}
    </div>
  );
}

export default App;
