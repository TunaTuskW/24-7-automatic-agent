import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-panel" style={{ padding: '24px', textAlign: 'center', border: '1px solid rgba(192,53,90,0.3)', background: 'rgba(192,53,90,0.05)' }}>
          <AlertCircle size={48} style={{ color: 'var(--pink)', margin: '0 auto 16px' }} />
          <h3 style={{ color: 'var(--pink)', fontFamily: 'JetBrains Mono', marginBottom: '8px' }}>Component Crashed</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '16px' }}>
            {this.state.error?.message || "An unexpected rendering error occurred."}
          </p>
          <button 
            onClick={this.handleRetry}
            style={{
              background: 'rgba(184,245,66,0.1)',
              color: 'var(--lime)',
              border: '1px solid var(--lime-dim)',
              padding: '8px 16px',
              borderRadius: '4px',
              fontFamily: 'JetBrains Mono',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
