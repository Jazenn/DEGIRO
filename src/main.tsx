import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { PrototypeDashboard } from './components/PrototypeDashboard';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {import.meta.env.DEV && new URLSearchParams(window.location.search).has('prototype')
      ? <PrototypeDashboard />
      : <App />}
  </React.StrictMode>
);
