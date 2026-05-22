#!/usr/bin/env python3
"""
train_models.py
Offline training script for HMM regime classifier.
Run once before deploying v2.0.0, then quarterly.
Saves trained model to data/hmm_model.pkl

Usage: python3 src/train_models.py
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

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

TRAINING_YEARS   = 5       # years of historical data
N_HIDDEN_STATES  = 6       # matches our six regime labels
N_ITERATIONS     = 500     # HMM EM training iterations
OUTPUT_PATH      = os.path.join(os.path.dirname(__file__), '..', 'data', 'hmm_model.pkl')
SCALER_PATH      = os.path.join(os.path.dirname(__file__), '..', 'data', 'hmm_scaler.pkl')

# Regime label mapping — assigned post-training based on emission means
# The HMM learns N_HIDDEN_STATES latent states. We label them after training
# by inspecting which emission means correspond to known regime patterns.
REGIME_LABELS = [
    "RISK_ON_EXPANSION",
    "LIQUIDITY_DRIVEN_RALLY",
    "STAGFLATION_STRESS",
    "RATE_SHOCK",
    "DEFLATION_FEAR",
    "NEUTRAL_TRANSITIONAL",
]

# ── DATA COLLECTION ────────────────────────────────────────────────────────────

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
    """
    Fetch historical daily data for HMM training features.
    Features: SPX return, US10Y delta, WTI return, DXY return,
              SPX GARCH vol, 2s10s spread delta
    Returns a numpy array of shape (n_observations, n_features)
    """
    logging.info(f"Fetching {years} years of training data...")
    period = f"{years * 365}d"

    fred_key = get_fred_key()

    # Equity and energy
    spx = yf.Ticker("^GSPC").history(period=period)["Close"]
    wti = yf.Ticker("CL=F").history(period=period)["Close"]
    dxy = yf.Ticker("DX-Y.NYB").history(period=period)["Close"]

    spx_ret = spx.pct_change() * 100
    wti_ret = wti.pct_change() * 100
    dxy_ret = dxy.pct_change() * 100

    # GARCH volatility on SPX returns
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

    # Treasury yields from FRED
    us2y_series = None
    us10y_series = None
    if fred_key:
        for series_id, var_name in [("DGS2", "us2y"), ("DGS10", "us10y")]:
            try:
                start_date = (
                    datetime.now(timezone.utc) - timedelta(days=years * 366)
                ).strftime("%Y-%m-%d")
                url = "https://api.stlouisfed.org/fred/series/observations"
                params = {
                    "series_id":         series_id,
                    "api_key":           fred_key,
                    "file_type":         "json",
                    "observation_start": start_date,
                }
                resp = requests.get(url, params=params, timeout=15, verify=True)
                resp.raise_for_status()
                obs = [
                    (o["date"], float(o["value"]))
                    for o in resp.json()["observations"]
                    if o["value"] != "."
                ]
                s = pd.Series(
                    dict(obs),
                    name=series_id,
                    dtype=float
                )
                s.index = pd.to_datetime(s.index)
                try:
                    s.index = s.index.tz_localize(None)
                except Exception:
                    pass
                if var_name == "us2y":
                    us2y_series = s
                else:
                    us10y_series = s
            except Exception as e:
                logging.warning(f"FRED {series_id} fetch failed: {e}")

    # Build feature dataframe — align all series on business days
    df = pd.DataFrame({
        "spx_ret":      spx_ret,
        "wti_ret":      wti_ret,
        "dxy_ret":      dxy_ret,
        "spx_garch_vol": spx_garch_vol,
    })
    df.index = pd.to_datetime(df.index).tz_localize(None)

    if us10y_series is not None:
        us10y_delta = us10y_series.diff()
        df["us10y_delta"] = us10y_delta.reindex(df.index, method="ffill")
    else:
        logging.warning("US10Y unavailable — using zero placeholder for training")
        df["us10y_delta"] = 0.0

    if us2y_series is not None and us10y_series is not None:
        spread = (us10y_series - us2y_series).diff()
        df["spread_delta"] = spread.reindex(df.index, method="ffill")
    else:
        df["spread_delta"] = 0.0

    df = df.dropna()
    logging.info(f"Training data shape: {df.shape}")
    return df


# ── REGIME LABELING ────────────────────────────────────────────────────────────

def label_states_by_emission(hmm_model, feature_names):
    """
    After training, assign human-readable regime labels to HMM states
    by inspecting the emission means of each hidden state.
    
    Labeling logic based on emission mean patterns:
    - High spx_ret, low us10y_delta        → RISK_ON_EXPANSION
    - High spx_ret, negative us10y_delta   → LIQUIDITY_DRIVEN_RALLY  
    - Negative spx_ret, high wti_ret       → STAGFLATION_STRESS
    - Negative spx_ret, high us10y_delta   → RATE_SHOCK
    - Negative spx_ret, negative wti_ret   → DEFLATION_FEAR
    - Near-zero everything                 → NEUTRAL_TRANSITIONAL
    """
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

        # Prevent duplicate labels — append state_id if collision
        if label in assigned:
            label = f"{label}_{state_id}"
        assigned.add(label)
        state_labels[state_id] = label

    return state_labels


# ── TRAINING ───────────────────────────────────────────────────────────────────

def train_hmm():
    df = fetch_training_data()

    feature_names = [
        "spx_ret", "wti_ret", "dxy_ret",
        "spx_garch_vol", "us10y_delta", "spread_delta"
    ]

    X = df[feature_names].values

    # Standardize features
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

    # Label states
    state_labels = label_states_by_emission(hmm, feature_names)
    logging.info(f"State labels assigned: {state_labels}")

    # Compute transition matrix summary
    trans_matrix = hmm.transmat_
    logging.info("Transition matrix (rows = from, cols = to):")
    for i in range(N_HIDDEN_STATES):
        row = " | ".join([f"{trans_matrix[i,j]:.3f}" for j in range(N_HIDDEN_STATES)])
        logging.info(f"  State {i} ({state_labels[i]}): {row}")

    # Save model, scaler, and metadata
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    model_package = {
        "hmm":           hmm,
        "scaler":        scaler,
        "state_labels":  state_labels,
        "feature_names": feature_names,
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "n_observations": len(X),
    }

    joblib.dump(model_package, OUTPUT_PATH)
    logging.info(f"Model saved to {OUTPUT_PATH}")

    # Validation — decode training sequence and report state distribution
    states = hmm.predict(X_scaled)
    from collections import Counter
    state_dist = Counter(states)
    logging.info("Training state distribution:")
    for state_id, count in sorted(state_dist.items()):
        pct = count / len(states) * 100
        logging.info(f"  {state_labels[state_id]}: {count} days ({pct:.1f}%)")

    print(f"[OK] HMM trained and saved — {N_HIDDEN_STATES} states, "
          f"{len(X)} observations, {N_ITERATIONS} iterations")
    return model_package


if __name__ == "__main__":
    train_hmm()
