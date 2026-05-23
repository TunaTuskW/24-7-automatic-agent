#!/usr/bin/env python3
"""
build_report.py - v3.6.0
Generates institutional macro updates displaying dual-engine (HMM + Deep MLP)
statistics alongside the decision-oriented AI Strategic Assumptions Layer.
"""
import os
import json
from datetime import datetime, timezone
def compute_deterministic_synthesis(kalman, volume_heat, extremes, epistemic):
    # Extract variables
    dominant_prob = kalman.get("dominant_prob", 0.33)
    brier = kalman.get("brier_score_calibration", 0.25)
    tvd = kalman.get("tvd", 0.0)
    kelly_frac = epistemic.get("kelly_exposure_fraction", 0.0)
    entropy = epistemic.get("shannon_entropy", 1.58)
    
    # 1. Chaos / Abstention Rule (The new noise filter)
    # If Kelly calculates 0% exposure, OR Entropy is near max (> 1.50)
    if kelly_frac == 0.0 or entropy > 1.50:
        return {
            "market_state": f"NOISY / HIGH CHAOS (Entropy: {entropy})",
            "directional_lean": "NO PREDICT (Statistical Coin-Flip)",
            "positioning": "STAND ASIDE. 0% Exposure.",
            "invalidation": "Requires dominant probability > 45.0%"
        }
        
    # 2. Base Deterministic Logic
    market_state = f"Regime clear (Prob: {dominant_prob*100:.1f}%)"
    lean = "Follow Dominant Regime"
    
    # Apply Volume & Extreme Overrides
    if extremes.get("temperature_state") == "TOO HOT" and extremes.get("crowded_state", "").startswith("LONG"):
        lean = "Mean Reversion (Bearish Bias)"
        market_state = "OVERHEATED & CROWDED"
    elif volume_heat.get("participation_type") == "INSTITUTIONAL DISTRIBUTION" and kalman.get("dominant_state") == "RISK_ON":
        lean = "Bearish Divergence (Retail Trapped)"
        market_state = "INSTITUTIONAL SELLING INTO RALLY"
        
    # 3. Dynamic Kelly Positioning
    positioning = f"Scale exposure to exactly {kelly_frac * 100:.1f}% of maximum capital."
    
    if brier > 0.20 or tvd > 0.08:
        positioning += " [WARNING: Model Conflict/Degraded - Maintain strict stops]"
        
    return {
        "market_state": market_state,
        "directional_lean": lean,
        "positioning": positioning,
        "invalidation": "Regime flip or VIX breakout."
    }
def main():
    snapshot_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    if not os.path.exists(snapshot_path):
        print(f"Error: {snapshot_path} not found. Run fetch_market_data.py first.")
        return
    with open(snapshot_path, 'r') as f:
        data = json.load(f)
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
    vol_heat = raw.get("volume_activity_heat", {})
    part_type = vol_heat.get("participation_type", "UNKNOWN")
    heat_idx = vol_heat.get("institutional_heat_index", 0.0)
    
    ext = data.get("market_extremes_insight", {})
    
    spx_pct = raw.get("SPX", {}).get("delta_pct", 0.0)
    spx_sign = "+" if spx_pct >= 0 else ""
    
    us10y = data.get("bonds", {}).get("US10Y", {}).get("current", 0.0) if data.get("bonds", {}).get("US10Y") else 0.0
    
    wti_pct = raw.get("WTI", {}).get("delta_pct", 0.0)
    wti_sign = "+" if wti_pct >= 0 else ""
    vix_level = raw.get("VIX", {}).get("current", 0.0)
    vix_pct = raw.get("VIX", {}).get("delta_pct", 0.0)
    vix_sign = "+" if vix_pct >= 0 else ""
    dxy_level = raw.get("DXY", {}).get("current", 0.0)
    dxy_pct = raw.get("DXY", {}).get("delta_pct", 0.0)
    dxy_sign = "+" if dxy_pct >= 0 else ""
    gold_pct = raw.get("Gold", {}).get("delta_pct", 0.0)
    gold_sign = "+" if gold_pct >= 0 else ""
    copper_pct = raw.get("Copper", {}).get("delta_pct", 0.0)
    copper_sign = "+" if copper_pct >= 0 else ""
    btc_pct = raw.get("BTC", {}).get("delta_pct", 0.0)
    btc_sign = "+" if btc_pct >= 0 else ""
    btc_level = raw.get("BTC", {}).get("current", 0.0)
    
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
    epistemic = data.get("epistemic_metrics", {})
    synth = compute_deterministic_synthesis(kalman, vol_heat, ext, epistemic)

    print("Using Algorithmic Directional Synthesis.")
    # Setup narrative mapping
    setup_narrative = "No structural liquidity sweeps detected in the current session."
    if setup_name == "PWL_Sweep":
        setup_narrative = f"ALERT: Wednesday PWL Swept ({pwl_level}). Volatility-filtered checks confirm clean institutional absorption. Standard technical analysis suggests a V-shape reversal trap."
    elif setup_name == "PWH_Sweep":
        setup_narrative = f"ALERT: PWH Swept ({pwh_level}). Distribution patterns identified at key ceiling. Trapped buyers likely to face liquidation cascade."
    # Compute dynamic confidence class
    computed_confidence = "HIGH"
    if tvd_score > 0.10 or brier_score > 0.25:
        computed_confidence = "LOW"
    elif tvd_score > 0.05 or brier_score > 0.18:
        computed_confidence = "MODERATE"
    report_content = f"""## {timestamp_str} — {session} — {tier}
**Regime:** {regime} | **MCS:** {mcs_score}
**Max Prob:** {dominant_prob:.1f}% | **Brier Calibration:** {brier_score:.4f}
**Model Distance (TVD):** {tvd_score:.4f}
a. SESSION SNAPSHOT
SPX {spx_sign}{spx_pct}% | DXY {dxy_level} | VIX {vix_level} | US10Y {us10y}% | WTI {wti_sign}{wti_pct}% | BTC {btc_sign}{btc_pct}%
b. ASSET DASHBOARD
- Equities: {eq_str}
- FX/Rates: {fx_str}
- Commodities: Gold {gold_sign}{gold_pct}% | Copper {copper_sign}{copper_pct}% | {fmt_ticker('Silver')}
- Crypto (Spot & Flows): BTC ${btc_level:,.0f} ({btc_sign}{btc_pct}%) | {crypto_str}
- Volatility: VIX {vix_level} 
- Activity Heat (Inst vs Retail): {part_type}
- Market Temp: {ext.get('temperature_state')}
- Crowdedness: {ext.get('crowded_state')}
c. TACTICAL EDGE
- PATTERN: {setup_name}
- SUCCESS PROBABILITY: {edge_prob:.1f}%
### QUANTITATIVE DIRECTIONAL SYNTHESIS
- **Market State:** {synth['market_state']}
- **Directional Lean:** {synth['directional_lean']}
- **Positioning:** {synth['positioning']}
- **Invalidation:** {synth['invalidation']}
"""
    report_filename = f"4 hours update ({timestamp_str}).md"
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
    os.system(f'python3 "{push_script}" "{report_path}" "{tier}"')
if __name__ == "__main__":
    main()
