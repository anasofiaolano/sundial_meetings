import React from 'react';
import ReactDOM from 'react-dom/client';
import { ResponsiveRouter } from './providers/ResponsiveRouter';
import { ToastProvider } from './components/Toast';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <ResponsiveRouter />
    </ToastProvider>
  </React.StrictMode>,
);
