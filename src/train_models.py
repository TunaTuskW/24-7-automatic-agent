#!/usr/bin/env python3
"""
train_models.py - v5.2.0
Offline training script for HMM regime classifier and MLP Deep Classifier.
Run quarterly. Saves trained models to data/
"""
import os
import json
import logging
import warnings
import src.config_loader
import numpy as np
import pandas as pd
import joblib
import yfinance as yf
import requests
import math
from datetime import datetime, timezone, timedelta

from arch import arch_model
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier
warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
# Configuration
TRAINING_YEARS   = 5
N_HIDDEN_STATES  = 3
N_ITERATIONS     = 500
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
def fetch_training_data(years=TRAINING_YEARS, interval="1d"):
    period = f"{years * 365}d"
    if interval == "1h":
        period = "1y"
    elif interval != "1d":
        period = "729d" # Max allowed for intraday in Yahoo Finance
    logging.info(f"Fetching {period} of training data with interval {interval}...")
    
    # Calculate dynamic rolling windows based on interval
    macro_window = 60 # 60 days
    short_window = 21 # 21 days (approx 1 trading month)
    ultra_short = 10  # 10 days
    
    if interval.endswith("h"):
        hours = float(interval.replace("h", "") or 1)
        bars = 6.5 / hours
        macro_window = int(60 * bars)
        short_window = int(21 * bars)
        ultra_short = int(10 * bars)
        
    fred_key = get_fred_key()
    tickers = ["^GSPC", "CL=F", "DX-Y.NYB", "SI=F", "USDCAD=X", "GC=F", "BTC-USD", "^VIX", "NVDA", "TSLA", "DELL", "SPCE"]
    data = yf.download(tickers, period=period, interval=interval, progress=False)
    
    spx = data["Close"]["^GSPC"].dropna()
    wti = data["Close"]["CL=F"].dropna()
    dxy = data["Close"]["DX-Y.NYB"].dropna()
    silver = data["Close"]["SI=F"].dropna()
    usdcad = data["Close"]["USDCAD=X"].dropna()
    gold = data["Close"]["GC=F"].dropna()
    vix = data["Close"]["^VIX"].dropna()
    
    spx_vol = data["Volume"]["^GSPC"].dropna()
    spx_high = data["High"]["^GSPC"].dropna()
    spx_low = data["Low"]["^GSPC"].dropna()
    spx_open = data["Open"]["^GSPC"].dropna()

    for idx, s in enumerate([spx, wti, dxy, silver, usdcad, gold, vix, spx_vol, spx_high, spx_low, spx_open]):
        s.index = pd.to_datetime(s.index).tz_localize(None)
        if interval == "1d":
            s.index = s.index.normalize()
        s = s[~s.index.duplicated(keep='last')]
        if idx == 0: spx = s
        elif idx == 1: wti = s
        elif idx == 2: dxy = s
        elif idx == 3: silver = s
        elif idx == 4: usdcad = s
        elif idx == 5: gold = s
        elif idx == 6: vix = s
        elif idx == 7: spx_vol = s
        elif idx == 8: spx_high = s
        elif idx == 9: spx_low = s
        elif idx == 10: spx_open = s

    spx_ret = spx.pct_change() * 100
    wti_ret = wti.pct_change() * 100
    dxy_ret = dxy.pct_change() * 100
    gsr_ret = (gold / silver).pct_change() * 100
    usdcad_ret = usdcad.pct_change() * 100
    btc = data["Close"]["BTC-USD"].dropna()
    btc.index = pd.to_datetime(btc.index).tz_localize(None)
    if interval == "1d":
        btc.index = btc.index.normalize()
    btc = btc[~btc.index.duplicated(keep='last')]
    btc_ret = btc.pct_change() * 100
    

    
    nvda = data["Close"]["NVDA"].dropna()
    nvda.index = pd.to_datetime(nvda.index).tz_localize(None)
    tsla = data["Close"]["TSLA"].dropna()
    tsla.index = pd.to_datetime(tsla.index).tz_localize(None)
    dell = data["Close"]["DELL"].dropna()
    dell.index = pd.to_datetime(dell.index).tz_localize(None)
    spce = data["Close"]["SPCE"].dropna()
    spce.index = pd.to_datetime(spce.index).tz_localize(None)
    
    if interval == "1d":
        nvda.index = nvda.index.normalize()
        tsla.index = tsla.index.normalize()
        dell.index = dell.index.normalize()
        spce.index = spce.index.normalize()
        

    nvda = nvda[~nvda.index.duplicated(keep='last')]
    nvda_ret = nvda.pct_change() * 100
    tsla = tsla[~tsla.index.duplicated(keep='last')]
    tsla_ret = tsla.pct_change() * 100
    dell = dell[~dell.index.duplicated(keep='last')]
    dell_ret = dell.pct_change() * 100
    spce = spce[~spce.index.duplicated(keep='last')]
    spce_ret = spce.pct_change() * 100
    
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
        "btc_ret":       btc_ret.reindex(spx_ret.index, method="ffill"),
        "gld_ret":       gold.pct_change().reindex(spx_ret.index, method="ffill") * 100,
        "wti_ret":       wti_ret.reindex(spx_ret.index, method="ffill"),
        "dxy_ret":       dxy_ret.reindex(spx_ret.index, method="ffill"),
        "vix":           vix.reindex(spx_ret.index, method="ffill"),
        "gsr_ret":       gsr_ret.reindex(spx_ret.index, method="ffill"),
        "usdcad_ret":    usdcad_ret.reindex(spx_ret.index, method="ffill"),
        "nvda_ret":      nvda_ret.reindex(spx_ret.index, method="ffill"),
        "tsla_ret":      tsla_ret.reindex(spx_ret.index, method="ffill"),
        "dell_ret":      dell_ret.reindex(spx_ret.index, method="ffill"),
        "spce_ret":      spce_ret.reindex(spx_ret.index, method="ffill"),
        "Volume":        spx_vol,
        "High":          spx_high,
        "Low":           spx_low,
        "Open":          spx_open,
        "Close":         spx
    })
    df.index = pd.to_datetime(df.index).tz_localize(None)
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
    # VIX Z-Score (Actual VIX index)
    vix_mean = df["vix"].rolling(macro_window).mean()
    vix_std = df["vix"].rolling(macro_window).std()
    df["vix_zscore"] = ((df["vix"] - vix_mean) / vix_std.replace(0, np.nan)).fillna(0)
    
    # Calculate Institutional Heat Index (Continuous)
    vol_sma20 = df["Volume"].rolling(short_window).mean()
    vol_std20 = df["Volume"].rolling(short_window).std()
    effort_z = (df["Volume"] - vol_sma20) / vol_std20
    range_size = df["High"] - df["Low"]
    result_vector = ((df["Close"] - df["Low"]) / range_size.replace(0, 0.0001)) - 0.5
    
    # Continuous calculation matches live ingestion perfectly
    df["Inst_Heat_Index"] = effort_z * result_vector
    
    # [NEW ALPHA FEATURES]
    # 1. SPX RSI (14)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, 0.0001)
    df["spx_rsi_14"] = 100 - (100 / (1 + rs))
    
    # 2. SPX MACD Histogram (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["spx_macd_hist"] = macd_line - signal_line
    
    # 3. SPX Bollinger Band Width (20)
    sma20 = df["Close"].rolling(window=20).mean()
    std20_bb = df["Close"].rolling(window=20).std()
    df["spx_bbw"] = (4 * std20_bb) / sma20.replace(0, 0.0001)
    
    # 4. SPX / VIX Rolling Correlation (10)
    vix_ret = df["vix"].pct_change() * 100
    df["spx_vix_corr"] = df["spx_ret"].rolling(window=10).corr(vix_ret).fillna(0)
    
    # CRITICAL: Drop NaNs generated by the new 20-day rolling windows
    df = df.dropna()
    logging.info(f"Training data shape: {df.shape}")
    return df

def train_ensemble_classifier(df, feature_names, output_path, interval="1d", target_col="spx_ret", threshold=1.5):
    logging.info(f"Training Ensemble Classifiers for {target_col}...")
    X = df[feature_names].values
    
    # Target labeling: always 5 periods to match backtester logic
    fwd_periods = 5
    
    # Scale threshold down for intraday or up for weekly
    if interval == "1wk":
        threshold *= 2.0
    elif interval == "4h":
        threshold *= 0.4
    elif interval == "1h":
        threshold *= 0.2
        
    forward_5d = df[target_col].shift(-fwd_periods).rolling(fwd_periods).sum().fillna(0)
    y = np.where(forward_5d > threshold, 1, np.where(forward_5d < -threshold, 0, 2))
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Neural architecture: scaled up
    mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        max_iter=1000,
        random_state=42,
    )
    mlp.fit(X_scaled, y)
    
    # Random Forest: Robust against overfitting
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=7,
        min_samples_leaf=3,
        random_state=42
    )
    rf.fit(X_scaled, y)
    
    # Gradient Boosting: HistGradientBoosting is optimized for tabular data
    gb = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_depth=5,
        random_state=42
    )
    gb.fit(X_scaled, y)
    
    mlp_package = {
        "model_mlp": mlp,
        "model_rf": rf,
        "model_gb": gb,
        "scaler": scaler,
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat()
    }
    joblib.dump(mlp_package, output_path)
    logging.info(f"Ensemble Classifiers saved successfully to {output_path}")

def train_all_ml_models(interval="1d"):
    df = fetch_training_data(interval=interval)
    
    # Aligned 16 features schema
    feature_names = [
        "spx_ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret", 
        "gsr_ret", "us10y_delta", "spread_level", "btc_ret",
        "nvda_ret", "tsla_ret", "dell_ret", "spce_ret",
        "spx_rsi_14", "spx_macd_hist", "spx_bbw", "spx_vix_corr"
    ]
    
    # Target Assets for Multi-Model ML Pipeline
    assets = [
        {"name": "spx", "col": "spx_ret", "threshold": 1.25},  
        {"name": "btc", "col": "btc_ret", "threshold": 7.5},   
        {"name": "gld", "col": "gld_ret", "threshold": 2.5},   
        {"name": "wti", "col": "wti_ret", "threshold": 6.25},
        {"name": "nvda", "col": "nvda_ret", "threshold": 8.0},
        {"name": "tsla", "col": "tsla_ret", "threshold": 8.0},
        {"name": "dell", "col": "dell_ret", "threshold": 8.0},
        {"name": "spce", "col": "spce_ret", "threshold": 2.0}
    ]
    
    for asset in assets:
        output_mlp_asset = os.path.join(os.path.dirname(__file__), '..', 'models', f'mlp_model_{asset["name"]}_{interval}.pkl' if interval != "1d" else f'mlp_model_{asset["name"]}.pkl')
        train_ensemble_classifier(df, feature_names, output_mlp_asset, interval=interval, target_col=asset["col"], threshold=asset["threshold"])
        
    logging.info("All Ensemble models trained successfully!")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", help="Data interval (e.g., 1d, 4h)")
    args = parser.parse_args()
    train_all_ml_models(interval=args.interval)
