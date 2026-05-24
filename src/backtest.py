#!/usr/bin/env python3
"""
backtest.py
Simple historical backtest for the HMM Regime Classifier.
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

from train_models import fetch_training_data

def run_backtest():
    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'hmm_model.pkl')
    if not os.path.exists(model_path):
        logging.error("HMM model not found. Run train_models.py first.")
        return

    package = joblib.load(model_path)
    hmm = package["hmm"]
    scaler = package["scaler"]
    state_labels = package["state_labels"]
    feature_names = package["feature_names"]

    df = fetch_training_data(years=2)
    X = df[feature_names].values
    X_scaled = scaler.transform(X)

    # Decode the hidden states sequence
    states = hmm.predict(X_scaled)
    df["regime_id"] = states
    df["regime_label"] = df["regime_id"].map(state_labels)

    # Analyze performance by regime
    results = []
    
    total_days = len(df)
    
    # Calculate annualized metrics
    for regime in df["regime_label"].unique():
        regime_df = df[df["regime_label"] == regime]
        days_in_regime = len(regime_df)
        
        # Mean daily returns
        avg_daily_spx = regime_df["spx_ret"].mean()
        avg_daily_us10y_delta = regime_df["us10y_delta"].mean()
        avg_daily_wti = regime_df["wti_ret"].mean()
        
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
    results_md = "# HMM 2-Year Historical Backtest Results\n\n"
    results_md += "| Regime | Days | Freq % | Ann. SPX Return | Ann. WTI Return | Avg 10Y Δ (bps/day) |\n"
    results_md += "|--------|------|--------|-----------------|-----------------|----------------------|\n"
    
    # Sort by frequency
    results.sort(key=lambda x: x["Days"], reverse=True)
    
    for r in results:
        results_md += f"| {r['Regime']} | {r['Days']} | {r['Freq %']}% | {r['Ann. SPX Ret %']}% | {r['Ann. WTI Ret %']}% | {r['Avg US10Y Delta bps/day']} bps |\n"
    
    # Save to file
    out_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'backtest_results.md')
    with open(out_path, 'w') as f:
        f.write(results_md)
        
    logging.info(f"Backtest complete. Results saved to {out_path}")

if __name__ == "__main__":
    run_backtest()
