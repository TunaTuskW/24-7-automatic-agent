#!/usr/bin/env python3
"""
build_report.py - v5.2.0
Generates institutional macro updates displaying dual-engine (HMM + Deep MLP)
statistics alongside the decision-oriented AI Strategic Assumptions Layer.
"""
import os
import json
from datetime import datetime, timezone
import src.config_loader
from dataclasses import dataclass

@dataclass
class ModelResult:
    name: str
    signal: str           # "long" | "short" | "flat"
    conviction: float     # [0.0, 1.0]
    is_noise: bool        
    regime: str           

def run_consensus_engine(kalman, volume_heat, extremes, mcs_score, epistemic, news_signal, current_regime, tactical_alpha_regime=None):
    models = []
    
    dom_state = kalman.get("dominant_state", "")
    k_signal = "long" if dom_state == "risk_on" else "short" if dom_state == "risk_off" else "flat"
    k_noise = kalman.get("is_ambiguous", False) or kalman.get("tvd", 0) > 0.10
    k_conviction = kalman.get("dominant_prob", 0.0)
    
    # 50% Conviction Slash if Tactical Alpha Contradicts Structural Beta
    if tactical_alpha_regime:
        is_alpha_risk_on = "RISK_ON" in tactical_alpha_regime
        is_beta_risk_on = "RISK_ON" in current_regime
        if is_alpha_risk_on != is_beta_risk_on:
            k_conviction *= 0.5
            
    models.append(ModelResult("HMM_Kalman", k_signal, k_conviction, k_noise, current_regime))
    
    m_signal = "long" if mcs_score > 10 else "short" if mcs_score < -10 else "flat"
    models.append(ModelResult("MCS", m_signal, min(abs(mcs_score)/100.0, 1.0), False, current_regime))
    
    part_type = volume_heat.get("participation_type", "UNKNOWN")
    v_signal = "long" if part_type == "INSTITUTIONAL_ACCUMULATION" else "short" if part_type == "INSTITUTIONAL_DISTRIBUTION" else "flat"
    models.append(ModelResult("Volume_Heat", v_signal, 0.8, part_type == "RETAIL_DRIFT", current_regime))
    
    k_obj = epistemic.get("kelly_exposure_fraction", {})
    k_frac = k_obj.get("SPX_Kelly", 0.0) if isinstance(k_obj, dict) else float(k_obj)
    e_signal = "long" if kalman.get("risk_on", 0) > kalman.get("risk_off", 0) else "short"
    e_noise = epistemic.get("shannon_entropy", 0) > 1.5
    models.append(ModelResult("Epistemic_Kelly", e_signal, k_frac, e_noise, current_regime))
    
    ext_state = extremes.get("temperature_state", "UNKNOWN")
    t_signal = "long" if ext_state == "ICE_COLD" else "short" if ext_state == "OVERHEATED" else "flat"
    models.append(ModelResult("Market_Extremes", t_signal, min(abs(extremes.get("temperature_zscore", 0))/3.0, 1.0), ext_state == "NORMAL", current_regime))
    
    clean_models = [m for m in models if not m.is_noise]
    if len(clean_models) <= 2:
        return "FLAT (Too much noise)", len(clean_models), "Neutral Impact (Low Conviction Market)"
        
    long_score = sum(m.conviction for m in clean_models if m.signal == "long")
    short_score = sum(m.conviction for m in clean_models if m.signal == "short")
    total = long_score + short_score
    if total == 0:
        return "FLAT (No conviction)", len(clean_models), "Neutral Impact (Zero Conviction)"
        
    dominant_dir = "LONG" if long_score > short_score else "SHORT"
    dominant_score = max(long_score, short_score) / total
    
    thresh = 0.60
    n_flag = news_signal.get("event_flag", 0)
    n_bias = news_signal.get("directional_bias", "normal")
    
    impact_str = "Neutral Impact (Threshold 0.60)"
    
    if n_flag == 1 or n_bias == "shock":
        thresh = 0.65
        impact_str = "High Event Uncertainty / Shock (Threshold Raised to 0.65)"
        
    if (dominant_dir == "LONG" and n_bias == "bullish") or (dominant_dir == "SHORT" and n_bias == "bearish"):
        thresh = 0.50
        impact_str = f"Signal Confirmation ({n_bias.upper()}) (Threshold Lowered to 0.50)"
        
    if dominant_score >= thresh:
        return f"{dominant_dir} (Score: {dominant_score:.2f} >= Thresh: {thresh:.2f})", len(clean_models), impact_str
    else:
        return f"FLAT (Score: {dominant_score:.2f} < Thresh: {thresh:.2f})", len(clean_models), impact_str

def compute_deterministic_synthesis(kalman, volume_heat, extremes, epistemic, direction_str, news_impact):
    dominant_prob = kalman.get("dominant_prob", 0.33)
    brier = kalman.get("brier_score_calibration", 0.25)
    tvd = kalman.get("tvd", 0.0)
    kelly_obj = epistemic.get("kelly_exposure_fraction", {})
    if isinstance(kelly_obj, dict):
        kelly_frac = kelly_obj.get("SPX_Kelly", 0.0)
        safe_haven_frac = kelly_obj.get("GLD_Kelly", 0.0)
    else:
        kelly_frac = kelly_obj
        safe_haven_frac = 0.0
        
    entropy = epistemic.get("shannon_entropy", 1.58)
    
    # 1. Base Consensus State (Trust the Consensus Engine)
    market_state = f"Consensus clear (HMM Prob: {dominant_prob*100:.1f}%)"
    if entropy > 1.50:
        market_state = f"NOISY / HIGH CHAOS (Entropy: {entropy:.2f})"
        
    lean = direction_str
    
    # 2. Extreme Overrides
    if extremes.get("temperature_state") == "TOO HOT" and extremes.get("crowded_state", "").startswith("LONG"):
        lean += " [Mean Reversion Bias]"
        market_state = "OVERHEATED & CROWDED"
    elif volume_heat.get("participation_type") == "INSTITUTIONAL DISTRIBUTION" and kalman.get("dominant_state") == "RISK_ON":
        lean += " [Bearish Divergence]"
        market_state = "INSTITUTIONAL SELLING INTO RALLY"
        
    # 3. Dynamic Kelly Positioning
    if kelly_frac == 0.0 and safe_haven_frac == 0.0:
        positioning = f"STAND ASIDE. 0% Exposure. {news_impact}"
    elif kelly_frac == 0.0 and safe_haven_frac > 0.0:
        positioning = f"RISK OFF. Scale SPX to 0%. Safe Haven Allocation: {safe_haven_frac * 100:.1f}%. {news_impact}"
    else:
        positioning = f"Scale SPX to {kelly_frac * 100:.1f}%. Safe Haven: {safe_haven_frac * 100:.1f}%. {news_impact}"
        
    if brier > 0.25:
        positioning += " [WARNING: Model Degraded (High Brier)]"
    elif tvd > 0.08:
        positioning += " [WARNING: High Model Conflict (TVD)]"
    return {
        "market_state": market_state,
        "directional_lean": lean,
        "positioning": positioning,
        "invalidation": "Regime flip or VIX breakout."
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", type=str, default="1 hour update", help="Title for the report")
    args = parser.parse_args()

    events_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    
    # Find latest partition
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
        print("Error: No event data found. Run fetch_market_data.py first.")
        return
        
    latest_part = sorted(part_dirs)[-1]
    events_file = os.path.join(latest_part, "events.jsonl")
    
    if not os.path.exists(events_file):
        print(f"Error: {events_file} not found.")
        return
        
    last_snapshot_payload = None
    with open(events_file, 'r') as f:
        for line in f:
            if not line.strip(): continue
            try:
                evt = json.loads(line)
                if evt.get("event_type") == "PipelineComplete":
                    last_snapshot_payload = evt.get("payload")
            except Exception: pass
            
    if not last_snapshot_payload:
        print("Error: No PipelineComplete event found.")
        return
        
    from src.schemas.models import MarketSnapshot
    snapshot = MarketSnapshot.model_validate(last_snapshot_payload)
    data = snapshot.model_dump()
    
    generated_utc = data.get("generated_utc", datetime.now(timezone.utc).isoformat())
    dt = datetime.fromisoformat(generated_utc)
    timestamp_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    mcs_score = data.get("mcs", {}).get("score", 0.0)
    mcs_label = data.get("mcs", {}).get("label", "NEUTRAL")
    regime = data.get("regime", {}).get("current", "UNKNOWN")
    
    # Kalman & Model Governance
    kalman = data.get("kalman_state", {})
    dominant_state = kalman.get("dominant_state", "unknown")
    dominant_prob = kalman.get("dominant_prob", 0.0) * 100
    sai_score = kalman.get("structural_ambiguity_index", 0.0) # Fallback if needed
    tvd_score = kalman.get("tvd", 0.0)
    brier_score = kalman.get("brier_score_calibration", 0.15)
    
    # MLP State
    mlp = data.get("mlp_deep_state", {}) or {}
    mlp_dominant = mlp.get("dominant_state", "unknown").upper()
    mlp_prob = mlp.get("dominant_prob", 0.0) * 100
    mlp_on = mlp.get("risk_on", 0.0) * 100
    mlp_off = mlp.get("risk_off", 0.0) * 100
    mlp_trans = mlp.get("transitional", 0.0) * 100
    tier = data.get("data_driven_escalation", "ROUTINE")
    # Raw indicators extraction
    raw = data.get("raw_indicators", {})
    vol_heat = raw.get("volume_activity_heat") or {}
    part_type = vol_heat.get("participation_type", "UNKNOWN")
    heat_idx = vol_heat.get("institutional_heat_index", 0.0)
    
    ext = data.get("market_extremes_insight", {})
    
    spx_pct = (raw.get("SPX") or {}).get("delta_pct", 0.0)
    spx_sign = "+" if spx_pct >= 0 else ""
    
    us10y = data.get("bonds", {}).get("US10Y", {}).get("current", 0.0) if data.get("bonds", {}).get("US10Y") else 0.0
    
    wti_pct = (raw.get("WTI") or {}).get("delta_pct", 0.0)
    wti_sign = "+" if wti_pct >= 0 else ""
    vix_level = (raw.get("VIX") or {}).get("current", 0.0)
    vix_pct = (raw.get("VIX") or {}).get("delta_pct", 0.0)
    vix_sign = "+" if vix_pct >= 0 else ""
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
    
    # Global Equities Extractor
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
    # Tactical setup
    tactical = raw.get("tactical_setup", {}) or {}
    setup_name = tactical.get("matched_setup", "NONE")
    edge_prob = tactical.get("regime_conditioned_probability", 0.50) * 100
    
    boundaries = raw.get("spx_weekly_boundaries", {}) or {}
    pwh_level = boundaries.get("pwh", 0.0)
    pwl_level = boundaries.get("pwl", 0.0)
    
    inv_bounds = data.get("invalidation_boundaries", {})
    us10y_target = inv_bounds.get("us10y_invalidation_level", 4.65)
    vix_target = inv_bounds.get("vix_invalidation_level", 22.0)
    session = "US Session"
    if 0 <= dt.hour < 8:
        session = "Asian Session"
    elif 8 <= dt.hour < 14:
        session = "European Session"
    kalman = data.get("kalman_state", {})
    epistemic = data.get("data_science_layer", {}).get("epistemic_metrics", {})
    news_signal = data.get("news_signal", {})
    
    tactical_alpha_regime = data.get("regime", {}).get("tactical_alpha_regime")
    direction, clean_count, news_impact = run_consensus_engine(kalman, vol_heat, ext, mcs_score, epistemic, news_signal, regime, tactical_alpha_regime)
    
    synth = compute_deterministic_synthesis(kalman, vol_heat, ext, epistemic, direction, news_impact)
    
    headlines = news_signal.get("top_headlines", [])
    headlines_str = "\n".join(f"> {h}" for h in headlines) if headlines else "> No significant headlines detected."
        
    divergence_str = "DETECTED" if news_signal.get("quantitative_divergence_flag", False) else "NONE"
    reasoning_str = news_signal.get("reasoning", "No CoT reasoning available.")
    
    report_content = f"""```text
[ SESSION SNAPSHOT ]
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
    report_filename = f"{args.title} ({timestamp_str}).md"
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports', 'updates')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, report_filename)
    with open(report_path, 'w') as f:
        f.write(report_content)
    print(f"Generated {report_filename} successfully.")
    log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'macro_weekly_log.md')
    log_entry = f"{timestamp_str} | {session} | {dominant_state.upper()} | {tier} | Automated update recorded.\n"
    with open(log_path, 'a') as f:
        f.write(log_entry)
    push_script = os.path.join(os.path.dirname(__file__), 'push_to_discord.py')
    import subprocess
    subprocess.run(["python3", push_script, report_path, tier], check=False)
if __name__ == "__main__":
    main()
