import os
import json
import joblib
import logging
import hashlib
import hmac
import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timezone, timedelta
from src.observability.logger import get_logger

logger = get_logger("feature-engine")

# Global dicts and vars needed
ALL_YF_TICKERS = {
    # Equities
    "SPX": "^GSPC", "NDX": "^NDX", "DAX": "^GDAXI", "FTSE": "^FTSE", "N225": "^N225",
    "HSI": "^HSI", "SHANGHAI": "000001.SS", "KOSPI": "^KS11", "TASI": "^TASI.SR", "DFM": "DFMGI.AE", "ES": "ES=F", "NQ": "NQ=F", "YM": "YM=F", "RTY": "RTY=F",
    # Single Name High-Vol Tech
    "NVDA": "NVDA", "TSLA": "TSLA", "DELL": "DELL", "SPCE": "SPCE",
    # Commodities & Safe Havens
    "WTI": "CL=F", "Brent": "BZ=F", "TTF": "TTF=F",
    "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    # FX & Safe Havens
    "DXY": "DX-Y.NYB", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", 
    "JPYUSD": "JPYUSD=X", "CHFUSD": "CHFUSD=X", "USDCAD": "USDCAD=X",
    # Volatility
    "VIX9D": "^VIX9D",
    "VIX": "^VIX",
    "VIX3M": "^VIX3M",
    "VVIX": "^VVIX",
    "SH": "SH",
    # Institutional Digital Asset Flow & Spot
    "BTC": "BTC-USD",
    "IBIT": "IBIT",      
    "ETHA": "ETHA",      
    "COIN": "COIN",
    # Credit Stress Proxy
    "HYG": "HYG",
    "LQD": "LQD"
}

garch_targets = {
    "SPX":   "^GSPC",
    "WTI":   "CL=F",
    "DXY":   "DX-Y.NYB",   
}

ROLLING_DAYS = 60

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
def get_signature_salt():
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'signature_salt.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            salt = f.read().strip()
            if salt:
                return salt
    return "MacroBriefingAgentTruChainFallbackSecret"
def sign_snapshot_payload(snapshot_dict):
    serialized = json.dumps(snapshot_dict, sort_keys=True)
    salt = get_signature_salt()
    return hmac.new(salt.encode('utf-8'), serialized.encode('utf-8'), hashlib.sha256).hexdigest()
def check_mathematical_consistency(parsed_assets):
    try:
        vix = parsed_assets.get("VIX")
        if vix and (vix["current"] > 100.0 or vix["current"] < 5.0):
            return False
        spx = parsed_assets.get("SPX")
        if spx and abs(spx["delta_pct"]) > 15.0:
            return False
        return True
    except Exception:
        return False
# Refactored for compliance: This function maintains a Local Cryptographic Signature Audit Trail for tracking snapshot integrity.
# It is not a decentralized immutable ledger, but a local cryptographic signature audit trail.
def append_to_immutable_chain(current_signature, output_utc):
    chain_log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'immutable_chain.log')
    os.makedirs(os.path.dirname(chain_log_path), exist_ok=True)
    
    prev_hash = "0" * 64
    if os.path.exists(chain_log_path):
        try:
            with open(chain_log_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    prev_hash = lines[-1].strip().split(",")[-1]
        except Exception as e:
            logger.error(f"Local Cryptographic Signature Audit Trail: Log read error: {e}")
    linked_block_hash = hashlib.sha256(f"{prev_hash}{current_signature}".encode('utf-8')).hexdigest()
    try:
        header_needed = not os.path.exists(chain_log_path)
        with open(chain_log_path, 'a') as f:
            if header_needed:
                f.write("timestamp_utc,snapshot_signature,prev_block_hash,linked_block_hash\n")
            f.write(f"{output_utc},{current_signature},{prev_hash},{linked_block_hash}\n")
    except Exception as e:
        logger.error(f"Local Cryptographic Signature Audit Trail: Append failure: {e}")
def compute_stats(series, garch_conditional_vol=None, rolling_window=ROLLING_DAYS):
    if series is None or len(series) < 2:
        return None
    current  = float(series.iloc[-1])
    prev     = float(series.iloc[-2])
    delta    = current - prev
    delta_pct = (delta / prev * 100) if prev != 0 else 0
    # Price level stats
    rolling  = series.tail(rolling_window)
    mean     = float(rolling.mean())
    std      = float(rolling.std()) if len(rolling) > 1 else 0
    
    # Return (delta_pct) z-score stats
    rolling_returns = series.pct_change().dropna().tail(rolling_window) * 100
    ret_mean = float(rolling_returns.mean()) if len(rolling_returns) > 0 else 0
    ret_std = float(rolling_returns.std()) if len(rolling_returns) > 1 else 0
    
    if garch_conditional_vol is not None and garch_conditional_vol > 0:
        z_score = delta_pct / garch_conditional_vol
    else:
        z_score = ((delta_pct - ret_mean) / ret_std) if ret_std > 0 else 0
        
    if len(rolling) >= 3:
        slope    = float(np.polyfit(range(len(rolling)), rolling.values, 1)[0])
        momentum = "up" if slope > 0 else "down" if slope < 0 else "flat"
    else:
        momentum = "flat"
    return {
        "current":   round(current, 4),
        "prev":      round(prev, 4),
        "delta":     round(delta, 4),
        "delta_pct": round(delta_pct, 3),
        "mean_60d":   round(mean, 4),
        "std_60d":    round(std, 4),
        "z_score":   round(z_score, 3),
        "momentum":  momentum,
    }
def compute_volume_heat(spx_series, spx_vol_series):
    if len(spx_series) < 20 or len(spx_vol_series) < 20:
        return {"participation_type": "UNKNOWN", "institutional_heat_index": 0.0}
    try:
        vol_mean = spx_vol_series.rolling(20).mean().iloc[-1]
        vol_std = spx_vol_series.rolling(20).std().iloc[-1]
        current_vol = float(spx_vol_series.iloc[-1])
        effort_z = (current_vol - vol_mean) / vol_std if vol_std > 0 else 0.0
        
        current_close = float(spx_series.iloc[-1])
        recent_low = float(spx_series.tail(10).min())
        recent_high = float(spx_series.tail(10).max())
        result_vector = (current_close - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
        
        ihi = effort_z * (result_vector - 0.5)
        
        part_type = "RETAIL_DRIFT"
        if effort_z > 1.0:
            part_type = "INSTITUTIONAL_ACCUMULATION" if result_vector > 0.5 else "INSTITUTIONAL_DISTRIBUTION"
            
        return {"participation_type": part_type, "institutional_heat_index": round(ihi, 3)}
    except Exception as e:
        return {"participation_type": "UNKNOWN", "institutional_heat_index": 0.0}

def compute_market_extremes(spx_series, vix_series, vvix_series=None, dxy_series=None, vix9d_series=None):
    try:
        spx_returns = spx_series.pct_change().dropna().tail(10) * 100
        vix_returns = vix_series.pct_change().dropna().tail(10) * 100
        
        # 1. Base Temperature & Crowdedness (Existing Logic)
        spx_abs = spx_returns.abs().sum()
        vix_abs = vix_returns.abs().sum()
        temperature_z = (spx_abs - vix_abs) / vix_abs if vix_abs > 0 else 0.0
        crowdedness = spx_returns.corr(vix_returns)
        
        # 2. Hidden Fragility Calculations
        fragility_score = 0.0
        vvix_ratio = 0.0
        cross_corr = 0.0
        
        if vvix_series is not None and not vvix_series.empty and float(vix_series.iloc[-1]) > 0:
            vvix_ratio = vvix_series.iloc[-1] / vix_series.iloc[-1]
            if vvix_ratio > 6.0:  # VVIX expanding much faster than VIX
                fragility_score += 0.4
                
        if dxy_series is not None and not dxy_series.empty:
            dxy_returns = dxy_series.pct_change().dropna().tail(10) * 100
            cross_corr = spx_returns.corr(dxy_returns)
            # If SPX and DXY are highly positively correlated, liquidity is draining
            if cross_corr > 0.4:
                fragility_score += 0.6
                
        # 3. Volatility Term Structure
        if vix9d_series is not None and not vix9d_series.empty:
            term_structure_inversion = 1.0 if float(vix9d_series.iloc[-1]) > float(vix_series.iloc[-1]) else 0.0
            fragility_score += (0.5 * term_structure_inversion)
                
        return {
            "temperature_zscore": round(temperature_z, 3),
            "temperature_state": "OVERHEATED" if temperature_z > 1.0 else "ICE_COLD" if temperature_z < -1.0 else "NORMAL",
            "crowded_state": "LONG_TRADE_TOO_CROWDED" if crowdedness > 0.5 else "SHORT_TRADE_TOO_CROWDED" if crowdedness < -0.5 else "BALANCED",
            "fragility_score": round(fragility_score, 3),
            "vvix_vix_ratio": round(vvix_ratio, 2)
        }
    except Exception:
        return {
            "temperature_zscore": 0.0,
            "temperature_state": "NORMAL",
            "crowded_state": "BALANCED",
            "fragility_score": 0.0,
            "vvix_vix_ratio": 0.0
        }
def compute_garch_volatility(ticker_symbol, lookback_days=250):
    try:
        from arch import arch_model
        data = yf.Ticker(ticker_symbol)
        hist = data.history(period=f"{lookback_days}d", interval="1d")
        if hist.empty or len(hist) < 20:
            return None, None, None
        returns = hist["Close"].pct_change().dropna() * 100
        model = arch_model(returns, vol="Garch", p=1, q=1, mean="Zero", rescale=False)
        result = model.fit(disp="off", show_warning=False)
        cond_vol = float(result.conditional_volatility.iloc[-1])
        forecast = result.forecast(horizon=1, reindex=False)
        forecast_vol = float(forecast.variance.iloc[-1, 0] ** 0.5)
        vol_history = result.conditional_volatility.dropna()
        percentile = float((vol_history < cond_vol).mean() * 100)
        vol_regime = "LOW" if percentile < 33 else "NORMAL" if percentile < 67 else "ELEVATED"
        return round(cond_vol, 4), vol_regime, round(forecast_vol, 4)
    except Exception as e:
        logger.error(f"GARCH error for {ticker_symbol}: {e}")
        return None, None, None
def load_mlp_models(interval="1d", assets=None):
    if assets is None:
        assets = ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]
    models = {}
    for asset in assets:
        model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'models', f'mlp_model_{asset}_{interval}.pkl')
        if not os.path.exists(model_path):
            model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'models', f'mlp_model_{asset}.pkl')
        try:
            if os.path.exists(model_path):
                models[asset] = joblib.load(model_path)
        except Exception as e:
            logger.error(f"MLP Load Failure for {asset}: {e}")
    return models

def run_multi_mlp_inference(features_vector, mlp_packages_dict, current_regime: str):
    results = {}
    for asset, mlp_package in mlp_packages_dict.items():
        res = run_mlp_inference(features_vector, mlp_package, current_regime, asset=asset)
        if res:
            results[asset] = res
    return results

def run_mlp_inference(features_vector, mlp_package, current_regime: str, asset="spx"):
    if mlp_package is None or current_regime is None:
        return None
    try:
        # Dead regime-routing model code removed in v5.3.1
            
        scaler = mlp_package["scaler"]
        obs = np.array([features_vector])
        
        # Algorithmic Outage Immunity: Replace NaN with 0.0 (mean) to prevent entire pipeline crash
        obs = np.nan_to_num(obs, nan=0.0, posinf=4.0, neginf=-4.0)
        
        obs_scaled = scaler.transform(obs)
        
        # Ensemble Prediction
        models = [
            mlp_package.get("model_mlp", mlp_package.get("model", mlp_package.get("model_base"))),
            mlp_package.get("model_rf"),
            mlp_package.get("model_gb")
        ]
        
        valid_models = [m for m in models if m is not None]
        if not valid_models:
            return None
            
        prob_up_list = []
        prob_down_list = []
        prob_neutral_list = []
        for m in valid_models:
            probs = m.predict_proba(obs_scaled)[0]
            if len(m.classes_) == 3:
                # 3 classes: [down, up, neutral] based on y encoding
                prob_up_list.append(probs[1])
                prob_down_list.append(probs[0])
                prob_neutral_list.append(probs[2])
            else:
                prob_up_list.append(probs[1])
                prob_down_list.append(probs[0])
                prob_neutral_list.append(0.0)
                
        if not prob_up_list:
            return None
            
        # Consensus Score calculation
        mean_prob_up = np.mean(prob_up_list)
        if len(prob_up_list) <= 1:
            consensus_score = 0.5   # single model = no ensemble agreement possible
        else:
            std_prob_up = np.std(prob_up_list)
            # High consensus if standard deviation is low (models agree)
            consensus_score = 1.0 if std_prob_up < 0.15 else 0.0
        
        # Extract Maximum Conviction to prevent ensemble suppression
        prob_down = round(float(np.max(prob_down_list)), 3)
        prob_up = round(float(np.max(prob_up_list)), 3)
        prob_neutral = round(float(np.mean(prob_neutral_list)), 3)
        predicted_class = 1 if prob_up > 0.5 else 0
        
        return {
            "bull_probability": prob_up,
            "bear_probability": prob_down,
            "neutral_probability": prob_neutral,
            "predicted_class": predicted_class,
            "consensus_score": consensus_score
        }
    except Exception as e:
        logger.error(f"MLP Inference Failure: {e}")
        return None
def compute_weekly_liquidity_boundaries(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="15d")
        if len(hist) < 10:
            return None
        hist['week'] = hist.index.isocalendar().week
        unique_weeks = list(hist['week'].unique())
        if len(unique_weeks) >= 2:
            prev_week_data = hist[hist['week'] == unique_weeks[-2]]
            pwh = float(prev_week_data['High'].max())
            pwl = float(prev_week_data['Low'].min())
            current_close = float(hist['Close'].iloc[-1])
            current_low = float(hist['Low'].iloc[-1])
            current_high = float(hist['High'].iloc[-1])
            intraday_range_pct = ((current_high - current_low) / current_low) * 100
            swept_pwl = current_low < pwl and current_close > pwl
            swept_pwh = current_high > pwh and current_close < pwh
            return {
                "pwh": round(pwh, 2),
                "pwl": round(pwl, 2),
                "swept_pwl_flag": bool(swept_pwl),
                "swept_pwh_flag": bool(swept_pwh),
                "intraday_range_pct": round(intraday_range_pct, 3)
            }
    except Exception as e:
        logger.error(f"Error computing weekly boundaries for {ticker_symbol}: {e}")
    return None
def calculate_model_tvd(p_dist, q_dist):
    """
    Computes Total Variation Distance (TVD) between HMM and MLP.
    TVD = 0.5 * sum(|P - Q|)
    """
    try:
        hmm_risk_on = p_dist.get("RISK_ON_EXPANSION", 0.0) + p_dist.get("LIQUIDITY_DRIVEN_RALLY", 0.0)
        hmm_risk_off = (p_dist.get("STAGFLATION_STRESS", 0.0) + 
                        p_dist.get("RATE_SHOCK", 0.0) + 
                        p_dist.get("DEFLATION_FEAR", 0.0) + 
                        p_dist.get("CRISIS_DISLOCATION", 0.0))
        hmm_trans = max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)
        
        P = np.array([hmm_risk_on, hmm_risk_off, hmm_trans])
        
        if isinstance(q_dist, dict) and "bull_probability" in q_dist:
            Q = np.array([
                q_dist.get("bull_probability", 0.33),
                q_dist.get("bear_probability", 0.34),
                q_dist.get("neutral_probability", 0.33)
            ])
        else:
            Q = np.array([q_dist.get("risk_on", 0.33), q_dist.get("risk_off", 0.34), q_dist.get("transitional", 0.33)])
        
        # Clip to prevent 0.0
        P = np.clip(P, 0.01, 0.99); P /= P.sum()
        Q = np.clip(Q, 0.01, 0.99); Q /= Q.sum()
        
        tvd = 0.5 * float(np.sum(np.abs(P - Q)))
        return round(tvd, 4)
    except Exception as e:
        return 0.0
def calculate_bayesian_conditional_probability(setup_name, current_regime):
    """
    Returns a prior probability estimate for a given market setup conditional
    on the current HMM regime.

    WARNING: These values are manually calibrated priors, not empirically 
    derived. TODO: Replace with values computed from the quantitative backtester
    on the next quarterly retrain cycle.
    """
    historical_matrices = {
        "PWL_Sweep": {
            "RISK_ON_EXPANSION": 0.84,
            "LIQUIDITY_DRIVEN_RALLY": 0.91, 
            "NEUTRAL_TRANSITIONAL": 0.64,
            "RATE_SHOCK": 0.31,
            "STAGFLATION_STRESS": 0.28,
            "DEFLATION_FEAR": 0.21,
            "CRISIS_DISLOCATION": 0.12
        },
        "PWH_Sweep": {
            "RISK_ON_EXPANSION": 0.18,
            "LIQUIDITY_DRIVEN_RALLY": 0.11,
            "NEUTRAL_TRANSITIONAL": 0.42,
            "RATE_SHOCK": 0.74, 
            "STAGFLATION_STRESS": 0.68,
            "DEFLATION_FEAR": 0.81,
            "CRISIS_DISLOCATION": 0.89
        }
    }
    regime_key = str(current_regime).replace("_4", "").replace("_3", "").replace("_2", "").replace("_5", "")
    try:
        p_success = historical_matrices.get(setup_name, {}).get(regime_key, 0.50)
        return round(p_success, 2)
    except Exception:
        return 0.50
def run_self_calibration(history, current_spx_val, current_ihi, grading_delay=5, interval="1d"):
    """
    Model Governance: Calculates rolling Brier Score with Retail Noise Filter.
    Waits `grading_delay` bars before grading to match training horizon.
    """
    brier_score = 0.15
    try:
        # Calculate threshold based on interval
        threshold = 1.5
        if interval == "1wk":
            threshold *= 2.0
        elif interval == "4h":
            threshold *= 0.4
        elif interval == "1h":
            threshold *= 0.2
            
        # Update the rolling window for the most recent un-graded forecasts
        for forecast in history:
            if not forecast.get("target_graded"):
                if "spx_vals_window" not in forecast:
                    forecast["spx_vals_window"] = []
                forecast["spx_vals_window"].append(current_spx_val)

        # Grade the prediction made `grading_delay` bars ago
        if len(history) > grading_delay:
            forecast_to_grade = history[-(grading_delay + 1)]
            if not forecast_to_grade.get("target_graded"):
                window = forecast_to_grade.get("spx_vals_window", [])
                if len(window) >= grading_delay:
                    # Compute rolling sum of returns
                    pct_returns = []
                    prev_val = forecast_to_grade["spx_val_at_prediction"]
                    for val in window[:grading_delay]:
                        if prev_val > 0:
                            pct_returns.append(((val - prev_val) / prev_val) * 100)
                        prev_val = val
                    ret = sum(pct_returns)
                else:
                    ret = ((current_spx_val - forecast_to_grade["spx_val_at_prediction"]) / forecast_to_grade["spx_val_at_prediction"]) * 100
                
                # Baseline outcome uses interval-specific threshold to match training
                actual_outcome = 1 if ret > threshold else 0
                
                forecast_to_grade["actual_outcome"] = actual_outcome
                forecast_to_grade["target_graded"] = True
                forecast_to_grade["squared_error"] = float((forecast_to_grade["predicted_risk_on"] - actual_outcome) ** 2)
        
        # Limit history
        history = history[-(grading_delay + 20):]
        
        # Calculate Brier score
        graded = [p for p in history if p.get("target_graded", False)]
        if len(graded) > 0:
            brier_score = float(np.mean([p["squared_error"] for p in graded]))
            if brier_score > 0.25:
                logger.warning(f"CRITICAL: Brier Score {brier_score} indicates degraded performance.")
            
        return round(brier_score, 4), history
    except Exception as e:
        logger.error(f"Self-calibration error: {e}")
        return 0.15, history
def compute_equity_momentum_score(equities):
    weights = {"SPX": 0.35, "NDX": 0.18, "DAX": 0.18, "N225": 0.18, "TASI": 0.06, "DFM": 0.05}
    weighted_z = 0.0
    total_weight = 0.0
    for name, weight in weights.items():
        asset = equities.get(name)
        if asset and asset.get("z_score") is not None:
            weighted_z += asset["z_score"] * weight
            total_weight += weight
    if total_weight == 0:
        return 0.0
    avg_z = weighted_z / total_weight
    scaled = -25.0 + ((avg_z - (-3.0)) / (3.0 - (-3.0))) * (25.0 - (-25.0))
    return round(max(-25.0, min(25.0, scaled)), 3)
def compute_rate_pressure_score(bonds):
    score = 0.0
    us10y = bonds.get("US10Y")
    spread = bonds.get("spread_2s10s")
    if us10y and us10y.get("delta") is not None:
        val = -us10y["delta"]
        scaled = -12.5 + ((val - (-0.3)) / (0.3 - (-0.3))) * (12.5 - (-12.5))
        score += round(max(-12.5, min(12.5, scaled)), 3)
    if spread is not None:
        scaled = -12.5 + ((spread - (-0.5)) / (1.5 - (-0.5))) * (12.5 - (-12.5))
        score += round(max(-12.5, min(12.5, scaled)), 3)
    return round(max(-25.0, min(25.0, score)), 3)
def compute_energy_stress_score(energy):
    z_scores = []
    for name in ["WTI", "Brent"]:
        asset = energy.get(name)
        if asset and asset.get("z_score") is not None:
            z_scores.append(asset["z_score"])
    if not z_scores:
        return 0.0
    avg_z = -sum(z_scores) / len(z_scores)
    scaled = -25.0 + ((avg_z - (-3.0)) / (3.0 - (-3.0))) * (25.0 - (-25.0))
    return round(max(-25.0, min(25.0, scaled)), 3)
def compute_cross_asset_coherence_score(equities, bonds, energy):
    score = 25.0
    spx = equities.get("SPX")
    us10y = bonds.get("US10Y")
    wti = energy.get("WTI")
    if not spx or not us10y:
        return 0.0
    spx_move = spx.get("delta_pct", 0)
    yield_move = us10y.get("delta", 0)
    if spx_move < -1.0 and yield_move > 0.08:
        score -= 20.0
    if spx_move > 0.5 and yield_move > 0.15:
        score -= 10.0
    if wti and wti.get("delta_pct", 0) > 2.0 and spx_move < -0.5:
        score -= 15.0
    return round(max(-25.0, min(25.0, score)), 3)
def compute_mcs(equities, bonds, energy):
    eq_score  = compute_equity_momentum_score(equities)
    rate_score = compute_rate_pressure_score(bonds)
    energy_score = compute_energy_stress_score(energy)
    coherence_score = compute_cross_asset_coherence_score(equities, bonds, energy)
    mcs = (eq_score * 1.2 + rate_score * 1.0 + energy_score * 0.8 + coherence_score * 1.0)
    mcs = round(max(-100.0, min(100.0, mcs)), 2)
    sub_components = {
        "equity_momentum":      round(eq_score, 3),
        "rate_pressure":        round(rate_score, 3),
        "energy_stress":        round(energy_score, 3),
        "cross_asset_coherence": round(coherence_score, 3),
    }
    return mcs, sub_components

