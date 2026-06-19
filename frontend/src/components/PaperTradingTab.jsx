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
      <div className="glass-panel col-span-12" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '-10px' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={() => setViewType('live')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: viewType === 'live' ? 'var(--accent-blue)' : 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}
          >
            Real-Time Mock Trading
          </button>
          <button 
            onClick={() => setViewType('backtest')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: viewType === 'backtest' ? 'var(--accent-blue)' : 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}
          >
            6-Month Backtest Simulation
          </button>
        </div>
        
        {viewType === 'backtest' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {triggerStatus && <span style={{ fontSize: '0.85rem', color: 'var(--success)' }}>{triggerStatus}</span>}
            <button 
              onClick={triggerBacktest}
              style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--success)', color: 'white', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}
            >
              Re-run Backtest
            </button>
          </div>
        )}
      </div>
      {/* Portfolio Summary */}
      <div className="glass-panel col-span-12 animate-fade-in delay-1">
        <h2><DollarSign size={20} className="text-muted"/> Portfolio Summary</h2>
        <div style={{ display: 'flex', gap: '40px', marginTop: '24px' }}>
          <div>
            <p className="stat-label">Total Equity</p>
            <p className="stat-value">${portfolio.total_equity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
          </div>
          <div>
            <p className="stat-label">Available Cash</p>
            <p className="stat-value" style={{ color: 'var(--accent-blue)' }}>
              ${portfolio.cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </p>
          </div>
          <div>
            <p className="stat-label">Total PnL</p>
            <p className="stat-value" style={{ color: pnl >= 0 ? 'var(--success)' : 'var(--warning)' }}>
              {pnl >= 0 ? '+' : ''}${pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ({pnlPct.toFixed(2)}%)
            </p>
          </div>
          {portfolio.win_rate !== undefined && (
            <div>
              <p className="stat-label">Win Rate</p>
              <p className="stat-value" style={{ color: portfolio.win_rate >= 50 ? 'var(--success)' : 'var(--warning)' }}>
                {portfolio.win_rate.toFixed(1)}%
              </p>
            </div>
          )}
          {portfolio.total_fees_paid !== undefined && (
            <div>
              <p className="stat-label">Slippage & Fees Paid</p>
              <p className="stat-value" style={{ color: 'var(--warning)' }}>
                ${portfolio.total_fees_paid.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Open Positions */}
      <div className="glass-panel col-span-12 animate-fade-in delay-2">
        <h2><PieChart size={20} className="text-muted"/> Open Positions</h2>
        {Object.keys(portfolio.positions).length === 0 ? (
          <p className="text-muted" style={{ marginTop: '16px' }}>No open positions. 100% Cash.</p>
        ) : (
          <div style={{ marginTop: '16px', overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                  <th style={{ padding: '8px 0', color: 'var(--text-muted)' }}>Asset</th>
                  <th style={{ padding: '8px 0', color: 'var(--text-muted)' }}>Shares</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(portfolio.positions).map(([symbol, shares]) => (
                  <tr key={symbol} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 0', fontWeight: 'bold' }}>{symbol}</td>
                    <td style={{ padding: '12px 0' }}>{shares.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trade History */}
      <div className="glass-panel col-span-12 animate-fade-in delay-3">
        <h2><History size={20} className="text-muted"/> Mock Execution Ledger</h2>
        {ledger.length === 0 ? (
          <p className="text-muted" style={{ marginTop: '16px' }}>No mock trades executed yet.</p>
        ) : (
          <div style={{ marginTop: '16px', overflowX: 'auto', maxHeight: '400px' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-glass)', backdropFilter: 'blur(10px)' }}>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Time</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Action</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Asset</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Shares</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Price</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Value</th>
                  <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Stats</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((trade, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      {new Date(trade.timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 8px', fontWeight: 'bold', color: trade.action === 'BUY' ? 'var(--success)' : 'var(--warning)' }}>
                      {trade.action}
                    </td>
                    <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>{trade.ticker}</td>
                    <td style={{ padding: '12px 8px' }}>{parseFloat(trade.shares).toFixed(4)}</td>
                    <td style={{ padding: '12px 8px' }}>${parseFloat(trade.price).toFixed(2)}</td>
                    <td style={{ padding: '12px 8px' }}>${parseFloat(trade.value).toFixed(2)}</td>
                    <td style={{ padding: '12px 8px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>{trade.stats || '-'}</td>
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
