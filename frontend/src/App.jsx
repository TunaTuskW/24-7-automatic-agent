import React, { useState, useEffect } from 'react';
import OverviewTab from './components/OverviewTab';
import TradingTerminal from './components/TradingTerminal';
import PaperTradingTab from './components/PaperTradingTab';
import MathModelTab from './components/MathModelTab';
import MacroTab from './components/MacroTab';
import DiagnosticsTab from './components/DiagnosticsTab';
import SettingsTab from './components/SettingsTab';
import ReportsTab from './components/ReportsTab';
import './index.css';

// Auth helper — reads stored key from localStorage (set in Settings tab)
export function apiPost(path, body = {}) {
  const key = localStorage.getItem('quantos_api_key') || '';
  return fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Api-Key': key },
    body: JSON.stringify(body)
  });
}

function formatClock(d, isLocal) {
  if (isLocal) {
    return [
      String(d.getHours()).padStart(2, '0'),
      String(d.getMinutes()).padStart(2, '0'),
      String(d.getSeconds()).padStart(2, '0')
    ].join(':');
  }
  return [
    String(d.getUTCHours()).padStart(2, '0'),
    String(d.getUTCMinutes()).padStart(2, '0'),
    String(d.getUTCSeconds()).padStart(2, '0')
  ].join(':');
}

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isLocalTime, setIsLocalTime] = useState(true);
  const [clock, setClock] = useState(() => formatClock(new Date(), true));
  const [data, setData] = useState({
    status: 'Syncing',
    regime: 'UNKNOWN',
    regimeProb: 0.0,
    kelly: 0.0,
    safeHaven: 0.0,
    vix: 0.0,
    spread: 0.0,
    lastUpdate: new Date().toISOString()
  });

  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const res = await fetch('/api/snapshot');
        if (res.ok) {
          const json = await res.json();
          setData(prev => ({ ...prev, ...json }));
        }
        const decRes = await fetch('/api/decision');
        if (decRes.ok) {
          const decJson = await decRes.json();
          setData(prev => ({ ...prev, decision: decJson }));
        }
      } catch (e) {
        console.error("API not ready yet");
      }
    };
    
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const tick = setInterval(() => setClock(formatClock(new Date(), isLocalTime)), 1000);
    return () => clearInterval(tick);
  }, [isLocalTime]);

  return (
    <div className="dashboard-container">
      {/* Identity Bar */}
      <header className="identity-header">
        <div className="logotype">
          [SYS] I MADE THIS FOR FUND v6.5.0
        </div>
        
        <div className="header-center">
          <span className="text-muted">REGIME:</span>
          <span className="text-cyan">{data.regime.replace(/_/g, ' ')}</span>
          <span className="text-purple">{(data.regimeProb * 100).toFixed(1)}%</span>
        </div>

        <div className="header-right">
          <span 
            className="text-muted" 
            onClick={() => setIsLocalTime(!isLocalTime)}
            title="Click to toggle timezone"
            style={{ cursor: 'pointer', borderBottom: '1px dashed #666' }}
          >
            {isLocalTime ? 'LOCAL' : 'UTC'} {clock}
          </span>
          <div className="status-beacon">
            <div className="status-dot"></div>
            {data.status.toUpperCase()}
          </div>
        </div>
      </header>
      
      {/* Segmented Orbital Selector -> High Density Tabs */}
      <div className="orbital-nav">
        <button className={`orbital-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>[ OVERVIEW ]</button>
        <button className={`orbital-tab ${activeTab === 'terminal' ? 'active' : ''}`} onClick={() => setActiveTab('terminal')}>[ TERMINAL ]</button>
        <button className={`orbital-tab ${activeTab === 'trading' ? 'active' : ''}`} onClick={() => setActiveTab('trading')}>[ LEDGER ]</button>
        <button className={`orbital-tab ${activeTab === 'macro' ? 'active' : ''}`} onClick={() => setActiveTab('macro')}>[ MACRO ]</button>
        <button className={`orbital-tab ${activeTab === 'model' ? 'active' : ''}`} onClick={() => setActiveTab('model')}>[ MODELS ]</button>
        <button className={`orbital-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>[ DIAGNOSTICS ]</button>
        <button className={`orbital-tab ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')}>[ REPORTS ]</button>
        <button className={`orbital-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>[ SYS_CFG ]</button>
      </div>

      {/* Main Tab Content */}
      <main>
        {activeTab === 'overview' && <OverviewTab data={data} />}
        {activeTab === 'terminal' && <TradingTerminal />}
        {activeTab === 'trading' && <PaperTradingTab />}
        {activeTab === 'macro' && <MacroTab />}
        {activeTab === 'model' && <MathModelTab />}
        {activeTab === 'logs' && <DiagnosticsTab />}
        {activeTab === 'reports' && <ReportsTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </main>
    </div>
  );
}

export default App;
