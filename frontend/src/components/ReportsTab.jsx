import React, { useState, useEffect } from 'react';
import { Play, FileText, DownloadCloud, Activity, CheckCircle, XCircle, Loader } from 'lucide-react';
import PipelineVisualizer from './PipelineVisualizer';
import ErrorBoundary from './ErrorBoundary';
import { apiPost } from '../App';

export default function ReportsTab() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState('');
  const [triggerStatus, setTriggerStatus] = useState(null); // null | {type, msg}

  const fetchReports = async () => {
    try {
      const res = await fetch('/api/reports');
      if (res.ok) {
        const json = await res.json();
        const list = json.reports || [];
        setReports(list);
        if (list.length > 0 && !selectedReport) {
          handleSelectReport(list[0].filename);
        }
      }
    } catch (e) {
      console.error('Failed to fetch reports list', e);
    }
  };

  const handleSelectReport = async (filename) => {
    setSelectedReport(filename);
    setReportContent('Loading...');
    try {
      const res = await fetch(`/reports/${filename}`);
      if (res.ok) {
        setReportContent(await res.text());
      } else {
        setReportContent('Failed to load report — file may have been deleted.');
      }
    } catch (e) {
      setReportContent('Error loading report.');
    }
  };

  const triggerJob = async (jobName) => {
    setTriggerStatus({ type: 'loading', msg: `Dispatching ${jobName}...` });
    try {
      const res = await apiPost('/api/trigger', { job: jobName });
      if (res.ok) {
        setTriggerStatus({ type: 'ok', msg: `${jobName} launched in background — check Diagnostics for output.` });
        setTimeout(() => setTriggerStatus(null), 6000);
      } else {
        const body = await res.json().catch(() => ({}));
        setTriggerStatus({ type: 'err', msg: `Failed: ${body.detail || res.status}` });
        setTimeout(() => setTriggerStatus(null), 6000);
      }
    } catch (e) {
      setTriggerStatus({ type: 'err', msg: `Network error: ${e.message}` });
      setTimeout(() => setTriggerStatus(null), 6000);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const formatSize = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

  const statusIcon = () => {
    if (!triggerStatus) return null;
    if (triggerStatus.type === 'loading') return <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />;
    if (triggerStatus.type === 'ok') return <CheckCircle size={14} />;
    return <XCircle size={14} />;
  };

  const statusColor = () => {
    if (!triggerStatus) return 'var(--lime)';
    if (triggerStatus.type === 'err') return 'var(--pink)';
    return 'var(--lime)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>

      {/* Control Panel */}
      <div className="glass-panel animate-fade-in delay-1" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0, fontSize: '0.95rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            <Activity size={16} style={{ color: 'var(--lime)' }} /> Manual Execution Override
          </h3>
          <p className="text-muted" style={{ margin: '6px 0 0 0', fontSize: '0.82rem' }}>
            Force the pipeline to run out-of-band without waiting for the internal APScheduler.
          </p>
          {triggerStatus && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px', fontSize: '0.82rem', fontFamily: 'JetBrains Mono', color: statusColor() }}>
              {statusIcon()}
              {triggerStatus.msg}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button className="btn-primary" onClick={() => triggerJob('1h')}>
            <Play size={13} /> Run 1H Context
          </button>
          <button className="btn-primary" onClick={() => triggerJob('1d')}>
            <Play size={13} /> Run 1D Execution
          </button>
          <button className="btn-primary" onClick={() => triggerJob('1w')}
            style={{ background: 'rgba(184,245,66,0.14)', borderColor: 'var(--lime)' }}>
            <Play size={13} /> Run 1W + Weekly Synthesis
          </button>
          <button className="btn-danger" onClick={() => triggerJob('test')}>
            <Play size={13} /> Run Diagnostic Backtest
          </button>
        </div>
      </div>

      {/* Pipeline Visualizer */}
      <ErrorBoundary>
        <PipelineVisualizer />
      </ErrorBoundary>

      {/* Split Pane */}
      <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: '600px' }}>

        {/* File List */}
        <div className="glass-panel animate-fade-in delay-2" style={{ width: '290px', display: 'flex', flexDirection: 'column', padding: '14px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px 12px 14px', borderBottom: '1px solid rgba(184,245,66,0.06)' }}>
            <h3 style={{ margin: 0, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              <DownloadCloud size={14} style={{ color: 'var(--text-muted)' }} /> Archive
            </h3>
            <button onClick={fetchReports} style={{ background: 'none', border: 'none', color: 'var(--lime-dim)', cursor: 'pointer', fontSize: '0.78rem', fontFamily: 'JetBrains Mono' }}>
              refresh
            </button>
          </div>

          <div style={{ overflowY: 'auto', flex: 1 }}>
            {reports.map((r, idx) => (
              <div
                key={idx}
                onClick={() => handleSelectReport(r.filename)}
                style={{
                  padding: '11px 14px',
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                  background: selectedReport === r.filename ? 'rgba(184,245,66,0.06)' : 'transparent',
                  borderLeft: selectedReport === r.filename ? '3px solid var(--lime)' : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'background 0.2s'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                  <FileText size={13} style={{ color: selectedReport === r.filename ? 'var(--lime)' : 'var(--text-muted)', flexShrink: 0 }} />
                  <span style={{ fontSize: '0.8rem', fontFamily: 'JetBrains Mono', wordBreak: 'break-word', color: selectedReport === r.filename ? 'var(--lime-soft)' : 'var(--text-main)' }}>
                    {r.filename.replace('updates/', '')}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)', paddingLeft: '21px' }}>
                  <span>{formatSize(r.size)}</span>
                  <span>{new Date(r.mtime * 1000).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
            {reports.length === 0 && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem', fontFamily: 'JetBrains Mono' }}>
                No reports in archive.
              </div>
            )}
          </div>
        </div>

        {/* Markdown Viewer */}
        <div className="glass-panel animate-fade-in delay-3" style={{ flex: 1, padding: '22px', display: 'flex', flexDirection: 'column' }}>
          {selectedReport ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '18px', paddingBottom: '14px', borderBottom: '1px solid rgba(184,245,66,0.08)' }}>
                <FileText size={20} style={{ color: 'var(--lime)' }} />
                <div>
                  <h2 style={{ margin: 0, fontSize: '0.9rem' }}>{selectedReport}</h2>
                  <span className="text-muted" style={{ fontSize: '0.78rem' }}>Raw Markdown Preview</span>
                </div>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', background: 'rgba(0,0,0,0.25)', padding: '18px', borderRadius: '8px', border: '1px solid rgba(184,245,66,0.06)' }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem', color: '#dde5cc', lineHeight: '1.55' }}>
                  {reportContent}
                </pre>
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
              Select a report from the archive.
            </div>
          )}
        </div>

      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
