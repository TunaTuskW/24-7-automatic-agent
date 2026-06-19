import React from 'react';
import { Activity, Zap, TrendingUp, ShieldAlert, Clock } from 'lucide-react';

export default function OverviewTab({ data }) {
  return (
    <div className="grid-layout">
      {/* Core State Panel (Tier 1) */}
      <div className="glass-panel col-span-8 animate-fade-in delay-1">
        <h2><Activity size={20} className="text-plasma-cyan"/> Market Regime State</h2>
        <div style={{ display: 'flex', gap: '40px', marginTop: '24px' }}>
          <div>
            <p className="stat-label">Dominant HMM Regime</p>
            <p className="stat-value text-plasma-cyan">
              {data.regime.replace(/_/g, ' ')}
            </p>
          </div>
          <div>
            <p className="stat-label">Model Confidence</p>
            <p className="stat-value text-plasma-purple">{(data.regimeProb * 100).toFixed(1)}%</p>
          </div>
        </div>
        
        <div className="progress-bg">
          <div 
            className="progress-fill" 
            style={{ width: `${data.regimeProb * 100}%` }}
          ></div>
        </div>
      </div>

      {/* Action Panel (Tier 1) */}
      <div className="glass-panel col-span-4 animate-fade-in delay-2">
        <h2><Zap size={20} className="text-plasma-amber"/> Target Allocation</h2>
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '180px', overflowY: 'auto' }}>
          {data.allocations && Object.entries(data.allocations).map(([asset, alloc]) => (
            <div key={asset} className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="stat-label">{asset.replace('_Kelly', '')}</span>
              <span className="stat-value" style={{ fontSize: '1.75rem', color: alloc > 0 ? 'var(--plasma-green)' : 'var(--text-muted)' }}>
                {(alloc * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {(!data.allocations || Object.keys(data.allocations).length === 0) && (
            <div className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="stat-label">SPX Target</span>
              <span className="stat-value text-plasma-green" style={{ fontSize: '1.75rem' }}>
                {(data.kelly * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Micro-Indicators (Tier 2 / 1) */}
      <div className="glass-panel col-span-3 animate-fade-in delay-3">
        <h2><ShieldAlert size={20} className="text-plasma-red"/> Volatility</h2>
        <p className="stat-value" style={{ marginTop: '16px' }}>{typeof data.vix === 'number' ? data.vix.toFixed(2) : data.vix}</p>
        <p className="stat-label" style={{ marginTop: '8px' }}>VIX Index</p>
      </div>

      <div className="glass-panel col-span-3 animate-fade-in delay-3">
        <h2><TrendingUp size={20} className="text-plasma-green"/> Yield Curve</h2>
        <p className="stat-value" style={{ marginTop: '16px' }}>{typeof data.spread === 'number' ? data.spread.toFixed(2) : data.spread}%</p>
        <p className="stat-label" style={{ marginTop: '8px' }}>10Y - 2Y Spread</p>
      </div>

      <div className="glass-panel col-span-6 animate-fade-in delay-3">
        <h2><Clock size={20} className="text-plasma-cyan"/> Engine Diagnostics</h2>
        <ul className="data-list" style={{ marginTop: '16px' }}>
          <li className="data-item">
            <span className="stat-label">Last 1H Context Inference</span>
            <span>{new Date(data.lastUpdate).toLocaleTimeString()}</span>
          </li>
          <li className="data-item">
            <span className="stat-label">Next Execution Window</span>
            <span>Midnight (1D Engine)</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
