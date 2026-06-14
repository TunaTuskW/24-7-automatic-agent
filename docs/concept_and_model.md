# Concept and Model: v6.1.0 Multi-Asset Trading Terminal & Dynamic Conviction Edge OS

## Core Concept
The Macro Briefing Agent has evolved into a fully autonomous, multi-asset trading engine capable of processing mathematical models for an array of global assets, specifically: `SPX`, `BTC`, `GLD`, `WTI`, `NVDA`, `TSLA`, `DELL`, and `SPCE`. 

Unlike traditional trading systems that utilize static thresholds, v6.1.0 introduces the **Dynamic Conviction Edge OS**. This framework evaluates not only the direction of an asset but enforces extremely strict, mathematically optimal "edges" based on the underlying volatility and beta profile of that specific asset.

## 1. Dynamic Asset Conviction Edge
The Risk Engine (`src/engines/risk_engine.py`) has been overhauled to apply per-asset Kelly Criterion base thresholds:
- **Core Index (`spx`)**: `> 58%` win probability threshold.
- **Safe Havens (`gld`)**: `> 55%` win probability threshold (allowing for easier hedging rotation during macro weakness).
- **High Beta Tech & Crypto (`nvda`, `tsla`, `btc`)**: `> 60-62%` win probability threshold.
- **Extreme Beta (`spce`)**: `> 65%` win probability threshold.

If the neural network's `bull_probability` does not drastically exceed these base edges, the Kelly Allocator will return exactly `0.0`, sitting in cash rather than risking capital on low-conviction noise.

## 2. Auto-Inversion & Calibration Penalties
To counteract overfitted mean-reversion during strong directional trends, the system actively monitors the `Brier Score` (a measure of model calibration). 
If the Brier Score exceeds `0.60`, the Risk Engine triggers **Auto-Inversion** (`1.0 - prob`), recognizing that the neural network is completely misaligned with the current regime and actively fading its primary signal.

## 3. Multi-Asset Trading Terminal
The frontend React architecture has been entirely restructured. The outdated paper-trading lists have been replaced with a professional `TradingTerminal.jsx` interface. 
- Integrated `lightweight-charts` to provide highly performant, sub-millisecond rendering of OHLCV data.
- **Backtest / Live Toggle Integration:** Dynamic markers are overlaid directly on the chart, displaying precisely where the algorithm rotated capital in and out of different assets.

## 4. Algorithmic Outage Degradation
To prevent a single asset's data outage (e.g., Yahoo Finance failing to deliver `DELL` data) from crashing the pipeline, the `quantitative_backtester.py` and `fetch_market_data.py` pipelines wrap inference in isolated `try/except` blocks. If one asset's model fails, it defaults to a neutral `0.5` probability with `0.0` consensus, allowing the rest of the portfolio to continue trading uninterrupted.
