import React, { useState, useEffect, useRef, useCallback } from "react";
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
          case "agent_chunk":
            console.log('[WebSocket] Agent chunk received:', data?.content?.substring(0, 50));
            setStreamingContent((prev) => prev + (data.content || ""));
            break;
          case "agent_start":
            setStreamingContent("");
            setToolCalls([]); // 清空之前的工具调用
            setToolCallAssistantContents({}); // 清空 assistant content
            break;
          case "agent_thinking":
            // 新一轮 LLM 调用开始
            console.log('[WebSocket] Agent thinking, iteration:', data?.iteration);
            // 不清空 toolCalls，让之前轮次的继续显示
            break;
          case "agent_finish":
            console.log('[WebSocket] Agent finish received:', data);
            setStreamingContent("");
            setIsProcessing(false);
            // 不清空 toolCalls，让它们继续显示
            // toolCalls 会在下一轮 agent_thinking 时清空
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
          case "agent_tool_call":
            // 工具调用开始 - 实时显示
            // 按 iteration 存储 assistant content
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
            // 工具调用完成 - 更新结果
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
        // 旧方式：纯文本
        payload = { content: messageData };
      } else {
        // 新方式：包含图片的对象
        payload = {
          content: messageData.content || '',
          images: messageData.images || []
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
            onClick={() => setActiveTab("chat")}
          >
            <Bot size={18} />
            <span>CHAT</span>
          </button>
          <button
            className={`nav-item ${activeTab === "config" ? "active" : ""}`}
            onClick={() => setActiveTab("config")}
          >
            <Settings size={18} />
            <span>SYSTEM</span>
          </button>
          <button
            className={`nav-item ${activeTab === "mcp" ? "active" : ""}`}
            onClick={() => setActiveTab("mcp")}
          >
            <Server size={18} />
            <span>SERVERS</span>
          </button>
          <button
            className={`nav-item ${activeTab === "extensions" ? "active" : ""}`}
            onClick={() => setActiveTab("extensions")}
          >
            <Package size={18} />
            <span>EXTENSIONS</span>
          </button>
          <button
            className={`nav-item ${activeTab === "cron" ? "active" : ""}`}
            onClick={() => setActiveTab("cron")}
          >
            <Clock size={18} />
            <span>CRON</span>
          </button>
          <button
            className={`nav-item ${activeTab === "agents" ? "active" : ""}`}
            onClick={() => setActiveTab("agents")}
          >
            <Users size={18} />
            <span>AGENTS</span>
          </button>
          <button
            className={`nav-item ${activeTab === "workspace" ? "active" : ""}`}
            onClick={() => setActiveTab("workspace")}
          >
            <FolderOpen size={18} />
            <span>WORKSPACE</span>
          </button>
          <button
            className={`nav-item ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            <History size={18} />
            <span>HISTORY</span>
          </button>
          <button
            className={`nav-item ${activeTab === "tokens" ? "active" : ""}`}
            onClick={() => setActiveTab("tokens")}
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
          {activeTab === "chat" && (
            <ChatPanel
              sendWSMessage={sendWSMessage}
              onSendMessage={handleSendMessage}
              onStopGeneration={handleStopGeneration}
              isProcessing={isProcessing}
              streamingContent={streamingContent}
              currentChatInstanceId={currentChatInstanceId}
              toolCalls={toolCalls}
              toolCallAssistantContents={toolCallAssistantContents}
            />
          )}
          {activeTab === "config" && (
            <ConfigPanel
              config={config}
              setConfig={setConfig}
              onSave={handleSaveConfig}
              isSaving={isSaving}
              sendWSMessage={sendWSMessage}
            />
          )}
          {activeTab === "mcp" && <MCPPanel sendWSMessage={sendWSMessage} />}
          {activeTab === "extensions" && (
            <ExtensionsPanel sendWSMessage={sendWSMessage} ws={ws.current} />
          )}
          {activeTab === "workspace" && (
            <WorkspacePanel sendWSMessage={sendWSMessage} />
          )}
          {activeTab === "history" && (
            <HistoryPanel sendWSMessage={sendWSMessage} />
          )}
          {activeTab === "cron" && <CronPanel sendWSMessage={sendWSMessage} />}
          {activeTab === "agents" && <AgentsPanel sendWSMessage={sendWSMessage} />}
          {activeTab === "tokens" && <TokenUsagePanel sendWSMessage={sendWSMessage} />}
        </div>
      </main>
    </div>
  );
}

export default App;
