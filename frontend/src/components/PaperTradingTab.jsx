import React, { useState, useEffect } from 'react';
import { DollarSign, PieChart, History } from 'lucide-react';

export default function PaperTradingTab() {
  const [viewType, setViewType] = useState('live'); // 'live' or 'backtest'
  const [triggerStatus, setTriggerStatus] = useState('');
  
  const [data, setData] = useState({
    portfolio: {
      cash: 10000.0,
      total_equity: 10000.0,
      positions: {}
    },
    ledger: []
  });
  
  const fetchPortfolio = async () => {
    try {
      const res = await fetch(`/api/portfolio?type=${viewType}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error("Failed to fetch portfolio data");
    }
  };

  useEffect(() => {
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 10000);
    return () => clearInterval(interval);
  }, [viewType]);

  const triggerBacktest = async () => {
    setTriggerStatus('Running Simulation...');
    try {
      const res = await fetch('/api/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job: 'test' })
      });
      if (res.ok) {
        setTriggerStatus('Backtest triggered. Please wait ~30s.');
        setTimeout(() => setTriggerStatus(''), 10000);
      } else {
        setTriggerStatus('Failed to trigger backtest (Unauthorized)');
      }
    } catch (e) {
      setTriggerStatus('Error triggering backtest');
    }
  };

  const { portfolio, ledger } = data;
  const pnl = portfolio.total_equity - 10000.0;
  const pnlPct = (pnl / 10000.0) * 100;

  return (
    <div className="grid-layout">
      {/* View Toggle */}
      <div className="glass-panel col-span-12" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '-10px', padding: '16px 24px' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={() => setViewType('live')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(0,255,224,0.1)', background: viewType === 'live' ? 'var(--gradient-primary)' : 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', fontFamily: 'Space Grotesk' }}
          >
            Real-Time Mock Trading
          </button>
          <button 
            onClick={() => setViewType('backtest')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(0,255,224,0.1)', background: viewType === 'backtest' ? 'var(--gradient-primary)' : 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', fontFamily: 'Space Grotesk' }}
          >
            6-Month Backtest Simulation
          </button>
        </div>
        
        {viewType === 'backtest' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {triggerStatus && <span style={{ fontSize: '0.85rem', color: 'var(--plasma-cyan)', fontFamily: 'JetBrains Mono' }}>{triggerStatus}</span>}
            <button 
              onClick={triggerBacktest}
              style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(0,255,224,0.1)', background: 'var(--plasma-green)', color: 'black', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', fontFamily: 'Space Grotesk' }}
            >
              Re-run Backtest
            </button>
          </div>
        )}
      </div>

      {/* Portfolio Summary */}
      <div className="glass-panel col-span-12 animate-fade-in delay-1">
        <h2><DollarSign size={20} className="text-plasma-cyan"/> Portfolio Summary</h2>
        <div style={{ display: 'flex', gap: '40px', marginTop: '24px', flexWrap: 'wrap' }}>
          <div>
            <p className="stat-label">Total Equity</p>
            <p className="stat-value">${portfolio.total_equity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
          </div>
          <div>
            <p className="stat-label">Available Cash</p>
            <p className="stat-value text-plasma-cyan">
              ${portfolio.cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </p>
          </div>
          <div>
            <p className="stat-label">Total PnL</p>
            <p className="stat-value" style={{ color: pnl >= 0 ? 'var(--plasma-green)' : 'var(--plasma-red)' }}>
              {pnl >= 0 ? '+' : ''}${pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ({pnlPct.toFixed(2)}%)
            </p>
          </div>
          {portfolio.win_rate !== undefined && (
            <div>
              <p className="stat-label">Win Rate</p>
              <p className="stat-value" style={{ color: portfolio.win_rate >= 50 ? 'var(--plasma-green)' : 'var(--plasma-amber)' }}>
                {portfolio.win_rate.toFixed(1)}%
              </p>
            </div>
          )}
          {portfolio.total_fees_paid !== undefined && (
            <div>
              <p className="stat-label">Slippage & Fees Paid</p>
              <p className="stat-value text-plasma-amber">
                ${portfolio.total_fees_paid.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Open Positions */}
      <div className="data-panel col-span-12 animate-fade-in delay-2">
        <h2><PieChart size={20} className="text-plasma-purple"/> Open Positions</h2>
        {Object.keys(portfolio.positions).length === 0 ? (
          <p className="text-muted" style={{ marginTop: '16px', fontFamily: 'JetBrains Mono' }}>No open positions. 100% Cash.</p>
        ) : (
          <div style={{ marginTop: '16px', overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontFamily: 'JetBrains Mono' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(0,255,224,0.1)' }}>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Asset</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Shares</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(portfolio.positions).map(([symbol, shares]) => (
                  <tr key={symbol} className="data-item">
                    <td style={{ padding: '12px 16px', fontWeight: 'bold', color: '#fff' }}>{symbol}</td>
                    <td style={{ padding: '12px 16px' }}>{shares.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trade History */}
      <div className="data-panel col-span-12 animate-fade-in delay-3">
        <h2><History size={20} className="text-plasma-amber"/> Mock Execution Ledger</h2>
        {ledger.length === 0 ? (
          <p className="text-muted" style={{ marginTop: '16px', fontFamily: 'JetBrains Mono' }}>No mock trades executed yet.</p>
        ) : (
          <div style={{ marginTop: '16px', overflowX: 'auto', maxHeight: '400px' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontFamily: 'JetBrains Mono' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'rgba(5, 12, 20, 0.9)', backdropFilter: 'blur(10px)', zIndex: 10 }}>
                <tr style={{ borderBottom: '1px solid rgba(0,255,224,0.1)' }}>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Time</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Action</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Asset</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Shares</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Price</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Value</th>
                  <th style={{ padding: '12px 16px', color: 'var(--plasma-cyan)', fontWeight: 'bold' }}>Stats</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((trade, i) => (
                  <tr key={i} className="data-item">
                    <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      {new Date(trade.timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px', fontWeight: 'bold', color: trade.action === 'BUY' ? 'var(--plasma-green)' : 'var(--plasma-red)' }}>
                      {trade.action}
                    </td>
                    <td style={{ padding: '12px 16px', fontWeight: 'bold', color: '#fff' }}>{trade.ticker}</td>
                    <td style={{ padding: '12px 16px' }}>{parseFloat(trade.shares).toFixed(4)}</td>
                    <td style={{ padding: '12px 16px' }}>${parseFloat(trade.price).toFixed(2)}</td>
                    <td style={{ padding: '12px 16px' }}>${parseFloat(trade.value).toFixed(2)}</td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>{trade.stats || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
