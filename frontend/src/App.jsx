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

import { formatTimeToggle } from "./utils/timeFormatter";
function formatClock(d, tz) {
  return formatTimeToggle(d, tz, false);
}

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [timeZone, setTimeZone] = useState('Local');
  const [clock, setClock] = useState(() => formatClock(new Date(), 'Local'));
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
    const tick = setInterval(() => setClock(formatClock(new Date(), timeZone)), 1000);
    return () => clearInterval(tick);
  }, [timeZone]);

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
          <select 
            className="text-muted" 
            value={timeZone}
            onChange={(e) => setTimeZone(e.target.value)}
            title="Select Timezone"
            style={{ cursor: 'pointer', background: 'transparent', border: 'none', borderBottom: '1px dashed #666', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', outline: 'none', appearance: 'none', paddingRight: '0' }}
          >
            <option value="Local">LOCAL TIME</option>
            <option value="UTC">UTC TIME</option>
            <option value="America/New_York">EST (New York)</option>
            <option value="Europe/London">GMT (London)</option>
            <option value="Asia/Tokyo">JST (Tokyo)</option>
            <option value="Asia/Ho_Chi_Minh">ICT (Ho Chi Minh)</option>
          </select><span className="text-muted" style={{marginLeft: "8px"}}>{clock}</span>
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
        {activeTab === 'overview' && <OverviewTab data={data} timeZone={timeZone} />}
        {activeTab === 'terminal' && <TradingTerminal timeZone={timeZone} />}
        {activeTab === 'trading' && <PaperTradingTab timeZone={timeZone} />}
        {activeTab === 'macro' && <MacroTab timeZone={timeZone} />}
        {activeTab === 'model' && <MathModelTab timeZone={timeZone} />}
        {activeTab === 'logs' && <DiagnosticsTab timeZone={timeZone} />}
        {activeTab === 'reports' && <ReportsTab timeZone={timeZone} />}
        {activeTab === 'settings' && <SettingsTab />}
      </main>
    </div>
  );
}

export default App;
