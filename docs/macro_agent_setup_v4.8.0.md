# Macro Briefing Agent v4.8.0: Mixture of Experts & CoT OS Manual

This manual details the upgrades in **v4.8.0 (Mixture of Experts & CoT OS)**, transforming the agent into a containerized **Multimodal Global Macro Mixture of Experts (MoE) OS** featuring parallel LLM pipelines, Chain-of-Thought (CoT) reasoning verification, capital defense divergence triggers, and streamlined cron schedules.

---

## 1. Architectural Blueprint & Decoupling

Following the v4.8.0 upgrades, the system operates as a fully event-driven, MoE pub-sub architecture orchestrated via Pydantic model schemas:

```
src/
├── interfaces/         # Core Interface Contracts (Abstract Base Classes)
│   ├── data_broker.py
│   └── llm_provider.py  <-- MoE Abstract Expert Contracts
├── adapters/           # Input Data & External API Fetchers (Adapter Pattern)
│   ├── yahoo_adapter.py  <-- Auto yfinance Yield Fallbacks
│   ├── gemini_adapter.py <-- gemini-2.5-flash MoE Parallel CoT Experts
│   └── forexfactory_adapter.py <-- Ingests High-Impact economic calendars
├── data_lake/          # Enterprise Partitioned Storage Engine
│   └── lake_manager.py <-- Event Logger Interceptor & Parquet/JSONL
├── engines/            # Mathematical, Statistical & Deep Learning Engines
│   ├── feature_engine.py
│   ├── hmm_engine.py
│   ├── risk_engine.py
│   └── consensus_engine.py <-- Synthesizes MoE outputs & Divergence checks
├── observability/      # Standardized Contextual Logging Framework
│   ├── logger.py
│   └── event_bus.py      <-- Pub-Sub Event Dispatcher
├── schemas/            # Strict Type Validation Layer
│   └── models.py         <-- Pydantic Data Structures (MarketSnapshot, etc.)
└── fetch_market_data.py # Conductor / Central Dependency Injection Orchestrator
```

---

## 2. Mixture of Experts (MoE) & Chain-of-Thought (CoT)

The core cognitive layer of the agent has been upgraded from a single text parser to a multi-expert neural-symbolic synthesis framework:

### A. Parallel LLM Experts
Using a `ThreadPoolExecutor`, the `Conductor` executes two independent specialized expert pipelines concurrently:
1. **Macro Policy Expert (`run_macro_policy_expert`):** 
   - **Inputs:** RSS financial headlines, Forex Factory USD/EUR/JPY High-Impact economic calendar events, and the current 2s10s Treasury yield spread.
   - **Outputs:** An analytical reasoning text block and a rate-hike probability score (`fed_policy_hawkishness_prob`).
2. **Market Psychology Expert (`run_market_psychology_expert`):**
   - **Inputs:** RSS financial headlines, the VIX z-score, and volume activity heat.
   - **Outputs:** An analytical reasoning text block, a fear/greed sentiment score (`fear_greed_sentiment_score`), and a quantitative divergence flag.

### B. Chain-of-Thought (CoT) Prompt Verification
To guarantee empirical justification and prevent LLM hallucinations, both experts are bound by a rigid **CoT Rule**:
- The model MUST write **exactly 3 sentences** of step-by-step reasoning explaining how the quantitative context justifies its conclusion *before* outputting the final probability score. This reasoning is outputted directly within the Pydantic JSON structure:
  ```json
  {
    "reasoning": "Sentence 1 of mathematical justification. Sentence 2 mapping indicator deltas. Sentence 3 outlining macro expectation.",
    "fed_policy_hawkishness_prob": 0.78
  }
  ```

### C. Consensus & Divergence Engine (`src/engines/consensus_engine.py`)
The `ConsensusEngine` consolidates reasoning and scores from both experts into a single unified `NewsSignal`:
- **Combined CoT Reasoning:** Merges the Macro and Psychology CoT blocks into a unified `[ MoE REASONING ]` text block.
- **Critical Capital Defense Slasher:** If the news headlines are extremely bullish, but the VIX z-score spikes > 1.5, the Psychology Expert sets `quantitative_divergence_flag: true`. The `ConsensusEngine` catches this narrative-reality divergence and dynamically **slashes Kelly target exposure by half (0.5x multiplier)** to protect trading capital.

---

## 3. High-Impact Economic Ingestion (`src/adapters/forexfactory_adapter.py`)

- **Economic Calendaring:** Ingests weekly High-Impact economic calendar events for USD, EUR, and JPY currencies from the Forex Factory API.
- **Schema Protection:** Parses and validates calendar data directly into type-safe Pydantic models: `EconomicCalendar` and `EconomicEvent`, which are appended directly to the main `MarketSnapshot`.

---

## 4. Visualizer & Report Integration

Both report compilation engines and interactive Jupyter environments have been upgraded to extract, format, and display the MoE Chain-of-Thought reasoning blocks:

- **`build_report.py` & `build_weekly_synthesis.py`:** Adds the `Quant Divergence` status and `[ MoE REASONING ]` step-by-step logical synthesis blocks directly into the Brutalist Markdown report.
- **Jupyter Notebooks (`visualize_math_4h.ipynb` & `visualize_math_1w.ipynb`):** Renders the MoE reasoning text and divergence metrics in polished Markdown blocks natively within your IDE.

---

## 5. Streamlined Cron Scheduling

To keep the agent lean and focused on high-priority session briefings and weekly syntheses, the daily 72-hour roll engine (`src/build_72h_roll.py` and `run_daily.sh` cron job) has been **completely removed**. The cron scheduler now runs exclusively on the **4-Hour Briefing (`run_4h.sh`)** and **Sunday Synthesis (`run_weekly.sh`)**:

```cron
# 1. Main 4-Hour Briefing (Runs past every 4th hour)
0 */4 * * * /Users/mac/agent/run_4h.sh >> /Users/mac/agent/logs/cron.log 2>&1

# 2. Weekly Synthesis (Runs every Sunday at 08:00 UTC)
0 8 * * 0 /Users/mac/agent/run_weekly.sh >> /Users/mac/agent/logs/cron.log 2>&1
```

---

## 6. Containerized Docker Deployment

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
1. Define your API keys in your shell or `.env` file:
   ```bash
   export GEMINI_API_KEY="your_gemini_key_here"
   export FRED_API_KEY="your_fred_key_here"
   ```
2. Build and run the container:
   ```bash
   docker-compose up --build
   ```
The container will execute the event-driven quantitative Conductor pipeline, log event bus cycles to your mapped local `/data` and `/reports` folders, and terminate cleanly.
