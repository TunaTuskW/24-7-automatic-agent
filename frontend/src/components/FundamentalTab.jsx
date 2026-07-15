import React, { useState, useEffect } from 'react';
import ErrorBoundary from './ErrorBoundary';

function FundamentalTabContent() {
  const [fundamentals, setFundamentals] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/fundamentals')
      .then(r => r.json())
      .then(data => {
        setFundamentals(data || {});
        setLoading(false);
      })
      .catch(e => {
        console.error("Failed to load fundamentals", e);
        setLoading(false);
      });
  }, []);

  return (
    <div className="grid-layout">
      <div className="data-panel col-span-12">
        <h2>[ FUNDAMENTAL ANALYSIS ]</h2>
        {loading ? (
          <p className="text-muted">Loading fundamental data...</p>
        ) : Object.keys(fundamentals).length === 0 ? (
          <p className="text-muted">No fundamental data available. Ensure the agent has run.</p>
        ) : (
          <div style={{ display: 'grid', gap: '16px' }}>
            {Object.entries(fundamentals).map(([ticker, data]) => {
              if (data.reasoning === "Not an equity.") return null;
              
              const isPositive = data.conviction_score > 0;
              const isNegative = data.conviction_score < 0;
              const scoreColor = isPositive ? 'var(--term-green)' : (isNegative ? 'var(--term-red)' : 'var(--text-bright)');
              const scoreStr = (isPositive ? '+' : '') + data.conviction_score.toFixed(2);

              return (
                <div key={ticker} style={{ padding: '16px', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-bright)' }}>{ticker}</h3>
                    <div style={{ fontWeight: 'bold', fontSize: '1.2rem', color: scoreColor }}>
                      Conviction: {scoreStr}
                    </div>
                  </div>
                  
                  <p style={{ color: 'var(--text-main)', lineHeight: '1.5', marginBottom: '16px' }}>
                    {data.reasoning}
                  </p>
                  
                  {data.insights && Object.keys(data.insights).length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                      {Object.entries(data.insights).map(([key, value]) => (
                        <div key={key} style={{ padding: '12px', background: 'var(--bg-hover)', borderLeft: `2px solid ${scoreColor}` }}>
                          <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>{key}</h4>
                          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-main)', lineHeight: '1.4' }}>{value}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function FundamentalTab() {
  return (
    <ErrorBoundary>
      <FundamentalTabContent />
    </ErrorBoundary>
  );
}
