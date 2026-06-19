# Concept and Model: v6.3.0 Multi-Asset Trading Terminal & Dynamic Conviction Edge OS

## Core Concept
The Macro Briefing Agent has evolved into a fully autonomous, multi-asset trading engine capable of processing mathematical models for an array of global assets, specifically: `SPX`, `BTC`, `GLD`, `WTI`, `NVDA`, `TSLA`, `DELL`, and `SPCE`. 

Unlike traditional trading systems that utilize static thresholds, v6.3.0 introduces the **Dynamic Conviction Edge OS**. This framework evaluates not only the direction of an asset but enforces extremely strict, mathematically optimal "edges" based on the underlying volatility and beta profile of that specific asset.

## 1. Dynamic Asset Conviction Edge
The Risk Engine ([src/engines/risk_engine.py](file:///Users/mac/agent/src/engines/risk_engine.py)) has been overhauled to apply per-asset Kelly Criterion base thresholds:
- **Core Index (`spx`)**: `> 50%` win probability threshold (lowered to maximize participation in strong regimes).
- **Safe Havens / Cryptos / Commodities**:
  - `btc`: `> 52%` win probability threshold.
  - `gld`: `> 52%` win probability threshold.
  - `wti`: `> 54%` win probability threshold.
- **Single-Name Tech / Extreme Beta**:
  - `nvda`: `> 53%` win probability threshold.
  - `tsla`: `> 56%` win probability threshold.
  - `dell`: `> 55%` win probability threshold.
  - `spce`: `> 72%` win probability threshold (extremely strict to filter out speculative noise).

If the neural network's `bull_probability` does not drastically exceed these base edges, the Kelly Allocator will return exactly `0.0`, sitting in cash rather than risking capital on low-conviction noise.

## 2. Auto-Inversion & Calibration Penalties
To counteract overfitted mean-reversion during strong directional trends, the system actively monitors the `Brier Score` (a measure of model calibration). 
If the Brier Score exceeds `0.60`, the Risk Engine triggers **Auto-Inversion** (`1.0 - prob`), recognizing that the neural network is completely misaligned with the current regime and actively fading its primary signal.

## 3. Multi-Asset Trading Terminal & Short Leg Execution
The frontend React architecture has been entirely restructured. The outdated paper-trading lists have been replaced with a professional `TradingTerminal.jsx` interface. 
- Integrated `lightweight-charts` to provide highly performant, sub-millisecond rendering of OHLCV data.
- **Backtest / Live Toggle Integration:** Dynamic markers are overlaid directly on the chart, displaying precisely where the algorithm rotated capital in and out of different assets.
- **Short Leg Execution:** The system supports active short positions in paper trading by mapping `Short_Kelly` to the ProShares Short S&P500 ETF (`SH`), executing rebalances in inverse direction during down-trends.

## 4. Algorithmic Outage Degradation
To prevent a single asset's data outage (e.g., Yahoo Finance failing to deliver `DELL` data) from crashing the pipeline, the `quantitative_backtester.py` and `fetch_market_data.py` pipelines wrap inference in isolated `try/except` blocks. If one asset's model fails, it defaults to a neutral `0.5` probability with `0.0` consensus, allowing the rest of the portfolio to continue trading uninterrupted.

## 5. Softened Regime Gates and Safe Rotation Order
- In high-volatility liquidity rallies, the Kalman filter and HMM often mischaracterize the market as `risk_off` or `CRISIS_DISLOCATION`. We softened this gate to apply a **0.5x scaling penalty** instead of a hard zero on the core SPX position, keeping exposure alive during major rallies.
- The Capital Rotation Engine has been moved to execute **AFTER** the universal regime and HMM coherence gates. This ensures that when single-name high-beta tech assets are forbidden (zeroed out), they are not re-amplified by the SPX rotation boost.
- The Retail Noise Filter has been deactivated to prevent unnecessary 50% suppression of high-conviction signals.

## 6. Core Bug Fixes and Code Alignment
To ensure model fidelity and operational stability under stress, the following 11 bug fixes were implemented:

1. **RL Policy Evaluation Guard:** Disabled experimental reinforcement learning policy inference (`self.use_rl_agent = False`) in [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) to prevent uncalibrated policy outputs from leaking into target allocations.
2. **Feature Rolling Window Alignment:** Set `self.dynamic_rolling_window = 20` inside [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) to ensure alignment between real-time data frame generation and the historical feature metrics.
3. **Feature Label Remapping:** Adjusted the ordered feature keys inside [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) from `spx_macd` to `spx_macd_hist` to align with the output keys defined in [src/engines/feature_engine.py](file:///Users/mac/agent/src/engines/feature_engine.py).
4. **Selective Divergence Capital Slasher:** Configured the quantitative divergence module in [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) to slash Kelly exposure across all long positions by 50% *except* for the safe-haven gold proxy (`GLD_Kelly`), defending capital without muting defensive positions.
5. **Immediate Bond State Synchronization:** Updated the data ingestion pipeline inside [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) to map `self.snapshot.bonds = bonds` immediately when fetched in `handle_data_fetched`.
6. **Drawdown Scope Restriction:** Restricted stop-loss check routines in [src/engines/market_event_detector.py](file:///Users/mac/agent/src/engines/market_event_detector.py) to only process `SPX` position updates, avoiding erroneous stop approaches triggered on stock single-names using SPX close values.
7. **Missing HMM File Fallback:** Implemented robust file-existence checks and regime default guards in [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) for cases where HMM pickle files are unavailable on disk.
8. **Rotation Ordering & Regime Locks:** Relocated the Capital Rotation Engine in [src/engines/risk_engine.py](file:///Users/mac/agent/src/engines/risk_engine.py) to run strictly after regime gates and HMM locks, and guarded it to block execution when the Kalman filter indicates `dominant_state == 'risk_off'`.
9. **Naïve Datetime Resolution:** Standardized timezone representation in [src/quantitative_backtester.py](file:///Users/mac/agent/src/quantitative_backtester.py) and [src/fetch_market_data.py](file:///Users/mac/agent/src/fetch_market_data.py) to handle naïve datetimes under Python 3.9 by enforcing explicit UTC mapping.
10. **Inverse ETF Short Allocation Mapping:** Registered ProShares Short S&P500 ETF (`SH`) as active target allocation in [src/engines/risk_engine.py](file:///Users/mac/agent/src/engines/risk_engine.py) and added it to the `ALL_YF_TICKERS` registry mapping in [src/adapters/paper_broker.py](file:///Users/mac/agent/src/adapters/paper_broker.py).
11. **Race-Condition Drawdown Elimination:** Removed local file-system writes of portfolio drawdown figures in [src/quantitative_backtester.py](file:///Users/mac/agent/src/quantitative_backtester.py) to prevent disk lock contention during multi-threaded stress runs.

