# Macro Briefing Agent - v3.5.0 Patch Notes

## The Epistemic Sizing Update
The system has been completely upgraded to utilize mathematically rigorous Epistemic Sizing rather than binary probability cutoffs. This effectively solves the previous structural paradox where the agent would abstain from predicting anything under a 60% probability, despite the mathematical random-chance baseline in a 3-regime system sitting at 33.3%.

### Features Implemented:
- **Shannon Entropy Measurement:** The `fetch_market_data.py` layer now calculates the pure information entropy of the Kalman probability array. The maximum entropy for a 3-state system is ~1.58 (indicating complete statistical chaos/noise).
- **Fractional Kelly Sizing:** The core mathematical engine now utilizes a modified Fractional Kelly Criterion. Instead of asking "Is this a valid trade?", it asks "How large is our statistical edge over random chance?". This edge dynamically scales the position size. If the agent's dominant probability drops to 40%, it no longer "aborts"—it calculates an aggressive but mathematically optimal ~13.3% position sizing.
- **Brier Calibration Penalty:** The Kelly Fraction dynamically penalizes its exposure output based on the Brier Score Calibration. A degraded model automatically slashes the Kelly fraction to zero.
- **Dynamic Deterministic Synthesis:** The local algorithmic logic engine inside `build_report.py` now receives the Epistemic Payload from the data layer and outputs exact mathematical sizing recommendations based on the Fractional Kelly sizing (e.g., "Scale exposure to exactly 14.5% of maximum capital"). The `NO PREDICT` fallback now only triggers if Kelly outputs exactly `0.0%` or if Shannon Entropy exceeds `1.50` (near-pure chaos).
