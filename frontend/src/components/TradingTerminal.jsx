import React, { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';
import { Activity } from 'lucide-react';

const ALL_TICKERS = ["SPX", "BTC", "GLD", "WTI", "NVDA", "TSLA", "DELL", "SPCE"];

const TradingTerminal = () => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const markersRef = useRef([]);

    const [activeTickers, setActiveTickers] = useState([]);
    const [selectedTicker, setSelectedTicker] = useState("SPX");
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [portfolio, setPortfolio] = useState({ equity: 100000, positions: {}, win_rate: 0 });
    const [ledger, setLedger] = useState([]);
    const [viewType, setViewType] = useState('backtest');

    useEffect(() => {
        fetch('/api/trading_settings')
            .then(r => r.json())
            .then(data => {
                if (data && data.active_tickers) {
                    setActiveTickers(data.active_tickers.map(t => t.toUpperCase()));
                }
            });
    }, []);

    const toggleTicker = async (ticker) => {
        let newTickers;
        if (activeTickers.includes(ticker)) {
            newTickers = activeTickers.filter(t => t !== ticker);
        } else {
            newTickers = [...activeTickers, ticker];
        }
        setActiveTickers(newTickers);

        await fetch('/api/trading_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active_tickers: newTickers.map(t => t.toLowerCase()) })
        });
    };

    useEffect(() => {
        setLoading(true);
        fetch(`/api/chart/${selectedTicker}`)
            .then(r => r.json())
            .then(data => {
                if (data && data.data) {
                    setChartData(data.data);
                }
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, [selectedTicker]);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { color: 'transparent' },
                textColor: 'rgba(255, 255, 255, 0.9)',
                fontFamily: 'JetBrains Mono, monospace',
            },
            grid: {
                vertLines: { color: 'rgba(0, 255, 224, 0.05)' },
                horzLines: { color: 'rgba(0, 255, 224, 0.05)' },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
            },
            width: chartContainerRef.current.clientWidth,
            height: 600,
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: '#00ff88',
            downColor: '#ff2d55',
            borderVisible: false,
            wickUpColor: '#00ff88',
            wickDownColor: '#ff2d55',
        });

        chartRef.current = chart;
        seriesRef.current = candleSeries;

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    useEffect(() => {
        if (seriesRef.current && chartData.length > 0) {
            seriesRef.current.setData(chartData);
            
            fetch(`/api/portfolio?type=${viewType}`)
                .then(r => r.json())
                .then(data => {
                    if (data) {
                        if (data.portfolio) {
                            setPortfolio({
                                equity: data.portfolio.total_equity || data.portfolio.equity || 100000,
                                positions: data.portfolio.positions || {},
                                win_rate: data.portfolio.win_rate || 0
                            });
                        }
                        if (data.ledger) {
                            setLedger(data.ledger);
                            const markers = [];
                            data.ledger.forEach(row => {
                                if (row.ticker && row.ticker.toUpperCase() === selectedTicker) {
                                    const timeMatch = chartData.find(d => row.timestamp && String(row.timestamp).includes(d.time));
                                    if (timeMatch) {
                                        markers.push({
                                            time: timeMatch.time,
                                            position: row.action === 'BUY' ? 'belowBar' : 'aboveBar',
                                            color: row.action === 'BUY' ? '#00ff88' : '#ff2d55',
                                            shape: row.action === 'BUY' ? 'arrowUp' : 'arrowDown',
                                            text: row.action
                                        });
                                    }
                                }
                            });
                            if (markers.length > 0) {
                                markers.sort((a, b) => new Date(a.time) - new Date(b.time));
                                const uniqueMarkers = [];
                                const seenTimes = new Set();
                                markers.forEach(m => {
                                    if (!seenTimes.has(m.time)) {
                                        seenTimes.add(m.time);
                                        uniqueMarkers.push(m);
                                    }
                                });
                                seriesRef.current.setMarkers(uniqueMarkers);
                            } else {
                                seriesRef.current.setMarkers([]);
                            }
                        }
                    }
                });
        }
    }, [chartData, selectedTicker]);

    return (
        <div className="terminal-container" style={{ display: 'flex', gap: '24px' }}>
            {/* Sidebar Controls (Tier 2) */}
            <div className="data-panel terminal-sidebar" style={{ width: '250px' }}>
                <h2 style={{ margin: '0 0 20px 0', fontSize: '1rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Activity size={18} className="text-plasma-cyan" /> Active Assets
                </h2>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {ALL_TICKERS.map(ticker => {
                        const isActive = activeTickers.includes(ticker);
                        return (
                            <div key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px', background: selectedTicker === ticker ? 'rgba(0,255,224,0.08)' : 'rgba(255,255,255,0.03)', borderRadius: '8px', cursor: 'pointer', border: selectedTicker === ticker ? '1px solid var(--plasma-cyan)' : '1px solid transparent', transition: 'all 0.2s' }} onClick={() => setSelectedTicker(ticker)}>
                                <span style={{ fontWeight: '600', color: selectedTicker === ticker ? '#fff' : 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>{ticker}</span>
                                
                                <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '34px', height: '20px' }}>
                                    <input 
                                        type="checkbox" 
                                        checked={isActive} 
                                        onChange={(e) => {
                                            e.stopPropagation();
                                            toggleTicker(ticker);
                                        }}
                                        style={{ opacity: 0, width: 0, height: 0 }} 
                                    />
                                    <span style={{ 
                                        position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0, 
                                        backgroundColor: isActive ? 'var(--plasma-cyan)' : '#333', 
                                        transition: '.4s', borderRadius: '34px' 
                                    }}>
                                        <span style={{
                                            position: 'absolute', content: '""', height: '14px', width: '14px', left: '3px', bottom: '3px',
                                            backgroundColor: 'var(--void)', transition: '.4s', borderRadius: '50%',
                                            transform: isActive ? 'translateX(14px)' : 'translateX(0)'
                                        }}></span>
                                    </span>
                                </label>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Main Chart Area (Tier 3) */}
            <div className="chart-panel terminal-main" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold' }}>{selectedTicker} / USD</h2>
                        <span style={{ padding: '4px 8px', borderRadius: '4px', background: 'rgba(0,255,224,0.1)', fontSize: '0.85rem', color: 'var(--plasma-cyan)', fontFamily: 'JetBrains Mono' }}>1D</span>
                    </div>
                    {loading && <div style={{ color: 'var(--plasma-cyan)', fontSize: '0.9rem', fontFamily: 'JetBrains Mono' }}>Loading Telemetry...</div>}
                </div>
                
                {/* Lightweight Charts Container */}
                <div ref={chartContainerRef} style={{ flex: 1, minHeight: '500px', overflow: 'hidden', marginBottom: '20px' }} />

                {/* Positions & Ledger Section */}
                <div className="data-panel" style={{ padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Active Positions & Stats</h3>
                        <div style={{ display: 'flex', gap: '24px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                            <span style={{ fontFamily: 'JetBrains Mono' }}>Equity: <b className="text-plasma-cyan">${portfolio.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</b></span>
                            <span style={{ fontFamily: 'JetBrains Mono' }}>Win Rate: <b className="text-plasma-cyan">{(portfolio.win_rate * 100).toFixed(1)}%</b></span>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '24px' }}>
                        {Object.keys(portfolio.positions || {}).map(pos => {
                            if (pos === "cash") return null;
                            const amt = portfolio.positions[pos];
                            if (amt === 0) return null;
                            return (
                                <div key={pos} style={{ background: 'rgba(0,255,224,0.05)', padding: '12px', borderLeft: '2px solid var(--plasma-cyan)' }}>
                                    <div className="stat-label">{pos} Position</div>
                                    <div className="stat-value" style={{ fontSize: '1.5rem', color: amt > 0 ? 'var(--plasma-green)' : 'var(--plasma-red)' }}>{amt.toFixed(4)}</div>
                                </div>
                            );
                        })}
                    </div>

                    <h4 style={{ margin: '0 0 12px 0', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Mock Execution Ledger</h4>
                    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.9rem', fontFamily: 'JetBrains Mono' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid rgba(0,255,224,0.1)' }}>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Time</th>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Action</th>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Ticker</th>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Price</th>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Value</th>
                                    <th style={{ padding: '8px', color: 'var(--text-muted)' }}>Stats</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ledger.slice(0, 50).map((row, i) => (
                                    <tr key={i} className="data-item">
                                        <td style={{ padding: '8px' }}>{row.timestamp}</td>
                                        <td style={{ padding: '8px', color: row.action === 'BUY' ? 'var(--plasma-green)' : 'var(--plasma-red)', fontWeight: 'bold' }}>{row.action}</td>
                                        <td style={{ padding: '8px' }}>{row.ticker}</td>
                                        <td style={{ padding: '8px' }}>${row.price}</td>
                                        <td style={{ padding: '8px' }}>${row.value}</td>
                                        <td style={{ padding: '8px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{row.stats || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TradingTerminal;
