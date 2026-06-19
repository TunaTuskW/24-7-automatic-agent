import sys

with open("src/engines/risk_engine.py", "r") as f:
    content = f.read()

# Remove the gate from the current position
gate_block = """        # Universal Equity Regime Gate
        # Kalman risk_off or black swan: zero ALL single-name long equity.
        # SPX is already handled above via is_downtrend. This extends to all names.
        if dominant_state == "risk_off" or is_black_swan:
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
            if dominant_state == "risk_off":
                btc_kelly = round(btc_kelly * 0.30, 3)
            logger.warning(
                f"Regime Gate: dominant_state={dominant_state}. "
                "All single-name long equity zeroed."
            )

        # HMM Coherence Gate
        # If HMM explicitly names a stress regime, single names are forbidden.
        STRESS_REGIMES = {
            "STAGFLATION_STRESS", "RATE_SHOCK", "DEFLATION_FEAR",
            "CRISIS_DISLOCATION", "VOLATILITY_EXPANSION", "COMMODITY_SHOCK"
        }
        if any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
            logger.warning(f"HMM Coherence Gate: {hmm_regime}. Single-name equity zeroed.")"""

content = content.replace(gate_block, "")

# Insert it right before the Global Portfolio Balancer
insert_target = "        # Global Portfolio Balancer (Normalize exposure)"
content = content.replace(insert_target, gate_block + "\n\n" + insert_target)

with open("src/engines/risk_engine.py", "w") as f:
    f.write(content)
