import React, { useState, useEffect } from 'react';
import OverviewTab from './components/OverviewTab';
import TradingTerminal from './components/TradingTerminal';
import PaperTradingTab from './components/PaperTradingTab';
import MathModelTab from './components/MathModelTab';
import MacroTab from './components/MacroTab';
import DiagnosticsTab from './components/DiagnosticsTab';
import SettingsTab from './components/SettingsTab';
import ReportsTab from './components/ReportsTab';
import { Settings, FileText, Satellite } from 'lucide-react';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
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
      } catch (e) {
        console.error("API not ready yet");
      }
    };
    
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard-container">
      {/* Signature Identity Bar */}
      <header className="identity-header animate-fade-in">
        <div className="logotype">
          <Satellite size={24} color="var(--plasma-cyan)" />
          QUANT/OS
        </div>
        
        <div className="header-center">
          <span>◉ {data.regime.replace(/_/g, ' ')}</span>
          <span style={{ color: 'var(--plasma-purple)' }}>
            {(data.regimeProb * 100).toFixed(1)}%
          </span>
        </div>

        <div className="header-right">
          <span>UTC {new Date(data.lastUpdate).toISOString().split('T')[1]?.substring(0,8) || "00:00:00"}</span>
          <div className="status-beacon">
            <div className="status-dot"></div>
            {data.status.toUpperCase()}
          </div>
        </div>
      </header>
      
      {/* Segmented Orbital Selector */}
      <div className="orbital-nav animate-fade-in delay-1">
        <button className={`orbital-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
        <button className={`orbital-tab ${activeTab === 'terminal' ? 'active' : ''}`} onClick={() => setActiveTab('terminal')}>Terminal</button>
        <button className={`orbital-tab ${activeTab === 'trading' ? 'active' : ''}`} onClick={() => setActiveTab('trading')}>Paper Trading</button>
        <button className={`orbital-tab ${activeTab === 'macro' ? 'active' : ''}`} onClick={() => setActiveTab('macro')}>Macro</button>
        <button className={`orbital-tab ${activeTab === 'model' ? 'active' : ''}`} onClick={() => setActiveTab('model')}>Math Model</button>
        <button className={`orbital-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>Diagnostics</button>
        
        <div style={{ width: '1px', background: 'rgba(0,255,224,0.2)', margin: '0 8px' }}></div>
        
        <button className={`orbital-tab ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={16}/> Reports
        </button>
        <button className={`orbital-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Settings size={16}/> Settings
        </button>
      </div>

      {/* Main Tab Content */}
      <main className="animate-fade-in delay-2">
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
