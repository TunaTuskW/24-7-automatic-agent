# Macro Briefing Agent v4.7.0: Multimodal Global Macro OS Manual

This manual details the upgrades in **v4.6.0 (Global Macro Pivot)** and **v4.7.0 (Multimodal LLM Synthesis)**, transforming the agent into a containerized **Multimodal Global Macro OS** with strong type validation, automated API fallbacks, and aggressive leverage sizing.

---

## 1. Architectural Blueprint & Decoupling

Following the v4.7.0 upgrades, the system operates as an event-driven pub-sub architecture orchestrated via Pydantic model schemas:

```
src/
├── interfaces/         # Core Interface Contracts (Abstract Base Classes)
│   ├── data_broker.py
│   └── llm_provider.py
├── adapters/           # Input Data & External API Fetchers (Adapter Pattern)
│   ├── yahoo_adapter.py  <-- Auto yfinance Yield Fallbacks
│   └── gemini_adapter.py <-- gemini-2.5-flash Multimodal Prompt Synthesis
├── data_lake/          # Enterprise Partitioned Storage Engine
│   └── lake_manager.py <-- Event Logger Interceptor & Parquet/JSONL
├── engines/            # Mathematical, Statistical & Deep Learning Engines
│   ├── feature_engine.py
│   ├── hmm_engine.py
│   └── risk_engine.py    <-- Pydantic Kalman & 1.2x Kelly Sizing
├── observability/      # Standardized Contextual Logging Framework
│   ├── logger.py
│   └── event_bus.py      <-- Pub-Sub Event Dispatcher
├── schemas/            # Strict Type Validation Layer
│   └── models.py         <-- Pydantic Data Structures (MarketSnapshot, etc.)
└── fetch_market_data.py # Conductor / Central Dependency Injection Orchestrator
```

---

## 2. Component Overhaul Details

### A. The Pub-Sub Event Bus (`src/observability/event_bus.py`)
- Standardizes in-memory communication using decoupled event publish/subscribe patterns.
- Orchestrates the conductor lifecycle through five distinct sequential events:
  1. `SystemStart`: Conductor begins operations, initializing logging contexts.
  2. `DataFetched`: Adapters complete multi-asset and bond yield extraction.
  3. `FeaturesEngineered`: FeatureEngine constructs stats, GARCH, and 10D feature vector.
  4. `EnginesCompleted`: HMMEngine runs inference and RiskEngine computes updated Kalman states.
  5. `PipelineComplete`: Snapshot is generated, signed via TruChain, and saved.

### B. Global Event Logging Interceptor (`src/data_lake/lake_manager.py`)
- Enforces an immutable audit log by intercepting every fired event.
- The `LakeManager.log_event()` method intercepts the payloads, extracts Pydantic parameters, serializes them, and appends them to a daily partitioned log: `data/raw/YYYY/MM/DD/events.jsonl`.
- Decoupled report compilers (`src/build_report.py`, `src/build_weekly_synthesis.py`) read directly from this log for `PipelineComplete` event payloads rather than raw static files.

### C. Strict Pydantic Data Schemas (`src/schemas/models.py`)
- Employs strict type validation utilizing Pydantic v2.0+ models:
  - **`NewsSignal`**: Holds central bank bias, qualitative sentiment labels, and conviction.
  - **`RegimeState`**: Mapped probabilities, tactical alpha regimes, start timestamps, and duration.
  - **`KalmanState`**: Dominant probability indices, covariance matrices, and model Total Variation Distance (TVD).
  - **`MarketSnapshot`**: The master validation model containing the entire pipeline state.

### D. Automated Yield Fallback Logic (`src/adapters/yahoo_adapter.py`)
- Protects execution flow from missing or unreliable Federal Reserve Economic Data (FRED) API keys.
- **Yahoo Finance Fallbacks:** If the FRED key is missing or calls fail, `YahooAdapter.fetch_yield` dynamically falls back to pulling Treasury proxy yields directly from Yahoo Finance:
  - `DGS10` (10-Year Treasury Yield) -> `^TNX` (10-Year Treasury Note Index proxy)
  - `DGS2` (2-Year Treasury Yield) -> `^FVX` (5-Year Treasury Note Index proxy fallback)

### E. Aggressive Kelly Sizing & Contraction Slasher (`src/engines/risk_engine.py`)
- **1.2x Aggressive Sizing:** Elevates Kelly exposure limits from 1.0 (100%) to 1.2 (120% target portfolio exposure) when market sentiment is highly bullish (`LONG` signal, >0.75 sentiment) during a structural expansion regime (`RISK_ON_EXPANSION`).
- **0.5x Contraction Slasher:** Instantly slashes Kelly sizing exposure by half (0.5x multiplier) if global news signals a `SHORT` position due to global rate shocks or severe economic contractions.

---

## 3. Multimodal Prompt & Free-Tier Optimization

### A. Quantitative Data Injection (`src/adapters/gemini_adapter.py`)
- Upgrades the LLM from a text-only news parser to a **Multimodal Synthesis Engine**.
- The Conductor streams the entire structured quantitative metadata (`self.feature_metadata`)—including asset momentum z-scores, yield shifts, volatility spreads, and volume indices—directly into the Gemini prompt payload alongside the unstructured RSS news headlines.

### B. Gemini prompt Overhaul
The custom prompt forces Gemini to verify qualitative news narratives against hard quantitative market realities:
- Outputs strictly structured JSON with: `global_macro_sentiment_score` and `fed_policy_hawkishness_prob`.
- Activates a `SHORT` signal (conviction-weighted) if the Federal Reserve policy Hawkishness sweeps past **0.75**, raising the `RATE_SHOCK` impact alert.

### C. Free-Tier Optimization
- Replaced `gemini-2.5-pro` with **`gemini-2.5-flash`**.
- This model shift provides ultra-low latency execution and gracefully avoids **HTTP 429 quota exhaustion errors** on free-tier API accounts while maintaining robust mathematical and semantic synthesis precision.

---

## 4. Containerized Docker Deployment

The OS is fully containerized to run in isolated microservice environments:

### `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["python3", "src/fetch_market_data.py"]
```

### `docker-compose.yml`
```yaml
version: '3.8'

services:
  quant_os:
    build: .
    container_name: quant_os
    environment:
      - FRED_API_KEY=${FRED_API_KEY:-}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
      - ./reports:/app/reports
    command: python3 src/fetch_market_data.py
```

### Running the Containerized OS
1. Export your API keys or define them in a `.env` file:
   ```bash
   export GEMINI_API_KEY="your_gemini_key_here"
   export FRED_API_KEY="your_fred_key_here"
   ```
2. Build and run the container:
   ```bash
   docker-compose up --build
   ```
The container will execute the event-driven quantitative Conductor pipeline, write outputs and event logs to your mapped local `/data` and `/reports` folders, and terminate cleanly.
