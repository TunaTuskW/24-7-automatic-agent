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

def generate_llm_synthesis(data, api_key, timestamp_str, log_content):
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are a global macro analyst writing the Weekly Macro Synthesis.
Here is the raw quantitative JSON snapshot for the end of the week:
{json.dumps(data, indent=2)}

Here is the log of all developments across the past 7 days:
{log_content}

Synthesize this data into a professional weekly institutional report.
Use the following strict structure:
# Weekly Macro Synthesis
**Date:** {timestamp_str}

## a. WEEK TAG
## b. REGIME SUMMARY
## c. ASSET PERFORMANCE
## d. KEY DEVELOPMENTS (Synthesize the log into 3 major bullet points)
## e. REGIME FLAGS
## f. WEEK AHEAD (Identify key risks and what data to watch)
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

    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%d UTC")
    
    log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'macro_weekly_log.md')
    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            log_content = f.read()

    report_content = None
    api_key = read_api_key()
    
    if api_key:
        print("API Key found. Attempting LLM weekly synthesis...")
        report_content = generate_llm_synthesis(data, api_key, timestamp_str, log_content)

    if not report_content:
        print("Using deterministic template.")
        # A simple weekly deterministic template
        template = f"""# Weekly Macro Synthesis
**Date:** {timestamp_str}

## a. WEEK TAG
**Dominant Session Character:** Transitional / Data-Driven (Automated Snapshot)

## b. REGIME SUMMARY
This automated weekly synthesis confirms the current market regime as **{data.get('regime', {}).get('current', 'UNKNOWN')}**.
The current Macro Condition Score (MCS) rests at {data.get('mcs', {}).get('score', 0)}, maintaining a {data.get('mcs', {}).get('label', 'UNKNOWN')} stance.

## c. ASSET PERFORMANCE (Snapshot)
- **SPX:** {data.get('equities', {}).get('SPX', {}).get('current', 'N/A')} ({data.get('equities', {}).get('SPX', {}).get('delta_pct', 0)}%)
- **US10Y:** {data.get('bonds', {}).get('US10Y', {}).get('current', 'N/A')}%
- **WTI:** {data.get('energy', {}).get('WTI', {}).get('current', 'N/A')} ({data.get('energy', {}).get('WTI', {}).get('delta_pct', 0)}%)

## d. KEY DEVELOPMENTS
*Automated reporting relies on the real-time data ingestion module. No qualitative human-in-the-loop developments are manually injected into this deterministic summary.*

## e. REGIME FLAGS
The Bayesian state estimator places the highest probability on **{data.get('kalman_state', {}).get('dominant_state', 'unknown')}** ({data.get('kalman_state', {}).get('dominant_prob', 0)*100:.1f}%). 

## f. WEEK AHEAD
Continued monitoring of the SPX conditional volatility (currently {data.get('garch_layer', {}).get('SPX', {}).get('vol_regime', 'UNKNOWN')}) will be critical to establishing whether this regime persists or breaks down.
"""
        report_content = template

    report_filename = f"macro weekly synthesis ({timestamp_str}).md"
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, report_filename)

    with open(report_path, 'w') as f:
        f.write(report_content)

    print(f"Generated {report_filename} successfully.")

    # Call push_to_discord
    push_script = os.path.join(os.path.dirname(__file__), 'push_to_discord.py')
    os.system(f'python3 "{push_script}" "{report_path}"')

if __name__ == "__main__":
    main()
