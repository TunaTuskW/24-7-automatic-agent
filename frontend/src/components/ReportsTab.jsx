import React, { useState, useEffect } from 'react';
import { Play, FileText, DownloadCloud, Activity, CheckCircle, Clock } from 'lucide-react';
import PipelineVisualizer from './PipelineVisualizer';

export default function ReportsTab() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState("");
  const [triggerStatus, setTriggerStatus] = useState(null);

  const fetchReports = async () => {
    try {
      const res = await fetch('/api/reports');
      if (res.ok) {
        const json = await res.json();
        setReports(json.reports || []);
        if (json.reports && json.reports.length > 0 && !selectedReport) {
          handleSelectReport(json.reports[0].filename);
        }
      }
    } catch (e) {
      console.error("Failed to fetch reports list", e);
    }
  };

  const handleSelectReport = async (filename) => {
    setSelectedReport(filename);
    setReportContent("Loading...");
    try {
      // The backend mounts the reports directory statically at /reports/
      const res = await fetch(`/reports/${filename}`);
      if (res.ok) {
        const text = await res.text();
        setReportContent(text);
      } else {
        setReportContent("Failed to load report content. It might have been deleted.");
      }
    } catch (e) {
      setReportContent("Error loading report.");
    }
  };

  const triggerJob = async (jobName) => {
    setTriggerStatus(`Dispatching ${jobName}...`);
    try {
      const res = await fetch('/api/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job: jobName })
      });
      if (res.ok) {
        setTriggerStatus(`✅ ${jobName} launched in background!`);
        setTimeout(() => setTriggerStatus(null), 4000);
      } else {
        setTriggerStatus(`❌ Failed to launch ${jobName}`);
      }
    } catch (e) {
      setTriggerStatus(`❌ Error launching ${jobName}`);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const formatSize = (bytes) => {
    return (bytes / 1024).toFixed(1) + ' KB';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
      
      {/* Control Panel */}
      <div className="glass-panel animate-fade-in delay-1" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}><Activity size={18} className="text-accent" /> Manual Execution Override</h3>
          <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>Force the pipeline to run out-of-band without waiting for the internal APScheduler.</p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          {triggerStatus && <span style={{ fontSize: '0.85rem', color: 'var(--success)' }}>{triggerStatus}</span>}
          
          <button 
            onClick={() => triggerJob('1h')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
          >
            <Play size={14} /> Run 1H Context
          </button>
          
          <button 
            onClick={() => triggerJob('1d')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
          >
            <Play size={14} /> Run 1D Execution
          </button>
          
          <button 
            onClick={() => triggerJob('1w')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--accent-blue)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 'bold' }}
          >
            <Play size={14} /> Run 1W & Weekly Synthesis
          </button>

          <button 
            onClick={() => triggerJob('test')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,100,100,0.2)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 'bold' }}
          >
            <Play size={14} /> Run Diagnostic Backtest
          </button>
        </div>
      </div>

      {/* Pipeline Visualizer */}
      <PipelineVisualizer />

      {/* Split Pane Viewer */}
      <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: '600px' }}>
        
        {/* Left Pane: File List */}
        <div className="glass-panel animate-fade-in delay-2" style={{ width: '300px', display: 'flex', flexDirection: 'column', padding: '16px 0' }}>
          <h3 style={{ padding: '0 16px 12px 16px', margin: 0, borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <DownloadCloud size={16} className="text-muted" /> Document Archive
          </h3>
          
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {reports.map((r, idx) => (
              <div 
                key={idx}
                onClick={() => handleSelectReport(r.filename)}
                style={{ 
                  padding: '12px 16px', 
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                  background: selectedReport === r.filename ? 'rgba(255,255,255,0.05)' : 'transparent',
                  borderLeft: selectedReport === r.filename ? '3px solid var(--accent-blue)' : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'background 0.2s'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <FileText size={14} className={selectedReport === r.filename ? "text-accent" : "text-muted"} />
                  <span style={{ fontSize: '0.85rem', fontWeight: selectedReport === r.filename ? 'bold' : 'normal', wordBreak: 'break-word' }}>
                    {r.filename.replace('updates/', '')}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', paddingLeft: '22px' }}>
                  <span>{formatSize(r.size)}</span>
                  <span>{new Date(r.mtime * 1000).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
            
            {reports.length === 0 && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                No reports found in the archive.
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Markdown Viewer */}
        <div className="glass-panel animate-fade-in delay-3" style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column' }}>
          {selectedReport ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <FileText size={24} className="text-accent" />
                <div>
                  <h2 style={{ margin: 0 }}>{selectedReport}</h2>
                  <span className="text-muted" style={{ fontSize: '0.85rem' }}>Raw Markdown Preview</span>
                </div>
              </div>
              
              <div style={{ flex: 1, overflowY: 'auto', background: 'rgba(0,0,0,0.2)', padding: '20px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <pre style={{ 
                  margin: 0, 
                  whiteSpace: 'pre-wrap', 
                  wordWrap: 'break-word', 
                  fontFamily: 'monospace', 
                  fontSize: '0.85rem',
                  color: '#e2e8f0',
                  lineHeight: '1.5'
                }}>
                  {reportContent}
                </pre>
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              Select a report from the archive to view.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
