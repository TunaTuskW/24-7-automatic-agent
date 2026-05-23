#!/usr/bin/env python3
"""
train_models.py - v3.0.0
Offline training script for HMM regime classifier and MLP Deep Classifier.
Run quarterly. Saves trained models to data/
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
warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
# Configuration
TRAINING_YEARS   = 5
N_HIDDEN_STATES  = 6
N_ITERATIONS     = 500
OUTPUT_PATH_HMM  = os.path.join(os.path.dirname(__file__), '..', 'data', 'hmm_model.pkl')
OUTPUT_PATH_MLP  = os.path.join(os.path.dirname(__file__), '..', 'data', 'mlp_model.pkl')
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
def fetch_training_data(years=TRAINING_YEARS):
    logging.info(f"Fetching {years} years of training data...")
    period = f"{years * 365}d"
    fred_key = get_fred_key()
    tickers = ["^GSPC", "CL=F", "DX-Y.NYB", "SI=F", "USDCAD=X", "GC=F"]
    data = yf.download(tickers, period=period, progress=False)
    
    spx = data["Close"]["^GSPC"].dropna()
    wti = data["Close"]["CL=F"].dropna()
    dxy = data["Close"]["DX-Y.NYB"].dropna()
    silver = data["Close"]["SI=F"].dropna()
    usdcad = data["Close"]["USDCAD=X"].dropna()
    gold = data["Close"]["GC=F"].dropna()
    
    spx_vol = data["Volume"]["^GSPC"].dropna()
    spx_high = data["High"]["^GSPC"].dropna()
    spx_low = data["Low"]["^GSPC"].dropna()

    for s in [spx, wti, dxy, silver, usdcad, gold, spx_vol, spx_high, spx_low]:
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()

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
        "usdcad_ret":    usdcad_ret,
        "Volume":        spx_vol,
        "High":          spx_high,
        "Low":           spx_low,
        "Close":         spx
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
    
    # Calculate Institutional Heat Index (Continuous)
    vol_sma20 = df["Volume"].rolling(20).mean()
    vol_std20 = df["Volume"].rolling(20).std()
    effort_z = (df["Volume"] - vol_sma20) / vol_std20
    range_size = df["High"] - df["Low"]
    result_vector = ((df["Close"] - df["Low"]) / range_size.replace(0, 0.0001)) - 0.5
    
    # Continuous calculation matches live ingestion perfectly
    df["Inst_Heat_Index"] = effort_z * result_vector
    
    # CRITICAL: Drop NaNs generated by the new 20-day rolling windows
    df = df.dropna()
    logging.info(f"Training data shape: {df.shape}")
    return df
def label_states_by_emission(hmm_model, feature_names):
    means = hmm_model.means_
    state_labels = {}
    spx_idx = feature_names.index("spx_ret")
    us10y_idx = feature_names.index("us10y_delta")
    wti_idx = feature_names.index("wti_ret")
    assigned = set()
    for state_id in range(len(means)):
        spx_m  = means[state_id][spx_idx]
        us10y_m = means[state_id][us10y_idx]
        wti_m  = means[state_id][wti_idx]
        if spx_m > 0.3 and us10y_m > 0.01:
            label = "RISK_ON_EXPANSION"
        elif spx_m > 0.3 and us10y_m < -0.01:
            label = "LIQUIDITY_DRIVEN_RALLY"
        elif spx_m < -0.2 and wti_m > 0.5:
            label = "STAGFLATION_STRESS"
        elif spx_m < -0.2 and us10y_m > 0.02:
            label = "RATE_SHOCK"
        elif spx_m < -0.2 and wti_m < -0.3:
            label = "DEFLATION_FEAR"
        else:
            label = "NEUTRAL_TRANSITIONAL"
        if label in assigned:
            label = f"{label}_{state_id}"
        assigned.add(label)
        state_labels[state_id] = label
    return state_labels
def train_mlp_classifier(df, feature_names, output_path):
    logging.info("Training MLP Deep Classifier...")
    X = df[feature_names].values
    
    # Target labeling: 0=Risk-Off (SPX drop), 1=Risk-On (SPX rally), 2=Transitional
    forward_spx_5d = df["spx_ret"].shift(-5).rolling(5).sum().fillna(0)
    y = np.where(forward_spx_5d > 1.5, 1, np.where(forward_spx_5d < -1.5, 0, 2))
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Neural architecture: 9 inputs -> 16 hidden -> 8 hidden -> 3 outputs
    mlp = MLPClassifier(
        hidden_layer_sizes=(16, 8),
        activation="relu",
        solver="adam",
        max_iter=1000,
        random_state=42,
        early_stopping=True
    )
    mlp.fit(X_scaled, y)
    
    mlp_package = {
        "model": mlp,
        "scaler": scaler,
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat()
    }
    joblib.dump(mlp_package, output_path)
    logging.info(f"MLP Deep Classifier saved successfully to {output_path}")
def train_hmm():
    df = fetch_training_data()
    
    # Aligned 10 features schema
    feature_names = [
        "spx_ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret", 
        "gsr_ret", "us10y_delta", "spread_level", "crypto_mfi_z", "usdcad_ret"
    ]
    
    X = df[feature_names].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logging.info(f"Training HMM with {N_HIDDEN_STATES} states on {len(X)} observations...")
    hmm = GaussianHMM(
        n_components=N_HIDDEN_STATES,
        covariance_type="full",
        n_iter=N_ITERATIONS,
        tol=1e-4,
        random_state=42,
        verbose=False,
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
    # Train supervised MLP classifier in parallel
    train_mlp_classifier(df, feature_names, OUTPUT_PATH_MLP)
    
    print("[OK] Both HMM and Deep MLP classifiers trained successfully!")
    return model_package
if __name__ == "__main__":
    train_hmm()
