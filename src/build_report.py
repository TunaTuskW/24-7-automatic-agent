#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone

def read_api_key():
    key_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'gemini_api_key.txt')
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("paste"):
                return key
    return None

def generate_llm_report(data, api_key, timestamp_str, session, tier):
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are an institutional macro analyst.
Generate the 4-hour macro update based on the following raw JSON data:
{json.dumps(data, indent=2)}

Use this header exact format:
## {timestamp_str} — {session} — {tier}

Write the report following strict institutional guidelines. Include:
1. Headline Block
2. Asset Dashboard (MCS, Regime, Bayesian State)
3. Data Observation
4. Market Implication
5. Narrative Continuity
6. Risk Flags (Primary and Secondary)
7. Forward Look
8. Carry-Forward
"""
        response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
        return response.text
    except Exception as e:
        print(f"LLM Generation failed: {e}. Falling back to deterministic template.")
        return None

def main():
    snapshot_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    if not os.path.exists(snapshot_path):
        print(f"Error: {snapshot_path} not found. Run fetch_market_data.py first.")
        return

    with open(snapshot_path, 'r') as f:
        data = json.load(f)

    # Extract required fields
    generated_utc = data.get("generated_utc", datetime.now(timezone.utc).isoformat())
    dt = datetime.fromisoformat(generated_utc)
    timestamp_str = dt.strftime("%Y-%m-%d %H:%M UTC")

    mcs_score = data.get("mcs", {}).get("score", 0)
    mcs_label = data.get("mcs", {}).get("label", "UNKNOWN")
    regime = data.get("regime", {}).get("current", "UNKNOWN")
    
    kalman = data.get("kalman_state", {})
    dominant_state = kalman.get("dominant_state", "unknown")
    dominant_prob = kalman.get("dominant_prob", 0) * 100

    tier = data.get("data_driven_escalation", "ROUTINE")

    spx_pct = data.get("equities", {}).get("SPX", {}).get("delta_pct", 0)
    spx_sign = "+" if spx_pct >= 0 else ""
    
    us10y = data.get("bonds", {}).get("US10Y", {}).get("current", 0)
    
    wti_pct = data.get("energy", {}).get("WTI", {}).get("delta_pct", 0)
    wti_sign = "+" if wti_pct >= 0 else ""

    sub = data.get("mcs", {}).get("sub_components", {})
    eq_mom = sub.get("equity_momentum", 0)
    rate_pres = sub.get("rate_pressure", 0)
    energy_stress = sub.get("energy_stress", 0)
    coherence = sub.get("cross_asset_coherence", 0)

    risk_on = kalman.get("risk_on", 0) * 100
    risk_off = kalman.get("risk_off", 0) * 100
    transitional = kalman.get("transitional", 0) * 100

    session = "US Session"
    if 0 <= dt.hour < 8:
        session = "Asian Session"
    elif 8 <= dt.hour < 14:
        session = "European Session"

    report_content = None
    api_key = read_api_key()
    
    if api_key:
        print("API Key found. Attempting LLM generation...")
        report_content = generate_llm_report(data, api_key, timestamp_str, session, tier)

    # Deterministic Fallback
    if not report_content:
        print("Using deterministic template.")
        # Enhanced Conditional Logic
        risk_flag_text = "Spikes in US10Y or significant drops in SPX beyond 1 standard deviation."
        implication_text = f"The current MCS of {mcs_score} indicates a {mcs_label} environment."
        
        if mcs_score < -20:
            risk_flag_text = "ELEVATED SYSTEMIC RISK. Cross-asset momentum is heavily skewed negatively."
            implication_text = "Deep contractionary phase detected. Extreme caution warranted for risk assets."
        elif tier == "CRITICAL":
            risk_flag_text = "CRITICAL ESCALATION. Market pricing implies acute structural stress."

        report_content = f"""## {timestamp_str} — {session} — {tier}
**MCS:** {mcs_score} ({mcs_label}) | **Regime:** {regime} [HMM]
**State:** {dominant_state} ({dominant_prob:.1f}%)
**Sources:** Reuters, Bloomberg, FRED

-----------------------------------------------
[ {tier} ] {timestamp_str} — {session}
Sentiment: {dominant_state.upper()} | SPX {spx_sign}{spx_pct}% | US10Y {us10y} | WTI {wti_sign}{wti_pct}%
Key: Automated routine snapshot based on deterministic market data.
-----------------------------------------------

a. SESSION TAG — {session}.

b. ASSET DASHBOARD
MCS SUMMARY
MCS: {mcs_score} — {mcs_label} | Regime: {regime}
Sub-components:
- Equity momentum: {eq_mom}
- Rate pressure: {rate_pres}
- Energy stress: {energy_stress}
- Cross-asset coherence: {coherence}

BAYESIAN STATE — Report on one line:
State distribution: Risk-On {risk_on:.1f}% | Risk-Off {risk_off:.1f}% | Transitional {transitional:.1f}%
Dominant: {dominant_state} ({dominant_prob:.1f}%)

CROSS-ASSET CHECK
No cross-asset flags this cycle (Automated).

c. DATA OBSERVATION
Equities (SPX: {spx_sign}{spx_pct}%), Bonds (US10Y: {us10y}%), Energy (WTI: {wti_sign}{wti_pct}%). This is an automated observation derived directly from the market_snapshot.json data payload.

d. MARKET IMPLICATION
{implication_text} Assets are exhibiting a {dominant_state} momentum.

e. NARRATIVE CONTINUITY
This automated update continues to track the {regime} regime identified by the HMM.

f. RISK FLAGS
PRIMARY RISK: {risk_flag_text}

g. FORWARD LOOK
Monitoring for regime shifts or sudden spikes in cross-asset volatility.

h. CARRY-FORWARD
- Track US10Y levels.
- Monitor SPX momentum.
"""

    report_filename = f"4 hours update ({timestamp_str}).md"
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports', 'updates')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, report_filename)

    with open(report_path, 'w') as f:
        f.write(report_content)
    print(f"Generated {report_filename} successfully.")

    # Append to weekly log
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'macro_weekly_log.md')
    
    log_entry = f"{timestamp_str} | {session} | {dominant_state.upper()} | {tier} | Automated deterministic snapshot recorded.\n"
    if api_key and report_content and "Key:" in report_content:
        # Try to extract the key headline from the LLM text
        import re
        match = re.search(r"Key:\s*(.*)", report_content)
        if match:
            key_text = match.group(1).strip()
            log_entry = f"{timestamp_str} | {session} | {dominant_state.upper()} | {tier} | {key_text}\n"

    with open(log_path, 'a') as f:
        f.write(log_entry)

    # Call push_to_discord
    push_script = os.path.join(os.path.dirname(__file__), 'push_to_discord.py')
    os.system(f'python3 "{push_script}" "{report_path}" "{tier}"')

if __name__ == "__main__":
    main()
