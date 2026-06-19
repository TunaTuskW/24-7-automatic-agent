import React, { useState, useEffect } from 'react';
import { Newspaper, Calendar, BrainCircuit, ShieldAlert } from 'lucide-react';

export default function MacroTab() {
  const [macroData, setMacroData] = useState(null);

  useEffect(() => {
    const fetchMacro = async () => {
      try {
        const res = await fetch('/api/macro');
        if (res.ok) {
          const json = await res.json();
          setMacroData(json);
        }
      } catch (e) {
        console.error("Failed to fetch macro data");
      }
    };
    
    fetchMacro();
    const interval = setInterval(fetchMacro, 60000); // 1 min poll
    return () => clearInterval(interval);
  }, []);

  if (!macroData || macroData.error) {
    return <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--plasma-cyan)', fontFamily: 'JetBrains Mono' }}>Waiting for Macro Agent inference...</div>;
  }

  const { news_signal, economic_calendar } = macroData;
  const signal = news_signal?.signal || 'UNKNOWN';
  
  let signalColor = 'var(--text-muted)';
  if (signal === 'LONG') signalColor = 'var(--plasma-green)';
  if (signal === 'SHORT') signalColor = 'var(--plasma-amber)';

  return (
    <div className="grid-layout">
      
      {/* LLM Reasoning Panel */}
      <div className="data-panel col-span-12 animate-fade-in delay-1">
        <h2><BrainCircuit size={20} className="text-plasma-purple"/> LLM Macro Sentiment Reasoning</h2>
        <div style={{ marginTop: '24px', display: 'flex', gap: '40px', flexWrap: 'wrap' }}>
          
          <div style={{ flex: '1 1 300px' }}>
            <div style={{ display: 'flex', gap: '24px', marginBottom: '24px' }}>
              <div>
                <p className="stat-label">Directional Bias</p>
                <p className="stat-value" style={{ color: signalColor, fontSize: '1.8rem' }}>{signal}</p>
              </div>
              <div>
                <p className="stat-label">Conviction Score</p>
                <p className="stat-value" style={{ fontSize: '1.8rem' }}>{(news_signal?.conviction * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="stat-label">Impact Assessment</p>
                <p className="stat-value" style={{ fontSize: '1.8rem', color: 'var(--plasma-cyan)' }}>{news_signal?.impact?.replace(/_/g, ' ')}</p>
              </div>
            </div>
            
            {news_signal?.quantitative_divergence_flag && (
              <div style={{ padding: '12px', backgroundColor: 'rgba(255, 183, 0, 0.1)', border: '1px solid var(--plasma-amber)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '24px' }}>
                <ShieldAlert size={16} className="text-plasma-amber" />
                <span style={{ color: 'var(--plasma-amber)', fontSize: '0.85rem', fontFamily: 'JetBrains Mono' }}>Quantitative Divergence Detected! (Narrative conflicts with price action)</span>
              </div>
            )}
          </div>
          
          <div style={{ flex: '2 1 400px', backgroundColor: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0,255,224,0.1)' }}>
            <h3 style={{ fontSize: '0.85rem', color: 'var(--plasma-cyan)', marginBottom: '8px', textTransform: 'uppercase', fontFamily: 'JetBrains Mono' }}>Synthesized Narrative</h3>
            <p style={{ lineHeight: '1.6', color: 'rgba(255,255,255,0.9)', fontSize: '0.95rem' }}>
              {news_signal?.reasoning || "No reasoning provided by LLM."}
            </p>
          </div>

        </div>
      </div>

      {/* Economic Calendar */}
      <div className="data-panel col-span-12 animate-fade-in delay-2">
        <h2><Calendar size={20} className="text-plasma-cyan"/> Upcoming High-Impact Events</h2>
        
        {(!economic_calendar?.events || economic_calendar.events.length === 0) ? (
          <p className="text-muted" style={{ marginTop: '16px', fontFamily: 'JetBrains Mono' }}>No high-impact events scheduled for this window.</p>
        ) : (
          <div style={{ marginTop: '24px', overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontFamily: 'JetBrains Mono' }}>
              <thead style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                <tr>
                  <th style={{ padding: '12px', color: 'var(--plasma-cyan)', borderBottom: '1px solid rgba(0,255,224,0.1)' }}>Date / Time (Local)</th>
                  <th style={{ padding: '12px', color: 'var(--plasma-cyan)', borderBottom: '1px solid rgba(0,255,224,0.1)' }}>Country</th>
                  <th style={{ padding: '12px', color: 'var(--plasma-cyan)', borderBottom: '1px solid rgba(0,255,224,0.1)' }}>Event</th>
                  <th style={{ padding: '12px', color: 'var(--plasma-cyan)', borderBottom: '1px solid rgba(0,255,224,0.1)' }}>Forecast</th>
                  <th style={{ padding: '12px', color: 'var(--plasma-cyan)', borderBottom: '1px solid rgba(0,255,224,0.1)' }}>Previous</th>
                </tr>
              </thead>
              <tbody>
                {economic_calendar.events.map((evt, i) => {
                  const dateObj = new Date(evt.date);
                  return (
                    <tr key={i} className="data-item" style={{ borderBottom: '1px solid rgba(0,255,224,0.05)' }}>
                      <td style={{ padding: '16px 12px', fontSize: '0.9rem', color: '#fff' }}>
                        {dateObj.toLocaleDateString()} <span className="text-muted">{dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                      </td>
                      <td style={{ padding: '16px 12px', fontWeight: 'bold', color: 'var(--plasma-purple)' }}>{evt.country}</td>
                      <td style={{ padding: '16px 12px', color: '#fff' }}>{evt.title}</td>
                      <td style={{ padding: '16px 12px', color: 'var(--text-muted)' }}>{evt.forecast || '-'}</td>
                      <td style={{ padding: '16px 12px', color: 'var(--text-muted)' }}>{evt.previous || '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
