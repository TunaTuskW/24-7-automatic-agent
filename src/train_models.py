import os
import json
import logging
import concurrent.futures
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, classification_report, brier_score_loss

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger("train-models")

TRAINING_YEARS = 5

def get_fred_key():
    key = os.environ.get("FRED_API_KEY")
    if key: return key
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'fred_api_key.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("PASTE"):
                return key
    return None

def fetch_training_data(years=TRAINING_YEARS, interval="1d"):
    period = f"{years * 365}d"
    if interval == "1h": period = "1y"
    elif interval != "1d": period = "729d"
    logger.info(f"Fetching {period} of training data with interval {interval}...")
    
    fred_key = get_fred_key()
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "tickers.json")
    active_syms = []
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
            active_syms = [tk["symbol"] for tk in cfg.get("active_tickers", [])]
            
    # Always get global macro indicators
    macro_tickers = ["^GSPC", "CL=F", "DX-Y.NYB", "SI=F", "USDCAD=X", "GC=F", "^VIX"]
    # Handle crypto mapping
    yf_active = ["BTC-USD" if s == "BTC" else s for s in active_syms]
    tickers = list(set(macro_tickers + yf_active))
    
    data = yf.download(tickers, period=period, interval=interval, progress=False)
    
    # Global Macro Extractions
    macro_data = {}
    macro_map = {
        "^GSPC": "spx",
        "CL=F": "wti",
        "DX-Y.NYB": "dxy",
        "SI=F": "silver",
        "USDCAD=X": "usdcad",
        "GC=F": "gold",
        "^VIX": "vix"
    }
    
    for yf_sym, name in macro_map.items():
        try:
            s = data["Close"][yf_sym].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            if interval == "1d": s.index = s.index.normalize()
            s = s[~s.index.duplicated(keep='last')]
            macro_data[f"{name}_close"] = s
            
            if name == "spx":
                v = data["Volume"]["^GSPC"].dropna()
                v.index = pd.to_datetime(v.index).tz_localize(None)
                if interval == "1d": v.index = v.index.normalize()
                v = v[~v.index.duplicated(keep='last')]
                macro_data["spx_vol"] = v
        except Exception as e:
            logger.warning(f"Could not load macro data {yf_sym}: {e}")

    # FRED
    us2y_series = None
    us10y_series = None
    if fred_key:
        for series_id, var_name in [("DGS2", "us2y"), ("DGS10", "us10y")]:
            try:
                start_date = (datetime.now(timezone.utc) - timedelta(days=years * 366)).strftime("%Y-%m-%d")
                url = "https://api.stlouisfed.org/fred/series/observations"
                params = {"series_id": series_id, "api_key": fred_key, "file_type": "json", "observation_start": start_date}
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                obs = [(o["date"], float(o["value"])) for o in resp.json()["observations"] if o["value"] != "."]
                s = pd.Series(dict(obs), name=series_id, dtype=float)
                s.index = pd.to_datetime(s.index).tz_localize(None)
                if var_name == "us2y": us2y_series = s
                else: us10y_series = s
            except Exception as e:
                logger.warning(f"FRED fetch failed: {e}")

    return data, macro_data, us2y_series, us10y_series, active_syms

def build_features_for_ticker(ticker, data, macro_data, us2y_series, us10y_series, interval):
    yf_sym = "BTC-USD" if ticker == "BTC" else ticker
    
    try:
        tk_close = data["Close"][yf_sym].dropna()
        tk_high = data["High"][yf_sym].dropna()
        tk_low = data["Low"][yf_sym].dropna()
        tk_vol = data["Volume"][yf_sym].dropna()
        
        for s in [tk_close, tk_high, tk_low, tk_vol]:
            s.index = pd.to_datetime(s.index).tz_localize(None)
            if interval == "1d": s.index = s.index.normalize()
    except Exception as e:
        logger.warning(f"Failed to extract {ticker}: {e}")
        return None, []
        
    df_dict = {
        "Close": tk_close,
        "High": tk_high,
        "Low": tk_low,
        "Volume": tk_vol,
        "ret": tk_close.pct_change() * 100
    }
    
    # Global Macro base
    if "dxy_close" in macro_data: df_dict["dxy_ret"] = macro_data["dxy_close"].pct_change() * 100
    if "wti_close" in macro_data: df_dict["wti_ret"] = macro_data["wti_close"].pct_change() * 100
    if "gold_close" in macro_data and "silver_close" in macro_data:
        df_dict["gsr_ret"] = (macro_data["gold_close"] / macro_data["silver_close"]).pct_change() * 100
    if "vix_close" in macro_data: df_dict["vix"] = macro_data["vix_close"]
    
    df = pd.DataFrame(df_dict).fillna(0)
    
    if us10y_series is not None:
        us10y_delta = us10y_series.diff()
        df["us10y_delta"] = us10y_delta.reindex(df.index, method="ffill").fillna(0)
    else:
        df["us10y_delta"] = 0.0
        
    if us2y_series is not None and us10y_series is not None:
        spread = (us10y_series - us2y_series).diff()
        df["spread_level"] = (us10y_series - us2y_series).reindex(df.index, method="ffill").fillna(0)
    else:
        df["spread_level"] = 0.0

    # Calculate Ticker-Specific Heat Index
    short_window = 21
    macro_window = 60
    if interval.endswith("h"):
        bars = 6.5 / float(interval.replace("h", "") or 1)
        short_window = int(21 * bars)
        macro_window = int(60 * bars)

    vix_mean = df["vix"].rolling(macro_window).mean()
    vix_std = df["vix"].rolling(macro_window).std()
    df["vix_zscore"] = ((df["vix"] - vix_mean) / vix_std.replace(0, np.nan)).fillna(0)

    vol_sma20 = df["Volume"].rolling(short_window).mean()
    vol_std20 = df["Volume"].rolling(short_window).std()
    effort_z = (df["Volume"] - vol_sma20) / vol_std20.replace(0, np.nan)
    range_size = df["High"] - df["Low"]
    result_vector = ((df["Close"] - df["Low"]) / range_size.replace(0, 0.0001)) - 0.5
    df["Inst_Heat_Index"] = (effort_z * result_vector).fillna(0)

    # Ticker Alpha features
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, 0.0001)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd_line - signal_line

    sma20 = df["Close"].rolling(window=20).mean()
    std20_bb = df["Close"].rolling(window=20).std()
    df["bbw"] = (4 * std20_bb) / sma20.replace(0, 0.0001)

    vix_ret = df["vix"].pct_change() * 100
    df["vix_corr"] = df["ret"].rolling(window=10).corr(vix_ret).fillna(0)

    df = df.dropna()
    
    feature_names = [
        "ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret", 
        "gsr_ret", "us10y_delta", "spread_level", "rsi_14", "macd_hist", "bbw", "vix_corr"
    ]
    return df, feature_names

def train_ensemble_classifier(df, feature_names, output_path, interval="1d", target_col="ret", threshold=1.5):
    logger.info(f"Training Ensemble Classifiers for {output_path}...")
    X = df[feature_names].values
    
    fwd_periods = 5
    if interval == "1wk": threshold *= 2.0
    elif interval == "4h": threshold *= 0.4
    elif interval == "1h": threshold *= 0.2
        
    forward_5d = df[target_col].rolling(fwd_periods).sum().shift(-fwd_periods)
    # Drop rows where we don't have future data
    valid_idx = forward_5d.notna()
    X = X[valid_idx]
    forward_5d = forward_5d[valid_idx]
    
    y = np.where(forward_5d > threshold, 1, np.where(forward_5d < -threshold, 0, 2))
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Proper time-series split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.15, shuffle=False)
    
    mlp = MLPClassifier(hidden_layer_sizes=(128, 64, 32), max_iter=500, early_stopping=True, validation_fraction=0.1, random_state=42)
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=20, random_state=42)
    gb = HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=0.5, random_state=42)
    
    mlp.fit(X_train, y_train)
    rf.fit(X_train, y_train)
    gb.fit(X_train, y_train)
    
    ensemble = VotingClassifier(
        estimators=[('mlp', mlp), ('rf', rf), ('gb', gb)],
        voting='soft',
        weights=[0.4, 0.3, 0.3]
    )
    ensemble.fit(X_train, y_train)
    
    # Optional: Log evaluation metrics on test set
    try:
        test_acc = ensemble.score(X_test, y_test)
        logger.info(f"Test Set Accuracy: {test_acc:.2%}")
    except Exception as e:
        logger.warning(f"Could not compute test accuracy: {e}")
    
    models_dir = os.path.dirname(output_path)
    os.makedirs(models_dir, exist_ok=True)
    
    joblib.dump({
        "model_mlp": mlp,
        "model_rf": rf,
        "model_gb": gb,
        "scaler": scaler,
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat()
    }, output_path)
    logger.info(f"Saved successfully to {output_path}")

def train_all_ml_models(interval="1d"):
    data, macro_data, us2y_series, us10y_series, active_syms = fetch_training_data(interval=interval)
    
    for tk in active_syms:
        df, feature_names = build_features_for_ticker(tk, data, macro_data, us2y_series, us10y_series, interval)
        if df is None or df.empty:
            logger.warning(f"Skipping {tk} due to insufficient data")
            continue
            
        # Dynamically set threshold based on asset volatility profile
        # Use 14-day ATR equivalent or a naive scaling
        std = df["ret"].std()
        tk_threshold = std * 1.5 if pd.notna(std) and std > 0 else 5.0
        
        output_mlp_asset = os.path.join(os.path.dirname(__file__), '..', 'models', f'mlp_model_{tk.lower()}_{interval}.pkl' if interval != "1d" else f'mlp_model_{tk.lower()}.pkl')
        train_ensemble_classifier(df, feature_names, output_mlp_asset, interval=interval, target_col="ret", threshold=tk_threshold)
        
    logger.info("All Ensemble models trained successfully!")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", help="Data interval (e.g., 1d, 4h)")
    args = parser.parse_args()
    train_all_ml_models(interval=args.interval)
