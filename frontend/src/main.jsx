import React from 'react';
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { DistillTaskProvider } from './contexts/DistillTaskContext'
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
    <BrowserRouter>
      <DistillTaskProvider>
        <div className="crt-overlay" />
        <App />
      </DistillTaskProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
