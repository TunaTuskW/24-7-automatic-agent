# Macro Briefing Agent v4.5.0: Enterprise Architecture Manual

This manual details the upgrades in **v4.5.0 Enterprise Architecture**, describing the structural decoupling, modular interfaces, adapters, partitioned data lake, quantitative engines, and structured logging.

---

## 1. Architectural Blueprint & Decoupling

Following the v4.5.0 upgrade, the codebase is refactored from a monolithic signal layout into a highly decoupled, modular quantitative pipeline. This structure enforces separation of concerns, strict type safety, and clean extension boundaries.

```
src/
├── interfaces/         # Core Interface Contracts (Abstract Base Classes)
│   ├── data_broker.py
│   └── llm_provider.py
├── adapters/           # Input Data & External API Fetchers (Adapter Pattern)
│   ├── yahoo_adapter.py
│   └── gemini_adapter.py
├── data_lake/          # Enterprise Partitioned Storage Engine
│   └── lake_manager.py
├── engines/            # Mathematical, Statistical & Deep Learning Engines
│   ├── feature_engine.py
│   ├── hmm_engine.py
│   └── risk_engine.py
├── observability/      # Standardized Contextual Logging Framework
│   └── logger.py
└── fetch_market_data.py # Conductor / Central Dependency Injection Orchestrator
```

---

## 2. Component Breakdown

### A. Observability & Logging Layer (`src/observability/logger.py`)
- **Dynamic Context Tracing:** Utilizes a custom `ComponentFilter` to dynamically append the `component` name (e.g., `conductor`, `lake-manager`, `yahoo-adapter`) to every log record.
- **Dual-Channel Output:**
  - **Console:** Highly legible human-readable prints formatted as: `YYYY-MM-DD HH:MM:SS - [component] LEVEL - Message`.
  - **JSONL (Structured Log):** Appends structured JSON logs to `data/logs/system_events.jsonl` with keys: `timestamp`, `level`, `component`, and `message`. This supports robust monitoring and downstream log parsing.

### B. Enterprise Data Lake (`src/data_lake/lake_manager.py`)
- **Daily Partitioning:** Organizes and writes all ingested and generated data under a standard temporal structure: `data/raw/YYYY/MM/DD/`.
- **Schema Protection:** Automatically flattens complex `pandas.MultiIndex` columns into a single `Ticker_Metric` flat string layout before saving to maintain strict Apache Parquet schema compatibility.
- **Dual-Storage Formats:**
  - **Tabular Data:** Employs `.save_tabular(df, filename)` to serialize dataframes directly to highly compressed `.parquet` formats via `pyarrow`.
  - **Unstructured Data:** Employs `.save_unstructured(dict, filename)` to log runtime dict states, snapshots, and news indicators directly into `.jsonl` appends.

### C. Interfaces Layer (`src/interfaces/`)
- Enforces strict OOP encapsulation and contract design:
  - **`DataBroker`:** Abstract contract defining `fetch_ohlcv_daily()`, `fetch_ohlcv_hourly()`, and `fetch_yield()`.
  - **`LLMProvider`:** Abstract contract defining `parse_news()` to ensure alternative LLM models can easily swap in.

### D. Adapters Layer (`src/adapters/`)
- Implements the interface contracts to interact with external providers:
  - **`YahooAdapter` (`DataBroker`):** Handles threaded multi-asset daily and hourly historical data downloads using `yfinance`, and parses interest rate yields from the Federal Reserve Economic Data (FRED) API.
  - **`GeminiAdapter` (`LLMProvider`):** Implements a JSON-constrained client calling Google GenAI (`gemini-2.5-pro`) to semantically score news headlines for shock boundaries (`geopolitical_shock_magnitude` and `liquidity_drain_probability`).

### E. Mapped Engines Layer (`src/engines/`)
- Isolates all mathematical calculations, statistical filters, and neural inferences:
  - **`feature_engine.py`:** Calculates structural asset metrics (moments, slopes, z-scores), GARCH(1,1) conditional volatility boundaries, composite Macro Condition Scores (MCS), volume heat indicators, and cryptographic hash-chain signatures (`TruChain`).
  - **`hmm_engine.py` (`HMMEngine`):** Loads saved Gaussian Hidden Markov Models to run real-time inference on daily and hourly features vectors to output underlying regime probability distributions.
  - **`risk_engine.py` (`RiskEngine`):** Updates structural states via Kalman Filters, computes epistemic uncertainty limits using Shannon Entropy, and calculates Fractional Kelly exposure sizing with duration decay penalties.

---

## 3. Conductor Orchestration & Dependency Injection

The pipeline orchestrator (`src/fetch_market_data.py`) has been upgraded to a **Conductor Pattern** featuring comprehensive **Dependency Injection**. It instantiates all required adapters and engines, injecting them into the execution flow rather than relying on hardcoded global states.

### Operational Sequence:
1. **Instantiation & Injection:** Conductor loads API keys, initializes `YahooAdapter`, `GeminiAdapter`, `LakeManager`, `HMMEngine`, and `RiskEngine`.
2. **ETL Phase:** Extracts daily and hourly asset data, saving raw snapshots directly to the Data Lake as partitioned Parquet tables (`raw_daily_ohlcv.parquet` and `raw_hourly_ohlcv.parquet`).
3. **Feature Construction:** Executes `FeatureEngine` computations to compute GARCH, MCS, Volume Heat, and assemble the 10-dimensional feature vector.
4. **regime Inference:** Feeds the feature vector to `HMMEngine` and `MLPClassifier` (supervised model) to identify market conditions.
5. **State Tracking & Risk Sizing:** Executes the Kalman Filter in `RiskEngine` using the previous snapshot from `data/market_snapshot_prior.json`, computes entropy limits, and calculates the calibrated portfolio exposure using Fractional Kelly.
6. **LLM News Processing:** Fetches market headlines and calls `GeminiAdapter` to score geopolitical shock limits.
7. **Consensus Compiler & Lake Log:** Compiles the complete state dataset, exports it to `data/market_snapshot.json` for compilation scripts, and persists the raw state JSON to the Data Lake as a daily partitioned `market_snapshot.jsonl` record.
