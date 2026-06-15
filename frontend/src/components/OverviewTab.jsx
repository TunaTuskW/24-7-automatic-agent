import React from 'react';
import { Activity, Zap, TrendingUp, ShieldAlert, Clock } from 'lucide-react';

export default function OverviewTab({ data }) {
  return (
    <div className="grid-layout">
      {/* Core State Panel */}
      <div className="glass-panel col-span-8 animate-fade-in delay-1">
        <h2><Activity size={20} className="text-muted"/> Market Regime State</h2>
        <div style={{ display: 'flex', gap: '40px', marginTop: '24px' }}>
          <div>
            <p className="stat-label">Dominant HMM Regime</p>
            <p className="stat-value" style={{ color: 'var(--accent-blue)' }}>
              {data.regime.replace('_', ' ')}
            </p>
          </div>
          <div>
            <p className="stat-label">Model Confidence</p>
            <p className="stat-value">{(data.regimeProb * 100).toFixed(1)}%</p>
          </div>
        </div>
        
        <div className="progress-bg">
          <div 
            className="progress-fill" 
            style={{ width: `${data.regimeProb * 100}%` }}
          ></div>
        </div>
      </div>

      {/* Action Panel */}
      <div className="glass-panel col-span-4 animate-fade-in delay-2">
        <h2><Zap size={20} className="text-muted"/> Current Allocation</h2>
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '200px', overflowY: 'auto' }}>
          {data.allocations && Object.entries(data.allocations).map(([asset, alloc]) => (
            <div key={asset} className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="text-muted">{asset.replace('_Kelly', '')}</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 600, color: alloc > 0 ? 'var(--success)' : 'var(--text)' }}>
                {(alloc * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {(!data.allocations || Object.keys(data.allocations).length === 0) && (
            <div className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="text-muted">Target SPX (Kelly)</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--success)' }}>
                {(data.kelly * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Micro-Indicators */}
      <div className="glass-panel col-span-3 animate-fade-in delay-3">
        <h2><ShieldAlert size={20} className="text-muted"/> Volatility</h2>
        <p className="stat-value" style={{ marginTop: '16px' }}>{data.vix}</p>
        <p className="text-muted" style={{ fontSize: '0.875rem' }}>VIX Index</p>
      </div>

      <div className="glass-panel col-span-3 animate-fade-in delay-3">
        <h2><TrendingUp size={20} className="text-muted"/> Yield Curve</h2>
        <p className="stat-value" style={{ marginTop: '16px' }}>{data.spread}%</p>
        <p className="text-muted" style={{ fontSize: '0.875rem' }}>10Y - 2Y Spread</p>
      </div>

      <div className="glass-panel col-span-6 animate-fade-in delay-3">
        <h2><Clock size={20} className="text-muted"/> Engine Diagnostics</h2>
        <ul className="data-list" style={{ marginTop: '16px' }}>
          <li className="data-item">
            <span className="text-muted">Last 1H Context Inference</span>
            <span>{new Date(data.lastUpdate).toLocaleTimeString()}</span>
          </li>
          <li className="data-item">
            <span className="text-muted">Next Execution Window</span>
            <span>Midnight (1D Engine)</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
