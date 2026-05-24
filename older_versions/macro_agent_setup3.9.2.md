
This patch resolves 4 critical flaws in the v3.9.1 Consensus Engine.

## What's Changed
- **Fixed Consensus Overwrite Paradox:** The `compute_deterministic_synthesis` function no longer overrides the Consensus Engine's direction with NO PREDICT if Kelly sizing is 0%. It now accurately reflects the model's directional signal while applying strict exposure warnings.
- **Fixed Type Hazards in Early Exits:** Addressed a typing flaw where early bailouts in the `run_consensus_engine` function returned floats instead of strings for `news_impact`. 
- **Fixed Lexical Hazards & Overly-Sensitive Flags:** Updated NLP to interpret News Sentiment as an Absolute Shock/Volatility multiplier rather than raw directional bias, avoiding financial jargon misclassification (like "rates cut"). Event flags now also require at least 3 keyword hits to trigger the 0.65 threshold penalty.
- **Restored Ghost Variables:** Injected `headlines_str` and `news_impact` directly into the `[ TACTICAL DIAGNOSTICS ]` block in both 4-hour and weekly synthesis templates.

**Changes Made:**
- **Shannon Entropy Measurement:** The data layer now computes the true informational entropy of the probability distribution (Max Entropy for 3-states is ~1.58).
- **Fractional Kelly Scaling:** The agent no longer asks if a trade is "valid"; it asks "how big is the edge?". Exposure scales natively between 0% and 100% based precisely on the distance from random noise (33.3%).
- **Brier Penalty Logic:** The Kelly output is dynamically penalized by poor calibration. If the models are highly degraded (Brier > 0.25), Kelly is mathematically choked to 0%.
- **Updated Synthesis Logic:** The local `build_report.py` logic engine now processes this Epistemic Payload directly, dynamically outputting sizing instructions (e.g., "Scale exposure to exactly 14.5%").

### Live Example (High Chaos Environment)
```markdown
### QUANTITATIVE DIRECTIONAL SYNTHESIS
- **Market State:** NOISY / HIGH CHAOS (Entropy: 1.58)
- **Directional Lean:** NO PREDICT (Statistical Coin-Flip)
- **Positioning:** STAND ASIDE. 0% Exposure.
- **Invalidation:** Requires dominant probability > 45.0%
```

## Architectural Shift: Pure Algorithmic Synthesis (v3.2.0)
Replaced the external Gemini LLM dependency with a purely deterministic, mathematical logic engine (`compute_deterministic_synthesis`) inside `build_report.py`.

**Changes Made:**
- **No More API Limits:** The agent no longer relies on external Google GenAI calls. It completely bypasses the `403 PERMISSION_DENIED` and `429 RESOURCE_EXHAUSTED` errors that the free-tier API keys were causing.
- **Instantaneous Reasoning:** The agent now computes the `Directional Lean` and `Positioning` instantly using a strict decision tree based on the Kalman `dominant_state`, Brier Score, and Volume Heat metrics.
- **Flawless Formatting:** The deterministic reasoning correctly drops straight into the `QUANTITATIVE DIRECTIONAL SYNTHESIS` block of the report.

### Live Example
```markdown
### QUANTITATIVE DIRECTIONAL SYNTHESIS
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
