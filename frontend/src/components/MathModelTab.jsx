import React, { useState, useEffect } from 'react';
import ErrorBoundary from './ErrorBoundary';
import { Database, Network, Cpu, AlertTriangle, TrendingUp, TrendingDown, Zap, BarChart2, GitBranch, Layers } from 'lucide-react';

function FeatureBar({ label, value, max = 5 }) {
  const pct = Math.min(Math.abs(value) / max, 1) * 100;
  const isNeg = value < 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', background: 'rgba(0,0,0,0.25)', padding: '10px 12px', borderRadius: '8px', borderLeft: `2px solid ${isNeg ? 'var(--pink-deep)' : 'var(--lime-dim)'}` }}>
      <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'Space Grotesk' }}>{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono', color: isNeg ? 'var(--pink-soft)' : 'var(--lime)', fontSize: '1.05rem', fontWeight: 700 }}>{value?.toFixed(4)}</span>
      <div style={{ height: '3px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', marginTop: '2px' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: isNeg ? 'var(--pink-deep)' : 'var(--lime-dim)', borderRadius: '2px', transition: 'width 0.8s ease', boxShadow: `0 0 6px ${isNeg ? 'rgba(192,53,90,0.5)' : 'rgba(184,245,66,0.5)'}` }} />
      </div>
    </div>
  );
}

function RegimeBar({ label, value, color }) {
  const pct = Math.min((value || 0) * 100, 100);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>{label}</span>
        <span style={{ color, fontFamily: 'JetBrains Mono', fontSize: '0.9rem', fontWeight: 700 }}>{pct.toFixed(1)}%</span>
      </div>
      <div className="progress-bg" style={{ marginBottom: '20px' }}>
        <div className="progress-fill" style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}55` }} />
      </div>
    </div>
  );
}

function MathModelTabContent() {
  const [modelData, setModelData] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    const fetchModel = async () => {
      try {
        const res = await fetch('/api/model');
        if (res.ok) {
          const json = await res.json();
          setModelData(json);
          setLastUpdate(new Date());
        }
      } catch (e) {
        console.error('Failed to fetch model telemetry');
      }
    };
    fetchModel();
    const interval = setInterval(fetchModel, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!modelData || modelData.error) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '50px', fontFamily: 'JetBrains Mono', color: 'var(--lime)' }}>
        Waiting for Data Science Engine telemetry...
      </div>
    );
  }

  const { data_science_layer, kalman_state, mlp_deep_state, regime, trend_state, smc_state, liquidity_state } = modelData;
  const featuresList = data_science_layer?.ordered_features_list || [];
  const featuresVector = data_science_layer?.features_vector || [];
  const epistemic = data_science_layer?.epistemic_metrics || {};
  const kelly = epistemic?.kelly_exposure_fraction || {};

  const dominantRegime = regime?.dominant_regime || 'UNKNOWN';
  const regimeProbs = regime?.probabilities || {};
  const regimeConf = regime?.dominant_prob || 0;

  return (
    <div className="grid-layout">

      {/* Feature Vector */}
      <div className="data-panel col-span-12 animate-fade-in delay-1">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
          <h2><Database size={17} style={{ color: 'var(--lime)' }} /> Data Science Layer — Input Vector</h2>
          {lastUpdate && (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
              Refreshed {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '16px', fontFamily: 'JetBrains Mono' }}>
          Real-time standardized feature vector processed by the ML pipeline.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '10px' }}>
          {featuresList.map((feat, i) => (
            <FeatureBar key={feat} label={feat} value={featuresVector[i] ?? 0} />
          ))}
        </div>
      </div>

      {/* Epistemic Metrics */}
      {Object.keys(epistemic).length > 0 && (
        <div className="glass-panel col-span-6 animate-fade-in delay-1">
          <h2><Zap size={17} style={{ color: 'var(--plasma-amber)' }} /> Epistemic Metrics</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontFamily: 'JetBrains Mono' }}>
            {epistemic.brier_score !== undefined && (
              <div className="data-item">
                <span className="text-muted" style={{ fontSize: '0.82rem' }}>Brier Score</span>
                <span style={{ color: epistemic.brier_score < 0.25 ? 'var(--lime)' : 'var(--plasma-amber)', fontWeight: 700 }}>
                  {epistemic.brier_score?.toFixed(4)}
                </span>
              </div>
            )}
            {epistemic.forecast_accuracy !== undefined && (
              <div className="data-item">
                <span className="text-muted" style={{ fontSize: '0.82rem' }}>Forecast Accuracy</span>
                <span style={{ color: 'var(--lime)', fontWeight: 700 }}>{(epistemic.forecast_accuracy * 100).toFixed(1)}%</span>
              </div>
            )}
            {typeof kelly === 'object' && Object.entries(kelly).map(([k, v]) => (
              <div className="data-item" key={k}>
                <span className="text-muted" style={{ fontSize: '0.82rem' }}>{k}</span>
                <span style={{ color: v > 0.1 ? 'var(--lime)' : 'var(--pink-soft)', fontWeight: 700 }}>{(v * 100).toFixed(2)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Regime Summary */}
      <div className="glass-panel col-span-6 animate-fade-in delay-1">
        <h2><GitBranch size={17} style={{ color: 'var(--pink)' }} /> Active Regime</h2>
        <div style={{ marginBottom: '16px' }}>
          <p style={{ fontFamily: 'JetBrains Mono', color: 'var(--lime)', fontSize: '1.5rem', fontWeight: 700, marginBottom: '4px' }}>
            {dominantRegime.replace(/_/g, ' ')}
          </p>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
            Confidence: <span style={{ color: 'var(--lime)' }}>{(regimeConf * 100).toFixed(1)}%</span>
          </span>
        </div>
        {Object.entries(regimeProbs).map(([label, prob]) => (
          <RegimeBar key={label} label={label.replace(/_/g, ' ')} value={prob} color={label.includes('RISK_ON') ? 'var(--lime)' : label.includes('STAGFLATION') ? 'var(--pink-deep)' : 'var(--plasma-amber)'} />
        ))}
      </div>

      {/* Kalman Filter */}
      <div className="glass-panel col-span-6 animate-fade-in delay-2">
        <h2><Network size={17} style={{ color: 'var(--pink-soft)' }} /> Kalman Filter — Regime Probability</h2>
        <div style={{ fontFamily: 'JetBrains Mono' }}>
          <RegimeBar label="Risk On" value={kalman_state?.risk_on} color="var(--lime)" />
          <RegimeBar label="Transitional" value={kalman_state?.transitional} color="var(--plasma-amber)" />
          <RegimeBar label="Risk Off" value={kalman_state?.risk_off} color="var(--pink-deep)" />
        </div>
        {kalman_state?.is_ambiguous && (
          <div style={{ marginTop: '16px', padding: '10px 14px', backgroundColor: 'rgba(240,192,64,0.08)', border: '1px solid var(--plasma-amber)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <AlertTriangle size={14} style={{ color: 'var(--plasma-amber)', flexShrink: 0 }} />
            <span style={{ color: 'var(--plasma-amber)', fontSize: '0.8rem', fontFamily: 'JetBrains Mono' }}>High structural ambiguity detected in covariance matrix.</span>
          </div>
        )}
        {kalman_state?.gain !== undefined && (
          <div style={{ marginTop: '14px', display: 'flex', gap: '16px', fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
            <span className="text-muted">Kalman Gain: <span style={{ color: 'var(--lime)' }}>{kalman_state.gain?.toFixed(4)}</span></span>
            {kalman_state?.innovation !== undefined && (
              <span className="text-muted">Innovation: <span style={{ color: 'var(--lime)' }}>{kalman_state.innovation?.toFixed(4)}</span></span>
            )}
          </div>
        )}
      </div>

      {/* MLP Neural Net */}
      <div className="glass-panel col-span-6 animate-fade-in delay-3">
        <h2><Cpu size={17} style={{ color: 'var(--lime-soft)' }} /> MLP Deep Neural Net — Consensus</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {mlp_deep_state && Object.entries(mlp_deep_state).map(([asset, preds]) => {
            const bullP = (preds.bull_probability || 0) * 100;
            const bearP = (preds.bear_probability || 0) * 100;
            const bias = bullP > bearP ? 'BULL' : 'BEAR';
            return (
              <div key={asset} style={{ background: 'rgba(0,0,0,0.2)', padding: '14px 16px', borderRadius: '8px', border: '1px solid rgba(184,245,66,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, color: '#fff', fontSize: '1rem', fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>{asset}</span>
                  <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '4px', background: bias === 'BULL' ? 'rgba(184,245,66,0.12)' : 'rgba(192,53,90,0.12)', color: bias === 'BULL' ? 'var(--lime)' : 'var(--pink)', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                    {bias === 'BULL' ? <TrendingUp size={10} style={{ display: 'inline', marginRight: '4px' }} /> : <TrendingDown size={10} style={{ display: 'inline', marginRight: '4px' }} />}
                    {bias}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '24px', fontFamily: 'JetBrains Mono' }}>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>BULL</span>
                    <span style={{ color: 'var(--lime)', fontWeight: 700, fontSize: '1.1rem' }}>{bullP.toFixed(1)}%</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>BEAR</span>
                    <span style={{ color: 'var(--pink-deep)', fontWeight: 700, fontSize: '1.1rem' }}>{bearP.toFixed(1)}%</span>
                  </div>
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                    <div style={{ width: '100%', height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${bullP}%`, background: 'linear-gradient(90deg, var(--lime-dim), var(--lime))', transition: 'width 0.8s ease' }} />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* SMC State */}
      {smc_state && Object.keys(smc_state).length > 0 && (
        <div className="glass-panel col-span-6 animate-fade-in delay-2">
          <h2><Layers size={17} style={{ color: 'var(--pink-soft)' }} /> SMC State Machine</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontFamily: 'JetBrains Mono', fontSize: '0.82rem' }}>
            {Object.entries(smc_state).map(([k, v]) => (
              <div className="data-item" key={k}>
                <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.08em' }}>{k.replace(/_/g, ' ')}</span>
                <span style={{ color: v === true ? 'var(--lime)' : v === false ? 'var(--pink-deep)' : typeof v === 'number' ? (v > 0 ? 'var(--lime)' : v < 0 ? 'var(--pink)' : 'var(--text-muted)') : 'var(--text-main)' }}>
                  {typeof v === 'boolean' ? (v ? 'YES' : 'NO') : typeof v === 'number' ? v.toFixed(4) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trend State */}
      {trend_state && Object.keys(trend_state).length > 0 && (
        <div className="glass-panel col-span-6 animate-fade-in delay-3">
          <h2><BarChart2 size={17} style={{ color: 'var(--lime-soft)' }} /> UT Bot Trend State</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontFamily: 'JetBrains Mono', fontSize: '0.82rem' }}>
            {Object.entries(trend_state).map(([k, v]) => (
              <div className="data-item" key={k}>
                <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.08em' }}>{k.replace(/_/g, ' ')}</span>
                <span style={{ color: typeof v === 'string' && v.includes('UP') ? 'var(--lime)' : typeof v === 'string' && v.includes('DOWN') ? 'var(--pink)' : 'var(--text-main)' }}>
                  {typeof v === 'number' ? v.toFixed(4) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

export default function MathModelTab() {
  return (
    <ErrorBoundary>
      <MathModelTabContent />
    </ErrorBoundary>
  );
}

