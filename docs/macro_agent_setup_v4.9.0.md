# Macro Briefing Agent v4.9.0: Active-Active Failover & GARCH Bayesian OS Manual

This manual details the upgrades in **v4.9.0 (Active-Active Failover & GARCH Bayesian OS)**, transforming the agent into a containerized **Multimodal Global Macro Mixture of Experts (MoE) OS** featuring dual-provider active-active LLM failover, GARCH Bayesian regime penalty filters, return-based 60-day z-scores, multi-timeframe models, and regime-specific Kelly portfolio sizing discounts.

---

## 1. Architectural Blueprint & Decoupling

Following the v4.9.0 upgrades, the system operates as a fully event-driven, MoE pub-sub architecture orchestrated via Pydantic model schemas and customizable command-line interval dispatching:

```
src/
├── interfaces/         # Core Interface Contracts (Abstract Base Classes)
│   ├── data_broker.py
│   └── llm_provider.py  <-- MoE Abstract Expert Contracts
├── adapters/           # Input Data & External API Fetchers (Adapter Pattern)
│   ├── yahoo_adapter.py  <-- Dynamic Interval OHLCV & Yield History fetching
│   ├── gemini_adapter.py <-- gemini-2.5-flash Parallel CoT Expert
│   ├── groq_adapter.py   <-- Llama 3 / Groq Parallel CoT Expert [NEW]
│   └── forexfactory_adapter.py <-- Ingests High-Impact economic calendars
├── data_lake/          # Enterprise Partitioned Storage Engine
│   └── lake_manager.py <-- Event Logger Interceptor & Parquet/JSONL
├── engines/            # Mathematical, Statistical & Deep Learning Engines
│   ├── feature_engine.py   <-- 60D Return z-scores & MLP Model Routing
│   ├── hmm_engine.py       <-- Multi-Fractal HMM regime classification
│   ├── risk_engine.py      <-- Kalman Filter & Regime-Penalized Kelly Sizing
│   └── consensus_engine.py <-- Synthesizes MoE outputs, Divergence checks & Signal mappings
├── observability/      # Standardized Contextual Logging Framework
│   ├── logger.py
│   └── event_bus.py      <-- Pub-Sub Event Dispatcher
├── schemas/            # Strict Type Validation Layer
│   └── models.py         <-- Pydantic Data Structures (MarketSnapshot, etc.)
└── fetch_market_data.py # Conductor / Central Orchestrator (Dependency Injection & CLI)
```

---

## 2. Active-Active Cross-Provider Failover & MoE

The core cognitive Mixture of Experts (MoE) layer has been upgraded to a dual-provider active-active resilient architecture:

### A. Dual-Provider LLM Engines (Groq & Gemini)
To guarantee 100% operational uptime and bypass API quota blocks, the system integrates a **Cross-Provider Failover & Failback Mechanism**:
* **Groq Adapter (`groq_adapter.py`)**: Connects to the Groq API utilizing `Llama 3` models.
* **Gemini Adapter (`gemini_adapter.py`)**: Connects to the Google Gemini API utilizing `gemini-2.5-flash` models.

### B. Parallel Resilient Expert Execution
Using a `ThreadPoolExecutor` and failover sub-routines, the Conductor runs the Experts concurrently:
1. **Macro Policy Expert (`run_macro`):**
   - **Primary Engine**: Executed first via Groq (`groq_adapter.run_macro_policy_expert`).
   - **Failover Route**: If Groq encounters rate limits, timeouts, or availability errors, it automatically falls back to Gemini (`gemini_adapter.run_macro_policy_expert`), prepending `"(Failover to Gemini)"` to the final reasoning payload.
2. **Market Psychology Expert (`run_psych`):**
   - **Primary Engine**: Executed first via Gemini (`gemini_adapter.run_market_psychology_expert`).
   - **Failover Route**: If Gemini fails, it automatically falls back to Groq (`groq_adapter.run_market_psychology_expert`), prepending `"(Failover to Groq)"` to the final reasoning payload.

*Both adapters retain the robust 10-attempt exponential backoff retry logic (`(attempt + 1) * 10`s delay) before triggering their respective failover paths.*

---

## 3. Quantitative Mathematical Upgrades

The core statistical and pricing engines in `feature_engine.py` and `fetch_market_data.py` have undergone critical structural transformations to expand lookback horizons and improve mathematical signal-to-noise ratios:

### A. 60-Day Lookback Horizon & Return z-Scores
- **60-Day Historical Window**: Replaced legacy 5-day lookbacks with a robust **60-day historical window** (`ROLLING_DAYS = 60`) for all trailing statistical metrics, capturing true medium-term market momentum and stability.
- **Return z-Scores**: Overhauled statistical z-scores. Rather than price-level drift, the z-score now measures **structural return anomalies**:
  $$z = \frac{\Delta\% - \text{mean}(\Delta\%_{60d})}{\text{std}(\Delta\%_{60d})}$$
  This isolates high-volatility return anomalies from baseline standard price levels.

### B. Treasury Yield & Spread Z-Scores
- The 10-year Treasury yield daily return z-score (`delta_zscore`) and the 2s10s yield spread z-score (`spread_zscore`) are computed dynamically using a 60-day window (`fetch_yield_history()` in `YahooAdapter`). These replace legacy raw yield values inside the `clean_daily` vector payloads.

### C. GARCH Bayesian Updating & Penalty Filter
To adapt mathematical regime expectations dynamically during sudden volatility spikes, the system introduces a **GARCH Bayesian Penalty Filter**:
- `compute_garch_volatility` now emits GARCH regime flags (`NORMAL` or `ELEVATED`).
- If the **SPX GARCH Regime** is flagged as **`ELEVATED`**, indicating structural intraday expansion stress, the Conductor interceptor dynamically **slashes HMM Risk-On probabilities by 50%**:
  - `LIQUIDITY_DRIVEN_RALLY` and `RISK_ON_EXPANSION` regime probabilities are cut in half.
  - The penalized probability mass is redistributed directly back into `NEUTRAL_TRANSITIONAL`.
- This ensures GARCH volatility spikes dynamically suppress bullish bias before portfolio Kelly sizing is computed.

---

## 4. Multi-Timeframe Deep MLP Classifier

- **Interval-Driven Model Loading**: `load_mlp_model(interval)` loads localized MLP model packages by timeframe (`mlp_model_1d.pkl`, `mlp_model_4h.pkl`, etc.) with backward compatibility fallbacks.
- **Regime-Routed MLP Inference**: MLP inference (`run_mlp_inference`) dynamically routes observations to specialized model variants based on the active HMM regime:
  - **Risk-On HMM Regimes**: Routed to `model_bull` (bullish supervised classifier).
  - **Risk-Off HMM Regimes**: Routed to `model_bear` (bearish supervised classifier).
  - **Neutral/Transitional Regimes**: Routed to `model_neutral` (base model).
- **Binary Sizing Mapping**: Mapped MLP outputs into standardized parameters: `bull_probability`, `bear_probability`, and `predicted_class`.

---

## 5. Advanced Kelly Sizing & Consensus Slashes

### A. Regime-Specific Kelly Sizing Penalties
Base portfolio exposure is penalized by Brier calibration scores and regime duration half-lives. In v4.9.0, we introduce **Regime Risk-Aversion Penalties** directly in the `RiskEngine`:
- **`risk_off` dominant HMM state**: Target Kelly sizing is dynamically **slashed by 50% (0.5x multiplier)** to preserve capital under high cross-asset stress.
- **`transitional` dominant HMM state**: Target Kelly sizing is dynamically **discounted by 25% (0.75x multiplier)** to protect against directionless choppy trading environments.

### B. Decoupled Consensus Signal Mapping (`consensus_engine.py`)
Voting and signal calculations are synthesized and routed under simplified clean boundaries:
- **`QUANT_DIVERGENCE_PANIC`**: Triggered if headlines are bullish but VIX spikes > 1.5. Sets signal to `SHORT` (exposure slashed by 50%).
- **`CONSENSUS_BEARISH`**: Triggered if `hawkish_prob > 0.6` and `fear_greed < 0.4`. Sets signal to `SHORT`.
- **`CONSENSUS_BULLISH`**: Triggered if `hawkish_prob < 0.4` and `fear_greed > 0.6`. Sets signal to `LONG` (1.2x sizing on risk-on regime).
- **`MIXED_SIGNALS`**: Default state. Sets signal to `MIXED` with conviction averaged between experts.

---

## 6. Shell Scheduling & CLI Intervals

The automated conductor now accepts dynamic `--interval` command-line flags. Scripts have been updated to target localized operational configurations:

### 1. Main 4-Hour Briefing (`run_4h.sh`)
Executes the Conductor with `4h` intervals, utilizing custom hourly data series and routing to `mlp_model_4h.pkl`:
```bash
PYTHONPATH=. python3 src/fetch_market_data.py --interval 4h
```

### 2. Sunday Weekly Synthesis (`run_weekly.sh`)
Executes the Conductor with `1wk` intervals, utilizing weekly data series and routing to `mlp_model_1wk.pkl`:
```bash
PYTHONPATH=. python3 src/fetch_market_data.py --interval 1wk
```
