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
    return <div className="glass-panel" style={{ textAlign: 'center', padding: '40px' }}>Waiting for Data Science Engine telemetry...</div>;
  }

  const { data_science_layer, kalman_state, mlp_deep_state } = modelData;
  const featuresList = data_science_layer?.ordered_features_list || [];
  const featuresVector = data_science_layer?.features_vector || [];

  return (
    <div className="grid-layout">
      
      {/* Raw Input Vector */}
      <div className="glass-panel col-span-12 animate-fade-in delay-1">
        <h2><Database size={20} className="text-muted"/> Data Science Layer: Input Vector</h2>
        <p className="text-muted" style={{ marginTop: '8px', marginBottom: '16px', fontSize: '0.9rem' }}>
          Real-time standardized feature vector processed by the ML engine.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '12px' }}>
          {featuresList.map((feat, i) => (
            <div key={feat} className="data-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '4px' }}>
              <span className="text-muted" style={{ fontSize: '0.75rem' }}>{feat}</span>
              <span style={{ fontFamily: 'monospace', color: 'var(--accent-blue)' }}>{featuresVector[i]?.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Kalman Filter */}
      <div className="glass-panel col-span-6 animate-fade-in delay-2">
        <h2><Network size={20} className="text-muted"/> Kalman Filter Regime Probability</h2>
        <div style={{ marginTop: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Risk On</span>
            <span style={{ color: 'var(--success)' }}>{(kalman_state?.risk_on * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg" style={{ marginBottom: '16px' }}>
            <div className="progress-fill" style={{ width: `${kalman_state?.risk_on * 100}%`, backgroundColor: 'var(--success)' }}></div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Transitional</span>
            <span style={{ color: 'var(--accent-blue)' }}>{(kalman_state?.transitional * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg" style={{ marginBottom: '16px' }}>
            <div className="progress-fill" style={{ width: `${kalman_state?.transitional * 100}%`, backgroundColor: 'var(--accent-blue)' }}></div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Risk Off</span>
            <span style={{ color: 'var(--warning)' }}>{(kalman_state?.risk_off * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-bg">
            <div className="progress-fill" style={{ width: `${kalman_state?.risk_off * 100}%`, backgroundColor: 'var(--warning)' }}></div>
          </div>
        </div>
        
        {kalman_state?.is_ambiguous && (
          <div style={{ marginTop: '24px', padding: '12px', backgroundColor: 'rgba(231, 76, 60, 0.1)', border: '1px solid var(--warning)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <AlertTriangle size={16} className="text-warning" />
            <span style={{ color: 'var(--warning)', fontSize: '0.85rem' }}>High structural ambiguity detected in covariance matrix.</span>
          </div>
        )}
      </div>

      {/* Deep Learning Consensus */}
      <div className="glass-panel col-span-6 animate-fade-in delay-3">
        <h2><Cpu size={20} className="text-muted"/> MLP Deep Neural Net Consensus</h2>
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {mlp_deep_state && Object.entries(mlp_deep_state).map(([asset, preds]) => (
            <div key={asset} className="data-item">
              <span style={{ fontWeight: 'bold', textTransform: 'uppercase', width: '40px' }}>{asset}</span>
              <div style={{ display: 'flex', gap: '16px', flex: 1, justifyContent: 'flex-end' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                  <span className="text-muted" style={{ fontSize: '0.7rem' }}>BULL</span>
                  <span style={{ color: 'var(--success)' }}>{(preds.bull_probability * 100).toFixed(1)}%</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                  <span className="text-muted" style={{ fontSize: '0.7rem' }}>BEAR</span>
                  <span style={{ color: 'var(--warning)' }}>{(preds.bear_probability * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
