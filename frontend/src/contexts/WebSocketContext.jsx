import React, { createContext, useContext, useRef, useCallback, useEffect, useState } from 'react';

const WebSocketContext = createContext(null);
const WS_BASE = "ws://127.0.0.1:18791";

export function WebSocketProvider({ children }) {
  const ws = useRef(null);
  const pendingRequests = useRef(new Map());
  const listeners = useRef(new Map());
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [showLoadingOverlay, setShowLoadingOverlay] = useState(true);
  const overlayShowTimeRef = useRef(Date.now());

  const generateRequestId = () => {
    return `req-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  };

  const subscribe = useCallback((eventType, callback) => {
    if (!listeners.current.has(eventType)) {
      listeners.current.set(eventType, new Set());
    }
    listeners.current.get(eventType).add(callback);
    return () => {
      listeners.current.get(eventType)?.delete(callback);
    };
  }, []);

  const unsubscribe = useCallback((eventType, callback) => {
    listeners.current.get(eventType)?.delete(callback);
  }, []);

  const sendMessage = useCallback((type, data, timeout = 10000, retryCount = 0) => {
    return new Promise((resolve, reject) => {
      if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
        if (retryCount < 3) {
          console.log(`[WebSocket] Not connected, retrying ${type} (attempt ${retryCount + 1})`);
          setTimeout(() => {
            sendMessage(type, data, timeout, retryCount + 1)
              .then(resolve)
              .catch(reject);
          }, 1000 * (retryCount + 1));
          return;
        }
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

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onBackendReady((port) => {
        console.log('[App] Backend ready on port:', port);
      });
      window.electronAPI.onBackendError((error) => {
        console.error('[App] Backend error:', error);
      });
    }
  }, []);

  useEffect(() => {
    let reconnectTimer = null;
    let isComponentMounted = true;

    const connectWS = () => {
      if (ws.current?.readyState === WebSocket.OPEN || 
          ws.current?.readyState === WebSocket.CONNECTING) {
        return;
      }

      ws.current = new WebSocket(`${WS_BASE}/ws`);

      ws.current.onopen = () => {
        if (!isComponentMounted) return;
        setConnectionStatus("connected");
        const elapsed = Date.now() - overlayShowTimeRef.current;
        const remaining = Math.max(0, 2000 - elapsed);
        setTimeout(() => {
          if (isComponentMounted) setShowLoadingOverlay(false);
        }, remaining);
      };

      ws.current.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const { type, request_id, data } = payload;

        // 处理待处理请求
        if (request_id && pendingRequests.current.has(request_id)) {
          const { resolve, reject } = pendingRequests.current.get(request_id);
          pendingRequests.current.delete(request_id);
          type === "error" 
            ? reject(new Error(data?.error || "Unknown error"))
            : resolve({ type, data });
          return;
        }

        // 分发到订阅者
        const typeListeners = listeners.current.get(type);
        if (typeListeners) {
          typeListeners.forEach((cb) => {
            try {
              cb(data, payload);
            } catch (e) {
              console.error(`[WebSocket] Listener error for ${type}:`, e);
            }
          });
        }

        // 向后兼容：广播通用 ws-message 事件和特定自定义事件
        window.dispatchEvent(new CustomEvent('ws-message', { detail: payload }));
        if (type === 'knowledge_distill_progress') {
          window.dispatchEvent(new CustomEvent('knowledge-distill-progress', { detail: data }));
        }
      };

      ws.current.onclose = (event) => {
        if (!isComponentMounted) return;
        setConnectionStatus("disconnected");
        setShowLoadingOverlay(true);
        overlayShowTimeRef.current = Date.now();
        if (event.code !== 1000 && event.code !== 1001) {
          reconnectTimer = setTimeout(connectWS, 3000);
        }
      };

      ws.current.onerror = () => {
        if (!isComponentMounted) return;
        setConnectionStatus("disconnected");
        setShowLoadingOverlay(true);
        overlayShowTimeRef.current = Date.now();
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

  return (
    <WebSocketContext.Provider value={{ 
      sendMessage, 
      subscribe,
      unsubscribe,
      connectionStatus, 
      showLoadingOverlay,
      ws 
    }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};
