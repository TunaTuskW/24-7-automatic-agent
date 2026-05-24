# Macro Briefing Agent v4.2.0: Multi-Fractal & LLM Hybrid Upgrade

## What Changed
- **[ADDED] Volatility Term Structure:** Integrated `VIX9D` and `VIX3M` to calculate term structure inversions. The Fragility Score is heavily penalized if `VIX9D > VIX` (Backwardation).
- **[ADDED] Multi-Fractal HMM Execution:** Upgraded `yf.download` to use `threads=True` for speed. Added a secondary tactical micro data fetch (Hourly interval). The HMM inference engine now runs concurrently on Structural Macro Data (Daily) and Tactical Micro Data (Hourly).
- **[ADDED] Timeframe Conflict Rules:** The Consensus Engine will now automatically slash the Kalman HMM conviction score by 50% if the Hourly tactical regime actively contradicts the Daily structural regime.
- **[MODIFIED] Semantic NLP News Processor:** Stripped out the legacy `vaderSentiment` heuristic. Integrated a strict JSON-constrained Google Gemini LLM pipeline to semantically parse headlines for `liquidity_drain_probability` and `geopolitical_shock_magnitude`.
- **[ADDED] Hyperparameter Tuning Meta-Agent:** Created a standalone script `src/tune_hyperparameters.py` scheduled to run weekly. It feeds massive text blocks (like FOMC minutes) into Gemini to output a JSON tuning configuration (`tuning_configs.json`). The constants inside `fetch_market_data.py` now dynamically load these tuned half-lives.

## What We Have (Professional System Architecture Overview)
This system is a pure-Python, fully automated quantitative pipeline designed to merge deterministic mathematical models with semantic LLM intelligence.

### 1. Data Ingestion & Signal Layer (`src/fetch_market_data.py`)
- **Asset Fetching:** Threaded parallel ingestion of 30+ tickers via `yfinance` covering Equities, Commodities, Volatility (`^VIX9D`, `^VIX`, `^VIX3M`, `^VVIX`), FX (`DX-Y.NYB`), and Institutional Crypto Flow (`IBIT`, `ETHA`).
- **Multi-Fractal Timeframes:** Ingests both Daily (Structural) and Hourly (Tactical) data to run separate, parallel models.
- **Bond/Yield Data:** US2Y and US10Y are ingested via the FRED API to calculate the `2s10s spread` and flag yield invalidation thresholds.
- **Semantic NLP News Processor:** Ingests RSS feeds and feeds them into a JSON-constrained Gemini LLM to derive strict mathematical shock probabilities instead of using legacy heuristic dictionaries.

### 2. Core Quantitative Engines (`src/fetch_market_data.py`)
- **Regime Persistence Engine:** Tracks state transitions (e.g., `RISK_ON`, `RISK_OFF`). Assigns a dynamic historical half-life to each state (loaded from the `tune_hyperparameters` meta-agent) and measures the `duration_days` and `transition_velocity`.
- **Hidden Fragility Index:** Monitors underlying structural stress before price collapse. It penalizes scores if the Volatility Term Structure inverts (`VIX9D > VIX`), if the `VVIX / VIX` ratio rapidly expands (> 6.0), or if global liquidity drains (`SPX/DXY` correlation > 0.4).
- **Epistemic Kelly Sizing:** Computes target portfolio exposure by measuring the distance between model edge and random noise.
  - **Calibration Penalty:** Evaluates past accuracy via the **Brier Score**. If the model is poorly calibrated (>0.25 Brier), Kelly sizing is severely choked.
  - **Duration Decay Penalty:** If a regime's duration exceeds its tuned half-life, an exponential decay penalty `exp(-0.2 * (duration - half_life))` forces systematic risk-reduction.

### 3. The Consensus Engine (`src/build_report.py`)
- The pipeline aggregates distinct quantitative signals (Kalman State, MCS, Volume Heat, Kelly Size, Extremes) into `ModelResult` dataclasses.
- **Deterministic Voting:** Runs a conviction-weighted vote across the modules.
- **Dynamic Thresholding:** The threshold required for the models to "agree" is dynamically conditioned by the semantic LLM shock probabilities.
- **Conflict Resolution (Timeframe & Chaos):** If internal models diverge, it measures the Total Variation Distance (TVD) and Shannon Entropy. High entropy automatically forces a `NO PREDICT` posture. If the Tactical (Hourly) HMM contradicts the Structural (Daily) HMM, the Consensus engine slashes the HMM Kalman conviction weight by 50%.

### 4. Layout & Orchestration
- **Formatting scripts:** `build_report.py` (4-hour) and `build_weekly_synthesis.py` (Weekly) format the raw mathematical vectors into minimalist, brutalist markdown templates.
- **Visualization:** Interactive Jupyter environments map the entire algorithmic brain natively in VS Code.
- **Hyperparameter Meta-Agent:** `src/tune_hyperparameters.py` runs weekly to inject NLP macro context directly into the math constants.
- **Delivery:** Output is pushed seamlessly via Discord/Telegram webhooks.
- **Cron Automation:** Operations are scheduled natively via OS cron triggers hitting `run_4h.sh` and `run_weekly.sh`.
