import os
import json
import argparse
import traceback
import feedparser
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.observability.logger import get_logger
from src.data_lake.lake_manager import LakeManager
from src.adapters.yahoo_adapter import YahooAdapter
from src.adapters.gemini_adapter import GeminiAdapter
from src.engines.hmm_engine import HMMEngine
from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import (
    ALL_YF_TICKERS, get_fred_key, get_signature_salt, sign_snapshot_payload,
    check_mathematical_consistency, append_to_immutable_chain,
    compute_stats, compute_volume_heat, compute_market_extremes,
    compute_garch_volatility, load_mlp_model, run_mlp_inference,
    compute_weekly_liquidity_boundaries, calculate_model_tvd,
    calculate_bayesian_conditional_probability, run_self_calibration,
    compute_mcs, garch_targets
)

logger = get_logger("conductor")

def fetch_rss_headlines():
    urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ]
    headlines = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                headlines.append(entry.title)
        except Exception as e:
            logger.error(f"RSS fetch failed: {e}")
    return headlines

def main():
    logger.info("Initializing v4.5 Enterprise Conductor")
    
    # 1. Dependency Injection
    fred_key = get_fred_key()
    data_broker = YahooAdapter(fred_key=fred_key)
    llm_provider = GeminiAdapter()
    lake_manager = LakeManager()
    
    hmm_engine = HMMEngine()
    risk_engine = RiskEngine()
    
    # 2. Extract Data (ETL Phase)
    logger.info("Starting Data Ingestion Phase")
    tickers = list(ALL_YF_TICKERS.values())
    raw_daily_data = data_broker.fetch_ohlcv_daily(tickers, period="30d")
    raw_hourly_data = data_broker.fetch_ohlcv_hourly(tickers, period="5d")
    
    lake_manager.save_tabular(raw_daily_data, "raw_daily_ohlcv.parquet")
    lake_manager.save_tabular(raw_hourly_data, "raw_hourly_ohlcv.parquet")
    
    def parse_assets(raw_df):
        parsed = {}
        if not isinstance(raw_df.columns, pd.MultiIndex):
            logger.error("Yahoo Finance data is not a MultiIndex (fetch failed or single ticker).")
            return parsed
            
        for name, tk in ALL_YF_TICKERS.items():
            if tk in raw_df.columns.levels[0]:
                tk_df = raw_df[tk].dropna(how="all")
                if len(tk_df) > 1:
                    parsed[name] = compute_stats(tk_df["Close"])
                    parsed[name]["raw_series"] = tk_df["Close"]
        return parsed
        
    parsed_daily = parse_assets(raw_daily_data)
    parsed_hourly = parse_assets(raw_hourly_data)
    
    # Clean up raw_series to not pollute JSON dump
    clean_daily = {}
    for k, v in parsed_daily.items():
        clean_daily[k] = {ik: iv for ik, iv in v.items() if ik != "raw_series"}
        
    bonds = {
        "US2Y": {"current": data_broker.fetch_yield("DGS2")},
        "US10Y": {"current": data_broker.fetch_yield("DGS10")}
    }
    if bonds["US2Y"]["current"] and bonds["US10Y"]["current"]:
        bonds["spread_2s10s"] = round(bonds["US10Y"]["current"] - bonds["US2Y"]["current"], 4)
    else: bonds["spread_2s10s"] = 0.0
    
    # 3. GARCH & Extremes
    logger.info("Starting Feature Engineering Phase")
    garch_layer = {}
    for name, ticker in garch_targets.items():
        cond_vol, regime, f_vol = compute_garch_volatility(ticker)
        garch_layer[name] = {"conditional_vol": cond_vol if cond_vol else 0.0}
        
    spx_s = parsed_daily.get("SPX", {}).get("raw_series")
    vix_s = parsed_daily.get("VIX", {}).get("raw_series")
    vvix_s = parsed_daily.get("VVIX", {}).get("raw_series")
    dxy_s = parsed_daily.get("DXY", {}).get("raw_series")
    vix9d_s = parsed_daily.get("VIX9D", {}).get("raw_series")
    
    extremes = compute_market_extremes(spx_s, vix_s, vvix_s, dxy_s, vix9d_s)
    
    # Calculate Volume Heat
    spx_series = raw_daily_data["^GSPC"]["Close"].dropna()
    spx_vol = raw_daily_data["^GSPC"]["Volume"].dropna()
    vol_heat_stats = compute_volume_heat(spx_series, spx_vol)
    clean_daily["volume_activity_heat"] = vol_heat_stats
    
    # Gold-to-Silver Ratio
    gold = clean_daily.get("Gold")
    silver = clean_daily.get("Silver")
    if gold and silver and silver.get("current", 0) > 0:
        gsr_current = gold["current"] / silver["current"]
        gsr_prev = gold["prev"] / silver["prev"]
        gsr_delta_pct = ((gsr_current - gsr_prev) / gsr_prev) * 100
        clean_daily["gold_to_silver_ratio"] = {
            "current": round(gsr_current, 3), "prev": round(gsr_prev, 3), "delta_pct": round(gsr_delta_pct, 3)
        }
        
    # Institutional Crypto MFI
    ibit = clean_daily.get("IBIT")
    etha = clean_daily.get("ETHA")
    if ibit and etha and ibit.get("z_score") is not None and etha.get("z_score") is not None:
        mfi_z = (ibit["z_score"] + etha["z_score"]) / 2
        clean_daily["institutional_crypto_mfi"] = {
            "composite_z": round(mfi_z, 3),
            "flow_regime": "INFLOW" if mfi_z > 1.0 else "OUTFLOW" if mfi_z < -1.0 else "FLAT"
        }
        
    # Keyless Credit ETF stress proxy
    hyg = clean_daily.get("HYG")
    lqd = clean_daily.get("LQD")
    if hyg and lqd and hyg.get("z_score") is not None and lqd.get("z_score") is not None:
        credit_z = (hyg["z_score"] + lqd["z_score"]) / 2
        clean_daily["credit_stress_proxy"] = {
            "composite_z": round(credit_z, 3), 
            "label": "CRITICAL" if credit_z < -2.0 else "ELEVATED" if credit_z < -1.0 else "NORMAL"
        }
        
    # Features vector
    ordered_feature_keys = [
        ("SPX_ret", "SPX", "delta_pct"),
        ("DXY_ret", "DXY", "delta_pct"),
        ("VIX_zscore", "VIX", "z_score"),
        ("WTI_ret", "WTI", "delta_pct"),
        ("GoldSilverRatio_ret", "gold_to_silver_ratio", "delta_pct"),
        ("US10Y_delta", "bonds", "delta"),
        ("US_2s10s_spread", "bonds", "spread_2s10s"),
        ("CryptoMFI_zscore", "institutional_crypto_mfi", "composite_z"),
        ("VolumeHeat_ihi", "volume_activity_heat", "institutional_heat_index"),
        ("USDCAD_ret", "USDCAD", "delta_pct")
    ]
    features_vector = []
    feature_metadata = {}
    for label, category, key in ordered_feature_keys:
        val = 0.0
        try:
            if category == "bonds":
                if key == "delta" and bonds.get("US10Y"): val = bonds["US10Y"].get("delta", 0.0)
                elif key == "spread_2s10s": val = bonds.get("spread_2s10s", 0.0)
            else: val = clean_daily.get(category, {}).get(key, 0.0)
            if val is None: val = 0.0
        except Exception: pass
        features_vector.append(float(val))
        feature_metadata[label] = float(val)
        
    mlp_package = load_mlp_model()
    mlp_state = run_mlp_inference(features_vector, mlp_package)
    
    # Engine Inference
    logger.info("Running Mathematical Engines")
    mcs, sub_comps = compute_mcs(clean_daily, bonds, clean_daily)
    
    hmm_beta_probs, hmm_beta_dom, tr_risk, _ = hmm_engine.run_inference(features_vector)
    hmm_alpha_probs, hmm_alpha_dom, _, _ = hmm_engine.run_inference(features_vector) # Should use hourly, but for simplicity now we use daily
    
    current_regime = hmm_beta_dom if hmm_beta_dom else "NEUTRAL_TRANSITIONAL"
    
    # 5. Risk Engine & State
    prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_snapshot_prior.json")
    prior = {}
    if os.path.exists(prior_path):
        try:
            with open(prior_path, 'r') as f:
                prior = json.load(f)
        except: pass
        
    prior_regime = prior.get("regime", {}).get("dominant_regime")
    regime_changed = current_regime != prior_regime
    
    now_utc = datetime.now(timezone.utc)
    prior_start_str = prior.get("regime", {}).get("start_utc", now_utc.isoformat())
    prior_start = datetime.fromisoformat(prior_start_str)
    
    if regime_changed:
        duration_days = 0.0
        start_utc_str = now_utc.isoformat()
    else:
        duration_days = (now_utc - prior_start).total_seconds() / 86400.0
        start_utc_str = prior_start_str
        
    prior_state = prior.get("kalman_state", {}).get("probabilities")
    prior_cov = prior.get("kalman_state", {}).get("covariance_matrix")
    kalman_res = risk_engine.run_kalman_filter(mcs, sub_comps, hmm_beta_probs or {}, prior_state, prior_cov)
    
    tvd_score = 0.0
    if mlp_state and hmm_beta_probs:
        tvd_score = calculate_model_tvd(hmm_beta_probs, mlp_state)
    kalman_res["tvd"] = tvd_score
    
    entropy = risk_engine.compute_shannon_entropy(np.array(list((hmm_beta_probs or {}).values())))
    
    half_life = 99.0
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "tuning_configs.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            t_conf = json.load(f)
            half_life = t_conf.get("regime_half_lives", {}).get(current_regime, 99.0)
            
    kelly = risk_engine.compute_kelly_sizing(kalman_res.get("dominant_prob", 0.33), 0.1, duration_days, half_life)
    
    # 6. NLP Processing
    logger.info("Calling LLM Provider")
    headlines = fetch_rss_headlines()
    news_res = llm_provider.parse_news(headlines)
    
    # 7. Final Snapshot
    data_science_layer = {"ordered_features_list": [lbl for lbl, _, _ in ordered_feature_keys], "features_vector": features_vector, "features_dict": feature_metadata}
    
    # Core calibration calculations (Brier Score)
    spx_ret_now = clean_daily.get("SPX", {}).get("delta_pct", 0.0) if clean_daily.get("SPX") else 0.0
    predictions_history_path = os.path.join(os.path.dirname(__file__), "..", "data", "mlp_predictions_history.json")
    brier_score = 0.1500
    try:
        from src.fetch_market_data_legacy import run_self_calibration
        brier_score, _ = run_self_calibration(spx_ret_now, predictions_history_path)
    except: pass
    
    kalman_res["brier_score_calibration"] = brier_score
    
    data_science_layer["epistemic_metrics"] = {
        "shannon_entropy": entropy,
        "kelly_exposure_fraction": kelly,
        "is_high_risk_edge": bool(kalman_res.get("dominant_prob", 0.0) >= 0.45)
    }
    
    escalation = "ROUTINE"
    if spx_ret_now and abs(spx_ret_now) > 2.0: escalation = "CRITICAL"
    elif spx_ret_now and abs(spx_ret_now) > 1.0: escalation = "ELEVATED"
    
    if tvd_score > 0.10 and escalation == "ROUTINE":
        escalation = "ELEVATED"
        
    snapshot = {
        "generated_utc": now_utc.isoformat(),
        "raw_indicators": clean_daily,
        "bonds": bonds,
        "market_extremes_insight": extremes,
        "regime": {
            "current": current_regime,
            "dominant_regime": current_regime,
            "tactical_alpha_regime": hmm_alpha_dom,
            "probabilities": hmm_beta_probs,
            "tactical_alpha_probabilities": hmm_alpha_probs,
            "transition_risk": tr_risk,
            "start_utc": start_utc_str,
            "duration_days": round(duration_days, 2)
        },
        "kalman_state": kalman_res,
        "mlp_deep_state": mlp_state,
        "data_science_layer": data_science_layer,
        "mcs": {"score": mcs, "label": "NEUTRAL", "components": sub_comps},
        "data_driven_escalation": escalation,
        "news_signal": news_res
    }
    
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_snapshot.json")
    with open(out_path, 'w') as f:
        json.dump(snapshot, f, indent=4)
        
    lake_manager.save_unstructured(snapshot, "market_snapshot")
    
    with open(prior_path, 'w') as f:
        json.dump(snapshot, f, indent=4)
        
    logger.info("v4.5 Enterprise Pipeline Complete")

if __name__ == "__main__":
    main()
