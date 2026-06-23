#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone, timedelta
import sys
import glob
import src.config_loader

sys.path.append(os.path.dirname(__file__))
from build_report import run_consensus_engine, compute_deterministic_synthesis

def read_api_key():
    key_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'gemini_api_key.txt')
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("paste"):
                return key
    return None

def fetch_30d_memory(reports_dir):
    """Fetches the last 30 days of 4-hour update markdown files and combines them."""
    log_content = ""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
    
    updates_dir = os.path.join(reports_dir, 'updates')
    if not os.path.exists(updates_dir):
        return "No historical 4h reports found."

    pattern = os.path.join(updates_dir, '4 hours update*.md')
    files = glob.glob(pattern)
    
    valid_files = []
    for f in files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f), tz=timezone.utc)
        if mtime >= cutoff_date:
            valid_files.append((mtime, f))
            
    # Sort chronologically
    valid_files.sort(key=lambda x: x[0])
    
    for mtime, fpath in valid_files:
        with open(fpath, 'r') as f:
            content = f.read()
            log_content += f"\n--- Report {mtime.strftime('%Y-%m-%d %H:%M UTC')} ---\n"
            log_content += content
            
    if not log_content:
        return "No historical 4h reports found within the last 30 days."
    return log_content

def generate_llm_synthesis(data, api_key, log_content):
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are a global macro analyst writing the Weekly Macro Synthesis.
Here is the raw quantitative JSON snapshot for the end of the week:
{json.dumps(data, indent=2)}

Here is the log of all 4-hour mathematical updates across the past 30 days (for reference checking and trend analysis):
{log_content}

Synthesize this data into a professional weekly institutional report. Do not repeat the mathematical matrix, focus purely on the written synthesis and narrative.
"""
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        print(f"LLM Generation failed: {e}. Falling back to deterministic template.")
        return None

def main():
    events_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    part_dirs = []
    if os.path.exists(events_path):
        for year in os.listdir(events_path):
            year_path = os.path.join(events_path, year)
            if not os.path.isdir(year_path): continue
            for month in os.listdir(year_path):
                month_path = os.path.join(year_path, month)
                for day in os.listdir(month_path):
                    day_path = os.path.join(month_path, day)
                    part_dirs.append(day_path)
    if not part_dirs:
        print("Error: No event data found.")
        return
    latest_part = sorted(part_dirs)[-1]
    events_file = os.path.join(latest_part, "events.jsonl")
    if not os.path.exists(events_file): return
    last_snapshot_payload = None
    import json
    with open(events_file, 'r') as f:
        for line in f:
            if not line.strip(): continue
            try:
                evt = json.loads(line)
                if evt.get("event_type") == "PipelineComplete":
                    last_snapshot_payload = evt.get("payload")
            except: pass
    if not last_snapshot_payload: return
    from src.schemas.models import MarketSnapshot
    snapshot = MarketSnapshot.model_validate(last_snapshot_payload)
    data = snapshot.model_dump()

    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%d UTC")
    
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    log_content = fetch_30d_memory(reports_dir)

    api_key = read_api_key()
    llm_synthesis_text = ""
    if api_key:
        print("API Key found. Attempting LLM weekly synthesis with 30-day memory...")
        llm_synthesis_text = generate_llm_synthesis(data, api_key, log_content) or ""

    # Always generate the mathematical matrix
    generated_utc = data.get("generated_utc", datetime.now(timezone.utc).isoformat())
    dt = datetime.fromisoformat(generated_utc)
    
    mcs_score = data.get("mcs", {}).get("score", 0.0)
    regime = data.get("regime", {}).get("current", "UNKNOWN")
    kalman = data.get("kalman_state", {})
    dominant_prob = kalman.get("dominant_prob", 0.0) * 100
    tvd_score = kalman.get("tvd", 0.0)
    brier_score = kalman.get("brier_score_calibration", 0.15)
    
    tier = data.get("data_driven_escalation", "ROUTINE")
    raw = data.get("raw_indicators", {})
    vol_heat = raw.get("volume_activity_heat") or {}
    part_type = vol_heat.get("participation_type", "UNKNOWN")
    ext = data.get("market_extremes_insight", {})
    
    spx_pct = (raw.get("SPX") or {}).get("delta_pct", 0.0)
    spx_sign = "+" if spx_pct >= 0 else ""
    us10y = data.get("bonds", {}).get("US10Y", {}).get("current", 0.0) if data.get("bonds", {}).get("US10Y") else 0.0
    wti_pct = (raw.get("WTI") or {}).get("delta_pct", 0.0)
    wti_sign = "+" if wti_pct >= 0 else ""
    vix_level = (raw.get("VIX") or {}).get("current", 0.0)
    dxy_level = (raw.get("DXY") or {}).get("current", 0.0)
    dxy_pct = (raw.get("DXY") or {}).get("delta_pct", 0.0)
    dxy_sign = "+" if dxy_pct >= 0 else ""
    gold_pct = (raw.get("Gold") or {}).get("delta_pct", 0.0)
    gold_sign = "+" if gold_pct >= 0 else ""
    copper_pct = (raw.get("Copper") or {}).get("delta_pct", 0.0)
    copper_sign = "+" if copper_pct >= 0 else ""
    btc_pct = (raw.get("BTC") or {}).get("delta_pct", 0.0)
    btc_sign = "+" if btc_pct >= 0 else ""
    btc_level = (raw.get("BTC") or {}).get("current", 0.0)
    
    def fmt_ticker(ticker_name):
        t_data = raw.get(ticker_name, {})
        if not t_data: return ""
        pct = t_data.get("delta_pct", 0.0)
        sign = "+" if pct >= 0 else ""
        return f"{ticker_name} {sign}{pct}%"

    eq_list = ["NDX", "DAX", "FTSE", "N225", "HSI", "SHANGHAI", "KOSPI", "TASI", "DFM"]
    eq_str = " | ".join(filter(None, [fmt_ticker(t) for t in eq_list]))
    fx_list = ["EURUSD", "GBPUSD", "JPYUSD", "CHFUSD", "USDCAD"]
    fx_str = " | ".join(filter(None, [fmt_ticker(t) for t in fx_list]))
    crypto_list = ["IBIT", "ETHA", "COIN"]
    crypto_str = " | ".join(filter(None, [fmt_ticker(t) for t in crypto_list]))

    credit = raw.get("credit_stress_proxy", {}) or {}
    credit_label = credit.get("label", "NORMAL")
    tactical = raw.get("tactical_setup", {}) or {}
    setup_name = tactical.get("matched_setup", "NONE")
    edge_prob = tactical.get("regime_conditioned_probability", 0.50) * 100
    
    epistemic = data.get("data_science_layer", {}).get("epistemic_metrics", {})
    news_signal = data.get("news_signal", {})
    
    direction, clean_count, news_impact = run_consensus_engine(kalman, vol_heat, ext, mcs_score, epistemic, news_signal, regime)
    synth = compute_deterministic_synthesis(kalman, vol_heat, ext, epistemic, direction, news_impact)
    
    divergence_str = "DETECTED" if news_signal.get("quantitative_divergence_flag", False) else "NONE"
    reasoning_str = news_signal.get("reasoning", "No CoT reasoning available.")
    
    math_matrix = f"""```text
[ WEEKLY MACRO SYNTHESIS ]
SPX {spx_sign}{spx_pct}% | DXY {dxy_level} | VIX {vix_level} | US10Y {us10y:.3f}% | WTI {wti_sign}{wti_pct}% | BTC {btc_sign}{btc_pct}%
[ ASSET DASHBOARD ]
- Equities: {eq_str}
- FX/Rates: {fx_str}
- Commodities: Gold {gold_sign}{gold_pct}% | Copper {copper_sign}{copper_pct}% | {fmt_ticker('Silver')}
- Crypto (Spot & Flows): BTC ${btc_level:,.0f} ({btc_sign}{btc_pct}%) | {crypto_str}
- Volatility: VIX {vix_level}
[ QUANTITATIVE MATRIX ]
SPX   | {spx_sign}{spx_pct}% | Heat: {part_type}
VIX   | {vix_level} | Temp: {ext.get('temperature_state', 'UNKNOWN')}
US10Y | {us10y:.3f}% | Crowd: {ext.get('crowded_state', 'UNKNOWN')}
DXY   | {dxy_level} ({dxy_sign}{dxy_pct}%) | Credit: {credit_label}
BTC   | {btc_level:,.0f} ({btc_sign}{btc_pct}%) | Crypto Flow: {(raw.get('institutional_crypto_mfi') or {}).get('flow_regime', 'UNKNOWN')}
[ SYSTEM HEALTH ]
Regime      : {regime}
Max Prob    : {dominant_prob:.1f}% 
Brier Score : {brier_score:.4f} ({'DEGRADED' if brier_score > 0.25 else 'CALIBRATED'})
Conflict    : {tvd_score:.4f} TVD
[ TACTICAL DIAGNOSTICS ]
> Edge Setup: {setup_name}
> Probability: {edge_prob:.1f}%
> Escalation: {tier}
> News Impact: {news_impact}
> Quant Divergence: {divergence_str}
[ MoE REASONING ]
{reasoning_str}
[ ALGORITHMIC SYNTHESIS ]
State       : {synth['market_state']}
Lean        : {synth['directional_lean']}
Positioning : {synth['positioning']}
Invalidation: {synth['invalidation']}
```
"""
    
    report_content = f"{math_matrix}\n\n{llm_synthesis_text}"

    report_filename = f"macro weekly synthesis ({timestamp_str}).md"
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, report_filename)

    with open(report_path, 'w') as f:
        f.write(report_content)

    print(f"Generated {report_filename} successfully.")

    # Call push_to_discord
    push_script = os.path.join(os.path.dirname(__file__), 'push_to_discord.py')
    import subprocess
    subprocess.run(["python3", push_script, report_path], check=False)

if __name__ == "__main__":
    main()
