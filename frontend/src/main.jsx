import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom/client'
import App from './App'
import './pixel-theme.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <div className="crt-overlay" />
    <App />
  </React.StrictMode>,
)
