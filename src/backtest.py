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

def fetch_data_for_backtest(years=2):
    logging.info(f"Fetching {years} years of training data...")
    period = f"{years * 365}d"
    fred_key = get_fred_key()
    tickers = ["^GSPC", "CL=F", "DX-Y.NYB", "SI=F", "USDCAD=X", "GC=F"]
    data = yf.download(tickers, period=period, progress=False)["Close"]
    
    spx = data["^GSPC"].dropna()
    wti = data["CL=F"].dropna()
    dxy = data["DX-Y.NYB"].dropna()
    silver = data["SI=F"].dropna()
    usdcad = data["USDCAD=X"].dropna()
    gold = data["GC=F"].dropna()

    for s in [spx, wti, dxy, silver, usdcad, gold]:
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()

    spx_ret = spx.pct_change() * 100
    wti_ret = wti.pct_change() * 100
    dxy_ret = dxy.pct_change() * 100
    gsr_ret = (gold / silver).pct_change() * 100
    usdcad_ret = usdcad.pct_change() * 100
    
    # approximate garch for speed
    spx_garch_vol = spx_ret.rolling(21).std()

    us2y_series = None
    us10y_series = None
    if fred_key:
        for series_id, var_name in [("DGS2", "us2y"), ("DGS10", "us10y")]:
            try:
                start_date = (datetime.now(timezone.utc) - timedelta(days=years * 366)).strftime("%Y-%m-%d")
                url = "https://api.stlouisfed.org/fred/series/observations"
                params = {
                    "series_id":         series_id,
                    "api_key":           fred_key,
                    "file_type":         "json",
                    "observation_start": start_date,
                }
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                obs = [(o["date"], float(o["value"])) for o in resp.json()["observations"] if o["value"] != "."]
                s = pd.Series(dict(obs), name=series_id, dtype=float)
                s.index = pd.to_datetime(s.index)
                s.index = s.index.tz_localize(None)
                if var_name == "us2y":
                    us2y_series = s
                else:
                    us10y_series = s
            except Exception as e:
                logging.warning(f"FRED {series_id} fetch failed: {e}")
    df = pd.DataFrame({
        "spx_ret":       spx_ret,
        "wti_ret":       wti_ret,
        "dxy_ret":       dxy_ret,
        "spx_garch_vol": spx_garch_vol,
        "gsr_ret":       gsr_ret,
        "usdcad_ret":    usdcad_ret
    })
    df.index = pd.to_datetime(df.index).tz_localize(None)
    # Keyless Credit ETF historical proxy
    df["crypto_mfi_z"] = df["spx_ret"].rolling(10).std() * 0.1
    if us10y_series is not None:
        us10y_delta = us10y_series.diff()
        df["us10y_delta"] = us10y_delta.reindex(df.index, method="ffill")
    else:
        df["us10y_delta"] = 0.0
    if us2y_series is not None and us10y_series is not None:
        spread = (us10y_series - us2y_series).diff()
        df["spread_delta"] = spread.reindex(df.index, method="ffill")
        df["spread_level"] = (us10y_series - us2y_series).reindex(df.index, method="ffill")
    else:
        df["spread_delta"] = 0.0
        df["spread_level"] = 0.0
    # Implied volatility index historical proxy
    df["vix_zscore"] = df["spx_garch_vol"].rolling(21).apply(lambda x: (x[-1] - x.mean())/x.std() if x.std() > 0 else 0)
    df = df.dropna()
    logging.info(f"Training data shape: {df.shape}")
    return df

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

    df = fetch_data_for_backtest(years=2)
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
