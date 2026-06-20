import React, { useState, useEffect } from 'react';
import { Newspaper, Calendar, BrainCircuit, ShieldAlert, RefreshCw, AlertCircle, Loader } from 'lucide-react';
import { apiPost } from '../App';

export default function MacroTab() {
  const [macroData, setMacroData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState(null);
  const [retrying, setRetrying] = useState(false);

  const fetchMacro = async () => {
    try {
      const res = await fetch('/api/macro');
      if (res.ok) {
        const json = await res.json();
        setMacroData(json);
        setLastFetch(new Date());
      }
    } catch (e) {
      console.error('Failed to fetch macro data');
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  };

  const handleRetry = async () => {
    setRetrying(true);
    // Trigger a 1H context run which refreshes the macro agent
    try {
      await apiPost('/api/trigger', { job: '1h' });
    } catch (_) {}
    setTimeout(fetchMacro, 4000);
  };

  useEffect(() => {
    fetchMacro();
    const interval = setInterval(fetchMacro, 60000);
    return () => clearInterval(interval);
  }, []);

  const hasError = !macroData || macroData.error || !macroData.news_signal;
  const { news_signal, economic_calendar } = macroData || {};
  const signal = news_signal?.signal || 'UNKNOWN';
  const isLocal = news_signal?.reasoning?.toLowerCase().includes('local bypass') ||
                  news_signal?.reasoning?.toLowerCase().includes('api key');

  let signalColor = 'var(--text-muted)';
  if (signal === 'LONG')  signalColor = 'var(--lime)';
  if (signal === 'SHORT') signalColor = 'var(--plasma-amber)';
  if (signal === 'FLAT')  signalColor = 'var(--pink-soft)';

  const ErrorBanner = () => (
    <div className="glass-panel animate-fade-in" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '40px', textAlign: 'center' }}>
      <AlertCircle size={40} style={{ color: 'var(--pink)', opacity: 0.7 }} />
      <div>
        <p style={{ fontFamily: 'JetBrains Mono', color: 'var(--pink-soft)', fontSize: '1rem', marginBottom: '8px' }}>
          Macro Agent Not Running
        </p>
        <p className="text-muted" style={{ fontSize: '0.85rem', maxWidth: '420px', lineHeight: '1.6' }}>
          The LLM macro agent could not produce a signal. This usually means the Gemini API key
          is missing or the last pipeline run has not completed yet.
          Check Settings to verify your key, or force a run below.
        </p>
      </div>
      <button className="btn-primary" onClick={handleRetry} disabled={retrying}
        style={{ marginTop: '8px' }}>
        {retrying ? <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={14} />}
        {retrying ? 'Triggering pipeline...' : 'Trigger 1H Context Run'}
      </button>
      {economic_calendar?.events?.length > 0 && (
        <p style={{ fontSize: '0.8rem', color: 'var(--lime-dim)', fontFamily: 'JetBrains Mono' }}>
          Economic calendar data is available below.
        </p>
      )}
      <style>{`@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }`}</style>
    </div>
  );

  return (
    <div className="grid-layout">

      {/* LLM Reasoning Panel */}
      {hasError ? (
        <div className="col-span-12 animate-fade-in delay-1">
          <ErrorBanner />
        </div>
      ) : (
        <div className="data-panel col-span-12 animate-fade-in delay-1">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
            <h2>
              <BrainCircuit size={18} style={{ color: 'var(--pink)' }} /> LLM Macro Sentiment Reasoning
            </h2>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              {lastFetch && (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                  Updated {lastFetch.toLocaleTimeString()}
                </span>
              )}
              <button className="btn-primary" style={{ padding: '5px 12px', fontSize: '0.78rem' }} onClick={fetchMacro}>
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
          </div>

          {isLocal && (
            <div style={{ padding: '10px 14px', marginBottom: '16px', backgroundColor: 'rgba(240,192,64,0.08)', border: '1px solid rgba(240,192,64,0.3)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
              <ShieldAlert size={15} style={{ color: 'var(--plasma-amber)', flexShrink: 0 }} />
              <span style={{ color: 'var(--plasma-amber)', fontSize: '0.82rem', fontFamily: 'JetBrains Mono' }}>
                Running in Local Bypass Mode — Gemini API key missing or invalid. Macro signal is fallback only.
              </span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div style={{ display: 'flex', gap: '28px', marginBottom: '20px', flexWrap: 'wrap' }}>
                <div>
                  <p className="stat-label">Directional Bias</p>
                  <p style={{ fontFamily: 'JetBrains Mono', fontSize: '1.8rem', fontWeight: 700, color: signalColor, marginTop: '4px', textShadow: `0 0 12px ${signalColor}` }}>{signal}</p>
                </div>
                <div>
                  <p className="stat-label">Conviction Score</p>
                  <p style={{ fontFamily: 'JetBrains Mono', fontSize: '1.8rem', fontWeight: 700, color: 'var(--lime)', marginTop: '4px' }}>
                    {((news_signal?.conviction || 0) * 100).toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="stat-label">Impact Assessment</p>
                  <p style={{ fontFamily: 'JetBrains Mono', fontSize: '1.6rem', fontWeight: 700, color: 'var(--pink-soft)', marginTop: '4px' }}>
                    {(news_signal?.impact || 'UNKNOWN').replace(/_/g, ' ')}
                  </p>
                </div>
              </div>

              {news_signal?.quantitative_divergence_flag && (
                <div style={{ padding: '10px 14px', backgroundColor: 'rgba(240,111,160,0.08)', border: '1px solid var(--pink-deep)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <ShieldAlert size={14} style={{ color: 'var(--pink)', flexShrink: 0 }} />
                  <span style={{ color: 'var(--pink-soft)', fontSize: '0.82rem', fontFamily: 'JetBrains Mono' }}>
                    Quantitative Divergence — narrative conflicts with price action.
                  </span>
                </div>
              )}
            </div>

            <div style={{ flex: '2 1 380px', backgroundColor: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(184,245,66,0.08)' }}>
              <h3 style={{ fontSize: '0.78rem', color: 'var(--lime)', marginBottom: '10px', textTransform: 'uppercase', fontFamily: 'JetBrains Mono', letterSpacing: '0.1em' }}>
                Synthesized Narrative
              </h3>
              <p style={{ lineHeight: '1.65', color: 'rgba(239,240,232,0.9)', fontSize: '0.9rem', fontFamily: 'Space Grotesk' }}>
                {news_signal?.reasoning || 'No reasoning provided by LLM.'}
              </p>

              {news_signal?.macro_regime_label && (
                <div style={{ marginTop: '14px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                    Regime: <span style={{ color: 'var(--lime)' }}>{news_signal.macro_regime_label}</span>
                  </span>
                  {news_signal?.key_themes?.map((t, i) => (
                    <span key={i} style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '4px', background: 'rgba(184,245,66,0.08)', color: 'var(--lime-soft)', fontFamily: 'JetBrains Mono' }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Economic Calendar — always show if data exists */}
      <div className="data-panel col-span-12 animate-fade-in delay-2">
        <h2>
          <Calendar size={18} style={{ color: 'var(--lime)' }} /> Upcoming High-Impact Events
        </h2>

        {(!economic_calendar?.events || economic_calendar.events.length === 0) ? (
          <p className="text-muted" style={{ marginTop: '14px', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
            No high-impact events in the current window.
          </p>
        ) : (
          <div style={{ marginTop: '16px', overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                  {['Date / Time (Local)', 'Country', 'Event', 'Forecast', 'Previous'].map(col => (
                    <th key={col} style={{ padding: '12px', color: 'var(--lime)', borderBottom: '1px solid rgba(184,245,66,0.1)', fontWeight: 600, letterSpacing: '0.05em', fontSize: '0.78rem', textTransform: 'uppercase' }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {economic_calendar.events.map((evt, i) => {
                  const d = new Date(evt.date);
                  return (
                    <tr key={i} className="data-item" style={{ borderBottom: '1px solid rgba(184,245,66,0.04)' }}>
                      <td style={{ padding: '14px 12px', color: 'var(--text-main)' }}>
                        {d.toLocaleDateString()} <span className="text-muted">{d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </td>
                      <td style={{ padding: '14px 12px', fontWeight: 700, color: 'var(--pink-soft)' }}>{evt.country}</td>
                      <td style={{ padding: '14px 12px', color: 'var(--text-main)' }}>{evt.title}</td>
                      <td style={{ padding: '14px 12px', color: 'var(--lime-soft)' }}>{evt.forecast || '—'}</td>
                      <td style={{ padding: '14px 12px' }} className="text-muted">{evt.previous || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
