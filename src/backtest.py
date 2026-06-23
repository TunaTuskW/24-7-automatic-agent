#!/usr/bin/env python3
"""
backtest.py
Historical backtest for the RegimeEnsemble using sub-engine rolling window simulation.
"""

import os
import json
import logging
import warnings
import numpy as np
import pandas as pd
import joblib
import yfinance as yf
import requests
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format='%(asctime)s — %(message)s')

def get_fred_key():
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'fred_api_key.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("PASTE"):
                return key
    return None

from src.train_models import fetch_training_data
from src.engines.trend_engine import TrendEngine
from src.engines.smc_engine import SMCEngine
from src.engines.session_engine import SessionEngine
from src.engines.liquidity_engine import LiquidityEngine
from src.engines.regime_ensemble import RegimeEnsemble

def run_backtest(interval="1d"):
    logging.info("Initializing Sub-Engines for Chronological Simulation...")
    trend_engine = TrendEngine()
    smc_engine = SMCEngine()
    session_engine = SessionEngine()
    liquidity_engine = LiquidityEngine()
    ensemble = RegimeEnsemble()

    df = fetch_training_data(years=2, interval=interval)
    if df is None or df.empty:
        logging.error("Failed to fetch training data.")
        return

    logging.info(f"Running rolling chronological simulation over {len(df)} bars (This may take a moment)...")
    
    lookback = 100
    regimes = ["NEUTRAL_TRANSITIONAL"] * len(df)
    
    for i in range(lookback, len(df)):
        window = df.iloc[i-lookback : i+1]
        
        # Poll micro-engines dynamically simulating live ingestion
        trend_state = trend_engine.score(window)
        smc_state = smc_engine.compute(window).__dict__
        
        session_state = session_engine.compute_session_state(window, window.index[-1])
        session_state.update(session_engine.compute_orb_signal(window))
        session_state.update(session_engine.td9_exhaustion_signal(window["Close"]))
        
        liq_state = liquidity_engine.compute(window)
        
        features_dict = {
            "vix_zscore": window["vix_zscore"].iloc[-1],
            "spread_level": window["spread_level"].iloc[-1]
        }
        
        probs, dominant_regime, tr_risk, _ = ensemble.compute(
            trend_state, smc_state, session_state, liq_state, features_dict
        )
        regimes[i] = dominant_regime

    df["regime_label"] = regimes
    
    # Fix Lookahead Bias: Shift the returns by 1 to get the FORWARD return
    df["fwd_spx_ret"] = df["spx_ret"].shift(-1)
    df["fwd_us10y_delta"] = df["us10y_delta"].shift(-1)
    df["fwd_wti_ret"] = df["wti_ret"].shift(-1)
    
    # Analyze performance by regime
    results = []
    total_days = len(df)
    
    for regime in df["regime_label"].unique():
        regime_df = df[df["regime_label"] == regime]
        days_in_regime = len(regime_df)
        if days_in_regime == 0:
            continue
            
        avg_daily_spx = regime_df["fwd_spx_ret"].mean()
        avg_daily_us10y_delta = regime_df["fwd_us10y_delta"].mean()
        avg_daily_wti = regime_df["fwd_wti_ret"].mean()
        
        # Annualized metrics (approx 252 trading days)
        ann_spx_ret = ((1 + avg_daily_spx/100)**252 - 1) * 100
        ann_wti_ret = ((1 + avg_daily_wti/100)**252 - 1) * 100
        
        results.append({
            "Regime": regime,
            "Days": days_in_regime,
            "Freq %": round(days_in_regime / total_days * 100, 1),
            "Ann. SPX Ret %": round(ann_spx_ret, 2),
            "Ann. WTI Ret %": round(ann_wti_ret, 2),
            "Avg US10Y Delta bps/day": round(avg_daily_us10y_delta * 100, 2)
        })

    # Output formatting
    results_md = "# Regime Ensemble 2-Year Historical Backtest Results\n\n"
    results_md += "| Regime | Days | Freq % | Ann. SPX Return | Ann. WTI Return | Avg 10Y Δ (bps/day) |\n"
    results_md += "|--------|------|--------|-----------------|-----------------|----------------------|\n"
    
    # Sort by frequency
    results.sort(key=lambda x: x["Days"], reverse=True)
    
    for r in results:
        results_md += f"| {r['Regime']} | {r['Days']} | {r['Freq %']}% | {r['Ann. SPX Ret %']}% | {r['Ann. WTI Ret %']}% | {r['Avg US10Y Delta bps/day']} bps |\n"
    
    # Save to file
    out_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'backtest_results.md')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(results_md)
        
    logging.info(f"Backtest complete. Results saved to {out_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", choices=["1d", "1h", "4h"])
    args = parser.parse_args()
    run_backtest(interval=args.interval)
