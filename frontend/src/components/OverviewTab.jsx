import { formatTimeToggle } from "../utils/timeFormatter";
import React from 'react';

export default function OverviewTab({ data, timeZone }) {
  return (
    <div className="grid-layout">
      {/* Top Row: Core State & Allocation */}
      <div className="data-panel col-span-8">
        <h2>[ MARKET REGIME STATE ]</h2>
        <div style={{ display: 'flex', gap: '40px', marginTop: '24px' }}>
          <div>
            <p className="stat-label">Dominant HMM Regime</p>
            <p className="stat-value text-plasma-cyan" style={{ fontSize: '1.4rem' }}>
              {data.regime.replace(/_/g, ' ')}
            </p>
          </div>
          <div>
            <p className="stat-label">Model Confidence</p>
            <p className="stat-value text-plasma-purple" style={{ fontSize: '1.4rem' }}>{(data.regimeProb * 100).toFixed(1)}%</p>
          </div>
          <div>
            <p className="stat-label">System State</p>
            <p className="stat-value text-plasma-green" style={{ fontSize: '1.4rem' }}>ONLINE / ACTIVE</p>
          </div>
        </div>
      </div>

      <div className="data-panel col-span-4">
        <h2>[ TARGET ALLOCATION ]</h2>
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
          {data.allocations && Object.entries(data.allocations).map(([asset, alloc]) => (
            <div key={asset} className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="stat-label">{asset.replace('_Kelly', '')}</span>
              <span className="stat-value" style={{ fontSize: '1.4rem', color: alloc > 0 ? 'var(--plasma-green)' : 'var(--text-muted)' }}>
                {(alloc * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {(!data.allocations || Object.keys(data.allocations).length === 0) && (
            <div className="data-item" style={{ padding: 0, border: 'none' }}>
              <span className="stat-label">SPX Target</span>
              <span className="stat-value text-plasma-green" style={{ fontSize: '1.4rem' }}>
                {(data.kelly * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Middle Row: Market Pulse & Indicators */}
      <div className="data-panel col-span-4">
        <h2>[ MARKET PULSE ]</h2>
        <table style={{ marginTop: '12px' }}>
          <tbody>
            <tr><td>SPX 500</td><td className={data.raw_indicators?.SPX?.delta_pct >= 0 ? "text-plasma-green" : "text-plasma-red"}>{(data.raw_indicators?.SPX?.delta_pct || 0).toFixed(2)}%</td><td>{(data.raw_indicators?.SPX?.current || 0).toFixed(2)}</td></tr>
            <tr><td>NDX 100</td><td className={data.raw_indicators?.NDX?.delta_pct >= 0 ? "text-plasma-green" : "text-plasma-red"}>{(data.raw_indicators?.NDX?.delta_pct || 0).toFixed(2)}%</td><td>{(data.raw_indicators?.NDX?.current || 0).toFixed(2)}</td></tr>
            <tr><td>RUT 2000</td><td className={data.raw_indicators?.RTY?.delta_pct >= 0 ? "text-plasma-green" : "text-plasma-red"}>{(data.raw_indicators?.RTY?.delta_pct || 0).toFixed(2)}%</td><td>{(data.raw_indicators?.RTY?.current || 0).toFixed(2)}</td></tr>
            <tr><td>DXY INDEX</td><td className={data.raw_indicators?.DXY?.delta_pct >= 0 ? "text-plasma-green" : "text-plasma-red"}>{(data.raw_indicators?.DXY?.delta_pct || 0).toFixed(2)}%</td><td>{(data.raw_indicators?.DXY?.current || 0).toFixed(2)}</td></tr>
            <tr><td>US 10Y YIELD</td><td className="text-muted">{(data.features_dict?.us10y_delta || 0).toFixed(2)} bps</td><td>N/A</td></tr>
          </tbody>
        </table>
      </div>

      <div className="data-panel col-span-4">
        <h2>[ MACRO INDICATORS ]</h2>
        <table style={{ marginTop: '12px' }}>
          <tbody>
            <tr><td>VIX INDEX</td><td className="text-plasma-amber">{(data.vix || 0).toFixed(2)}</td><td>{data.vix > 20 ? "ELEVATED" : "NORMAL"}</td></tr>
            <tr><td>10Y-2Y SPREAD</td><td className="text-plasma-amber">{(data.spread || 0).toFixed(2)}</td><td>{data.spread < 0 ? "INVERTED" : "NORMAL"}</td></tr>
            <tr><td>MOVE INDEX</td><td className="text-muted">N/A</td><td>N/A</td></tr>
            <tr><td>LIQUIDITY IDX</td><td className="text-plasma-green">{(data.features_dict?.Inst_Heat_Index || 0).toFixed(2)}</td><td>ACTIVE</td></tr>
            <tr><td>SKEW IDX</td><td className="text-muted">N/A</td><td>N/A</td></tr>
          </tbody>
        </table>
      </div>

      <div className="data-panel col-span-4">
        <h2>[ INSTITUTIONAL FLOWS ]</h2>
        <table style={{ marginTop: '12px' }}>
          <tbody>
            <tr><td>DARK POOL IDX</td><td className="text-plasma-green">N/A</td><td>N/A</td></tr>
            <tr><td>RETAIL SENTIMENT</td><td className="text-plasma-red">N/A</td><td>N/A</td></tr>
            <tr><td>CTA POSITIONING</td><td className="text-plasma-green">N/A</td><td>N/A</td></tr>
            <tr><td>GAMMA EXPOSURE</td><td className="text-plasma-amber">N/A</td><td>N/A</td></tr>
            <tr><td>SHORT INTEREST</td><td className="text-muted">N/A</td><td>N/A</td></tr>
          </tbody>
        </table>
      </div>

      {/* Bottom Row: Unified Decision & Diagnostics */}
      {data.decision && (
        <div className="data-panel col-span-8" style={{ borderLeft: '4px solid ' + (data.decision.conviction_gate_passed ? 'var(--plasma-green)' : 'var(--plasma-amber)') }}>
          <h2>[ UNIFIED TRADE DECISION: {data.decision.recommended_action} ]</h2>
          <p className="stat-value" style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
            {data.decision.decision_rationale}
          </p>
          <div style={{ display: 'flex', gap: '40px', marginTop: '16px' }}>
            <div>
              <p className="stat-label">Conviction Gate</p>
              <p className="stat-value" style={{ color: data.decision.conviction_gate_passed ? 'var(--plasma-green)' : 'var(--plasma-amber)' }}>
                {data.decision.conviction_gate_passed ? "PASSED" : "BLOCKED"}
              </p>
            </div>
            <div>
              <p className="stat-label">Entry Score</p>
              <p className="stat-value">{data.decision.entry_score.toFixed(2)}</p>
            </div>
            <div>
              <p className="stat-label">Macro Conviction</p>
              <p className="stat-value">{data.decision.macro_conviction.toFixed(2)}</p>
            </div>
          </div>
          {data.decision.risk_flags && data.decision.risk_flags.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <p className="stat-label text-plasma-amber">Risk Flags</p>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                {data.decision.risk_flags.map(f => (
                  <span key={f} style={{ padding: '2px 4px', border: '1px solid var(--plasma-amber)', fontSize: '10px', color: 'var(--plasma-amber)' }}>
                    {f.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="data-panel col-span-4">
        <h2>[ DIAGNOSTICS & TELEMETRY ]</h2>
        <ul className="data-list" style={{ marginTop: '16px', listStyle: 'none' }}>
          <li className="data-item">
            <span className="stat-label">Last 1H Inference</span>
            <span className="text-bright">{formatTimeToggle(data.lastUpdate, timeZone, false)}</span>
          </li>
          <li className="data-item">
            <span className="stat-label">Next Execution</span>
            <span className="text-bright">Midnight (1D)</span>
          </li>
          <li className="data-item">
            <span className="stat-label">Latency</span>
            <span className="text-plasma-green">Live</span>
          </li>
          <li className="data-item">
            <span className="stat-label">Data Nodes</span>
            <span className="text-plasma-green">SYNCED</span>
          </li>
          <li className="data-item">
            <span className="stat-label">API Quota</span>
            <span className="text-plasma-amber">OK</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
