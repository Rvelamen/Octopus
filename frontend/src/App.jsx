import React, { useState, useEffect, useMemo } from "react";
import {
  Routes,
  Route,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
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
  PanelLeftClose,
  PanelRight,
  BookOpen,
  Library,
  Brain,
  GitBranch,
} from "lucide-react";
import Chat from "./pages/Chat/ChatPanel";
import Config from "./pages/Config";
import MCP from "./pages/MCP";
import Extensions from "./pages/Extensions";
import History from "./pages/History";
import Memory from "./pages/Memory";
import Workspace from "./pages/Workspace";
import Cron from "./pages/Cron";
import Agents from "./pages/Agents";
import Tokens from "./pages/Tokens";
import Knowledge from "./pages/Knowledge";
import { LibraryTab } from "./pages/Knowledge/library";
import PdfViewerWindow from "./pages/PdfViewerWindow";
import MarkdownEditorWindow from "./pages/MarkdownEditorWindow";
import WorkflowWindow from "./pages/WorkflowWindow";
import WorkflowTabTitle from "./workflow/components/WorkflowTabTitle";
import GlobalLoadingOverlay from "./components/GlobalLoadingOverlay";
import TTSPlayer from "./components/TTSPlayer";
import { useWebSocket } from "./contexts/WebSocketContext";
import { useChatState } from "./hooks/useChatState";

const APP_TITLE_BY_TAB = {
  chat: "Chat",
  config: "System",
  mcp: "MCP Servers",
  extensions: "Extensions",
  cron: "Cron Jobs",
  agents: "Agents",
  workspaces: "Workspace",
  history: "History",
  memory: "Memory",
  tokens: "Tokens",
  workflows: "Workflows",
  library: "Library",
  knowledge: "Knowledge",
};

function App() {
  // Hooks must be called before any early return
  const navigate = useNavigate();
  const location = useLocation();

  const { sendMessage, connectionStatus, showLoadingOverlay, ws } = useWebSocket();
  const chat = useChatState();

  // ===== 状态 =====
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [config, setConfig] = useState({
    providers: {},
    agents: { defaults: { model: "deepseek-chat", workspace: "" } },
    tools: {},
    channels: {},
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);

  // activeTab 从路由派生，避免 useEffect 中 setState
  const activeTab = useMemo(() => {
    const tabMap = {
      '/chat': 'chat',
      '/config': 'config',
      '/mcp': 'mcp',
      '/extensions': 'extensions',
      '/cron': 'cron',
      '/agents': 'agents',
      '/workspaces': 'workspaces',
      '/library': 'library',
      '/history': 'history',
      '/memory': 'memory',
      '/tokens': 'tokens',
      '/knowledge': 'knowledge',
      '/workflows': 'workflows',
    };
    return tabMap[location.pathname] || 'chat';
  }, [location.pathname]);

  // 切回 chat tab 时，把 ref 中累积的 streamingContent 同步到 state
  useEffect(() => {
    if (activeTab === 'chat') {
      chat.syncStreamingContent();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, chat.syncStreamingContent]);

  // ===== 独立窗口检测（hooks 之后）=====
  const hash = window.location.hash;
  const isPdfWindow =
    window.location.pathname === '/pdf-viewer' ||
    hash.startsWith('#pdf-viewer') ||
    hash.startsWith('#/pdf-viewer');
  if (isPdfWindow) {
    return <PdfViewerWindow />;
  }

  const isMarkdownWindow =
    window.location.pathname === '/markdown-editor' ||
    hash.startsWith('#markdown-editor') ||
    hash.startsWith('#/markdown-editor');
  if (isMarkdownWindow) {
    return <MarkdownEditorWindow />;
  }

  const isWorkflowWindow =
    window.location.pathname === '/workflow-window' ||
    hash.startsWith('#workflow-window') ||
    hash.startsWith('#/workflow-window');
  if (isWorkflowWindow) {
    return <WorkflowWindow />;
  }

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

  // 处理导航
  const handleNavClick = (tab) => {
    // Workflow 迁移到独立窗口
    if (tab === 'workflows') {
      if (window.electronAPI?.openWorkflowWindow) {
        window.electronAPI.openWorkflowWindow();
        return;
      }
      // 降级：浏览器环境或无 Electron API 时继续走路由
    }

    const routeMap = {
      chat: '/chat',
      config: '/config',
      mcp: '/mcp',
      extensions: '/extensions',
      cron: '/cron',
      agents: '/agents',
      workspaces: '/workspaces',
      library: '/library',
      history: '/history',
      memory: '/memory',
      tokens: '/tokens',
      knowledge: '/knowledge',
      workflows: '/workflows',
    };
    navigate(routeMap[tab] || '/chat');
  };

  const appTitleBarText = APP_TITLE_BY_TAB[activeTab] ?? "OCTOPUS";

  // 渲染导航分组
  const renderNavItems = (items) => {
    return items.map(({ key, icon: Icon, label }) => (
      <button
        key={key}
        className={`nav-item ${activeTab === key ? "active" : ""}`}
        onClick={() => handleNavClick(key)}
        title={label}
      >
        <Icon size={20} />
        {!sidebarCollapsed && <span>{label}</span>}
      </button>
    ));
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
          {activeTab === 'workflows' ? (
            <WorkflowTabTitle />
          ) : (
            <span>{appTitleBarText}</span>
          )}
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
              {/* 核心 */}
              {renderNavItems([
                { key: 'chat', icon: Bot, label: 'Chat' },
                { key: 'knowledge', icon: BookOpen, label: 'Knowledge' },
                { key: 'workspaces', icon: FolderOpen, label: 'Workspace' },
              ])}
              {/* 系统 */}
              {renderNavItems([
                { key: 'config', icon: Settings, label: 'Config' },
                { key: 'agents', icon: Users, label: 'Agents' },
                { key: 'mcp', icon: Server, label: 'MCP' },
              ])}
              {/* 集成 */}
              {renderNavItems([
                { key: 'extensions', icon: Package, label: 'Extensions' },
                { key: 'cron', icon: Clock, label: 'Cron' },
              ])}
              {/* 数据 */}
              {renderNavItems([
                { key: 'history', icon: HistoryIcon, label: 'History' },
                { key: 'memory', icon: Brain, label: 'Memory' },
                { key: 'library', icon: Library, label: 'Library' },
                { key: 'tokens', icon: Zap, label: 'Tokens' },
              ])}
              {/* 工作流 */}
              {renderNavItems([
                { key: 'workflows', icon: GitBranch, label: 'Workflows' },
              ])}
            </nav>
            {!sidebarCollapsed && (
              <div className="sidebar-footer">
                <span className="footer-version">v1.0.0</span>
                <span
                  className={`footer-status-dot ${connectionStatus}`}
                  title={connectionStatus === 'connected' ? 'Online' : connectionStatus === 'connecting' ? 'Connecting...' : 'Offline'}
                />
              </div>
            )}
          </div>
        </aside>

        <main className="main-content">
          <div className="content-area">
            <Routes>
              <Route path="/chat" element={
                <Chat
                  sendWSMessage={sendMessage}
                  connectionStatus={connectionStatus}
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
              <Route path="/memory" element={
                <Memory sendWSMessage={sendMessage} />
              } />
              <Route path="/cron" element={<Cron sendWSMessage={sendMessage} />} />
              <Route path="/agents" element={<Agents sendWSMessage={sendMessage} />} />
              <Route path="/tokens" element={<Tokens sendWSMessage={sendMessage} />} />
              <Route path="/knowledge" element={<Knowledge sendWSMessage={sendMessage} />} />
              <Route path="/library" element={<LibraryTab sendWSMessage={sendMessage} />} />
              <Route path="/workflows" element={<WorkflowWindow />} />
              <Route path="/pdf-viewer" element={<PdfViewerWindow />} />
              <Route path="/markdown-editor" element={<MarkdownEditorWindow />} />
              <Route path="/" element={
                <Chat
                  sendWSMessage={sendMessage}
                  connectionStatus={connectionStatus}
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
          onClose={() => chat.setTtsAudio(null)}
        />
      )}
    </div>
  );
}

export default App;
