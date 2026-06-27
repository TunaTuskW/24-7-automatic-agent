import os
import joblib
import pandas as pd
import numpy as np
import yfinance as yf

from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from src.engines.feature_engine import ALL_YF_TICKERS, ROLLING_DAYS
from src.observability.logger import get_logger
import argparse

logger = get_logger("train-models")

def fetch_training_data(interval="1d", period="10y"):
    tickers = list(ALL_YF_TICKERS.values()) + ["^TNX", "GLD"]
    logger.info(f"Fetching {period} of data for {len(tickers)} tickers... (interval={interval})")
    
    # yf interval 4h is not valid for 10y, so we might have to use 1d and simulate, or use 60d for 1h/4h
    if interval in ["1h", "4h"]:
        period = "730d"  # max for 1h
        
    raw_data = yf.download(tickers, period=period, interval=interval, group_by="ticker", auto_adjust=True, progress=False)
    
    def safe_get(ticker, col="Close"):
        try:
            if ticker in raw_data and col in raw_data[ticker]:
                return raw_data[ticker][col].ffill().bfill()
        except:
            pass
        # Fallback to empty series of same index
        idx = raw_data.index if not raw_data.empty else []
        return pd.Series(0.0, index=idx)

    spx_close = safe_get("^GSPC", "Close")
    spx_vol = safe_get("^GSPC", "Volume")
    
    # 1. spx_ret
    spx_ret = spx_close.pct_change(fill_method=None) * 100
    
    # 2. dxy_ret
    dxy_close = safe_get("DX-Y.NYB", "Close")
    dxy_ret = dxy_close.pct_change(fill_method=None) * 100
    
    # 3. vix_zscore
    vix_close = safe_get("^VIX", "Close")
    vix_zscore = (vix_close - vix_close.rolling(ROLLING_DAYS).mean()) / vix_close.rolling(ROLLING_DAYS).std()
    
    # 4. Inst_Heat_Index
    vol_mean = spx_vol.rolling(20).mean()
    vol_std = spx_vol.rolling(20).std()
    effort_z = (spx_vol - vol_mean) / vol_std.replace(0, 0.0001)
    recent_low = spx_close.rolling(10).min()
    recent_high = spx_close.rolling(10).max()
    result_vector = (spx_close - recent_low) / (recent_high - recent_low).replace(0, 0.0001)
    result_vector = result_vector.fillna(0.5)
    ihi = effort_z * (result_vector - 0.5)
    
    # 5. wti_ret
    wti_ret = safe_get("CL=F", "Close").pct_change(fill_method=None) * 100
    
    # 6. gsr_ret
    gc_close = safe_get("GC=F", "Close")
    si_close = safe_get("SI=F", "Close")
    # avoid division by zero
    gsr_series = gc_close / si_close.replace(0, np.nan)
    gsr_ret = gsr_series.pct_change(fill_method=None) * 100
    
    # 7. us10y_delta & 8. spread_level
    us10y = safe_get("^TNX", "Close")
    us2y = safe_get("^FVX", "Close")  # 2-year Treasury, matches inference (FRED DGS2 / Yahoo ^FVX)
    us10y_delta = us10y.diff()
    spread_2s10s = us10y - us2y
    
    # 9. btc_ret
    btc_ret = safe_get("BTC-USD", "Close").pct_change(fill_method=None) * 100
    
    # 10. es_ret, nq_ret, rty_ret
    es_ret = safe_get("ES=F", "Close").pct_change(fill_method=None) * 100
    nq_ret = safe_get("NQ=F", "Close").pct_change(fill_method=None) * 100
    rty_ret = safe_get("RTY=F", "Close").pct_change(fill_method=None) * 100
    
    # Single Names
    nvda_ret = safe_get("NVDA", "Close").pct_change(fill_method=None) * 100
    tsla_ret = safe_get("TSLA", "Close").pct_change(fill_method=None) * 100
    dell_ret = safe_get("DELL", "Close").pct_change(fill_method=None) * 100
    spce_ret = safe_get("SPCE", "Close").pct_change(fill_method=None) * 100
    
    # 17. spx_rsi_14
    delta = spx_close.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, 0.0001)
    spx_rsi_14 = 100 - (100 / (1 + rs))
    
    # 18. spx_macd_hist
    ema12 = spx_close.ewm(span=12, adjust=False).mean()
    ema26 = spx_close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    spx_macd_hist = macd_line - signal_line
    
    # 19. spx_bbw
    sma20 = spx_close.rolling(window=20).mean()
    std20_bb = spx_close.rolling(window=20).std()
    spx_bbw = (4 * std20_bb) / sma20.replace(0, 0.0001)
    
    # 20. spx_vix_corr
    vix_ret = vix_close.pct_change(fill_method=None) * 100
    spx_vix_corr = spx_ret.rolling(window=10).corr(vix_ret)

    # Note: Returns will be used for RL environment
    df = pd.DataFrame({
        "spx_ret": spx_ret,
        "dxy_ret": dxy_ret,
        "vix_zscore": vix_zscore,
        "Inst_Heat_Index": ihi,
        "wti_ret": wti_ret,
        "gsr_ret": gsr_ret,
        "us10y_delta": us10y_delta,
        "spread_level": spread_2s10s,
        "btc_ret": btc_ret,
        "es_ret": es_ret,
        "nq_ret": nq_ret,
        "rty_ret": rty_ret,
        "nvda_ret": nvda_ret,
        "tsla_ret": tsla_ret,
        "dell_ret": dell_ret,
        "spce_ret": spce_ret,
        "spx_rsi_14": spx_rsi_14,
        "spx_macd_hist": spx_macd_hist,
        "spx_bbw": spx_bbw,
        "spx_vix_corr": spx_vix_corr,
        
        # Additional returns needed for RL env
        "gld_ret": raw_data["GLD"]["Close"].pct_change(fill_method=None) * 100
    })
    
    # For HMM/MLP, we need z-scores for returns.
    # We will just ffill and fillna
    df = df.ffill().fillna(0.0)
    return df

def train(interval="1d"):
    df = fetch_training_data(interval=interval, period="10y" if interval=="1d" else "730d")
    
    # 20 feature columns
    feature_cols = [
        "spx_ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret",
        "gsr_ret", "us10y_delta", "spread_level", "btc_ret", "es_ret", 
        "nq_ret", "rty_ret", "nvda_ret", "tsla_ret", "dell_ret", "spce_ret",
        "spx_rsi_14", "spx_macd_hist", "spx_bbw", "spx_vix_corr"
    ]
    
    X_df = df[feature_cols].copy()
    
    # Z-score the raw returns to match production feature_engine
    returns_cols = ["spx_ret", "dxy_ret", "wti_ret", "gsr_ret", "btc_ret", "es_ret", "nq_ret", "rty_ret", "nvda_ret", "tsla_ret", "dell_ret", "spce_ret"]
    for col in returns_cols:
        X_df[col] = (X_df[col] - X_df[col].rolling(ROLLING_DAYS).mean()) / X_df[col].rolling(ROLLING_DAYS).std()
        
    X_df = X_df.dropna()
    
    # Target for MLP: 1-bar forward SPX return > 0
    y = (df["spx_ret"].shift(-1) > 0).astype(int).loc[X_df.index].values
    X = X_df.values
    
    logger.info(f"Training on dataset of shape {X.shape} for interval {interval}")
    
    scaler_mlp = StandardScaler()
    X_scaled = scaler_mlp.fit_transform(X)
    
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42)
    mlp.fit(X_scaled, y)
    
    mlp_package = {
        "model_base": mlp,
        "model_bull": mlp,
        "model_bear": mlp,
        "model_neutral": mlp,
        "scaler": scaler_mlp
    }
    
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "..", "models"), exist_ok=True)
    shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", f"mlp_model_{interval}.pkl")
    joblib.dump(mlp_package, shared_path)
    if interval == "4h":
        default_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", f"mlp_model.pkl")
        joblib.dump(mlp_package, default_shared_path)
    
    # Also save under per-asset names so load_mlp_models can find them
    for asset in ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]:
        asset_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", f"mlp_model_{asset}_{interval}.pkl")
        joblib.dump(mlp_package, asset_path)
        if interval == "4h":
            default_asset_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", f"mlp_model_{asset}.pkl")
            joblib.dump(mlp_package, default_asset_path)
        
    logger.info(f"Retraining complete for {interval}. Models saved (shared + per-asset).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d")
    args = parser.parse_args()
    train(interval=args.interval)
