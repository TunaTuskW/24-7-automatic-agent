# Macro Briefing Agent - v3.2.0 Patch Notes

## Core Architectural Shift: Algorithmic Synthesis
- **API Dependency Removed:** Completely stripped the Gemini LLM integration from `build_report.py`. The agent no longer makes external network calls to generate the qualitative synthesis, eliminating API key requirements, quota limits, and potential `403/429` network failures.
- **Purely Deterministic Logic:** The agent now computes the `Directional Lean` and `Positioning` instantly using a strict algorithmic decision tree (`compute_deterministic_synthesis`). This tree mathematically evaluates the Kalman filter's `dominant_state`, the `Brier Score`, and the `Volume Heat` metrics to formulate a consistent, data-driven synthesis.

## Algorithmic Governance Rules (v3.2.0)
- **High Entropy Fail-Safe:** If `Brier Score > 0.25` or `TVD > 0.10`, the algorithm explicitly forces a `LOW CONFIDENCE` override on the directional lean and mandates a "Reduce position sizing" warning.
- **Overheated Cascade Protection:** If Market Temperature is `OVERHEATED` and Trade Crowdedness is `LONG_TRADE_TOO_CROWDED`, the algorithm automatically pivots to a "Mean Reversion (Bearish Bias)" and advises capping long exposure to avoid a liquidation cascade.
- **Capitulation Bottom Detection:** If Market Temperature is `ICE_COLD` and Volume Heat detects `INSTITUTIONAL_ACCUMULATION`, the algorithm automatically triggers a "Capitulation Bottom (Bullish Bias)" signaling institutional absorption of retail panic.
- **Retail Divergence:** If the core model signals `RISK_ON` but the volume heat shows `INSTITUTIONAL_DISTRIBUTION`, the algorithm flags the retail drift and advises tightening trailing stops.
