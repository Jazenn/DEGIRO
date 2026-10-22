import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { DashboardShell } from './components/DashboardShell';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {window.location.pathname === '/dashboard-preview' ? <DashboardShell /> : <App />}
  </React.StrictMode>
);
