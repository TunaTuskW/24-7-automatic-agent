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
        // Fetch trading settings
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
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
            },
            width: chartContainerRef.current.clientWidth,
            height: 600,
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: '#4CAF50',
            downColor: '#FF5252',
            borderVisible: false,
            wickUpColor: '#4CAF50',
            wickDownColor: '#FF5252',
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
            
            // Mocking markers for buy/sell based on backtest ledger
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
                                            color: row.action === 'BUY' ? '#4CAF50' : '#FF5252',
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
        <div className="terminal-container" style={{ display: 'flex', gap: '24px', animation: 'fadeIn 0.4s ease-out' }}>
            {/* Sidebar Controls */}
            <div className="terminal-sidebar" style={{ width: '250px', background: 'rgba(255,255,255,0.02)', padding: '20px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <h3 style={{ margin: '0 0 20px 0', fontSize: '1rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Activity size={18} /> Active Assets
                </h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {ALL_TICKERS.map(ticker => {
                        const isActive = activeTickers.includes(ticker);
                        return (
                            <div key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px', background: selectedTicker === ticker ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)', borderRadius: '8px', cursor: 'pointer', border: selectedTicker === ticker ? '1px solid var(--accent-blue)' : '1px solid transparent', transition: 'all 0.2s' }} onClick={() => setSelectedTicker(ticker)}>
                                <span style={{ fontWeight: '600', color: selectedTicker === ticker ? '#fff' : 'var(--text-muted)' }}>{ticker}</span>
                                
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
                                        backgroundColor: isActive ? 'var(--accent-blue)' : '#333', 
                                        transition: '.4s', borderRadius: '34px' 
                                    }}>
                                        <span style={{
                                            position: 'absolute', content: '""', height: '14px', width: '14px', left: '3px', bottom: '3px',
                                            backgroundColor: 'white', transition: '.4s', borderRadius: '50%',
                                            transform: isActive ? 'translateX(14px)' : 'translateX(0)'
                                        }}></span>
                                    </span>
                                </label>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Main Chart Area */}
            <div className="terminal-main" style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold' }}>{selectedTicker} / USD</h2>
                        <span style={{ padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.1)', fontSize: '0.85rem' }}>1D</span>
                    </div>
                    {loading && <div style={{ color: 'var(--accent-blue)', fontSize: '0.9rem' }}>Loading Chart Data...</div>}
                </div>
                
                {/* Lightweight Charts Container */}
                <div ref={chartContainerRef} style={{ flex: 1, minHeight: '500px', borderRadius: '8px', overflow: 'hidden', marginBottom: '20px' }} />

                {/* Positions & Ledger Section */}
                <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '600' }}>Active Positions & Stats</h3>
                        <div style={{ display: 'flex', gap: '16px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                            <span>Equity: <b style={{color: '#fff'}}>${portfolio.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</b></span>
                            <span>Win Rate: <b style={{color: '#fff'}}>{(portfolio.win_rate * 100).toFixed(1)}%</b></span>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
                        {Object.keys(portfolio.positions || {}).map(pos => {
                            if (pos === "cash") return null;
                            const amt = portfolio.positions[pos];
                            if (amt === 0) return null;
                            return (
                                <div key={pos} style={{ background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '8px' }}>
                                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{pos} Position</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: amt > 0 ? '#4CAF50' : '#FF5252' }}>{amt.toFixed(4)}</div>
                                </div>
                            );
                        })}
                    </div>

                    <h4 style={{ margin: '0 0 12px 0', fontSize: '1rem', color: 'var(--text-muted)' }}>Mock Execution Ledger</h4>
                    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
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
                                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                        <td style={{ padding: '8px' }}>{row.timestamp}</td>
                                        <td style={{ padding: '8px', color: row.action === 'BUY' ? '#4CAF50' : '#FF5252', fontWeight: 'bold' }}>{row.action}</td>
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
