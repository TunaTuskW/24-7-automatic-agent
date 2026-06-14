import React, { useState, useEffect, useRef } from 'react';
import { Activity, Database, BrainCircuit, ShieldAlert, Save, CheckCircle, Zap, Globe } from 'lucide-react';

export default function PipelineVisualizer() {
  const [logs, setLogs] = useState([]);
  const [activeComponent, setActiveComponent] = useState(null);
  const [activeMessage, setActiveMessage] = useState("");
  const wsRef = useRef(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/pipeline`;
    
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs(prev => [...prev, data].slice(-20)); // Keep last 20 logs for brief display
        
        setActiveComponent(data.component);
        setActiveMessage(data.message);

        if (data.message && data.message.includes("Complete")) {
            setActiveComponent("complete");
        }
      } catch (e) {
        console.error("WS Parse Error", e);
      }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const isActive = (components) => {
    if (activeComponent === "complete") return false;
    return components.includes(activeComponent);
  };

  const isComplete = activeComponent === "complete";

  const Node = ({ id, label, icon: Icon, components, delay = "0s", highlightColor = "#00f0ff" }) => {
    const active = isActive(components) || (isComplete && id === 'complete');
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', zIndex: 2,
        transition: 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
        transform: active ? 'scale(1.15)' : 'scale(1)',
        opacity: active ? 1 : 0.7,
        animation: active ? `pulse 1.5s infinite alternate ${delay}` : 'none'
      }}>
        <div style={{
          width: '54px', height: '54px', borderRadius: '12px',
          background: active ? `rgba(0,0,0,0.8)` : 'rgba(255,255,255,0.05)',
          border: `2px solid ${active ? highlightColor : 'rgba(255,255,255,0.1)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: active ? `0 0 25px ${highlightColor}80, inset 0 0 10px ${highlightColor}40` : '0 4px 6px rgba(0,0,0,0.1)',
          color: active ? highlightColor : '#aaa'
        }}>
          <Icon size={24} />
        </div>
        <span style={{ fontSize: '0.75rem', fontWeight: active ? 'bold' : 'normal', color: active ? '#fff' : '#888', textShadow: active ? `0 0 5px ${highlightColor}` : 'none' }}>
          {label}
        </span>
      </div>
    );
  };

  return (
    <div style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
      <h3 style={{ margin: '0 0 20px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Activity className="text-accent" size={18} /> Process Graph Visualizer
      </h3>

      {/* Graph Area */}
      <div style={{ position: 'relative', width: '100%', maxWidth: '800px', margin: '0 auto', height: '360px' }}>
        
        {/* SVG Connectors */}
        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 1, pointerEvents: 'none' }}>
          <defs>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(255,255,255,0.1)" />
              <stop offset="100%" stopColor="rgba(0,240,255,0.4)" />
            </linearGradient>
          </defs>

          {/* Lines */}
          <path d="M400,40 L400,90" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          
          <path d="M400,90 L250,90 L250,110" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          <path d="M400,90 L550,90 L550,110" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          
          <path d="M250,150 L250,190 L400,190 L400,210" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          <path d="M550,150 L550,190 L400,190 L400,210" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />

          <path d="M400,250 L400,280" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          <path d="M400,280 L300,280 L300,300" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
          <path d="M400,280 L500,280 L500,300" stroke="url(#lineGrad)" strokeWidth="2" fill="none" />
        </svg>

        {/* Nodes Positioning */}
        <div style={{ position: 'absolute', top: '0px', left: '50%', transform: 'translateX(-50%)' }}>
          <Node id="trigger" label="Conductor" icon={Zap} components={['conductor']} highlightColor="#ffd700" />
        </div>

        <div style={{ position: 'absolute', top: '100px', left: '250px', transform: 'translateX(-50%)' }}>
          <Node id="ingest1" label="Data Ingestion" icon={Database} components={['yahoo-adapter', 'forexfactory-adapter', 'economic-calendar']} />
        </div>

        <div style={{ position: 'absolute', top: '100px', left: '550px', transform: 'translateX(-50%)' }}>
          <Node id="inference1" label="State Filters" icon={BrainCircuit} components={['hmm-engine', 'kalman-filter']} highlightColor="#bd00ff" />
        </div>

        <div style={{ position: 'absolute', top: '200px', left: '50%', transform: 'translateX(-50%)' }}>
          <Node id="inference" label="AI Consensus" icon={Activity} components={['gemini-adapter', 'consensus-engine']} highlightColor="#00f0ff" />
        </div>

        <div style={{ position: 'absolute', top: '290px', left: '300px', transform: 'translateX(-50%)' }}>
          <Node id="risk" label="Risk Engine" icon={ShieldAlert} components={['risk-engine']} highlightColor="#ff4444" />
        </div>
        
        <div style={{ position: 'absolute', top: '290px', left: '500px', transform: 'translateX(-50%)' }}>
          <Node id="lake" label="Data Lake" icon={Save} components={['lake-manager']} highlightColor="#00ff00" />
        </div>

        {/* Floating Active State Message Box */}
        {activeComponent && activeComponent !== 'complete' && (
          <div style={{
            position: 'absolute', bottom: '0px', left: '50%', transform: 'translateX(-50%)',
            background: 'rgba(0,0,0,0.85)', padding: '10px 20px', borderRadius: '20px',
            border: '1px solid var(--accent-blue)', color: 'var(--text-bright)',
            fontSize: '0.8rem', whiteSpace: 'nowrap', boxShadow: '0 4px 20px rgba(0, 240, 255, 0.3)',
            zIndex: 10, display: 'flex', alignItems: 'center', gap: '8px',
            animation: 'slide-up 0.3s ease-out'
          }}>
            <Activity size={14} className="text-accent" style={{ animation: 'spin 2s linear infinite' }} />
            <span style={{ color: '#ffb86c' }}>[{activeComponent}]</span> {activeMessage}
          </div>
        )}
      </div>
      
      <div style={{ marginTop: '20px', padding: '12px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.75rem', color: '#aaa', maxHeight: '150px', overflowY: 'auto' }}>
        {logs.map((log, i) => (
          <div key={i} style={{ marginBottom: '4px' }}>
            <span style={{ color: '#555' }}>{log.timestamp}</span>{' '}
            <span style={{ color: log.level === 'ERROR' ? '#ff4444' : log.level === 'WARNING' ? '#ffb86c' : '#00f0ff' }}>[{log.component}]</span>{' '}
            {log.message}
          </div>
        ))}
      </div>
    </div>
  );
}
