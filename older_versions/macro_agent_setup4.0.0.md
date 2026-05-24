# Macro Briefing Agent v4.0.0: Persistence & Fragility Upgrade

The v4.0.0 Macro Upgrade introduces two critical mathematical engines to the quantitative core: **Regime Path-Dependency (Persistence)** and **Hidden Volatility (Fragility Index)**. These engines run quietly in the background without cluttering the UI layout.

## What's New

### 1. The Fragility Index (VVIX & Cross-Asset Correlation)
The `compute_market_extremes` engine in `fetch_market_data.py` now calculates a `fragility_score` to detect structural market weaknesses before they appear in price action:
- **VVIX integration:** We now ingest the CBOE VIX Volatility Index (`^VVIX`). If the ratio of VVIX to VIX expands rapidly (> 6.0), the fragility score increases, indicating extreme hedging demand.
- **DXY Cross-Correlation:** We ingest the US Dollar Index. If the S&P 500 (SPX) and the US Dollar (DXY) become highly positively correlated (> 0.4), it signals global liquidity drainage, significantly increasing the fragility score.

### 2. Regime Persistence Scoring (Duration Engine)
Markets are highly path-dependent. `fetch_market_data.py` now tracks exactly how long the market has spent in its current regime state.
- Each state has a dynamically assigned historical half-life (`RISK_ON` = 11 days, `NEUTRAL_TRANSITIONAL` = 2.5 days, `RISK_OFF` = 1.2 days).
- The regime data object natively outputs `duration_days`, `stability_half_life`, and `transition_velocity`.

### 3. Kelly Sizing Decay Penalty
The `compute_kelly_sizing` algorithm now natively penalizes older trades to avoid "overstaying a welcome".
- If a regime's `duration_days` exceeds its mathematical `stability_half_life`, an exponential decay penalty `exp(-0.2 * (duration - half_life))` is applied.
- This forcefully scales the portfolio exposure out of the aging regime, enforcing systematic profit-taking or risk-reduction before the transition occurs.403 PERMISSION_DENIED` and `429 RESOURCE_EXHAUSTED` errors that the free-tier API keys were causing.
- **Instantaneous Reasoning:** The agent now computes the `Directional Lean` and `Positioning` instantly using a strict decision tree based on the Kalman `dominant_state`, Brier Score, and Volume Heat metrics.
- **Flawless Formatting:** The deterministic reasoning correctly drops straight into the `QUANTITATIVE DIRECTIONAL SYNTHESIS` block of the report.

### Live Example
```markdown
- **Market State:** RISK_ON
- **Directional Lean:** Weak Bullish (LOW CONFIDENCE)
- **Positioning:** Reduce position sizing. Models divergent or poorly calibrated.
- **Invalidation:** VIX breakout > 18.28 or US10Y > 4.575%
```

## Objective Achieved
Successfully refined the **v3.0.0** release to implement the continuous Institutional Heat Index (IHI) via Volume Spread Analysis directly into the ML feature vector. Eliminated unstable hard thresholds and replaced redundant Python sentiment proxies by natively delegating sentiment interpretation to the LLM via prompt directives.

## Part 1 & 2: Data Engine Helpers & Pipeline Integration (`src/fetch_market_data.py`)
> [!NOTE]
> We have stripped out all hardcoded Python sentiment logic in favor of delegating sentiment analysis to the LLM natively.

- **Continuous Institutional Heat Index (IHI):** Updated `compute_institutional_heat_index(hist_df)` to compute a continuous Z-score multiplier. It uses a 20-day standard deviation to calculate `effort_z`, and outputs `heat_index = effort_z * result_vector` to provide a perfectly smooth numeric feature for the Machine Learning models.
- **Robust Market Extremes:** Updated `compute_market_extremes()` to use 10-day absolute divergence logic for Market Crowdedness instead of the previous 5-day correlation, calculating explicit return vectors for SPX and VIX.
- **Sentiment Delegation:** Completely deleted `compute_insight_sentiment_proxy()`, stripping it out of the JSON snapshot entirely.
- **Pipeline Integration:** Injected `volume_activity_heat` into the structured feature vector using the new continuous `effort_zscore`.

## Part 3: ML Engine Re-Calibration (`src/train_models.py`)
> [!WARNING]
> Historical backfill must structurally match the live pipeline calculations to ensure zero data drift.

- Updated `fetch_training_data()` to recalculate the historical `Inst_Heat_Index` using the continuous formulation.
- Added `vol_std20`, `effort_z`, and `result_vector`.
- Included the **CRITICAL** `.dropna()` operation after calculating the new 20-day rolling volume windows to prevent NaN poison from crashing the pipeline during model training operations.

## Part 4: Report Builder & AI Assumptions (`src/build_report.py`)
- Adjusted `generate_llm_report()` to natively prompt the LLM to deduce the current market sentiment (Fear/Greed) directly from the VIX and Credit Stress parameters.
- Re-plumbed the `CRITICAL TASK` instructions to explicitly state: `"You must deduce the current market sentiment (Fear/Greed) natively from the provided VIX and Credit Stress parameters."`
- Updated the deterministic text template to neatly list the continuous IHI formatting to 3 decimal places (`{heat_idx:.3f}`). 

## Part 5: Setup Guidelines Updates (`docs/macro_agent_setup3.0.0.md`)
- Overwrote the existing Patch Notes in `macro_agent_setup3.0.0.md` with the new finalized **Continuous Volume Heat & Robust Diagnostics** release details, ensuring flawless automation logic propagation for future clones.


## System Architecture Overview (Technical Developer Manual)

This system is a pure-Python, fully automated quantitative pipeline designed to replace legacy LLM heuristics with deterministic mathematical models. 

### 1. Data Ingestion & Signal Layer (`src/fetch_market_data.py`)
- **Asset Fetching:** Parallel ingestion of 30+ tickers via `yfinance` covering Equities, Commodities, Volatility (`^VIX`, `^VVIX`), FX (`DX-Y.NYB`), and Institutional Crypto Flow (`IBIT`, `ETHA`).
- **Bond/Yield Data:** US2Y and US10Y are ingested via the FRED API to calculate the `2s10s spread` and flag yield invalidation thresholds.
- **NLP NewsSignalVector:** Ingests RSS feeds (Yahoo Finance) and applies `vaderSentiment` scoring. Sentiments are strictly interpreted as Absolute Shock/Volatility multipliers rather than directional bias. Event flags trigger if 3+ macro cluster keywords are detected.

### 2. Core Quantitative Engines (`src/fetch_market_data.py`)
- **Regime Persistence Engine:** Tracks state transitions (e.g., `RISK_ON`, `RISK_OFF`). Assigns a historical half-life to each state (e.g., 11.0 days for `RISK_ON`) and measures the `duration_days` and `transition_velocity`.
- **Hidden Fragility Index:** Monitors underlying structural stress before price collapse. It penalizes scores if the `VVIX / VIX` ratio rapidly expands (> 6.0) or if global liquidity drains, detected via high cross-asset correlation between `SPX` and `DXY` (> 0.4).
- **Epistemic Kelly Sizing:** Computes target portfolio exposure by measuring the distance between model edge and random noise.
  - **Calibration Penalty:** Evaluates past accuracy via the **Brier Score**. If the model is poorly calibrated (>0.25 Brier), Kelly sizing is severely choked.
  - **Duration Decay Penalty:** If a regime's duration exceeds its half-life, an exponential decay penalty `exp(-0.2 * (duration - half_life))` forces systematic risk-reduction.

### 3. The Consensus Engine (`src/build_report.py`)
- The pipeline aggregates 5 distinct quantitative signals (Kalman State, MCS, Volume Heat, Kelly Size, Extremes) into `ModelResult` dataclasses.
- **Deterministic Voting:** Runs a conviction-weighted vote across the modules.
- **Dynamic Thresholding:** The threshold required for the models to "agree" is dynamically conditioned by the `NewsSignalVector` (e.g., event risk raises the required conviction to `0.65`).
- **Conflict Resolution:** If internal models are too divergent, it measures the Total Variation Distance (TVD) and Shannon Entropy (Chaos). High entropy automatically forces a `NO PREDICT` or `STAND ASIDE` posture.

### 4. Layout & Orchestration
- **Formatting scripts:** `build_report.py` (4-hour) and `build_weekly_synthesis.py` (Weekly) format the raw mathematical vectors into minimalist, brutalist markdown templates.
- **Delivery:** Output is pushed seamlessly via Discord/Telegram webhooks.
- **Cron Automation:** Operations are scheduled natively via OS cron triggers hitting `run_4h.sh` and `run_weekly.sh`.
