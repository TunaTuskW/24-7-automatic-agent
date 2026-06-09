# Macro Briefing Agent v5.1.0: Multi-Asset Ensemble OS & Capital Rotation Manual

This manual details the upgrades in **v5.1.0 (Multi-Asset Ensemble OS & Capital Rotation Engine)**, transforming the agent into a containerized **Multi-Asset Ensemble Machine Learning & Global Macro OS** featuring ensemble classifiers, capital rotation, consensus calibration, auto-inversion, black swan breakers, and visual backtest plotting.

---

## 1. Modular Pipeline & Script Ecosystem

Following the v5.1.0 upgrades, the system operates as a highly decoupled, event-driven Mixture of Experts (MoE) & Multi-Asset Ensemble pipeline:

```
src/
├── interfaces/         # OOP Abstract Interface Contracts
│   ├── data_broker.py
│   └── llm_provider.py
├── adapters/           # Data & API Fetching Adapters
│   ├── yahoo_adapter.py        <-- fetch_yield_history & yield delta calculations
│   ├── gemini_adapter.py       <-- gemini-2.5-flash CoT expert & failover logic
│   ├── groq_adapter.py         <-- Groq Llama 3 CoT expert & failover logic
│   └── forexfactory_adapter.py <-- USD/EUR/JPY high-impact economic calendar
├── data_lake/          # Database Partitioning Engine
│   └── lake_manager.py <-- Event Logger & Parquet/JSONL persistence
├── engines/            # Mathematical & Machine Learning Engines
│   ├── feature_engine.py   <-- Ensemble loading, inference routing, Brier self-calibration
│   ├── hmm_engine.py       <-- GaussianHMM uniform start & VIX GARCH Bayesian Penalty Filter
│   ├── risk_engine.py      <-- Multi-Asset Kelly allocations, rotation, overrides, and breakers
│   └── consensus_engine.py <-- MoE synthesis, signal mapping, and Echo Chamber check
├── observability/      # Logging & Dispatching Layer
│   ├── logger.py
│   └── event_bus.py        <-- Pub-sub execution flow
├── schemas/            # Strict Type Validation Layer
│   └── models.py           <-- Pydantic models (MarketSnapshot, EconomicCalendar, etc.)
├── generate_visual_map.py   # Centralized Visualizer Script (replaces legacy Jupyter notebooks)
└── fetch_market_data.py # Central Conductor (Dependency Injection & Telemetry Orchestration)
```

---

## 2. Multi-Asset Ensemble ML Pipeline

The deep learning classifier framework has transitioned from a single-asset, single-model system to a robust multi-asset ensemble network:

### A. Ensemble Model Inception
* The engine trains distinct supervised classifiers for **four core target assets**:
  - **S&P 500 (`spx`)**
  - **Bitcoin (`btc`)**
  - **Gold (`gld`)**
  - **Crude Oil (`wti`)**
* For each asset, the pipeline fits an ensemble of three models to reduce predictive variance:
  1. **Multi-Layer Perceptron (MLP)**
  2. **Random Forest (RF)**
  3. **Gradient Boosting (GB)**
* Models are saved locally as ensemble packages (e.g., `mlp_model_spx_4h.pkl`, `mlp_model_btc.pkl`).

### B. Calibration Model Consensus Score
* During inference, the system evaluates predictions from all three models.
* The standard deviation of their probability outputs is calculated.
* If standard deviation is low ($\sigma < 0.15$),indicating high model consensus, a **Consensus Score** of `1.0` is registered.
* High model consensus scales up the target Kelly exposure by **1.5x**, while low consensus penalizes exposure by **0.5x**.

### C. Auto-Inversion Calibration Module
* If a model's rolling Brier Score degrades above `0.60` (signaling that the model is negatively calibrated due to extreme regime drift or overfitted mean-reversion), the conductor automatically triggers the **Auto-Inversion Module**:
  $$\text{Probability}_{\text{adjusted}} = 1.0 - \text{Probability}_{\text{raw}}$$
* This dynamically converts a lagging predictive signal into a highly accurate contrarian lean.

---

## 3. Advanced Sizing Overrides & Portfolio Overlays

The `RiskEngine` compiles model probabilities and regime states to construct a diversified, risk-balanced allocation vector.

### A. Sizing Overrides & Circuit Breakers
1. **Capitulation Override (Contrarian Buy)**:
   - **Conditions**: S&P 500 z-score return is oversold (`spx_ret_z` between `-1.5` and `-3.0`), volume heat highlights institutional accumulation (`ihi > 0.0`), and MLP probability is bullish (`mlp_prob > 0.5`).
   - **Impact**: Bypasses baseline risk-off penalties, applying a **0.9x guarded contrarian Kelly sizer**.
2. **Momentum Ignition Override (Trend Buy)**:
   - **Conditions**: S&P 500 return z-score is positive (`spx_ret_z > 1.0`), volume heat is positive (`ihi > 0.1`), and MLP probability is bullish ($0.4 < \text{mlp\_prob} \le 0.80$).
   - **Impact**: Bypasses Brier Score calibration penalties entirely (`calibration_penalty = 1.0`) and applies an aggressive **1.25x momentum Kelly multiplier**.
3. **Black Swan Circuit Breaker**:
   - **Conditions**: SPX return z-score drops below `-3.5` standard deviations.
   - **Impact**: Automatically liquidates all equity exposure (`SPX_Kelly = 0.0`) to shield capital from severe tail risk.
4. **Macro Trend Override**:
   - **Conditions**: SPX trades below its 20 EMA (technical downtrend).
   - **Impact**: Forces SPX Long Kelly size to exactly `0.0`.
5. **Retail Noise Filter**:
   - **Conditions**: In non-risk-off dominant regimes where institutional heat is negative (`ihi < 0.0`).
   - **Impact**: Slashes S&P 500 exposure by 50% to prevent chasing retail-driven noise.

### B. Capital Rotation Engine
* If the primary equity asset (S&P 500) shows weakness ($\text{spx\_prob} < 0.40$), the system triggers the **Capital Rotation Engine**.
* Capital is redirected to alternatives showing strong individual momentum: Gold (`gld`), Bitcoin (`btc`), and Crude Oil (`wti`) receive a **1.5x allocation scale factor**.

### C. HMM Regime-Specific Alternative Asset Filters
* Under HMM regimes representing high structural stress (`DEFLATION_FEAR` or `CRISIS_DISLOCATION`):
  - Crypto (`btc`) and Energy (`wti`) Kelly allocations are set to **0.0**.
  - Gold (`gld`) is dynamically boosted to absorb remaining capital as a defensive safe haven:
    $$\text{GLD\_Kelly} = \max(\text{GLD\_Kelly}, 1.0 - \text{SPX\_Kelly} - \text{Short\_Kelly})$$

### D. Global Portfolio Balancer
* The portfolio balancer limits maximum combined leverage. If the sum of S&P 500 (Long & Short), Gold, Bitcoin, and Oil allocations exceeds a hard leverage ceiling of **1.2 (120% exposure)**, the engine scales all allocations proportionally to enforce safety:
  $$\text{Scale} = \frac{1.2}{\text{Total\_Exposure}}$$
* The remaining portfolio weight is held as cash.

---

## 4. Phase 2 Live Telemetry Engine

Upon completion of each run, the conductor compiles and outputs real-time metrics to a structured live telemetry file:
* **Path**: `/Users/mac/agent/data/live_telemetry.json`
* **Schema**:
  ```json
  {
    "timestamp_utc": "2026-06-09T07:45:00Z",
    "dominant_regime": "RISK_ON_EXPANSION",
    "spx_kelly_fraction": 0.85,
    "safe_haven_kelly_fraction": 0.0,
    "is_capitulation_override_active": false,
    "institutional_heat_index": 0.12
  }
  ```

---

## 5. Parallel LLM Echo Chamber Detector

* To prevent narrative reinforcement loops where parallel experts (Macro Policy and Market Psychology) fall back onto the same LLM provider due to network errors or rate limits, the `ConsensusEngine` monitors active providers:
  - If both experts execute on the same platform (e.g. Groq-to-Gemini failover triggers simultaneously on both), an **LLM Echo Chamber Flag** is raised.
  - The News Conviction Score is penalized by **0.70x** to neutralize narrative correlation bias.

---

## 6. Visualization & Plotting

* Legacy Jupyter notebooks have been replaced by the centralized visualizer script **`src/generate_visual_map.py`**.
* The script automatically parses daily backtest logs (`reports/backtest_extended_results.md`) and outputs high-resolution stacked allocation maps (`reports/visualize_map.png`) showing the real-time transitions between Equities, Crypto, Energy, Gold, and Cash.
