import React, { useState, useEffect } from 'react';
import { Database, Network, Cpu, AlertTriangle } from 'lucide-react';

export default function MathModelTab() {
  const [modelData, setModelData] = useState(null);

  useEffect(() => {
    const fetchModel = async () => {
      try {
        const res = await fetch('/api/model');
        if (res.ok) {
          const json = await res.json();
          setModelData(json);
        }
      } catch (e) {
        console.error("Failed to fetch model telemetry");
      }
    };
    
    fetchModel();
    const interval = setInterval(fetchModel, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!modelData || modelData.error) {
    return <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', fontFamily: 'JetBrains Mono', color: 'var(--plasma-cyan)' }}>Waiting for Data Science Engine telemetry...</div>;
  }

  const { data_science_layer, kalman_state, mlp_deep_state } = modelData;
  const featuresList = data_science_layer?.ordered_features_list || [];
  const featuresVector = data_science_layer?.features_vector || [];

  return (
    <div className="grid-layout">
      
      {/* Raw Input Vector */}
      <div className="data-panel col-span-12 animate-fade-in delay-1">
        <h2><Database size={20} className="text-plasma-cyan"/> Data Science Layer: Input Vector</h2>
        <p className="text-muted" style={{ marginTop: '8px', marginBottom: '16px', fontSize: '0.9rem', fontFamily: 'JetBrains Mono' }}>
          Real-time standardized feature vector processed by the ML engine.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '12px' }}>
          {featuresList.map((feat, i) => (
            <div key={feat} className="data-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px', background: 'rgba(0,255,224,0.02)', padding: '12px', borderLeft: '2px solid var(--plasma-cyan)' }}>
              <span className="stat-label" style={{ fontSize: '0.7rem' }}>{feat}</span>
              <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--plasma-cyan)', fontSize: '1.2rem', fontWeight: 'bold' }}>{featuresVector[i]?.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Kalman Filter */}
      <div className="glass-panel col-span-6 animate-fade-in delay-2">
        <h2><Network size={20} className="text-plasma-purple"/> Kalman Filter Regime Probability</h2>
        <div style={{ marginTop: '24px', fontFamily: 'JetBrains Mono' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Risk On</span>
            <span style={{ color: 'var(--plasma-green)' }}>{(kalman_state?.risk_on * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg" style={{ marginBottom: '24px' }}>
            <div className="progress-fill" style={{ width: `${kalman_state?.risk_on * 100}%`, background: 'var(--gradient-safe)' }}></div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Transitional</span>
            <span style={{ color: 'var(--plasma-cyan)' }}>{(kalman_state?.transitional * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg" style={{ marginBottom: '24px' }}>
            <div className="progress-fill" style={{ width: `${kalman_state?.transitional * 100}%`, background: 'var(--plasma-cyan)', boxShadow: '0 0 10px var(--plasma-cyan)' }}></div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Risk Off</span>
            <span style={{ color: 'var(--plasma-amber)' }}>{(kalman_state?.risk_off * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg">
            <div className="progress-fill" style={{ width: `${kalman_state?.risk_off * 100}%`, background: 'var(--gradient-risk)' }}></div>
          </div>
        </div>
        
        {kalman_state?.is_ambiguous && (
          <div style={{ marginTop: '24px', padding: '12px', backgroundColor: 'rgba(255, 183, 0, 0.1)', border: '1px solid var(--plasma-amber)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <AlertTriangle size={16} className="text-plasma-amber" />
            <span style={{ color: 'var(--plasma-amber)', fontSize: '0.85rem', fontFamily: 'JetBrains Mono' }}>High structural ambiguity detected in covariance matrix.</span>
          </div>
        )}
      </div>

      {/* Deep Learning Consensus */}
      <div className="glass-panel col-span-6 animate-fade-in delay-3">
        <h2><Cpu size={20} className="text-plasma-green"/> MLP Deep Neural Net Consensus</h2>
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {mlp_deep_state && Object.entries(mlp_deep_state).map(([asset, preds]) => (
            <div key={asset} className="data-item" style={{ background: 'rgba(0,255,224,0.03)', padding: '16px', borderRadius: '8px' }}>
              <span style={{ fontWeight: 'bold', textTransform: 'uppercase', width: '60px', color: '#fff', fontSize: '1.2rem', fontFamily: 'JetBrains Mono' }}>{asset}</span>
              <div style={{ display: 'flex', gap: '24px', flex: 1, justifyContent: 'flex-end', fontFamily: 'JetBrains Mono' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                  <span className="stat-label" style={{ fontSize: '0.7rem' }}>BULL</span>
                  <span style={{ color: 'var(--plasma-green)', fontSize: '1.2rem', fontWeight: 'bold' }}>{(preds.bull_probability * 100).toFixed(1)}%</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                  <span className="stat-label" style={{ fontSize: '0.7rem' }}>BEAR</span>
                  <span style={{ color: 'var(--plasma-red)', fontSize: '1.2rem', fontWeight: 'bold' }}>{(preds.bear_probability * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
