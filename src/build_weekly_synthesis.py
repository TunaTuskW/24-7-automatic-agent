#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone
import sys
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
        
        generated_utc = data.get("generated_utc", datetime.now(timezone.utc).isoformat())
        dt = datetime.fromisoformat(generated_utc)
        
        mcs_score = data.get("mcs", {}).get("score", 0.0)
        regime = data.get("regime", {}).get("current", "UNKNOWN")
        kalman = data.get("kalman_state", {})
        dominant_state = kalman.get("dominant_state", "unknown")
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
        
        epistemic = data.get("epistemic_metrics", {})
        news_signal = data.get("news_signal", {})
        
        direction, clean_count, news_impact = run_consensus_engine(kalman, vol_heat, ext, mcs_score, epistemic, news_signal, regime)
        synth = compute_deterministic_synthesis(kalman, vol_heat, ext, epistemic, direction, news_impact)
        
        headlines = news_signal.get("top_headlines", [])
        headlines_str = "\n".join(f"> {h}" for h in headlines) if headlines else "> No significant headlines detected."
        
        template = f"""```text
[ WEEKLY MACRO SYNTHESIS ]
SPX {spx_sign}{spx_pct}% | DXY {dxy_level} | VIX {vix_level} | US10Y {us10y}% | WTI {wti_sign}{wti_pct}% | BTC {btc_sign}{btc_pct}%
[ ASSET DASHBOARD ]
- Equities: {eq_str}
- FX/Rates: {fx_str}
- Commodities: Gold {gold_sign}{gold_pct}% | Copper {copper_sign}{copper_pct}% | {fmt_ticker('Silver')}
- Crypto (Spot & Flows): BTC ${btc_level:,.0f} ({btc_sign}{btc_pct}%) | {crypto_str}
- Volatility: VIX {vix_level}
[ QUANTITATIVE MATRIX ]
SPX   | {spx_sign}{spx_pct}% | Heat: {part_type}
VIX   | {vix_level} | Temp: {ext.get('temperature_state', 'UNKNOWN')}
US10Y | {us10y}% | Crowd: {ext.get('crowded_state', 'UNKNOWN')}
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
[ ALGORITHMIC SYNTHESIS ]
State       : {synth['market_state']}
Lean        : {synth['directional_lean']}
Positioning : {synth['positioning']}
Invalidation: {synth['invalidation']}
```
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
