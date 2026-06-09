# Macro Briefing Agent v5.0.0: Capitulation OS & Dual-Asset Allocation Manual

This manual details the upgrades in **v5.0.0 (Capitulation OS & Dual-Asset Allocation)**, transforming the agent into a containerized **Multimodal Global Macro Mixture of Experts (MoE) OS** featuring dynamic measurement noise filters, capitulation and momentum overrides, dual-asset Kelly allocations (SPX and Safe Haven), and live telemetry tracking.

---

## 1. Architectural Blueprint & Decoupling

Following the v5.0.0 upgrades, the system operates as an enterprise-grade, event-driven Mixture of Experts (MoE) pipeline supporting timeframe-decoupled operations and active-active failover execution:

```
src/
├── interfaces/         # Core Interface Contracts (Abstract Base Classes)
│   ├── data_broker.py
│   └── llm_provider.py  <-- MoE Abstract Expert Contracts
├── adapters/           # Input Data & External API Fetchers (Adapter Pattern)
│   ├── yahoo_adapter.py  <-- Dynamic Interval OHLCV & Yield History fetching
│   ├── gemini_adapter.py <-- gemini-2.5-flash Parallel CoT Expert
│   ├── groq_adapter.py   <-- Llama 3 / Groq Parallel CoT Expert
│   └── forexfactory_adapter.py <-- Ingests High-Impact economic calendars
├── data_lake/          # Enterprise Partitioned Storage Engine
│   └── lake_manager.py <-- Event Logger Interceptor & Parquet/JSONL
├── engines/            # Mathematical, Statistical & Deep Learning Engines
│   ├── feature_engine.py   <-- Dynamic rolling windows, return z-scores & MLP Routing
│   ├── hmm_engine.py       <-- GaussianHMM Uniform Start & GARCH Penalty Filter
│   ├── risk_engine.py      <-- Dynamic Covariance Noise, Kelly Overrides & Dual Allocation
│   └── consensus_engine.py <-- Synthesizes MoE, signal mapping & signal overrides
├── observability/      # Standardized Contextual Logging Framework
│   ├── logger.py
│   └── event_bus.py      <-- Pub-Sub Event Dispatcher
├── schemas/            # Strict Type Validation Layer
│   └── models.py         <-- Pydantic Data Structures (MarketSnapshot, etc.)
└── fetch_market_data.py # Conductor / Central Orchestrator (Telemetry & Overrides)
```

---

## 2. Advanced Sizing Overrides & Risk Engine Upgrades

The core mathematical layers in the `HMMEngine` and `RiskEngine` have been upgraded to support dynamic covariance adjustments, calibration grading, contrarian/trend-following overrides, and multi-asset capital allocation:

### A. Dynamic Measurement Noise Covariance
To prevent sudden, single-bar HMM regime jumps that cause excessive trading turnover, the `HMMEngine` and `RiskEngine` track sudden changes in regime expectations:
* **Sudden Fear Spikes**: If a sudden observation spike in Risk-Off probability occurs (`z[1] > 0.6` while the prior state prediction was `x[1] < 0.3`), the filter dynamically inflates the measurement noise covariance matrix:
  $$R = \mathbf{I} \times 0.25 \quad (\text{instead of } 0.05)$$
* **Impact**: Enforces a multi-bar confirmation period before shifting the active dominant state, smoothing out session-level noise.

### B. System Sizing Overrides
The Conductor evaluates structural indicator combinations to execute high-conviction **System Overrides** that bypass baseline HMM regime penalties:
1. **Capitulation Override (Contrarian Buy)**:
   - **Conditions**: S&P 500 z-score return is extremely oversold (`spx_ret_z` between `-1.5` and `-3.0`), volume heat highlights strong institutional support (`current_ihi > 0.0`), and MLP probability is bullish (`mlp_prob > 0.5`).
   - **Impact**: Bypasses Risk-Off penalties, applying a **0.9x guarded contrarian Kelly multiplier** to buy oversold panics.
2. **Momentum Ignition Override (Trend-Following Buy)**:
   - **Conditions**: S&P 500 return z-score is strongly positive (`spx_ret_z > 1.0`), volume heat is positive (`current_ihi > 0.1`), and MLP probability is positive (`mlp_prob > 0.4`).
   - **Impact**: Bypasses Brier Score penalties entirely (`calibration_penalty = 1.0`) and applies an aggressive **1.25x momentum multiplier** to follow trend breaks.

### C. Self-Calibration & Delayed Retail Noise Filter
- **Delayed Calibration**: Tracks historical forecasts against actual forward SPX returns using a **5-bar delayed grading window** (`run_self_calibration` in `fetch_market_data.py`).
- **Dynamic Brier Score**: Dynamically calculates the calibration penalty, functioning as a real-time filter to reduce trade size when model forecasting accuracy degrades.

---

## 3. Dual-Asset Kelly Portfolio Sizing

The `RiskEngine` has been upgraded from single-asset equity sizing to a robust **Dual-Asset Allocation System** that manages Equities, Safe Havens, and Cash:
* **SPX Kelly Sizing**: Calculates target equity exposure. Sizing is governed by Brier scores, regime half-lives, and dynamic overrides.
* **Safe Haven Overlay**: If the inferred HMM regime is `CRISIS_DISLOCATION` or `DEFLATION_FEAR` and equity Kelly size drops below 20% (`SPX_Kelly < 0.2`), the system dynamically redirects capital to gold and bond overlays:
  $$\text{Safe\_Haven\_Kelly} = 1.0 - \text{SPX\_Kelly}$$
* **Cash Allocation**: The remaining portfolio balance is placed in cash:
  $$\text{Cash} = 1.0 - \text{SPX\_Kelly} - \text{Safe\_Haven\_Kelly}$$
* **Snapshot Schema**: Returns a type-safe nested dictionary: `{"SPX_Kelly": spx_kelly, "Safe_Haven_Kelly": safe_haven_kelly, "Cash": cash}`.

---

## 4. Phase 2 Live Telemetry Engine

To support external dashboards and real-time monitoring interfaces, the orchestrator compiles and writes a structured live telemetry file on pipeline completion:
* **Path**: `/Users/mac/agent/data/live_telemetry.json`
* **JSON Payload**:
  ```json
  {
    "timestamp_utc": "2026-06-01T09:03:00Z",
    "dominant_regime": "RISK_ON_EXPANSION",
    "spx_kelly_fraction": 0.85,
    "safe_haven_kelly_fraction": 0.0,
    "is_capitulation_override_active": false,
    "institutional_heat_index": 0.12
  }
  ```

---

## 5. Statistical & Ingestion Upgrades

### A. Dynamic Rolling Windows by Interval
Statistical z-score calculations in `feature_engine.py` adapt dynamically to the operational interval of the conductor:
* **Baseline**: Calibrated to match a standard **3 macro months (60 trading days)** lookback window.
* **Daily Ingestion**: Sets window size to `60` daily bars.
* **Hourly Ingestion (e.g. 4h)**: Calculates bars per day based on 6.5 trading hours per day (390 mins). For `4h`, sets window to `int(60 * 1.625) = 97` bars.
* **Weekly Ingestion**: Sets window to `int((60 / 5) / weeks) = 12` weekly bars.

### B. Uniform HMM Start Probabilities
- Before scoring samples, the `HMMEngine` dynamically enforces a uniform start probability distribution across components:
  $$\text{startprob\_} = \frac{1.0}{N}$$
  This regularizes single-bar posterior inferences and prevents degenerate state traps in low-sample environments.

---

## 6. Multi-Asset Presenters & Compilation

Presenters have been overhauled to display dual-asset portfolio weights:
* **Brutalist Markdown Reports (`build_report.py`)**: Renders Safe Haven and SPX allocations directly in brutalist text tables (e.g., `Scale SPX to 60.0%. Safe Haven: 40.0%.`).
* **Notebook analytics (`visualize_math_4h.ipynb`)**: Graphing and visualization blocks extract multi-asset allocations to render dual-curve transition maps.
* **CLI Custom Intervals**:
  - Main 4-Hour Briefing (`run_4h.sh`): Executes conductor utilizing `4h` intervals.
  - Sunday Weekly Synthesis (`run_weekly.sh`): Executes conductor utilizing `1wk` intervals.
