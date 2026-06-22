import { formatTimeToggle } from "../utils/timeFormatter";
import React, { useState, useEffect, useRef } from 'react';

export default function DiagnosticsTab({ timeZone }) {
  const [logs, setLogs] = useState([]);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const terminalEndRef = useRef(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/logs');
      if (res.ok) {
        const json = await res.json();
        setLogs(json.logs || []);
      }
    } catch (e) {
      console.error("Failed to fetch logs");
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000); // 5 sec poll
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isAutoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, isAutoScroll]);

  const getLogColor = (level) => {
    switch (level) {
      case 'ERROR': return 'var(--plasma-red)';
      case 'WARNING': return 'var(--plasma-amber)';
      case 'INFO': return 'var(--plasma-cyan)';
      default: return 'var(--text-muted)';
    }
  };

  return (
    <div className="grid-layout">
      <div className="data-panel col-span-12 animate-fade-in delay-1" style={{ display: 'flex', flexDirection: 'column', height: '70vh' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
             System Diagnostics Console
          </h2>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', fontFamily: 'JetBrains Mono' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer', color: 'var(--plasma-cyan)' }}>
              <input 
                type="checkbox" 
                checked={isAutoScroll} 
                onChange={(e) => setIsAutoScroll(e.target.checked)} 
                style={{ accentColor: 'var(--plasma-cyan)' }}
              />
              Auto-scroll
            </label>
            <button onClick={fetchLogs} style={{ background: 'transparent', border: 'none', color: 'var(--plasma-cyan)', cursor: 'pointer' }}>
              
            </button>
          </div>
        </div>

        <div style={{ 
          flex: 1, 
          backgroundColor: 'var(--void)', 
          borderRadius: '8px', 
          padding: '16px', 
          overflowY: 'auto', 
          fontFamily: 'JetBrains Mono, monospace', 
          fontSize: '0.85rem',
          border: '1px solid var(--glass-border)',
          boxShadow: 'inset 0 0 20px rgba(0,255,224,0.02)'
        }}>
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>Awaiting system events...</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="terminal-log" style={{ display: 'flex', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {formatTimeToggle(log.timestamp, timeZone, false)}
                </span>
                <span style={{ color: getLogColor(log.level), width: '60px', fontWeight: 'bold' }}>
                  {log.level}
                </span>
                <span style={{ color: 'var(--text-muted)', width: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  [{log.component}]
                </span>
                <span style={{ color: 'rgba(255,255,255,0.9)', wordBreak: 'break-all' }}>
                  {log.message}
                </span>
              </div>
            ))
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
}
