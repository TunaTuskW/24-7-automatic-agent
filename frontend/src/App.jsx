import React, { useState, useEffect } from 'react';
import OverviewTab from './components/OverviewTab';
import TradingTerminal from './components/TradingTerminal';
import PaperTradingTab from './components/PaperTradingTab';
import MathModelTab from './components/MathModelTab';
import MacroTab from './components/MacroTab';
import DiagnosticsTab from './components/DiagnosticsTab';
import SettingsTab from './components/SettingsTab';
import ReportsTab from './components/ReportsTab';
import { Settings, FileText, Activity } from 'lucide-react';
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

  const tabStyle = (tabId) => ({
    padding: '8px 16px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', transition: 'all 0.2s',
    background: activeTab === tabId ? 'var(--accent-blue)' : 'transparent',
    color: activeTab === tabId ? '#fff' : 'var(--text-muted)'
  });

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="header animate-fade-in">
        <div>
          <h1>QuantOS Engine</h1>
          <p className="text-muted" style={{ marginTop: '4px' }}>Autonomous HMM Dual-Timeframe Trader</p>
        </div>
        
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '8px', background: 'rgba(255,255,255,0.05)', padding: '6px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}>
          <button onClick={() => setActiveTab('overview')} style={tabStyle('overview')}>Overview</button>
          <button onClick={() => setActiveTab('terminal')} style={tabStyle('terminal')}>Terminal</button>
          <button onClick={() => setActiveTab('trading')} style={tabStyle('trading')}>Paper Trading</button>
          <button onClick={() => setActiveTab('macro')} style={tabStyle('macro')}>Macro Sentiment</button>
          <button onClick={() => setActiveTab('model')} style={tabStyle('model')}>Math Model</button>
          <button onClick={() => setActiveTab('logs')} style={tabStyle('logs')}>Diagnostics</button>
          <div style={{ width: '1px', background: 'rgba(255,255,255,0.2)', margin: '0 8px' }}></div>
          <button onClick={() => setActiveTab('reports')} style={{...tabStyle('reports'), display: 'flex', alignItems: 'center', gap: '6px'}}>
            <FileText size={16}/> Reports
          </button>
          <button onClick={() => setActiveTab('settings')} style={{...tabStyle('settings'), display: 'flex', alignItems: 'center', gap: '6px'}}>
            <Settings size={16}/> Settings
          </button>
        </div>

        <div className="status-badge">
          <div className="status-dot"></div>
          {data.status}
        </div>
      </header>

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
