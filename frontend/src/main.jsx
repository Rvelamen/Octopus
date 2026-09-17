import React from 'react';
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { DistillTaskProvider } from './contexts/DistillTaskContext'
import { WebSocketProvider } from './contexts/WebSocketContext'
import './i18n'
import './pixel-theme.css'

// Polyfill for URL.parse (used by react-pdf / pdfjs-dist in some environments)
if (typeof URL !== 'undefined' && !URL.parse) {
  URL.parse = function (url, base) {
    try {
      return new URL(url, base);
    } catch {
      return null;
    }
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <WebSocketProvider>
        <DistillTaskProvider>
          <div className="crt-overlay" />
          <App />
        </DistillTaskProvider>
      </WebSocketProvider>
    </HashRouter>
  </React.StrictMode>,
)
