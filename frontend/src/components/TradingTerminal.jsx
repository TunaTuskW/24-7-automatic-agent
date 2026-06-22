import React, { useEffect, useState } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';

const ALL_TICKERS = ["SPX", "BTC", "GLD", "WTI", "NVDA", "TSLA", "DELL", "SPCE"];

const getSymbol = (ticker) => {
    const map = {
        "SPX": "AMEX:SPY",
        "BTC": "OKX:BTCUSDT",
        "GLD": "OKX:XAUTUSDT",
        "WTI": "OKX:CLUSDT.P",
        "NVDA": "NASDAQ:NVDA",
        "TSLA": "NASDAQ:TSLA",
        "DELL": "NYSE:DELL",
        "SPCE": "OKX:SPCXUSDT.P"
    };
    return map[ticker] || `NASDAQ:${ticker}`;
};

const TradingTerminal = () => {
    const [activeTickers, setActiveTickers] = useState([]);
    const [selectedTicker, setSelectedTicker] = useState("SPX");
    const [interval, setInterval] = useState("D"); // Default to D for TradingView
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
        // Fetch portfolio separately since chartData fetch is gone
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
                        }
                    }
                })
                .catch(console.error);
    }, [viewType]);

    return (
        <div className="terminal-container" style={{ display: 'flex', gap: '24px' }}>
            {/* Sidebar Controls (Tier 2) */}
            <div className="data-panel terminal-sidebar" style={{ width: '250px' }}>
                <h2>[ ACTIVE ASSETS ]</h2>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {ALL_TICKERS.map(ticker => {
                        const isActive = activeTickers.includes(ticker);
                        return (
                            <div key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', background: selectedTicker === ticker ? 'var(--bg-hover)' : 'var(--bg-panel)', border: selectedTicker === ticker ? '1px solid var(--term-cyan)' : '1px solid var(--border-color)', cursor: 'pointer' }} onClick={() => setSelectedTicker(ticker)}>
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
                                        backgroundColor: isActive ? 'var(--term-cyan)' : 'var(--border-color)'
                                    }}>
                                        <span style={{
                                            position: 'absolute', content: '""', height: '14px', width: '14px', left: '3px', bottom: '3px',
                                            backgroundColor: 'var(--bg-color)',
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <h2>{selectedTicker} / USD</h2>
                        <div style={{ display: 'flex', gap: '4px' }}>
                            {/* We defer timeframe control to the AdvancedChart itself, but we can keep standard ones for aesthetics if desired, but actually we should just let TradingView handle it. */}
                        </div>
                    </div>
                </div>
                
                {/* AdvancedChart Container */}
                <div style={{ flex: 1, minHeight: '600px', marginBottom: '20px', borderRadius: '4px', overflow: 'hidden' }}>
                    <AdvancedRealTimeChart 
                        theme="dark"
                        symbol={getSymbol(selectedTicker)}
                        allow_symbol_change={true}
                        interval="D"
                        timezone="Etc/UTC"
                        style="1"
                        locale="en"
                        enable_publishing={false}
                        hide_top_toolbar={false}
                        hide_legend={false}
                        save_image={false}
                        autosize={true}
                    />
                </div>

                {/* Positions & Ledger Section */}
                <div className="data-panel">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h2>[ ACTIVE POSITIONS & STATS ]</h2>
                        <div style={{ display: 'flex', gap: '24px' }}>
                            <span>EQUITY: <b className="text-cyan">${portfolio.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</b></span>
                            <span>WIN RATE: <b className="text-cyan">{(portfolio.win_rate * 100).toFixed(1)}%</b></span>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px', marginBottom: '16px' }}>
                        {Object.keys(portfolio.positions || {}).map(pos => {
                            if (pos === "cash") return null;
                            const amt = portfolio.positions[pos];
                            if (amt === 0) return null;
                            return (
                                <div key={pos} style={{ background: 'var(--bg-hover)', padding: '8px', border: '1px solid var(--border-color)', borderLeft: '2px solid var(--term-cyan)' }}>
                                    <div className="stat-label">{pos} Position</div>
                                    <div className="stat-value" style={{ color: amt > 0 ? 'var(--term-green)' : 'var(--term-red)' }}>{amt.toFixed(4)}</div>
                                </div>
                            );
                        })}
                    </div>

                    <h2>[ MOCK EXECUTION LEDGER ]</h2>
                    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        <table>
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Action</th>
                                    <th>Ticker</th>
                                    <th>Price</th>
                                    <th>Value</th>
                                    <th>Stats</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ledger.slice(0, 50).map((row, i) => (
                                    <tr key={i} className="table-row-item">
                                        <td className="text-muted">{row.timestamp}</td>
                                        <td className={row.action === 'BUY' ? 'text-green' : 'text-red'}>{row.action}</td>
                                        <td className="text-bright">{row.ticker}</td>
                                        <td>${row.price}</td>
                                        <td className="text-main">${row.value}</td>
                                        <td className="text-muted">{row.stats || '-'}</td>
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
