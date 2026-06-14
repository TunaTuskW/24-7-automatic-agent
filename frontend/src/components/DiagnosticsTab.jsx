import React, { useState, useEffect, useRef } from 'react';
import { Terminal, RefreshCw } from 'lucide-react';

export default function DiagnosticsTab() {
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
      case 'ERROR': return 'var(--warning)';
      case 'WARNING': return '#f39c12';
      case 'INFO': return 'var(--accent-blue)';
      default: return 'var(--text-muted)';
    }
  };

  return (
    <div className="grid-layout">
      <div className="glass-panel col-span-12 animate-fade-in delay-1" style={{ display: 'flex', flexDirection: 'column', height: '70vh' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Terminal size={20} className="text-muted" /> System Diagnostics Console
          </h2>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={isAutoScroll} 
                onChange={(e) => setIsAutoScroll(e.target.checked)} 
              />
              Auto-scroll
            </label>
            <button onClick={fetchLogs} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        <div style={{ 
          flex: 1, 
          backgroundColor: '#000', 
          borderRadius: '8px', 
          padding: '16px', 
          overflowY: 'auto', 
          fontFamily: 'monospace', 
          fontSize: '0.85rem',
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: 'inset 0 0 20px rgba(0,0,0,0.8)'
        }}>
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>Awaiting system events...</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} style={{ marginBottom: '6px', lineHeight: '1.4', display: 'flex', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {new Date(log.timestamp).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}
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
