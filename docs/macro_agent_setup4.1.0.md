# Macro Briefing Agent v4.1.0: Math Visualization Update

## What Changed
- **[ADDED] Jupyter Visualizer:** Created `src/visualize_math_4h.ipynb` and `src/visualize_math_1w.ipynb` to allow interactive, local inspection of the mathematical engines inside VS Code.
- **[ADDED] Graphing Dependencies:** Installed `matplotlib`, `seaborn`, and `jupyter` natively into the environment.
- **[ADDED] Visual Dashboards:** The notebook overlays HMM regime states directly onto the S&P 500 price chart, plots the VVIX/SPX Fragility Index heatmaps, and tracks the Epistemic Kelly Exposure sizing curve over the last 2 years.

## What We Have (Professional System Architecture Overview)
This system is a pure-Python, fully automated quantitative pipeline designed to replace legacy LLM heuristics with deterministic mathematical models. 

### 1. Data Ingestion & Signal Layer (`src/fetch_market_data.py`)
- **Asset Fetching:** Parallel ingestion of 30+ tickers via `yfinance` covering Equities, Commodities, Volatility (`^VIX`, `^VVIX`), FX (`DX-Y.NYB`), and Institutional Crypto Flow (`IBIT`, `ETHA`).
- **Bond/Yield Data:** US2Y and US10Y are ingested via the FRED API to calculate the `2s10s spread` and flag yield invalidation thresholds.
- **Stealth NLP NewsSignalVector:** Ingests RSS feeds (Yahoo Finance) and applies `vaderSentiment` scoring in the background. Sentiments are strictly interpreted as Absolute Shock/Volatility multipliers rather than directional bias. Event flags trigger if 3+ macro cluster keywords are detected.

### 2. Core Quantitative Engines (`src/fetch_market_data.py`)
- **Regime Persistence Engine:** Tracks state transitions (e.g., `RISK_ON`, `RISK_OFF`). Assigns a historical half-life to each state (e.g., 11.0 days for `RISK_ON`) and measures the `duration_days` and `transition_velocity`.
- **Hidden Fragility Index:** Monitors underlying structural stress before price collapse. It penalizes scores if the `VVIX / VIX` ratio rapidly expands (> 6.0) or if global liquidity drains, detected via high cross-asset correlation between `SPX` and `DXY` (> 0.4).
- **Epistemic Kelly Sizing:** Computes target portfolio exposure by measuring the distance between model edge and random noise.
  - **Calibration Penalty:** Evaluates past accuracy via the **Brier Score**. If the model is poorly calibrated (>0.25 Brier), Kelly sizing is severely choked.
  - **Duration Decay Penalty:** If a regime's duration exceeds its half-life, an exponential decay penalty `exp(-0.2 * (duration - half_life))` forces systematic risk-reduction.

### 3. The Consensus Engine (`src/build_report.py`)
- The pipeline aggregates 5 distinct quantitative signals (Kalman State, MCS, Volume Heat, Kelly Size, Extremes) into `ModelResult` dataclasses.
- **Deterministic Voting:** Runs a conviction-weighted vote across the modules.
- **Dynamic Thresholding:** The threshold required for the models to "agree" is dynamically conditioned by the stealth `NewsSignalVector` (e.g., event risk raises the required conviction to `0.65`).
- **Conflict Resolution:** If internal models are too divergent, it measures the Total Variation Distance (TVD) and Shannon Entropy (Chaos). High entropy automatically forces a `NO PREDICT` or `STAND ASIDE` posture.

### 4. Layout & Orchestration
- **Formatting scripts:** `build_report.py` (4-hour) and `build_weekly_synthesis.py` (Weekly) format the raw mathematical vectors into minimalist, brutalist markdown templates.
- **Visualization:** `src/visualize_math_4h.ipynb` and `src/visualize_math_1w.ipynb` provide interactive Jupyter environments to plot math vectors and regime transitions natively in VS Code.
- **Delivery:** Output is pushed seamlessly via Discord/Telegram webhooks.
- **Cron Automation:** Operations are scheduled natively via OS cron triggers hitting `run_4h.sh` and `run_weekly.sh`.
