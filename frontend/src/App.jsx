import React, { useState, useEffect, useMemo, Suspense, lazy } from "react";
import { useTranslation } from "react-i18next";
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
import Cron from "./pages/Cron";
import Agents from "./pages/Agents";
import Tokens from "./pages/Tokens";
// 重组件路由懒加载（monaco/mdxeditor/pixi/mermaid/react-pdf 等重库按需加载）
const Workspace = lazy(() => import("./pages/Workspace"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
const LibraryTab = lazy(() =>
  import("./pages/Knowledge/library").then((m) => ({ default: m.LibraryTab }))
);
const PdfViewerWindow = lazy(() => import("./pages/PdfViewerWindow"));
const MarkdownEditorWindow = lazy(() => import("./pages/MarkdownEditorWindow"));
const WorkflowWindow = lazy(() => import("./pages/WorkflowWindow"));
import WorkflowTabTitle from "./workflow/components/WorkflowTabTitle";
import GlobalLoadingOverlay from "./components/GlobalLoadingOverlay";
import TTSPlayer from "./components/TTSPlayer";
import WindowDots from "./components/layout/WindowDots";
import octopusLogo from "./assets/octopus-logo.png";
import { useWebSocket } from "./contexts/WebSocketContext";
import { useChatState } from "./hooks/useChatState";

// 懒加载路由的 Suspense 兜底
const RouteFallback = () => {
  const { t } = useTranslation();
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary, #888)', fontSize: 13 }}>
      {t('common.loading')}
    </div>
  );
};

function App() {
  // Hooks must be called before any early return
  const { t } = useTranslation();
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
    return <Suspense fallback={<RouteFallback />}><PdfViewerWindow /></Suspense>;
  }

  const isMarkdownWindow =
    window.location.pathname === '/markdown-editor' ||
    hash.startsWith('#markdown-editor') ||
    hash.startsWith('#/markdown-editor');
  if (isMarkdownWindow) {
    return <Suspense fallback={<RouteFallback />}><MarkdownEditorWindow /></Suspense>;
  }

  const isWorkflowWindow =
    window.location.pathname === '/workflow-window' ||
    hash.startsWith('#workflow-window') ||
    hash.startsWith('#/workflow-window');
  if (isWorkflowWindow) {
    return <Suspense fallback={<RouteFallback />}><WorkflowWindow /></Suspense>;
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

  const appTitleBarText = t(`title.${activeTab}`, { defaultValue: "OCTOPUS" });

  // 渲染导航分组
  const renderNavGroup = (groupLabel, items) => {
    if (sidebarCollapsed) {
      return items.map(({ key, icon: Icon, label }) => (
        <button
          key={key}
          className={`nav-item ${activeTab === key ? "active" : ""}`}
          onClick={() => handleNavClick(key)}
          title={label}
        >
          <Icon size={18} />
        </button>
      ));
    }
    return (
      <div className="nav-group" key={groupLabel}>
        <div className="nav-group-label">{groupLabel}</div>
        {items.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            className={`nav-item ${activeTab === key ? "active" : ""}`}
            onClick={() => handleNavClick(key)}
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </div>
    );
  };

  // ===== 渲染 =====
  return (
    <div className="app-container">
      {/* WebSocket 未连接时显示全局 Loading */}
      {showLoadingOverlay && <GlobalLoadingOverlay />}

      {/* 整窗顶栏 */}
      <header className={`app-titlebar ${sidebarCollapsed ? 'app-titlebar-collapsed' : ''}`}>
        <div className="app-titlebar-brand">
          {sidebarCollapsed ? (
            <img
              src={octopusLogo}
              alt="OCTOPUS"
              className="app-titlebar-logo-img"
              draggable={false}
            />
          ) : (
            <div className="app-titlebar-logo-pill">
              <div className="logo app-titlebar-logo">
                <span className="logo-text">OCTOPUS</span>
              </div>
            </div>
          )}
        </div>
        <div className="app-titlebar-sep" aria-hidden />
        <div className="tab-title">
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? t('titlebar.expandSidebar') : t('titlebar.collapseSidebar')}
          >
            {sidebarCollapsed ? <PanelRight size={14} /> : <PanelLeftClose size={14} />}
          </button>
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
            title={t('titlebar.restartBackend')}
            style={{ WebkitAppRegion: 'no-drag' }}
          >
            <RotateCcw size={12} className={isRestarting ? "spinning" : ""} />
            <span>{isRestarting ? t('titlebar.restarting') : t('titlebar.restart')}</span>
          </button>
          <div className={`status-indicator ${connectionStatus}`} style={{ WebkitAppRegion: 'no-drag' }}></div>
          <span className={`status-text ${connectionStatus}`} style={{ WebkitAppRegion: 'no-drag' }}>
            {connectionStatus === "connected"
              ? t('titlebar.online')
              : connectionStatus === "connecting"
                ? t('titlebar.connecting')
                : t('titlebar.offline')}
          </span>
          {/* 全局窗口控制按钮（最小化/最大化/关闭），用户不需要进入 Chat 页就能操作窗口 */}
          <WindowDots interactive />
        </div>
      </header>

      <div className={`app-body ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}>
        {/* Sidebar */}
        <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
          <div className="sidebar-nav">
            <nav>
              {renderNavGroup(t('nav.group.core'), [
                { key: 'chat', icon: Bot, label: t('nav.chat') },
                { key: 'workspaces', icon: FolderOpen, label: t('nav.workspace') },
              ])}
              {renderNavGroup(t('nav.group.knowledge'), [
                { key: 'knowledge', icon: BookOpen, label: t('nav.knowledge') },
                { key: 'library', icon: Library, label: t('nav.library') },
              ])}
              {renderNavGroup(t('nav.group.automation'), [
                { key: 'agents', icon: Users, label: t('nav.agents') },
                { key: 'workflows', icon: GitBranch, label: t('nav.workflows') },
                { key: 'cron', icon: Clock, label: t('nav.cron') },
              ])}
              {renderNavGroup(t('nav.group.integrations'), [
                { key: 'mcp', icon: Server, label: t('nav.mcp') },
                { key: 'extensions', icon: Package, label: t('nav.extensions') },
              ])}
              {renderNavGroup(t('nav.group.system'), [
                { key: 'history', icon: HistoryIcon, label: t('nav.history') },
                { key: 'memory', icon: Brain, label: t('nav.memory') },
                { key: 'tokens', icon: Zap, label: t('nav.tokens') },
                { key: 'config', icon: Settings, label: t('nav.config') },
              ])}
            </nav>
            {!sidebarCollapsed && (
              <div className="sidebar-footer">
                <span className="footer-version">v1.0.0</span>
                <span className={`footer-status ${connectionStatus}`}>
                  <span className="footer-status-dot" />
                  {connectionStatus === 'connected' ? t('titlebar.online') : connectionStatus === 'connecting' ? t('titlebar.connecting') : t('titlebar.offline')}
                </span>
              </div>
            )}
          </div>
        </aside>

        <main className="main-content">
          <div className="content-area">
            <Suspense fallback={<RouteFallback />}>
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
            </Suspense>
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
