import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import json
import warnings
import argparse
import os
warnings.filterwarnings("ignore")

from src.engines.hmm_engine import HMMEngine
from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import ALL_YF_TICKERS, compute_stats, compute_volume_heat, run_mlp_inference, load_mlp_model

def run_backtest(interval="1d"):
    print(f"=== Starting Q1 2026 Quantitative Backtest ({interval}) ===")
    
    # We need rolling metrics, so we start fetching from late 2025
    start_fetch_date = "2025-11-01"
    end_fetch_date = "2026-06-05" # To get forward returns at end of May
    
    # Target backtest range
    q1_start = pd.to_datetime("2026-01-01")
    q1_end = pd.to_datetime("2026-05-30")
    
    tickers_to_fetch = list(ALL_YF_TICKERS.values()) + ["^TNX", "^FVX"]
    
    print(f"Downloading historical data from {start_fetch_date} to {end_fetch_date}...")
    try:
        raw_data = yf.download(tickers_to_fetch, start=start_fetch_date, end=end_fetch_date, interval=interval, group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print(f"Failed to download data: {e}")
        return

    # Extract SPX Trading days in Q1
    raw_data.index = raw_data.index.tz_localize(None)
    spx_data = raw_data["^GSPC"].dropna()
    q1_trading_days = spx_data[(spx_data.index >= q1_start) & (spx_data.index <= q1_end)].index
    
    hmm_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', f'hmm_model_{interval}.pkl')
    # Backward compatibility fallback
    if not os.path.exists(hmm_model_path) and interval == "1d":
        hmm_model_path = None # HMMEngine will fallback to hmm_model.pkl
        
    hmm = HMMEngine(model_path=hmm_model_path)
    risk = RiskEngine()
    mlp_package = load_mlp_model(interval)
    
    prior_k_state = None
    prior_k_cov = None
    
    results = []
    
    print(f"Found {len(q1_trading_days)} trading days in Q1 2026. Running simulation...")
    
    for i, current_date in enumerate(q1_trading_days):
        # 1. Slice data up to current_date
        historical_slice = raw_data[raw_data.index <= current_date]
        
        # 2. Extract series for each asset
        parsed_daily = {}
        for name, tk in ALL_YF_TICKERS.items():
            if tk in historical_slice.columns.levels[0]:
                tk_df = historical_slice[tk].dropna(how="all")
                if len(tk_df) > 10:
                    parsed_daily[name] = compute_stats(tk_df["Close"])
                    parsed_daily[name]["raw_series"] = tk_df["Close"]
        
        spx = parsed_daily.get("SPX")
        if not spx:
            continue
            
        # 3. Compute Complex Features
        # US10Y and US2Y
        us10y_yield = 0.0
        us2y_yield = 0.0
        if "^TNX" in historical_slice.columns.levels[0]:
            tnx_slice = historical_slice["^TNX"]["Close"].dropna()
            if len(tnx_slice) > 0:
                us10y_yield = float(tnx_slice.iloc[-1])
        if "^FVX" in historical_slice.columns.levels[0]:
            fvx_slice = historical_slice["^FVX"]["Close"].dropna()
            if len(fvx_slice) > 0:
                us2y_yield = float(fvx_slice.iloc[-1])
        
        us_2s10s_spread = 0.0
        us_2s10s_spread_z = 0.0
        if "^TNX" in historical_slice.columns.levels[0] and "^FVX" in historical_slice.columns.levels[0]:
            spread_series = (historical_slice["^TNX"]["Close"] - historical_slice["^FVX"]["Close"]).dropna()
            if len(spread_series) > 0:
                us_2s10s_spread = float(spread_series.iloc[-1])
            spread_delta_series = spread_series.diff().dropna()
            if len(spread_delta_series) > 0:
                rolling = spread_delta_series.tail(60)
                mean = rolling.mean()
                std = rolling.std()
                if std > 0:
                    us_2s10s_spread_z = (float(spread_delta_series.iloc[-1]) - mean) / std
        us10y_delta = 0.0 # Standardize to 0 for missing delta if stats aren't computed for ^TNX
        us10y_delta_z = 0.0
        if len(tnx_slice) > 1:
            us10y_delta_series = tnx_slice.diff().dropna()
            if len(us10y_delta_series) > 0:
                us10y_delta = float(us10y_delta_series.iloc[-1])
                rolling = us10y_delta_series.tail(60)
                mean = rolling.mean()
                std = rolling.std()
                if std > 0:
                    us10y_delta_z = (us10y_delta - mean) / std
            
        # Gold Silver Ratio
        gsr_delta_pct = 0.0
        gold = parsed_daily.get("Gold")
        silver = parsed_daily.get("Silver")
        if gold and silver and silver.get("current", 0) > 0:
            gsr_current = gold["current"] / silver["current"]
            gsr_prev = gold["prev"] / silver["prev"]
            gsr_delta_pct = ((gsr_current - gsr_prev) / gsr_prev) * 100
            
        # Crypto MFI
        ibit = parsed_daily.get("IBIT")
        etha = parsed_daily.get("ETHA")
        mfi_z = 0.0
        if ibit and etha and ibit.get("z_score") is not None and etha.get("z_score") is not None:
            mfi_z = (ibit["z_score"] + etha["z_score"]) / 2
            
        # Volume Heat
        spx_close = historical_slice["^GSPC"]["Close"].dropna()
        spx_vol = historical_slice["^GSPC"]["Volume"].dropna()
        volume_heat = compute_volume_heat(spx_close, spx_vol)
        ihi = volume_heat.get("institutional_heat_index", 0.0)
        
        # 4. Construct feature vector
        features_dict = {
            "SPX_ret_z": parsed_daily.get("SPX", {}).get("z_score", 0.0),
            "DXY_ret_z": parsed_daily.get("DXY", {}).get("z_score", 0.0),
            "VIX_zscore": parsed_daily.get("VIX", {}).get("z_score", 0.0),
            "WTI_ret_z": parsed_daily.get("WTI", {}).get("z_score", 0.0),
            "GoldSilverRatio_ret_z": parsed_daily.get("Gold", {}).get("z_score", 0.0), # Simplification
            "US10Y_delta_z": us10y_delta_z,
            "US_2s10s_spread_z": us_2s10s_spread_z,
            "CryptoMFI_zscore": mfi_z,
            "VolumeHeat_ihi": ihi,
            "USDCAD_ret_z": parsed_daily.get("USDCAD", {}).get("z_score", 0.0),
        }
        
        ordered_keys = ["SPX_ret_z", "DXY_ret_z", "VIX_zscore", "WTI_ret_z", "GoldSilverRatio_ret_z", "US10Y_delta_z", "US_2s10s_spread_z", "CryptoMFI_zscore", "VolumeHeat_ihi", "USDCAD_ret_z"]
        features_vector = [float(features_dict[k]) for k in ordered_keys]
        
        if i < 3:
            print(f"[{current_date.strftime('%Y-%m-%d')}] Features: {features_vector}")
        
        # 5. Math Engines
        regime_probs, dom_regime, tr_risk, _ = hmm.run_inference(features_vector)
        if regime_probs is None:
            regime_probs = {"NEUTRAL_TRANSITIONAL": 1.0}
            
        kalman_state = risk.run_kalman_filter(
            mcs=50.0, # Dummy MCS
            sub_components={},
            hmm_regime_probs=regime_probs,
            prior_state=prior_k_state,
            prior_cov=prior_k_cov
        )
        prior_k_state = kalman_state.probabilities
        prior_k_cov = kalman_state.covariance_matrix
        
        # Run Mixture of Experts Deep Classifier
        try:
            mlp_state = run_mlp_inference(features_vector, mlp_package, kalman_state.dominant_state)
            mlp_prob = mlp_state.get("bull_probability", 0.5)
        except Exception as e:
            print(f"MLP Error: {e}")
            mlp_prob = 0.5
            
        kelly_size = risk.compute_kelly_sizing(mlp_prob, dominant_state=kalman_state.dominant_state, brier_score=0.15)
        
        # Shift logic based on timeframe
        if interval == "1d":
            future_slice = spx_data[spx_data.index > current_date]
            forward_ret = future_slice["Close"].pct_change().shift(-3).head(1).values
        elif interval == "4h":
            future_slice = spx_data[spx_data.index > current_date]
            forward_ret = future_slice["Close"].pct_change().shift(-18).head(1).values # Approx 3 days
        elif interval == "1wk":
            future_slice = spx_data[spx_data.index > current_date]
            forward_ret = future_slice["Close"].pct_change().shift(-1).head(1).values # Approx 1 week
        else:
            forward_ret = [0.0]
            
        forward_3d_ret = float(forward_ret[0]) * 100 if len(forward_ret) > 0 and not pd.isna(forward_ret[0]) else 0.0
            
        results.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "spx_close": round(spx_close.iloc[-1], 2),
            "dom_regime": dom_regime,
            "kalman_state": kalman_state.dominant_state,
            "kelly_exposure": round(kelly_size, 3),
            "fwd_3d_ret": round(forward_3d_ret, 3)
        })

    # 7. Generate Output Report
    win_count = 0
    drawdown_protected = 0
    total_drawdowns = 0
    
    for r in results:
        if r["fwd_3d_ret"] > 0 and r["kelly_exposure"] > 0.5:
            win_count += 1
        elif r["fwd_3d_ret"] < 0 and r["kelly_exposure"] < 0.5:
            win_count += 1
            
        if r["fwd_3d_ret"] < -1.0:
            total_drawdowns += 1
            if r["kelly_exposure"] < 0.3:
                drawdown_protected += 1
                
    accuracy = (win_count / len(results)) * 100
    protection_rate = (drawdown_protected / total_drawdowns * 100) if total_drawdowns > 0 else 100.0
    
    report = f"""# Quantitative Engine Backtest: Extended (Jan 1 - May 30)

**Test Period:** Jan 1, 2026 to May 30, 2026
**Samples:** {len(results)} Trading Days

## Performance Summary
- **Edge Accuracy (Captured Uptrends):** {accuracy:.1f}%
- **Drawdown Protection Rate:** {protection_rate:.1f}% ({drawdown_protected}/{total_drawdowns} major dips avoided)
- **Average Kelly Allocation:** {np.mean([r['kelly_exposure'] for r in results]):.3f}

## Daily Log (Sample of last 10 days)
| Date | SPX Close | HMM Regime | Kalman State | Kelly Exposure | 3-Day Fwd Ret |
|------|-----------|------------|--------------|----------------|---------------|
"""
    for r in results:
        report += f"| {r['date']} | {r['spx_close']} | {r['dom_regime']} | {r['kalman_state']} | {r['kelly_exposure']} | {r['fwd_3d_ret']}% |\n"
        
    with open("/Users/mac/agent/reports/backtest_extended_results.md", "w") as f:
        f.write(report)
        
    print("Backtest complete! Report generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", choices=["1d", "1wk", "1h", "4h"])
    args = parser.parse_args()
    run_backtest(interval=args.interval)
