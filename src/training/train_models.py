#!/usr/bin/env python3
"""
train_models.py - v4.9.0
Offline training script for HMM regime classifier and MLP Deep Classifier.
Implements 60-day rolling windows and covariance regularization (min_covar=0.01).
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
from hmmlearn.hmm import GaussianHMM
from arch import arch_model
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
import argparse

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
# Configuration
TRAINING_YEARS   = 10
N_HIDDEN_STATES  = 6
N_ITERATIONS     = 500

def get_model_paths(interval="1d"):
    hmm_path = os.path.join(os.path.dirname(__file__), '..', '..', 'models', f'hmm_model_{interval}.pkl')
    mlp_path = os.path.join(os.path.dirname(__file__), '..', '..', 'models', f'mlp_model_{interval}.pkl')
    return hmm_path, mlp_path

def get_fred_key():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'fred_api_key.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("PASTE"):
                return key
    return None

def fetch_training_data(years=TRAINING_YEARS, interval="1d"):
    period = f"{years}y"
    if interval in ["1h", "4h"]:
        period = "730d"
        years = 2
    logging.info(f"Fetching {period} of training data at interval {interval}...")
    
    fred_key = get_fred_key()
    tickers = ["^GSPC", "CL=F", "DX-Y.NYB", "SI=F", "USDCAD=X", "GC=F"]
    data = yf.download(tickers, period=period, interval=interval, progress=False)
    
    spx = data["Close"]["^GSPC"].dropna()
    wti = data["Close"]["CL=F"].dropna()
    dxy = data["Close"]["DX-Y.NYB"].dropna()
    silver = data["Close"]["SI=F"].dropna()
    usdcad = data["Close"]["USDCAD=X"].dropna()
    gold = data["Close"]["GC=F"].dropna()
    
    spx_vol = data["Volume"]["^GSPC"].dropna()
    spx_high = data["High"]["^GSPC"].dropna()
    spx_low = data["Low"]["^GSPC"].dropna()

    for i, s in enumerate([spx, wti, dxy, silver, usdcad, gold, spx_vol, spx_high, spx_low]):
        s = s[~s.index.duplicated(keep='last')]
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize() if interval not in ["1h", "4h", "1m", "5m", "15m"] else pd.to_datetime(s.index).tz_localize(None)
        
        # Write back to variable
        if i == 0: spx = s
        elif i == 1: wti = s
        elif i == 2: dxy = s
        elif i == 3: silver = s
        elif i == 4: usdcad = s
        elif i == 5: gold = s
        elif i == 6: spx_vol = s
        elif i == 7: spx_high = s
        elif i == 8: spx_low = s

    spx_ret = spx.pct_change() * 100
    wti_ret = wti.pct_change() * 100
    dxy_ret = dxy.pct_change() * 100
    gsr_ret = (gold / silver).pct_change() * 100
    usdcad_ret = usdcad.pct_change() * 100
    logging.info("Fitting GARCH on SPX for training volatility series...")
    try:
        garch_model = arch_model(
            spx_ret.dropna(), vol="Garch", p=1, q=1,
            mean="Zero", rescale=False
        )
        garch_fit = garch_model.fit(disp="off", show_warning=False)
        spx_garch_vol = garch_fit.conditional_volatility
    except Exception as e:
        logging.warning(f"GARCH training failed, using rolling std: {e}")
        spx_garch_vol = spx_ret.rolling(60).std()
        
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
                s.index = pd.to_datetime(s.index).tz_localize(None)
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
        "usdcad_ret":    usdcad_ret,
        "Volume":        spx_vol,
        "High":          spx_high,
        "Low":           spx_low,
        "Close":         spx
    })
    df.index = pd.to_datetime(df.index).tz_localize(None)
    
    # CRITICAL FIX: Fill forward and dropna before rolling windows to prevent NaN propagation
    df = df.ffill().dropna()
    
    # Keyless Credit ETF historical proxy
    df["crypto_mfi_z"] = df["spx_ret"].rolling(60).std() * 0.1
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
        
    # Implied volatility index historical proxy - updated to 60-day rolling
    df["vix_zscore"] = df["spx_garch_vol"].rolling(60).apply(lambda x: (x[-1] - x.mean())/x.std() if x.std() > 0 else 0)
    
    # Calculate Institutional Heat Index (Continuous) - updated to 60-day rolling
    vol_sma60 = df["Volume"].rolling(60).mean()
    vol_std60 = df["Volume"].rolling(60).std()
    effort_z = (df["Volume"] - vol_sma60) / vol_std60
    range_size = df["High"] - df["Low"]
    result_vector = ((df["Close"] - df["Low"]) / range_size.replace(0, 0.0001)) - 0.5
    
    df["Inst_Heat_Index"] = effort_z * result_vector
    
    # Transform raw percentages to 60-day rolling z-scores
    for col in ["spx_ret", "dxy_ret", "wti_ret", "gsr_ret", "usdcad_ret", "us10y_delta", "spread_delta"]:
        df[f"{col}_z"] = df[col].rolling(60).apply(lambda x: (x[-1] - x.mean())/x.std() if x.std() > 0 else 0)
    
    # Drop any remaining NaNs from the initial 60-day warm-up
    df = df.dropna()
    logging.info(f"Training data shape: {df.shape}")
    return df

def label_states_by_emission(hmm_model, feature_names):
    means = hmm_model.means_
    logging.info(f"HMM Means Matrix:\n{np.round(means, 3)}")
    state_labels = {}
    spx_idx = feature_names.index("spx_ret_z")
    us10y_idx = feature_names.index("us10y_delta_z")
    wti_idx = feature_names.index("wti_ret_z")
    gsr_idx = feature_names.index("gsr_ret_z")
    vix_idx = feature_names.index("vix_zscore")
    assigned = set()
    for state_id in range(len(means)):
        spx_m  = means[state_id][spx_idx]
        us10y_m = means[state_id][us10y_idx]
        wti_m  = means[state_id][wti_idx]
        gsr_m  = means[state_id][gsr_idx]
        vix_m  = means[state_id][vix_idx]
        
        if spx_m > 0.05 and us10y_m > 0.01:
            label = "RISK_ON_EXPANSION"
        elif spx_m > 0.05 and us10y_m < -0.01:
            label = "LIQUIDITY_DRIVEN_RALLY"
        elif spx_m < -0.05 and wti_m > 0.05:
            label = "STAGFLATION_STRESS"
        elif spx_m < -0.05 and us10y_m > 0.02:
            label = "RATE_SHOCK"
        elif spx_m < -0.05 and wti_m < -0.05:
            label = "DEFLATION_FEAR"
        elif wti_m > 0.05 or gsr_m > 0.05:
            label = "COMMODITY_SHOCK"
        elif vix_m > 0.05:
            label = "VOLATILITY_EXPANSION"
        else:
            label = "NEUTRAL_TRANSITIONAL"
        if label in assigned:
            label = f"{label}_{state_id}"
        assigned.add(label)
        state_labels[state_id] = label
    return state_labels

def train_expert(X, y, fallback_model=None):
    if len(X) < 100 and fallback_model is not None:
        return fallback_model
    mlp = MLPClassifier(
        hidden_layer_sizes=(16, 8),
        activation="relu",
        solver="adam",
        max_iter=1000,
        random_state=42,
        early_stopping=True
    )
    if len(np.unique(y)) < 2:
        # Cannot train if only 1 class is present, use fallback
        return fallback_model if fallback_model else mlp.fit(X, y)
    mlp.fit(X, y)
    return mlp

def train_moe_classifiers(df, feature_names, hmm_model, scaler_hmm, state_labels, output_path):
    logging.info("Training Mixture of Experts (MoE) Deep Classifiers...")
    
    # Target labeling: 0=Risk-Off (SPX drop), 1=Risk-On (SPX rally), 2=Transitional
    forward_spx_5d = df["spx_ret"].shift(-5).rolling(5).sum().fillna(0)
    df["y"] = np.where(forward_spx_5d > 1.5, 1, np.where(forward_spx_5d < -1.5, 0, 2))
    
    X_all = df[feature_names].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_all)
    y_all = df["y"].values
    
    # Train Base Expert (Fallback)
    logging.info("Training Base MLP...")
    mlp_base = train_expert(X_scaled, y_all)
    
    # Split by Regime
    hmm_preds = hmm_model.predict(scaler_hmm.transform(X_all))
    df["regime_label"] = pd.Series(hmm_preds).map(state_labels).values
    
    mask_bull = df["regime_label"].str.contains("RISK|RALLY", na=False)
    mask_bear = df["regime_label"].str.contains("STRESS|SHOCK|FEAR", na=False)
    mask_neutral = df["regime_label"].str.contains("NEUTRAL", na=False)
    
    logging.info(f"MoE Split - Bull: {mask_bull.sum()}, Bear: {mask_bear.sum()}, Neutral: {mask_neutral.sum()}")
    
    mlp_bull = train_expert(X_scaled[mask_bull], y_all[mask_bull], mlp_base) if mask_bull.sum() > 0 else mlp_base
    mlp_bear = train_expert(X_scaled[mask_bear], y_all[mask_bear], mlp_base) if mask_bear.sum() > 0 else mlp_base
    mlp_neutral = train_expert(X_scaled[mask_neutral], y_all[mask_neutral], mlp_base) if mask_neutral.sum() > 0 else mlp_base
    
    mlp_package = {
        "model_base": mlp_base,
        "model_bull": mlp_bull,
        "model_bear": mlp_bear,
        "model_neutral": mlp_neutral,
        "scaler": scaler,
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat()
    }
    joblib.dump(mlp_package, output_path)
    logging.info(f"MoE Package saved successfully to {output_path}")

def train_hmm(interval="1d"):
    OUTPUT_PATH_HMM, OUTPUT_PATH_MLP = get_model_paths(interval)
    df = fetch_training_data(interval=interval)
    
    feature_names = [
        "spx_ret_z", "dxy_ret_z", "vix_zscore", "wti_ret_z", "gsr_ret_z", 
        "us10y_delta_z", "spread_delta_z", "crypto_mfi_z", "Inst_Heat_Index", "usdcad_ret_z"
    ]
    
    X = df[feature_names].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logging.info(f"Training HMM with {N_HIDDEN_STATES} states on {len(X)} observations...")
    
    # CRITICAL: min_covar=0.01 for covariance regularization
    hmm = GaussianHMM(
        n_components=N_HIDDEN_STATES,
        covariance_type="full",
        n_iter=N_ITERATIONS,
        tol=1e-4,
        random_state=42,
        verbose=False,
        min_covar=0.01 
    )
    hmm.fit(X_scaled)
    state_labels = label_states_by_emission(hmm, feature_names)
    logging.info(f"State labels assigned: {state_labels}")
    
    os.makedirs(os.path.dirname(OUTPUT_PATH_HMM), exist_ok=True)
    model_package = {
        "hmm":           hmm,
        "scaler":        scaler,
        "state_labels":  state_labels,
        "feature_names": feature_names,
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "n_observations": len(X),
    }
    joblib.dump(model_package, OUTPUT_PATH_HMM)
    logging.info(f"HMM Model saved to {OUTPUT_PATH_HMM}")
    
    train_moe_classifiers(df, feature_names, hmm, scaler, state_labels, OUTPUT_PATH_MLP)
    
    print(f"[OK] Both HMM and Deep MLP classifiers trained successfully for interval {interval}!")
    return model_package

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", choices=["1d", "1wk", "1h", "4h"])
    args = parser.parse_args()
    train_hmm(interval=args.interval)
