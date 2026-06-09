import os
import joblib
import pandas as pd
import numpy as np
import yfinance as yf
from hmmlearn.hmm import GaussianHMM
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from src.engines.feature_engine import ALL_YF_TICKERS, ROLLING_DAYS
from src.observability.logger import get_logger

logger = get_logger("train-models")

def build_features_df(period="10y"):
    tickers = list(ALL_YF_TICKERS.values())
    logger.info(f"Fetching {period} of data for {len(tickers)} tickers...")
    raw_data = yf.download(tickers, period=period, interval="1d", group_by="ticker", auto_adjust=True, progress=False)
    
    df_list = []
    
    # We will compute the 10 raw features historically
    # 1. SPX_ret
    spx_close = raw_data["^GSPC"]["Close"]
    spx_ret = spx_close.pct_change() * 100
    
    # 2. DXY_ret
    dxy_close = raw_data["DX-Y.NYB"]["Close"]
    dxy_ret = dxy_close.pct_change() * 100
    
    # 3. VIX_zscore (We will compute rolling z-score of VIX close)
    vix_close = raw_data["^VIX"]["Close"]
    vix_zscore = (vix_close - vix_close.rolling(ROLLING_DAYS).mean()) / vix_close.rolling(ROLLING_DAYS).std()
    
    # 4. WTI_ret
    wti_close = raw_data["CL=F"]["Close"]
    wti_ret = wti_close.pct_change() * 100
    
    # 5. GoldSilverRatio_ret
    gold_close = raw_data["GC=F"]["Close"]
    silver_close = raw_data["SI=F"]["Close"]
    gsr = gold_close / silver_close
    gsr_ret = gsr.pct_change() * 100
    
    # 6. US10Y_delta
    # 7. US_2s10s_spread
    try:
        from pandas_datareader import data as pdr
        us10y = pdr.get_data_fred('DGS10', start=spx_close.index[0], end=spx_close.index[-1])['DGS10']
        us2y = pdr.get_data_fred('DGS2', start=spx_close.index[0], end=spx_close.index[-1])['DGS2']
    except:
        # Fallback to yfinance proxy for 10Y
        tnx = yf.download("^TNX", period=period, interval="1d", progress=False)["Close"]
        if isinstance(tnx, pd.DataFrame):
            tnx = tnx.squeeze()
        us10y = tnx
        us2y = pd.Series(index=spx_close.index, data=0.0) # Cannot easily get 2y from yf without ^IRX etc.
        
    us10y = us10y.reindex(spx_close.index).ffill()
    us2y = us2y.reindex(spx_close.index).ffill()
    
    us10y_delta = us10y.diff()
    spread_2s10s = us10y - us2y
    
    # 8. CryptoMFI_zscore
    btc_close = raw_data["BTC-USD"]["Close"]
    btc_ret = btc_close.pct_change() * 100
    crypto_zscore = (btc_ret - btc_ret.rolling(ROLLING_DAYS).mean()) / btc_ret.rolling(ROLLING_DAYS).std()
    
    # 9. VolumeHeat_ihi
    spx_vol = raw_data["^GSPC"]["Volume"]
    vol_mean = spx_vol.rolling(20).mean()
    vol_std = spx_vol.rolling(20).std()
    effort_z = (spx_vol - vol_mean) / vol_std
    
    recent_low = spx_close.rolling(10).min()
    recent_high = spx_close.rolling(10).max()
    result_vector = (spx_close - recent_low) / (recent_high - recent_low)
    result_vector = result_vector.fillna(0.5)
    ihi = effort_z * (result_vector - 0.5)
    
    # 10. USDCAD_ret
    usdcad_close = raw_data["USDCAD=X"]["Close"]
    usdcad_ret = usdcad_close.pct_change() * 100
    
    features_df = pd.DataFrame({
        "SPX_ret": spx_ret.reindex(spx_close.index),
        "DXY_ret": dxy_ret.reindex(spx_close.index).ffill(),
        "WTI_ret": wti_ret.reindex(spx_close.index).ffill(),
        "GoldSilverRatio_ret": gsr_ret.reindex(spx_close.index).ffill(),
        "US10Y_delta": us10y_delta.reindex(spx_close.index).ffill(),
        "US_2s10s_spread": spread_2s10s.reindex(spx_close.index).ffill(),
        "USDCAD_ret": usdcad_ret.reindex(spx_close.index).ffill()
    })
    
    # Fill NAs and drop first 60 days
    features_df = features_df.ffill().fillna(0.0)
    
    # Convert ONLY raw return features to 60-day rolling z-scores
    zscore_df = (features_df - features_df.rolling(ROLLING_DAYS).mean()) / features_df.rolling(ROLLING_DAYS).std()
    
    # Add back the features that were already natively z-scored
    zscore_df["VIX_zscore"] = vix_zscore.reindex(spx_close.index).ffill().fillna(0.0)
    zscore_df["CryptoMFI_zscore"] = crypto_zscore.reindex(spx_close.index).ffill().fillna(0.0)
    zscore_df["VolumeHeat_ihi"] = ihi.reindex(spx_close.index).ffill().fillna(0.0)
    
    # Reorder columns to match fetch_market_data.py
    ordered_cols = ["SPX_ret", "DXY_ret", "VIX_zscore", "WTI_ret", "GoldSilverRatio_ret", "US10Y_delta", "US_2s10s_spread", "CryptoMFI_zscore", "VolumeHeat_ihi", "USDCAD_ret"]
    zscore_df = zscore_df[ordered_cols]
    
    # Drop rows with NaNs (the first 60 days of rolling window)
    zscore_df = zscore_df.dropna()
    
    # Target for MLP: 5-day forward SPX return > 0
    zscore_df["Target"] = (spx_close.shift(-5) > spx_close).astype(int)[zscore_df.index]
    
    return zscore_df

def train():
    df = build_features_df(period="10y")
    if df.empty:
        logger.error("Failed to build features DataFrame.")
        return
        
    X = df.drop(columns=["Target"]).values
    y = df["Target"].values
    
    logger.info(f"Training on dataset of shape {X.shape}")
    
    # 1. Train MLP
    scaler_mlp = StandardScaler()
    X_scaled = scaler_mlp.fit_transform(X)
    
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42)
    mlp.fit(X_scaled, y)
    
    mlp_package = {
        "model_base": mlp,
        "model_bull": mlp,  # Can be specialized later
        "model_bear": mlp,
        "model_neutral": mlp,
        "scaler": scaler_mlp
    }
    
    # 2. Train HMM with Covariance Regularization
    scaler_hmm = StandardScaler()
    X_hmm_scaled = scaler_hmm.fit_transform(X)
    
    # min_covar=0.01 prevents mathematical collapse in low volatility
    hmm = GaussianHMM(n_components=5, covariance_type="diag", n_iter=100, random_state=42, min_covar=0.01)
    hmm.fit(X_hmm_scaled)
    
    # Heuristically label states based on SPX return means in each state
    hidden_states = hmm.predict(X_hmm_scaled)
    state_returns = {}
    for i in range(5):
        mask = (hidden_states == i)
        state_returns[i] = df["SPX_ret"].iloc[mask].mean() if np.sum(mask) > 0 else 0
        
    sorted_states = sorted(state_returns.items(), key=lambda x: x[1])
    
    state_labels = {
        sorted_states[0][0]: "CRISIS_DISLOCATION",
        sorted_states[1][0]: "STAGFLATION_STRESS",
        sorted_states[2][0]: "NEUTRAL_TRANSITIONAL",
        sorted_states[3][0]: "RISK_ON_EXPANSION",
        sorted_states[4][0]: "LIQUIDITY_DRIVEN_RALLY"
    }
    
    hmm_package = {
        "hmm": hmm,
        "scaler": scaler_hmm,
        "state_labels": state_labels
    }
    
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', '..', 'models'), exist_ok=True)
    joblib.dump(mlp_package, os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'mlp_model.pkl'))
    joblib.dump(hmm_package, os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'hmm_model.pkl'))
    
    logger.info("Retraining complete. Models saved to /models.")

if __name__ == "__main__":
    train()
